"""sync all missing columns and tables from models

Revision ID: 002
Revises: 001
Create Date: 2026-07-19

Introspects the actual DB schema and adds any columns/tables
that exist in the SQLAlchemy models but are missing in the database.
Safe and idempotent — only adds, never drops or modifies data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.config.database import Base
from src.config.models import *  # noqa: F401,F403


revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _make_column(col) -> sa.Column:
    """Reconstruct a sa.Column from a mapped_column for add_column."""
    sa_col = col.column
    return sa.Column(
        sa_col.name,
        sa_col.type,
        nullable=sa_col.nullable,
        default=sa_col.default,
        server_default=sa_col.server_default,
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    added = 0

    for table_name, table_obj in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            print(f"  Creating missing table: {table_name}")
            table_obj.create(bind, checkfirst=True)
            added += 1
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

        for col_name, col_obj in table_obj.columns.items():
            if col_name not in existing_cols:
                print(f"  Adding missing column: {table_name}.{col_name}")
                try:
                    op.add_column(table_name, _make_column(col_obj))
                    added += 1
                except Exception as e:
                    print(f"    WARNING: could not add {table_name}.{col_name}: {e}")

    if added == 0:
        print("  Schema already in sync, nothing to do.")
    else:
        print(f"  Added {added} column(s)/table(s).")


def downgrade() -> None:
    pass
