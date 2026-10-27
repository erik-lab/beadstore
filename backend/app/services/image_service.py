"""Taking a photo in, cleaning it up, and storing it.

Every upload is decoded and **re-encoded** rather than stored as it arrived.
That costs CPU and buys three things:

- **Metadata is dropped.** Phone photos carry GPS coordinates in EXIF, and
  these images end up on a public Etsy listing. Re-encoding from pixels is
  the reliable way to lose that, rather than trying to strip tags from a
  format that has several places to hide them.
- **It proves the file is really an image.** A decode that succeeds is
  stronger than trusting a declared content type or a magic-byte check.
- **Oversized photos get shrunk once**, here, instead of every viewer
  downloading 12 megapixels of bead.

Pillow is imported lazily, so a virtualenv without it leaves the rest of the
app working and gives a clear message on the one feature that needs it.
"""
import hashlib
import io
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.storage import StorageError, get_object_store
from app.models.product import Product
from app.models.product_image import ProductImage

# Etsy recommends at least 2000px on the shortest side so its zoom works, and
# there's no point holding more than that.
MAX_DIMENSION = 2400
# Checked against the decoded pixel count before any resize, since a small
# file can decompress into an enormous bitmap (a "decompression bomb").
MAX_PIXELS = 50_000_000
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
JPEG_QUALITY = 88

# What we accept in, keyed to how Pillow names the format. Everything is
# re-encoded to JPEG except PNG, which is kept for images with transparency.
# What we accept in, keyed to Pillow's own format names. Everything is
# re-encoded on the way out, so an accepted format doesn't have to be one
# we'd ever store — MPO in particular is what an iPhone produces for HDR and
# Portrait shots (several JPEGs in one file). Pillow decodes its first frame
# happily; it was only this list that rejected it.
ACCEPTED_FORMATS = {"JPEG", "JPEG2000", "PNG", "WEBP", "GIF", "BMP", "TIFF", "MPO", "HEIF", "HEIC"}
MAX_IMAGES_PER_PRODUCT = 10


_heif_registered = False


def _register_heif(Image) -> None:
    """Teach Pillow to read HEIC/HEIF, which iPhones shoot by default.

    Pillow can't decode these on its own — it needs pillow-heif, which
    registers an opener. Without it an iPhone photo failed as "could not be
    read as an image" even though HEIC was advertised as supported, which is
    a worse outcome than not offering it at all.

    Missing package is not fatal: every other format still works, and the
    error for a HEIC then says what to install.
    """
    global _heif_registered
    if _heif_registered:
        return
    try:
        import pillow_heif
    except ImportError:
        return
    pillow_heif.register_heif_opener()
    Image.init()
    _heif_registered = True


def _pillow():
    try:
        from PIL import Image, ImageOps

        _register_heif(Image)
        return Image, ImageOps
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Image uploads need the Pillow package on the server "
                "(pip install -r requirements.txt)."
            ),
        )


def _bad_image(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def process_image(data: bytes, filename: str = "") -> tuple[bytes, str, int, int]:
    """Decode, orient, shrink and re-encode. Returns (bytes, content_type, w, h)."""
    if not data:
        raise _bad_image("That file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"'{filename or 'That image'}' is {len(data) / 1024 / 1024:.1f}MB, over the "
                f"{MAX_UPLOAD_BYTES // 1024 // 1024}MB limit. Most phones can email or export a "
                "smaller copy."
            ),
        )

    Image, ImageOps = _pillow()
    # Pillow's own bomb guard raises on absurd dimensions; ours is explicit
    # and gives a message that says what to do.
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS

    try:
        source = Image.open(io.BytesIO(data))
        source.load()
    except Exception:  # noqa: BLE001 - Pillow raises many types for bad input
        # HEIC gets its own message: it's what an iPhone shoots by default,
        # so "unreadable" is misleading when the real answer is a missing
        # server package.
        if not _heif_registered and (filename or "").lower().endswith((".heic", ".heif")):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Reading HEIC photos needs the pillow-heif package on the server "
                    "(pip install -r requirements.txt). Until then, set the iPhone's camera to "
                    '"Most Compatible" (Settings > Camera > Formats) so it shoots JPEG, or '
                    "send the photo to yourself first, which converts it."
                ),
            )
        raise _bad_image(
            f"Could not read '{filename or 'that file'}' as an image. "
            "JPEG, PNG, WEBP, HEIC and TIFF all work."
        )

    image_format = (source.format or "").upper()
    if image_format and image_format not in ACCEPTED_FORMATS:
        raise _bad_image(f"'{image_format}' images aren't supported. Try JPEG, PNG or HEIC.")

    if source.width * source.height > MAX_PIXELS:
        raise _bad_image(
            f"'{filename or 'That image'}' is {source.width}x{source.height}, which is too large "
            "to process. Export it at a smaller size."
        )

    # Phones record orientation as an EXIF tag instead of rotating pixels, so
    # this has to be applied before the metadata is discarded or the photo
    # ends up sideways on Etsy.
    source = ImageOps.exif_transpose(source)

    has_alpha = source.mode in ("RGBA", "LA", "PA") or (
        source.mode == "P" and "transparency" in source.info
    )

    if max(source.size) > MAX_DIMENSION:
        source.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    buffer = io.BytesIO()
    if has_alpha:
        # Kept as PNG: flattening transparency onto white would wreck a
        # cut-out product shot.
        source.convert("RGBA").save(buffer, format="PNG", optimize=True)
        content_type = "image/png"
    else:
        source.convert("RGB").save(
            buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
        )
        content_type = "image/jpeg"

    # A new image built from pixels alone — no EXIF, no GPS, no thumbnails.
    return buffer.getvalue(), content_type, source.width, source.height


