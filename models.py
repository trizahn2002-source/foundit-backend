from config import db
from sqlalchemy.orm import validates

from werkzeug.security import generate_password_hash, check_password_hash

# Each person adds their model in their own section below.
# Keep to your section to avoid merge conflicts.

# ---------- users (Wesley) ----------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now()
    )

    def set_password(self, password):
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check whether a password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Return public user details without the password hash."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
        }

    def __repr__(self):
        return f"<User {self.id}: {self.username}>"

# ---------- categories and items (Samuel) ----------
class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    items = db.relationship("Item", back_populates="category")

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    def __repr__(self):
        return f"<Category {self.id}  {self.name}>"


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(10), nullable=False)  # "lost" or "found"
    status = db.Column(db.String(20), nullable=False, default="active")
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    date = db.Column(db.Date)
    image_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    category = db.relationship("Category", back_populates="items")
    user = db.relationship("User")
    # No "claims" relationship here: Regan's Claim model creates Item.claims
    @validates("title")
    def validate_title(self, key, value):
        if not value or not value.strip():
            raise ValueError("Item title is required.")
        return value.strip()

    @validates("type")
    def validate_type(self, key, value):
        if value not in ("lost", "found"):
            raise ValueError("Type must be 'lost' or 'found'.")
        return value

    @validates("status")
    def validate_status(self, key, value):
        if value not in ("active", "claimed", "resolved"):
            raise ValueError("Status must be active, claimed or resolved.")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "status": self.status,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "date": self.date.isoformat() if self.date else None,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "category_id": self.category_id,
            "category": self.category.name if self.category else None,
            "user_id": self.user_id,
            "reporter_username": self.user.username if self.user else None,
        }

    def __repr__(self):
        return f"<Item {self.id} {self.title} ({self.type})>"

# ---------- claims (Regan) ----------
from sqlalchemy.orm import validates


class Claim(db.Model):
    __tablename__ = "claims"

    STATUSES = ("pending", "approved", "rejected")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="status_valid",
        ),
        db.UniqueConstraint("user_id", "item_id", name="uq_claims_user_item"),
    )

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    # Contact details voluntarily shared by the finder
    # when approving an ownership claim.
    contact_method = db.Column(db.String(20), nullable=True)
    contact_detail = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)

    user = db.relationship(
        "User", backref=db.backref("claims", cascade="all, delete-orphan")
    )
    item = db.relationship(
        "Item", backref=db.backref("claims", cascade="all, delete-orphan")
    )

    @validates("message")
    def validate_message(self, key, value):
        if not value or not value.strip():
            raise ValueError("A claim must include a message.")
        return value.strip()

    @validates("status")
    def validate_status(self, key, value):
        if value not in self.STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(self.STATUSES)}.")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_id": self.user_id,
            "item_id": self.item_id,
            "item_title": self.item.title if self.item else None,
        }

    def __repr__(self):
        return f"<Claim {self.id} user={self.user_id} item={self.item_id} {self.status}>"

    