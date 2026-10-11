from config import db


# Each person adds their model in their own section below.
# Keep to your section to avoid merge conflicts.

# ---------- users (Wesley) ----------


# ---------- categories and items (Samuel) ----------


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
        }

    def __repr__(self):
        return f"<Claim {self.id} user={self.user_id} item={self.item_id} {self.status}>"