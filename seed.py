from datetime import date
from config import app, db
from models import User, Category, Item, Claim

with app.app_context():
    print("Clearing old data...")
    Claim.query.delete()
    Item.query.delete()
    Category.query.delete()
    User.query.delete()

    print("Adding users...")
    amina = User(username="amina", email="amina@example.com")
    amina.set_password("password123")
    brian = User(username="brian", email="brian@example.com")
    brian.set_password("password123")
    grace = User(username="grace", email="grace@example.com")
    grace.set_password("password123")
    db.session.add_all([amina, brian, grace])

    print("Adding categories...")
    names = ["Electronics", "Bags", "Documents", "Keys", "Clothing", "Other"]
    cats = {name: Category(name=name) for name in names}
    db.session.add_all(cats.values())
    db.session.commit()

    print("Adding items...")
    items = [
        Item(title="Black Backpack", type="lost", category=cats["Bags"], user_id=amina.id,
             description="Black JanSport backpack with a red keychain.",
             location="Sarit Centre, Westlands", latitude=-1.2615, longitude=36.8025,
             date=date(2026, 9, 28)),
        Item(title="Black Backpack", type="found", category=cats["Bags"], user_id=brian.id,
             description="Black backpack found near the food court, has a keychain.",
             location="Westgate Mall, Westlands", latitude=-1.2567, longitude=36.803,
             date=date(2026, 9, 28)),
        Item(title="Samsung Phone", type="lost", category=cats["Electronics"], user_id=grace.id,
             description="Samsung Galaxy A54 in a blue case.",
             location="Kenyatta Avenue, Nairobi CBD", latitude=-1.2841, longitude=36.8255,
             date=date(2026, 9, 25)),
        Item(title="Phone in Blue Case", type="found", category=cats["Electronics"], user_id=amina.id,
             description="Samsung phone in a blue case found on a matatu bench.",
             location="Archives Stage, Nairobi CBD", latitude=-1.2849, longitude=36.8243,
             date=date(2026, 9, 26)),
        Item(title="Car Keys", type="lost", category=cats["Keys"], user_id=brian.id,
             description="Toyota car key with a green keyring.",
             location="Two Rivers Mall, Limuru Road", latitude=-1.2105, longitude=36.7955,
             date=date(2026, 9, 20), status="resolved"),
        Item(title="Grey Hoodie", type="found", category=cats["Clothing"], user_id=grace.id,
             description="Grey hoodie, size M, left on a bench.",
             location="Uhuru Park, Nairobi", latitude=-1.2885, longitude=36.8165,
             date=date(2026, 9, 27)),
    ]
    db.session.add_all(items)
    db.session.commit()

    print("Done! 3 users, 6 categories, 6 items added.")