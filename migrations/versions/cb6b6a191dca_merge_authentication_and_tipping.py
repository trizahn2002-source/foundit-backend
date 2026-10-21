"""merge authentication and tipping

Revision ID: cb6b6a191dca
Revises: 4337763b595f, 403d8e2a168e
Create Date: 2026-10-21 14:34:28.733346

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb6b6a191dca'
down_revision = ('4337763b595f', '403d8e2a168e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
