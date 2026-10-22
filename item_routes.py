from sqlalchemy.orm import joinedload
from pagination import get_page_args, pagination_meta
from datetime import date
from sqlalchemy.exc import IntegrityError
from flask import jsonify, request, session
from config import app, db
from models import Item, Category

ITEM_TYPES = {"lost", "found"}
ITEM_STATUSES = {"active", "claimed", "resolved"}  # same list as the Item validator in models.py

# field -> max length, for the text columns in models.py
TEXT_LIMITS = {"title": 120, "status": 20, "location": 200}
OPTIONAL_TEXT = ["description", "location", "image_url"]  # may be sent as null
EDITABLE = ["title", "description", "type", "status", "location",
            "latitude", "longitude", "date", "image_url", "category_id"]


def current_user_id():
    return session.get("user_id")  # must match the key Wesley's login sets


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def clean(data, partial=False):
    """Validate the request body. Returns (values, error)."""
    if not isinstance(data, dict):
        return None, "request body must be a JSON object"

    values = {k: data[k] for k in EDITABLE if k in data}

    # required on create; on PATCH they may be left out but never set to null
    for field in ("title", "type", "category_id"):
        if field in values and values[field] is None:
            return None, f"{field} cannot be null"
        if not partial and field not in values:
            return None, f"{field} is required"

    # text fields: must be strings, within the column length
    for field in ("title", "description", "status", "location", "image_url"):
        if field not in values or values[field] is None:
            continue
        if not isinstance(values[field], str):
            return None, f"{field} must be text"
        values[field] = values[field].strip()
        if field in TEXT_LIMITS and len(values[field]) > TEXT_LIMITS[field]:
            return None, f"{field} must be at most {TEXT_LIMITS[field]} characters"
    if "title" in values and not values["title"]:
        return None, "title cannot be empty"
    if "status" in values and values["status"] not in ITEM_STATUSES:
        return None, "status must be 'active', 'claimed' or 'resolved'"

    if "type" in values and values["type"] not in ITEM_TYPES:
        return None, "type must be 'lost' or 'found'"

    if "category_id" in values:
        cid = values["category_id"]
        if not isinstance(cid, int) or isinstance(cid, bool):
            return None, "category_id must be a whole number"
        if not db.session.get(Category, cid):
            return None, "category does not exist"

    for field, limit in (("latitude", 90), ("longitude", 180)):
        if values.get(field) is not None:
            if not is_number(values[field]) or abs(values[field]) > limit:
                return None, f"{field} must be a number between -{limit} and {limit}"

    if values.get("date") is not None:
        try:
            values["date"] = date.fromisoformat(values["date"])
        except (ValueError, TypeError):
            return None, "date must be YYYY-MM-DD"

    return values, None


@app.route("/api/categories", methods=["GET"])
def list_categories():
    categories = Category.query.order_by(Category.name).all()
    return jsonify([c.to_dict() for c in categories]), 200


@app.route("/api/items", methods=["GET"])
def list_items():
    query = Item.query

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Item.title.ilike(like),
            Item.description.ilike(like),
            Item.location.ilike(like),
        ))
    if request.args.get("category"):
        try:
            category_id = int(request.args["category"])
        except ValueError:
            return jsonify({"error": "category must be a whole number"}), 400
        query = query.filter(Item.category_id == category_id)
    if request.args.get("type"):
        query = query.filter(Item.type == request.args["type"])
    if request.args.get("status"):
        query = query.filter(Item.status == request.args["status"])

    # load category and user in the same query (to_dict reads both)
    query = query.options(joinedload(Item.category), joinedload(Item.user))
    # id tie-breaker keeps the page order stable when created_at values match
    query = query.order_by(Item.created_at.desc(), Item.id.desc())

    
    if "page" not in request.args:
        return jsonify([i.to_dict() for i in query.all()]), 200

    page, per_page = get_page_args()
    page_result = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [i.to_dict() for i in page_result.items],
        "pagination": pagination_meta(page_result),
    }), 200

CATEGORY_NAME_MAX = 50  # the categories.name column holds 50 characters


def clean_category_name(data):
    """Returns (name, error) for a category request body."""
    if not isinstance(data, dict):
        return None, "request body must be a JSON object"
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "name is required"
    name = " ".join(name.split())  # trim and collapse extra spaces
    if len(name) > CATEGORY_NAME_MAX:
        return None, f"name must be at most {CATEGORY_NAME_MAX} characters"
    return name, None


def category_name_taken(name, ignore_id=None):
    """True if another category already uses this name (ignoring upper/lower case)."""
    query = Category.query.filter(db.func.lower(Category.name) == name.lower())
    if ignore_id is not None:
        query = query.filter(Category.id != ignore_id)
    return query.first() is not None


@app.route("/api/categories", methods=["POST"])
def create_category():
    if not current_user_id():
        return jsonify({"error": "Login required"}), 401

    name, error = clean_category_name(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    if category_name_taken(name):
        return jsonify({"error": "A category with that name already exists"}), 409

    category = Category(name=name)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:  # two people added the same name at the same moment
        db.session.rollback()
        return jsonify({"error": "A category with that name already exists"}), 409
    return jsonify(category.to_dict()), 201


@app.route("/api/categories/<int:category_id>", methods=["PATCH"])
def update_category(category_id):
    if not current_user_id():
        return jsonify({"error": "Login required"}), 401

    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found"}), 404

    name, error = clean_category_name(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    if category_name_taken(name, ignore_id=category.id):
        return jsonify({"error": "A category with that name already exists"}), 409

    category.name = name
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A category with that name already exists"}), 409
    return jsonify(category.to_dict()), 200


@app.route("/api/categories/<int:category_id>", methods=["DELETE"])
def delete_category(category_id):
    if not current_user_id():
        return jsonify({"error": "Login required"}), 401

    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found"}), 404

    # items need a category, so a category that is still in use cannot be deleted
    in_use = Item.query.filter_by(category_id=category.id).count()
    if in_use:
        return jsonify({
            "error": f"This category is used by {in_use} item(s). Move or delete them first."
        }), 409

    db.session.delete(category)
    db.session.commit()
    return "", 204

@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(item.to_dict()), 200


@app.route("/api/items", methods=["POST"])
def create_item():
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    values, error = clean(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    try:
        item = Item(**values, user_id=user_id)
    except ValueError as e:  # model validators in models.py
        return jsonify({"error": str(e)}), 400
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/api/items/<int:item_id>", methods=["PATCH"])
def update_item(item_id):
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.user_id != user_id:
        return jsonify({"error": "Not allowed"}), 403

    values, error = clean(request.get_json(silent=True), partial=True)
    if error:
        return jsonify({"error": error}), 400

    try:
        for key, value in values.items():
            setattr(item, key, value)
    except ValueError as e:  # model validators in models.py
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    db.session.commit()
    return jsonify(item.to_dict()), 200


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.user_id != user_id:
        return jsonify({"error": "Not allowed"}), 403

    db.session.delete(item)
    db.session.commit()
    return "", 204