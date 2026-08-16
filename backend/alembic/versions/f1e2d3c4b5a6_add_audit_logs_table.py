"""add audit logs table

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('record_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('changes', sa.String(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_table_record', 'audit_logs', ['table_name', 'record_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_table_record', table_name='audit_logs')
    op.drop_table('audit_logs')
