"""add etsy_listing_images table and etsy_listing_syncs.etsy_state

Etsy fixes an image's rank at upload and has no reorder call, so the app has
to remember what it previously sent or every push would duplicate images or
leave the order wrong.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-10-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('etsy_listing_syncs', sa.Column('etsy_state', sa.String(length=20), nullable=True))

    op.create_table(
        'etsy_listing_images',
        sa.Column('etsy_listing_sync_id', sa.Uuid(), nullable=False),
        sa.Column('product_image_id', sa.Uuid(), nullable=True),
        sa.Column('etsy_image_id', sa.String(length=50), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['etsy_listing_sync_id'], ['etsy_listing_syncs.id'], ondelete='CASCADE'),
        # SET NULL, not CASCADE: when a photo is deleted locally this row has
        # to outlive it, so the next push can tell Etsy to drop its copy.
        sa.ForeignKeyConstraint(['product_image_id'], ['product_images.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('etsy_listing_sync_id', 'product_image_id', name='uq_etsy_listing_images_sync_image'),
    )
    op.create_index(
        op.f('ix_etsy_listing_images_etsy_listing_sync_id'),
        'etsy_listing_images',
        ['etsy_listing_sync_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_etsy_listing_images_etsy_listing_sync_id'), table_name='etsy_listing_images')
    op.drop_table('etsy_listing_images')
    op.drop_column('etsy_listing_syncs', 'etsy_state')
