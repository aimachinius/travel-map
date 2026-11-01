"""enable place search extensions

Revision ID: a05c8b520b04
Revises: a5d38c5aa5c1
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a05c8b520b04"
down_revision: Union[str, Sequence[str], None] = "a5d38c5aa5c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    # Không xóa extension vì có thể được sử dụng bởi thành phần khác.
    pass