def _extension_for(content_type: str) -> str:
    return "png" if content_type == "image/png" else "jpg"


def get_product_or_404(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def list_images(db: Session, product_id: uuid.UUID) -> list[ProductImage]:
    return (
        db.query(ProductImage)
        .filter(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order, ProductImage.created_at)
        .all()
    )


def add_image(
    db: Session,
    product_id: uuid.UUID,
    data: bytes,
    filename: str = "",
    alt_text: str | None = None,
) -> ProductImage:
    product = get_product_or_404(db, product_id)

    existing = list_images(db, product_id)
    if len(existing) >= MAX_IMAGES_PER_PRODUCT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This product already has {MAX_IMAGES_PER_PRODUCT} photos, which is as many as "
                "Etsy accepts. Remove one first."
            ),
        )

    processed, content_type, width, height = process_image(data, filename)
    checksum = hashlib.sha256(processed).hexdigest()

    duplicate = next((image for image in existing if image.checksum == checksum), None)
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That same photo is already on this product.",
        )

    image_id = uuid.uuid4()
    storage_key = f"products/{product.id}/{image_id}.{_extension_for(content_type)}"

    store = get_object_store()
    try:
        store.put(storage_key, processed, content_type)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not save the image to storage: {exc}",
        )

    next_order = (
        db.query(func.coalesce(func.max(ProductImage.sort_order), -1))
        .filter(ProductImage.product_id == product_id)
        .scalar()
        + 1
    )

    image = ProductImage(
        id=image_id,
        product_id=product.id,
        storage_key=storage_key,
        content_type=content_type,
        byte_size=len(processed),
        width=width,
        height=height,
        sort_order=next_order,
        original_filename=(filename or None),
        checksum=checksum,
        alt_text=alt_text,
    )
    db.add(image)
    try:
        db.commit()
    except Exception:
        # Don't leave an orphaned object in the bucket that nothing points to.
        db.rollback()
        try:
            store.delete(storage_key)
        except StorageError:
            pass
        raise
    db.refresh(image)
    return image


def get_image_or_404(db: Session, image_id: uuid.UUID) -> ProductImage:
    image = db.get(ProductImage, image_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image


def read_image_bytes(image: ProductImage) -> bytes:
    try:
        return get_object_store().get(image.storage_key)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The image file could not be read from storage: {exc}",
        )


def update_image(db: Session, image_id: uuid.UUID, alt_text: str | None) -> ProductImage:
    image = get_image_or_404(db, image_id)
    image.alt_text = alt_text
    db.commit()
    db.refresh(image)
    return image


def delete_image(db: Session, image_id: uuid.UUID) -> None:
    image = get_image_or_404(db, image_id)
    product_id, storage_key = image.product_id, image.storage_key

    db.delete(image)
    db.commit()

    # Storage is cleaned up after the row is gone. The other order risks a
    # row pointing at a deleted file; this way the worst case is an orphaned
    # object, which costs a little space and nothing else.
    try:
        get_object_store().delete(storage_key)
    except StorageError:
        pass

    _compact_sort_orders(db, product_id)


def reorder_images(db: Session, product_id: uuid.UUID, image_ids: list[uuid.UUID]) -> list[ProductImage]:
    """Set the display order, first listed first.

    The first image is the primary one — what Etsy shows in search results —
    so this is also how "make this the main photo" works.
    """
    get_product_or_404(db, product_id)
    images = {image.id: image for image in list_images(db, product_id)}

    unknown = [str(image_id) for image_id in image_ids if image_id not in images]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"These images don't belong to this product: {', '.join(unknown)}",
        )
    if len(set(image_ids)) != len(image_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The same image was listed twice."
        )

    for position, image_id in enumerate(image_ids):
        images[image_id].sort_order = position
    # Anything the caller left out keeps its relative order, after the rest,
    # so a partial list can't silently drop photos from the product.
    for offset, image in enumerate(
        sorted(
            (image for image_id, image in images.items() if image_id not in set(image_ids)),
            key=lambda i: (i.sort_order, i.created_at),
        )
    ):
        image.sort_order = len(image_ids) + offset

    db.commit()
    return list_images(db, product_id)


def _compact_sort_orders(db: Session, product_id: uuid.UUID) -> None:
    """Close gaps left by a delete, so orders stay 0..n-1."""
    changed = False
    for position, image in enumerate(list_images(db, product_id)):
        if image.sort_order != position:
            image.sort_order = position
            changed = True
    if changed:
        db.commit()
