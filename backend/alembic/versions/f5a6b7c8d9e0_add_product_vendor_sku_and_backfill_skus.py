"""add products.vendor_sku, move imported codes into it, and backfill shop SKUs

`products.sku` now means the shop's own generated code (unique, immutable,
barcoded, sent to Etsy). Any value already in it came from a supplier — the
inventory importer wrote the code it found on the source — so those move to
the new `vendor_sku` column, and every product is given a freshly generated
shop code.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-10-24 00:00:00.000000

"""
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Duplicated from app/services/sku_service.py rather than imported: a
# migration has to keep producing the same codes it produced the day it ran,
# even if the generator is changed later.
#
# The copy still has to agree with sku_service._check_character, or every code
# this backfills fails validation the moment anything scans or re-keys it. The
# odd weighting matters — see that function for why an even one is broken on a
# 32-character alphabet.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PREFIX = "BS-"
BODY_LENGTH = 5


def _format_sku(body: str) -> str:
    total = sum((2 * index + 1) * ALPHABET.index(char) for index, char in enumerate(body))
    return f"{PREFIX}{body}{ALPHABET[total % len(ALPHABET)]}"


def upgrade() -> None:
    op.add_column('products', sa.Column('vendor_sku', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_products_vendor_sku'), 'products', ['vendor_sku'], unique=False)

    products = sa.table(
        'products',
        sa.column('id', sa.Uuid()),
        sa.column('sku', sa.String()),
        sa.column('vendor_sku', sa.String()),
    )
    connection = op.get_bind()

    # Whatever is in `sku` today is a supplier's code under the old meaning.
    connection.execute(products.update().values(vendor_sku=products.c.sku))

    # Then give every product a shop code. Generated one at a time against a
    # set of what's been used, so this stays correct whatever is already in
    # the table — including a partially migrated one from a failed run.
    rows = connection.execute(sa.select(products.c.id, products.c.sku)).fetchall()
    used = {row.sku for row in rows if row.sku and row.sku.startswith(PREFIX)}
    for row in rows:
        if row.sku and row.sku.startswith(PREFIX):
            continue  # already a shop code
        while True:
            candidate = _format_sku("".join(secrets.choice(ALPHABET) for _ in range(BODY_LENGTH)))
            if candidate not in used:
                used.add(candidate)
                break
        connection.execute(products.update().where(products.c.id == row.id).values(sku=candidate))


def downgrade() -> None:
    products = sa.table(
        'products',
        sa.column('id', sa.Uuid()),
        sa.column('sku', sa.String()),
        sa.column('vendor_sku', sa.String()),
    )
    connection = op.get_bind()
    # Put the supplier codes back where they used to live, discarding the
    # generated shop codes.
    connection.execute(products.update().values(sku=products.c.vendor_sku))

    op.drop_index(op.f('ix_products_vendor_sku'), table_name='products')
    op.drop_column('products', 'vendor_sku')
