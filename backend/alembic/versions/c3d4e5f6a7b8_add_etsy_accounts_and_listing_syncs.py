"""add etsy_accounts and etsy_listing_syncs tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'etsy_accounts',
        sa.Column('shop_id', sa.String(length=50), nullable=False),
        sa.Column('shop_name', sa.String(length=255), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=False),
        sa.Column('scopes', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shop_id'),
    )

    op.create_table(
        'etsy_listing_syncs',
        sa.Column('catalog_listing_id', sa.Uuid(), nullable=False),
        sa.Column('etsy_shop_id', sa.String(length=50), nullable=False),
        sa.Column('etsy_listing_id', sa.String(length=50), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('taxonomy_id', sa.Integer(), nullable=True),
        sa.Column('shipping_profile_id', sa.Integer(), nullable=True),
        sa.Column('return_policy_id', sa.Integer(), nullable=True),
        sa.Column('who_made', sa.String(length=20), nullable=True),
        sa.Column('when_made', sa.String(length=30), nullable=True),
        sa.Column('is_supply', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['catalog_listing_id'], ['catalog_listings.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('catalog_listing_id', name='uq_etsy_listing_syncs_catalog_listing'),
    )


def downgrade() -> None:
    op.drop_table('etsy_listing_syncs')
    op.drop_table('etsy_accounts')
