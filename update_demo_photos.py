
import base64
from pathlib import Path

from config import app, db
from models import Item

PHOTO_DIR = Path(__file__).parent / "demo_photos"

# Existing demo items and their corresponding photographs
photos = {
    ("Black Backpack", "lost"): ("backpack_lost.jpg", "image/jpeg"),
    ("Black Backpack", "found"): ("backpack_found.png", "image/png"),
    ("Samsung Phone", "lost"): ("samsung_lost.png", "image/png"),
    ("Phone in Blue Case", "found"): ("samsung_found.png", "image/png"),
    ("Car Keys", "lost"): ("carkeys_found.png", "image/png"),
    ("Grey Hoodie", "found"): ("greyhoodie_found.png", "image/png"),
}

with app.app_context():
    updates = []

    for (title, item_type), (filename, mime_type) in photos.items():
        item = Item.query.filter_by(
            title=title,
            type=item_type
        ).one_or_none()

        if item is None:
            print(f"Skipped {title} ({item_type}): item missing or not unique.")
            continue

        photo_path = PHOTO_DIR / filename

        if not photo_path.is_file():
            print(f"Missing image: {photo_path}")
            continue

        image_data = base64.b64encode(
            photo_path.read_bytes()
        ).decode("ascii")

        item.image_url = f"data:{mime_type};base64,{image_data}"
        updates.append(item)

        print(f"Prepared photo for {title} ({item_type})")

    if len(updates) == len(photos):
        db.session.commit()
        print("Success! All six demo item photos updated.")
    else:
        db.session.rollback()
        print("No changes saved because some records or photos were missing.")
