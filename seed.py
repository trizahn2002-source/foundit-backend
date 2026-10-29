
from datetime import date
from config import app, db
from models import User, Category, Item


with app.app_context():
    print("Starting safe database seeding...")

    # 1. Add sample users without deleting existing users.
    sample_users = [
        ("amina", "amina@example.com"),
        ("brian", "brian@example.com"),
        ("grace", "grace@example.com"),
    ]

    users = {}

    for username, email in sample_users:
        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(username=username, email=email)
            user.set_password("password123")
            db.session.add(user)
            print(f"Added user: {username}")
        else:
            print(f"User already exists: {username}")

        users[username] = user

    # 2. Add missing categories only.
    category_names = [
        "Electronics",
        "Bags",
        "Documents",
        "Keys",
        "Clothing",
        "Wallets",
        "Phones",
        "Laptops",
        "Identification Documents",
        "Accessories",
        "Other"
    ]

    categories = {}

    for name in category_names:
        category = Category.query.filter_by(name=name).first()

        if not category:
            category = Category(name=name)
            db.session.add(category)
            print(f"Added category: {name}")
        else:
            print(f"Category already exists: {name}")

        categories[name] = category

    db.session.commit()

    # 3. Never automatically add sample reports to
    # a database containing real or existing reports.
    if Item.query.count() > 0:
        print("Existing items detected.")
        print("Skipping sample items to protect current data.")
        print("No existing items, claims, or photos were deleted.")

    else:
        print("No items found. Adding sample reports...")

        items = [
            Item(
                title="Black Backpack",
                type="lost",
                category=categories["Bags"],
                user_id=users["amina"].id,
                description="Black JanSport backpack with a red keychain.",
                location="Sarit Centre, Westlands",
                latitude=-1.2615,
                longitude=36.8025,
                date=date(2026, 9, 28),
            ),
            Item(
                title="Black Backpack",
                type="found",
                category=categories["Bags"],
                user_id=users["brian"].id,
                description="Black backpack found near the food court, has a keychain.",
                location="Westgate Mall, Westlands",
                latitude=-1.2567,
                longitude=36.803,
                date=date(2026, 9, 28),
            ),
            Item(
                title="Samsung Phone",
                type="lost",
                category=categories["Phones"],
                user_id=users["grace"].id,
                description="Samsung Galaxy A54 in a blue case.",
                location="Kenyatta Avenue, Nairobi CBD",
                latitude=-1.2841,
                longitude=36.8255,
                date=date(2026, 9, 25),
            ),
            Item(
                title="Phone in Blue Case",
                type="found",
                category=categories["Phones"],
                user_id=users["amina"].id,
                description="Samsung phone in a blue case found on a matatu bench.",
                location="Archives Stage, Nairobi CBD",
                latitude=-1.2849,
                longitude=36.8243,
                date=date(2026, 9, 26),
            ),
            Item(
                title="Car Keys",
                type="lost",
                category=categories["Keys"],
                user_id=users["brian"].id,
                description="Toyota car key with a green keyring.",
                location="Two Rivers Mall, Limuru Road",
                latitude=-1.2105,
                longitude=36.7955,
                date=date(2026, 9, 20),
                status="resolved",
            ),
            Item(
                title="Grey Hoodie",
                type="found",
                category=categories["Clothing"],
                user_id=users["grace"].id,
                description="Grey hoodie, size M, left on a bench.",
                location="Uhuru Park, Nairobi",
                latitude=-1.2885,
                longitude=36.8165,
                date=date(2026, 9, 27),
            ),
        ]

        db.session.add_all(items)
        db.session.commit()

        print("Six sample reports added successfully.")

    print("Safe seeding completed.")
