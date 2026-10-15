import math
import re
from datetime import timedelta

from flask import Blueprint, jsonify
from models import Item
from config import db

matches_bp = Blueprint("matches", __name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on",
    "at", "to", "for", "with", "is", "was", "my",
    "it", "this", "that", "i", "lost", "found"
}


def keywords(item):
    text = f"{item.title or ''} {item.description or ''}"
    words = re.findall(r"[a-z0-9]+", text.lower())
    return set(words) - STOPWORDS


def distance_km(first, second):
    coords = (
        first.latitude, first.longitude,
        second.latitude, second.longitude
    )

    if any(value is None for value in coords):
        return None

    lat1, lon1, lat2, lon2 = map(math.radians, coords)

    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin((lon2 - lon1) / 2) ** 2
    )

    return 6371 * 2 * math.asin(math.sqrt(min(1, a)))


def match_score(first, second):
    if first.type == second.type:
        return None

    if first.category_id != second.category_id:
        return None

    if first.status != "active" or second.status != "active":
        return None

    if first.user_id == second.user_id:
        return None

    if first.date and second.date:
        if abs((first.date - second.date).days) > 7:
            return None

    shared = keywords(first) & keywords(second)

    if len(shared) < 2:
        return None

    score = 3 if len(shared) >= 4 else 2
    distance = distance_km(first, second)

    if distance is not None:
        if distance <= 2:
            score += 3
        elif distance <= 5:
            score += 2
        elif distance <= 10:
            score += 1

    return {
        "score": score,
        "shared_keywords": sorted(shared),
        "distance_km": round(distance, 2) if distance is not None else None,
    }


@matches_bp.get("/api/items/<int:item_id>/matches")
def get_possible_matches(item_id):
    item = db.session.get(Item, item_id)

    if item is None:
        return jsonify({"error": "Item not found"}), 404

    if item.status != "active":
        return jsonify({"matches": [], "count": 0}), 200

    opposite_type = "found" if item.type == "lost" else "lost"

    candidates = Item.query.filter_by(
        type=opposite_type,
        category_id=item.category_id,
        status="active",
    ).filter(Item.id != item.id, Item.user_id != item.user_id).all()

    results = []

    for candidate in candidates:
        details = match_score(item, candidate)

        if details is not None:
            results.append({
                "item": candidate.to_dict(),
                **details,
            })

    results.sort(key=lambda result: result["score"], reverse=True)

    return jsonify({
        "item_id": item.id,
        "count": len(results),
        "matches": results,
    }), 200