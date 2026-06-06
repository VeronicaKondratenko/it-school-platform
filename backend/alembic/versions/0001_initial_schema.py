"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-06 00:00:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import backend.app.models  # noqa: F401
    from backend.app.database import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    import backend.app.models  # noqa: F401
    from backend.app.database import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
