"""add attribute options table and new product attribute columns

Revision ID: a1b2c3d4e5f6
Revises: d6ff40fa4f51
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd6ff40fa4f51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('manufacturing_method', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('design_motif', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('hole_configuration', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('cut_style', sa.String(length=100), nullable=True))

    op.create_table(
        'attribute_options',
        sa.Column('field', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=150), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('field', 'value', name='uq_attribute_options_field_value'),
    )


def downgrade() -> None:
    op.drop_table('attribute_options')
    op.drop_column('products', 'cut_style')
    op.drop_column('products', 'hole_configuration')
    op.drop_column('products', 'design_motif')
    op.drop_column('products', 'manufacturing_method')
