"""add user_roles pivot table

Revision ID: 0b1f2e984b23
Revises: d3e0bdf517ef
Create Date: 2026-06-18 23:09:14.873065

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0b1f2e984b23"
down_revision: Union[str, Sequence[str], None] = "d3e0bdf517ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Migrate existing users.role → user_roles rows (one row per user)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO user_roles (id, user_id, role) "
            "SELECT gen_random_uuid(), id, role FROM users "
            "WHERE role IS NOT NULL"
        )
    )

    op.drop_column("users", "role")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "users", sa.Column("role", sa.VARCHAR(), autoincrement=False, nullable=False)
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users SET role = ur.role "
            "FROM (SELECT DISTINCT ON (user_id) user_id, role FROM user_roles) ur "
            "WHERE users.id = ur.user_id"
        )
    )

    op.drop_table("user_roles")
