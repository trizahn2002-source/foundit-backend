"""merge image_url migrations

Revision ID: afbbef45a372
Revises: e1e10dfe7632, 99ce5ed86cc5
Create Date: 2026-10-15 22:58:13.337224

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'afbbef45a372'
down_revision = ('e1e10dfe7632', '99ce5ed86cc5')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
