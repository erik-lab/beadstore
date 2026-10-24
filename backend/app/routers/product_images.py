"""Product photos: upload, order, serve, delete.

Nested under /products/{id}/images since an image has no meaning apart from
its product. The one exception is serving the bytes, which is by image id —
that URL ends up in an <img src> and shouldn't need the product id too.
"""
import base64
import binascii
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.storage import get_object_store
from app.models.product_image import ProductImage
from app.schemas.product_image import (
    ProductImageRead,
    ProductImageReorder,
    ProductImageUpdate,
    ProductImageUpload,
)
from app.services import image_service

router = APIRouter(prefix="/products", tags=["product-images"])


def _to_read(image: ProductImage, is_primary: bool) -> ProductImageRead:
    """Attach the fields that aren't columns: where to fetch it, and rank.

    A public bucket hands back a CDN URL so image traffic skips this process
    entirely; otherwise the client is pointed at our own serving endpoint.
    """
    public = get_object_store().public_url(image.storage_key)
    return ProductImageRead(
        **{
            field: getattr(image, field)
            for field in (
                "id",
                "product_id",
                "content_type",
                "byte_size",
                "width",
                "height",
                "sort_order",
                "original_filename",
                "alt_text",
                "created_at",
            )
        },
        url=public or f"/api/v1/products/images/{image.id}/file",
        is_primary=is_primary,
    )


def _read_list(images: list[ProductImage]) -> list[ProductImageRead]:
    return [_to_read(image, index == 0) for index, image in enumerate(images)]


@router.get(
    "/{product_id}/images",
    response_model=list[ProductImageRead],
    dependencies=[Depends(get_current_user)],
)
def list_product_images(product_id: uuid.UUID, db: Session = Depends(get_db)):
    image_service.get_product_or_404(db, product_id)
    return _read_list(image_service.list_images(db, product_id))


@router.post(
    "/{product_id}/images",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
def upload_product_image(
    product_id: uuid.UUID, payload: ProductImageUpload, db: Session = Depends(get_db)
):
    """Add a photo. It's re-encoded on the way in, which drops EXIF/GPS."""
    try:
        data = base64.b64decode(payload.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That image didn't upload correctly. Try again.",
        )

    image = image_service.add_image(
        db, product_id, data, filename=payload.filename, alt_text=payload.alt_text
    )
    images = image_service.list_images(db, product_id)
    return _to_read(image, bool(images) and images[0].id == image.id)


@router.patch(
    "/{product_id}/images/reorder",
    response_model=list[ProductImageRead],
    dependencies=[Depends(get_current_user)],
)
def reorder_product_images(
    product_id: uuid.UUID, payload: ProductImageReorder, db: Session = Depends(get_db)
):
    """Reorder photos — the first is the primary one Etsy shows in search."""
    return _read_list(image_service.reorder_images(db, product_id, payload.image_ids))


@router.patch(
    "/images/{image_id}",
    response_model=ProductImageRead,
    dependencies=[Depends(get_current_user)],
)
def update_product_image(
    image_id: uuid.UUID, payload: ProductImageUpdate, db: Session = Depends(get_db)
):
    image = image_service.update_image(db, image_id, payload.alt_text)
    images = image_service.list_images(db, image.product_id)
    return _to_read(image, bool(images) and images[0].id == image.id)


@router.delete(
    "/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_product_image(image_id: uuid.UUID, db: Session = Depends(get_db)):
    image_service.delete_image(db, image_id)


@router.get("/images/{image_id}/file", dependencies=[Depends(get_current_user)])
def get_product_image_file(image_id: uuid.UUID, db: Session = Depends(get_db)):
    """Stream the stored bytes.

    Used when the bucket isn't public — local development always, and any
    deployment that keeps its bucket private. Cached hard because the bytes
    at a given image id never change: an edit uploads a new image.
    """
    image = image_service.get_image_or_404(db, image_id)
    return Response(
        content=image_service.read_image_bytes(image),
        media_type=image.content_type,
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
