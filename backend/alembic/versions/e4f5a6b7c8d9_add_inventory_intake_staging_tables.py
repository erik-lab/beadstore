"""add inventory_intake_batches and inventory_intake_rows staging tables

Revision ID: e4f5a6b7c8d9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inventory_intake_batches',
        sa.Column('source_kind', sa.Enum('paste', 'spreadsheet', 'document', 'voice', name='intakesourcekind', native_enum=False, length=20), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'committed', 'discarded', name='intakebatchstatus', native_enum=False, length=20), nullable=False),
        sa.Column('parser_notes', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'inventory_intake_rows',
        sa.Column('batch_id', sa.Uuid(), nullable=False),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('raw_fragment', sa.Text(), nullable=True),
        sa.Column('product_name', sa.String(length=255), nullable=True),
        sa.Column('category_name', sa.String(length=150), nullable=True),
        sa.Column('subtype_name', sa.String(length=150), nullable=True),
        sa.Column('matched_product_id', sa.Uuid(), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column('unit_type', sa.String(length=30), nullable=True),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('vendor_name', sa.String(length=255), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('received_date', sa.Date(), nullable=True),
        sa.Column('sku', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('attributes_json', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('missing_fields', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Enum('high', 'medium', 'low', name='intakeconfidence', native_enum=False, length=10), nullable=False),
        sa.Column('status', sa.Enum('needs_review', 'ready', 'committed', 'skipped', name='intakerowstatus', native_enum=False, length=20), nullable=False),
        sa.Column('commit_error', sa.Text(), nullable=True),
        sa.Column('created_product_id', sa.Uuid(), nullable=True),
        sa.Column('created_inventory_unit_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['inventory_intake_batches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['matched_product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['created_product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['created_inventory_unit_id'], ['inventory_units.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inventory_intake_rows_batch_id'), 'inventory_intake_rows', ['batch_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_intake_rows_batch_id'), table_name='inventory_intake_rows')
    op.drop_table('inventory_intake_rows')
    op.drop_table('inventory_intake_batches')
