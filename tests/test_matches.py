from datetime import date

from app import app
from config import db
from models import Item, Category, User

with app.app_context():
    user1 = db.session.get(User, 1)
    user2 = db.session.get(User, 2)

    bags = Category.query.filter_by(name="Bags").first()
    electronics = Category.query.filter_by(name="Electronics").first()

    base = Item(
        title="Purple Umbrella",
        description="Purple umbrella with silver handle",
        type="lost",
        status="active",
        category=bags,
        user_id=user1.id,
        date=date(2026, 10, 1),
    )

    db.session.add(base)
    db.session.flush()

    bad_matches = [
        # Wrong category
        Item(
            title="Purple Umbrella",
            description="Purple umbrella with silver handle",
            type="found",
            status="active",
            category=electronics,
            user_id=user2.id,
            date=date(2026, 10, 1),
        ),

        # Same user
        Item(
            title="Purple Umbrella",
            description="Purple umbrella with silver handle",
            type="found",
            status="active",
            category=bags,
            user_id=user1.id,
            date=date(2026, 10, 1),
        ),

        # More than 7 days apart
        Item(
            title="Purple Umbrella",
            description="Purple umbrella with silver handle",
            type="found",
            status="active",
            category=bags,
            user_id=user2.id,
            date=date(2026, 10, 20),
        ),

        # Fewer than 2 shared keywords
        Item(
            title="Blue Bag",
            description="Blue bag",
            type="found",
            status="active",
            category=bags,
            user_id=user2.id,
            date=date(2026, 10, 1),
        ),
    ]

    db.session.add_all(bad_matches)
    db.session.commit()

    client = app.test_client()
    response = client.get(f"/api/items/{base.id}/matches")

    print("Status:", response.status_code)
    print("Response:", response.get_json())

    for item in bad_matches:
        db.session.delete(item)

    db.session.delete(base)
    db.session.commit()