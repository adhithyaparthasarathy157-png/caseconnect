"""add institution representative assignments

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
"""

import sqlalchemy as sa

from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("institution_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key("fk_users_institution_id", "institutions", ["institution_id"], ["id"])
        batch.create_index("ix_users_institution_id", ["institution_id"], unique=False)
    # Development-only synthetic representative linked to the existing first demo institution.
    op.execute("""INSERT INTO users (email, full_name, password_hash, role, is_active, bureau_id, institution_id, region_scope)
        SELECT 'institution.rep@demo.example.com', 'Demo Institution Representative',
        '$2b$12$cn6X0Q35mHTH45LYQhXoh.IJmdjoZcX7E4Y12v/oo0.1t/PEQqlUq',
        'INSTITUTION_REPRESENTATIVE', 1, b.id, i.id, NULL
        FROM institutions i JOIN bureaus b ON b.code = 'RB'
        WHERE i.permanent_id = 'DEMO-AICTE-0001'
        AND NOT EXISTS (SELECT 1 FROM users WHERE email = 'institution.rep@demo.example.com')""")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_institution_id", type_="foreignkey")
        batch.drop_index("ix_users_institution_id")
        batch.drop_column("institution_id")
