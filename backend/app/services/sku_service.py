"""Generating the shop's own product codes.

Bead supplies have no universal identifier — there's no GS1 barcode on a
strand of Czech glass — so the shop mints its own. These are what go on bin
labels, into barcodes, and into the `sku` Etsy carries on a listing's
inventory, so an Etsy order comes back identifiable.

Two deliberate choices:

**Opaque, not meaningful.** A code like BEAD-GLASS-0001 looks helpful until
something is recategorized, and then the code lies forever. Classification
lives in the database, where it can change; the code only has to be unique
and stable.

**Crockford base32.** Its alphabet drops I, L, O and U precisely so a code
can be read aloud, hand-keyed and OCR'd without 0/O or 1/I confusion — worth
more here than the four extra characters a full base32 would buy.
"""
import secrets

from sqlalchemy.orm import Session

from app.models.product import Product

# Crockford's base32 alphabet: no I, L, O or U.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PREFIX = "BS-"
BODY_LENGTH = 5
# 32**5 ≈ 33.5M codes. At a few thousand products the chance of drawing one
# already taken is vanishingly small, and the retry below covers it anyway.
MAX_ATTEMPTS = 10


def _check_character(body: str) -> str:
    """A positionally-weighted check character over the same alphabet.

    Weights are **odd** on purpose. The alphabet is 32 characters, so the
    arithmetic is mod 32 — a power of two, where an even weight can be
    cancelled out entirely: with a weight of 2, mistyping a character for one
    16 places away in the alphabet changes the total by exactly 32 and the
    check character doesn't move. Odd weights are invertible mod 32, so every
    single mistyped character changes the check. (Found by the test that now
    pins it, not by inspection.)

    Weighting by position at all is what catches transpositions, which a flat
    sum sails straight past. One limitation remains, and it's narrow: swapping
    two adjacent characters whose alphabet positions differ by exactly 16 —
    "0G" for "G0" — still checks out, because consecutive odd weights differ
    by 2 and 2 x 16 is again a multiple of 32. Closing that would mean a
    prime modulus, which no longer fits one character of this alphabet, or a
    second check character. Not worth either: these codes are read by a
    Code128 scanner, which carries its own checksum, and this character is the
    safety net for the times they're typed by hand.
    """
    total = sum((2 * index + 1) * ALPHABET.index(char) for index, char in enumerate(body))
    return ALPHABET[total % len(ALPHABET)]


def format_sku(body: str) -> str:
    return f"{PREFIX}{body}{_check_character(body)}"


def is_valid_sku(sku: str) -> bool:
    """Whether a scanned or typed code is well-formed and self-consistent.

    Catches a mistyped or misread code before it's used to look up the wrong
    product — the reason for carrying a check character at all.
    """
    if not sku or not sku.startswith(PREFIX):
        return False
    code = sku[len(PREFIX) :]
    if len(code) != BODY_LENGTH + 1:
        return False
    body, check = code[:BODY_LENGTH], code[BODY_LENGTH]
    if any(char not in ALPHABET for char in code):
        return False
    return _check_character(body) == check


def generate_product_sku(db: Session) -> str:
    """Mint an unused product code.

    Random rather than sequential: no counter row to lock, nothing to
    migrate, and the code doesn't leak how many products the shop has. The
    uniqueness check makes the draw safe, and `products.sku` is UNIQUE so the
    database has the final say even under a race.
    """
    for _ in range(MAX_ATTEMPTS):
        body = "".join(secrets.choice(ALPHABET) for _ in range(BODY_LENGTH))
        sku = format_sku(body)
        if db.query(Product.id).filter(Product.sku == sku).first() is None:
            return sku
    # Effectively unreachable at any plausible catalog size; raising beats
    # returning a duplicate and tripping the unique constraint later, where
    # the cause would be far less obvious.
    raise RuntimeError(
        f"Could not find an unused product code after {MAX_ATTEMPTS} attempts — "
        "the code space may be unexpectedly full."
    )
