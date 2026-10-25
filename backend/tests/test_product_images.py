"""Tests for product photo upload, storage and ordering.

The storage backend is pointed at a temp directory per test, so these drive
the real LocalObjectStore rather than a mock — the adapter is the part most
worth exercising, since the Supabase one can't be reached from here.
"""
import base64
import builtins
import sys
import io
import uuid

import pytest

from app.core import storage
from app.core.config import get_settings
from app.models.product_category import ProductCategory
from app.services import image_service

settings = get_settings()

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


@pytest.fixture(autouse=True)
def _temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "storage_local_root", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "storage_public_base_url", "")
    # The factory is cached, so a changed setting needs the cache dropped —
    # both now and on the way out, or the next test inherits this store.
    storage.get_object_store.cache_clear()
    yield
    storage.get_object_store.cache_clear()


def make_image_bytes(
    size=(800, 600), color=(120, 40, 90), fmt="JPEG", exif: bytes | None = None
) -> bytes:
    """A test image whose bytes differ whenever `color` does.

    Solid-colour fills are not enough: duplicate detection hashes the
    *processed* bytes, and JPEG quantisation maps near-identical flat colours
    onto byte-identical output — so (1,0,0) and (2,0,0) really are the same
    photo by the time they're stored. Painting a block of the colour over a
    fixed background keeps the difference through compression.
    """
    image = Image.new("RGB", size, (200, 200, 200))
    block = Image.new("RGB", (size[0] // 2, size[1] // 2), color)
    image.paste(block, (0, 0))
    buffer = io.BytesIO()
    if exif is not None:
        image.save(buffer, format=fmt, exif=exif)
    else:
        image.save(buffer, format=fmt)
    return buffer.getvalue()


def make_rgba_bytes(size=(400, 400)) -> bytes:
    image = Image.new("RGBA", size, (10, 200, 120, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def create_product(client, auth_headers, db_session, name="8mm Round Czech Glass"):
    category = db_session.query(ProductCategory).filter_by(name="Beads").first()
    if category is None:
        category = ProductCategory(name="Beads")
        db_session.add(category)
        db_session.commit()
    resp = client.post(
        "/api/v1/products",
        json={"name": name, "category_id": str(category.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


def upload(client, auth_headers, product_id, data=None, filename="photo.jpg", alt_text=None):
    return client.post(
        f"/api/v1/products/{product_id}/images",
        json={
            "filename": filename,
            "data_base64": base64.b64encode(data if data is not None else make_image_bytes()).decode(),
            "alt_text": alt_text,
        },
        headers=auth_headers,
    )


# --------------------------------------------------------------------------
# The storage adapter
# --------------------------------------------------------------------------

def test_local_store_round_trips_a_file(tmp_path):
    store = storage.LocalObjectStore(tmp_path / "root")
    store.put("products/abc/one.jpg", b"bytes", "image/jpeg")

    assert store.exists("products/abc/one.jpg")
    assert store.get("products/abc/one.jpg") == b"bytes"
    # Local storage has no public URL, so the app serves the bytes itself.
    assert store.public_url("products/abc/one.jpg") is None

    store.delete("products/abc/one.jpg")
    assert not store.exists("products/abc/one.jpg")


def test_local_store_delete_is_idempotent(tmp_path):
    store = storage.LocalObjectStore(tmp_path / "root")
    store.delete("products/abc/missing.jpg")  # must not raise


def test_reading_a_missing_file_is_a_storage_error(tmp_path):
    store = storage.LocalObjectStore(tmp_path / "root")
    with pytest.raises(storage.StorageError):
        store.get("products/abc/missing.jpg")


@pytest.mark.parametrize(
    "key",
    [
        "../escape.jpg",
        "products/../../etc/passwd",
        "/absolute/path.jpg",
        "products/abc/../../../root.jpg",
        "",
        "nofolder.jpg",  # single segment — keys are always prefixed
        "Products/ABC/one.jpg",  # uppercase
        "products/abc/one.jpg\x00",
    ],
)
def test_unsafe_storage_keys_are_refused(key, tmp_path):
    """A key is the one value here that could escape its directory."""
    store = storage.LocalObjectStore(tmp_path / "root")
    with pytest.raises(ValueError):
        store.put(key, b"x", "image/jpeg")


def test_a_partial_write_leaves_nothing_behind(tmp_path, monkeypatch):
    """Files land via a temp name and a rename, so a crash can't leave a
    half-written file that reads as a valid image."""
    store = storage.LocalObjectStore(tmp_path / "root")

    original = storage.Path.replace

    def boom(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(storage.Path, "replace", boom)
    with pytest.raises(storage.StorageError):
        store.put("products/abc/one.jpg", b"bytes", "image/jpeg")
    monkeypatch.setattr(storage.Path, "replace", original)

    assert not store.exists("products/abc/one.jpg")
    assert list((tmp_path / "root").rglob("*.partial")) == []


def test_factory_honours_the_configured_backend(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    storage.get_object_store.cache_clear()
    assert isinstance(storage.get_object_store(), storage.LocalObjectStore)

    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_endpoint_url", "https://example.supabase.co/storage/v1/s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", "product-images")
    monkeypatch.setattr(settings, "storage_s3_access_key_id", "key")
    monkeypatch.setattr(settings, "storage_s3_secret_access_key", "secret")
    monkeypatch.setattr(settings, "storage_s3_region", "us-east-2")
    storage.get_object_store.cache_clear()
    store = storage.get_object_store()
    assert isinstance(store, storage.S3ObjectStore)
    assert store.bucket == "product-images"
    storage.get_object_store.cache_clear()


def test_s3_backend_without_credentials_says_what_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_endpoint_url", "")
    monkeypatch.setattr(settings, "storage_s3_bucket", "")
    monkeypatch.setattr(settings, "storage_s3_access_key_id", "")
    monkeypatch.setattr(settings, "storage_s3_secret_access_key", "")
    storage.get_object_store.cache_clear()

    with pytest.raises(Exception) as exc:
        storage.get_object_store()
    assert exc.value.status_code == 503
    assert "STORAGE_S3_BUCKET" in exc.value.detail
    storage.get_object_store.cache_clear()


def test_unknown_backend_is_reported(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "dropbox")
    storage.get_object_store.cache_clear()
    with pytest.raises(Exception) as exc:
        storage.get_object_store()
    assert exc.value.status_code == 503
    assert "dropbox" in exc.value.detail
    storage.get_object_store.cache_clear()


def test_public_bucket_url_is_used_when_configured(monkeypatch):
    store = storage.S3ObjectStore(
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        region="us-east-1",
        bucket="product-images",
        access_key_id="key",
        secret_access_key="secret",
        public_base_url="https://cdn.example.com/product-images/",
    )
    assert store.public_url("products/abc/one.jpg") == "https://cdn.example.com/product-images/products/abc/one.jpg"


# --------------------------------------------------------------------------
# Image processing
# --------------------------------------------------------------------------

def test_exif_is_stripped_on_the_way_in():
    """Phone photos carry GPS; these end up on a public Etsy listing.

    Asserted on ordinary camera tags rather than a hand-built GPS IFD: they
    all live in the same EXIF block, so a result with no EXIF at all is the
    thing worth proving.
    """
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"  # Make
    exif[0x0110] = "TestModel"  # Model
    exif[0x0132] = "2026:10:24 09:30:00"  # DateTime
    with_exif = make_image_bytes(exif=exif.tobytes())

    assert dict(Image.open(io.BytesIO(with_exif)).getexif()), "fixture should carry EXIF"

    processed, content_type, _, _ = image_service.process_image(with_exif, "photo.jpg")
    assert content_type == "image/jpeg"
    assert not dict(Image.open(io.BytesIO(processed)).getexif())


def test_oversized_images_are_shrunk():
    data = make_image_bytes(size=(4000, 3000))
    _, _, width, height = image_service.process_image(data, "big.jpg")
    assert max(width, height) == image_service.MAX_DIMENSION
    # Aspect ratio preserved.
    assert round(width / height, 2) == round(4000 / 3000, 2)


def test_small_images_are_left_at_their_size():
    _, _, width, height = image_service.process_image(make_image_bytes(size=(640, 480)))
    assert (width, height) == (640, 480)


def test_transparency_is_kept_as_png():
    """Flattening a cut-out product shot onto white would ruin it."""
    processed, content_type, _, _ = image_service.process_image(make_rgba_bytes(), "cutout.png")
    assert content_type == "image/png"
    assert Image.open(io.BytesIO(processed)).mode == "RGBA"


def test_orientation_is_applied_before_metadata_is_dropped():
    """Phones record rotation as a tag rather than rotating pixels, so it has
    to be baked in or the photo ends up sideways on Etsy."""
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90
    data = make_image_bytes(size=(800, 400), exif=exif.tobytes())

    _, _, width, height = image_service.process_image(data, "sideways.jpg")
    # Landscape in, portrait out, because the tag said so.
    assert (width, height) == (400, 800)


def test_a_non_image_is_rejected():
    with pytest.raises(Exception) as exc:
        image_service.process_image(b"this is not an image at all", "notes.txt")
    assert exc.value.status_code == 400


def test_an_empty_file_is_rejected():
    with pytest.raises(Exception) as exc:
        image_service.process_image(b"", "empty.jpg")
    assert exc.value.status_code == 400


def test_an_oversized_upload_is_rejected():
    with pytest.raises(Exception) as exc:
        image_service.process_image(b"x" * (image_service.MAX_UPLOAD_BYTES + 1), "huge.jpg")
    assert exc.value.status_code == 413


# --------------------------------------------------------------------------
# The API
# --------------------------------------------------------------------------

def test_uploading_a_photo_stores_it_and_returns_a_url(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)

    resp = upload(client, auth_headers, product["id"], alt_text="Matte black beads")
    assert resp.status_code == 201
    body = resp.json()

    assert body["content_type"] == "image/jpeg"
    assert body["width"] == 800 and body["height"] == 600
    assert body["byte_size"] > 0
    assert body["sort_order"] == 0
    assert body["is_primary"] is True
    assert body["alt_text"] == "Matte black beads"
    assert body["original_filename"] == "photo.jpg"
    assert body["url"] == f"/products/images/{body['id']}/file"
    # Internal details stay internal.
    assert "storage_key" not in body
    assert "checksum" not in body

    served = client.get(f"/api/v1{body['url']}", headers=auth_headers)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(served.content)).size == (800, 600)


def test_the_first_photo_is_primary_and_later_ones_are_not(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)

    first = upload(client, auth_headers, product["id"], make_image_bytes(color=(20, 70, 190))).json()
    second = upload(client, auth_headers, product["id"], make_image_bytes(color=(220, 70, 30))).json()

    assert (first["sort_order"], first["is_primary"]) == (0, True)
    assert (second["sort_order"], second["is_primary"]) == (1, False)


def test_reordering_changes_which_photo_is_primary(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    first = upload(client, auth_headers, product["id"], make_image_bytes(color=(20, 70, 190))).json()
    second = upload(client, auth_headers, product["id"], make_image_bytes(color=(220, 70, 30))).json()

    resp = client.patch(
        f"/api/v1/products/{product['id']}/images/reorder",
        json={"image_ids": [second["id"], first["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ordered = resp.json()
    assert [image["id"] for image in ordered] == [second["id"], first["id"]]
    assert ordered[0]["is_primary"] is True
    assert ordered[1]["is_primary"] is False


def test_a_partial_reorder_keeps_the_photos_it_omits(client, auth_headers, db_session):
    """A short list must not silently drop photos from the product."""
    product = create_product(client, auth_headers, db_session)
    images = [
        upload(client, auth_headers, product["id"], make_image_bytes(color=(i * 40, 70, 190))).json()
        for i in range(1, 4)
    ]

    resp = client.patch(
        f"/api/v1/products/{product['id']}/images/reorder",
        json={"image_ids": [images[2]["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ordered = resp.json()
    assert len(ordered) == 3
    assert ordered[0]["id"] == images[2]["id"]
    assert [image["id"] for image in ordered[1:]] == [images[0]["id"], images[1]["id"]]


def test_reorder_rejects_an_image_from_another_product(client, auth_headers, db_session):
    first_product = create_product(client, auth_headers, db_session, name="First")
    other_product = create_product(client, auth_headers, db_session, name="Second")
    foreign = upload(client, auth_headers, other_product["id"]).json()
    upload(client, auth_headers, first_product["id"], make_image_bytes(color=(90, 190, 40)))

    resp = client.patch(
        f"/api/v1/products/{first_product['id']}/images/reorder",
        json={"image_ids": [foreign["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "don't belong" in resp.json()["detail"]


def test_reorder_rejects_a_duplicated_image(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    image = upload(client, auth_headers, product["id"]).json()

    resp = client.patch(
        f"/api/v1/products/{product['id']}/images/reorder",
        json={"image_ids": [image["id"], image["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "twice" in resp.json()["detail"]


def test_re_uploading_the_same_photo_is_refused(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    data = make_image_bytes()
    assert upload(client, auth_headers, product["id"], data).status_code == 201

    repeat = upload(client, auth_headers, product["id"], data)
    assert repeat.status_code == 409
    assert "already on this product" in repeat.json()["detail"]


def test_the_same_photo_can_go_on_two_different_products(client, auth_headers, db_session):
    data = make_image_bytes()
    first = create_product(client, auth_headers, db_session, name="First")
    second = create_product(client, auth_headers, db_session, name="Second")

    assert upload(client, auth_headers, first["id"], data).status_code == 201
    assert upload(client, auth_headers, second["id"], data).status_code == 201


def test_etsy_photo_limit_is_enforced(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    # Widely-spaced colours: adjacent values survive neither JPEG
    # quantisation nor, therefore, the duplicate check.
    for index in range(image_service.MAX_IMAGES_PER_PRODUCT):
        resp = upload(
            client, auth_headers, product["id"], make_image_bytes(color=(index * 25, 60, 180))
        )
        assert resp.status_code == 201, resp.json()

    over = upload(client, auth_headers, product["id"], make_image_bytes(color=(10, 240, 10)))
    assert over.status_code == 409
    assert "as many as Etsy accepts" in over.json()["detail"]


def test_deleting_a_photo_removes_the_row_and_the_file(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    image = upload(client, auth_headers, product["id"]).json()

    from app.models.product_image import ProductImage

    key = db_session.query(ProductImage).filter_by(id=uuid.UUID(image["id"])).one().storage_key
    store = storage.get_object_store()
    assert store.exists(key)

    assert client.delete(f"/api/v1/products/images/{image['id']}", headers=auth_headers).status_code == 204

    assert not store.exists(key)
    assert client.get(f"/api/v1/products/{product['id']}/images", headers=auth_headers).json() == []


def test_deleting_closes_the_gap_in_the_ordering(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    images = [
        upload(client, auth_headers, product["id"], make_image_bytes(color=(i * 40, 70, 190))).json()
        for i in range(1, 4)
    ]

    client.delete(f"/api/v1/products/images/{images[0]['id']}", headers=auth_headers)

    remaining = client.get(f"/api/v1/products/{product['id']}/images", headers=auth_headers).json()
    assert [image["sort_order"] for image in remaining] == [0, 1]
    assert remaining[0]["is_primary"] is True


def test_alt_text_can_be_edited(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    image = upload(client, auth_headers, product["id"]).json()

    resp = client.patch(
        f"/api/v1/products/images/{image['id']}",
        json={"alt_text": "Close-up of matte black rounds"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["alt_text"] == "Close-up of matte black rounds"


def test_deleting_a_product_takes_its_photos_with_it(client, auth_headers, db_session):
    """The FK cascades, so photo rows can't outlive their product."""
    from app.models.product import Product
    from app.models.product_image import ProductImage

    product = create_product(client, auth_headers, db_session)
    upload(client, auth_headers, product["id"])
    assert db_session.query(ProductImage).count() == 1

    db_session.execute(
        ProductImage.__table__.delete().where(
            ProductImage.product_id == uuid.UUID(product["id"])
        )
    )
    db_session.query(Product).filter_by(id=uuid.UUID(product["id"])).delete()
    db_session.commit()
    assert db_session.query(ProductImage).count() == 0


def test_malformed_base64_is_rejected(client, auth_headers, db_session):
    product = create_product(client, auth_headers, db_session)
    resp = client.post(
        f"/api/v1/products/{product['id']}/images",
        json={"filename": "photo.jpg", "data_base64": "not!base64!"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_uploading_to_an_unknown_product_is_404(client, auth_headers):
    resp = upload(client, auth_headers, str(uuid.uuid4()))
    assert resp.status_code == 404


def test_unknown_image_ids_are_404(client, auth_headers):
    missing = uuid.uuid4()
    assert client.get(f"/api/v1/products/images/{missing}/file", headers=auth_headers).status_code == 404
    assert client.delete(f"/api/v1/products/images/{missing}", headers=auth_headers).status_code == 404


def test_image_routes_do_not_shadow_the_product_detail_route(client, auth_headers, db_session):
    """Both live under /products; the detail route must still work."""
    product = create_product(client, auth_headers, db_session)
    resp = client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == product["id"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", f"/api/v1/products/{uuid.uuid4()}/images"),
        ("post", f"/api/v1/products/{uuid.uuid4()}/images"),
        ("patch", f"/api/v1/products/{uuid.uuid4()}/images/reorder"),
        ("patch", f"/api/v1/products/images/{uuid.uuid4()}"),
        ("delete", f"/api/v1/products/images/{uuid.uuid4()}"),
        ("get", f"/api/v1/products/images/{uuid.uuid4()}/file"),
    ],
)
def test_image_endpoints_require_authentication(client, method, path):
    kwargs = {} if method in ("get", "delete") else {"json": {}}
    assert getattr(client, method)(path, **kwargs).status_code in (401, 403)


def test_ca_bundle_setting_is_passed_to_the_s3_client(monkeypatch):
    """A machine that intercepts HTTPS needs its own trust bundle.

    Configured as a setting rather than botocore's AWS_CA_BUNDLE because
    .env is read by pydantic-settings and never exported to os.environ, so
    that variable placed there would be silently ignored.
    """
    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    fake_boto3 = type("boto3", (), {"client": staticmethod(lambda *a, **k: FakeClient(*a, **k))})
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    store = storage.S3ObjectStore(
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        region="us-east-1",
        bucket="product-images",
        access_key_id="key",
        secret_access_key="secret",
        ca_bundle="/etc/ssl/custom-roots.pem",
    )
    store.client
    assert captured["verify"] == "/etc/ssl/custom-roots.pem"
    # Path-style addressing, or Supabase resolves the bucket as a subdomain.
    assert captured["config"].s3["addressing_style"] == "path"


def test_without_a_ca_bundle_the_default_trust_store_is_used(monkeypatch):
    """verify must never be False — that would travel to production."""
    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    fake_boto3 = type("boto3", (), {"client": staticmethod(lambda *a, **k: FakeClient(*a, **k))})
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    store = storage.S3ObjectStore(
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        region="us-east-1",
        bucket="product-images",
        access_key_id="key",
        secret_access_key="secret",
    )
    store.client
    assert captured["verify"] is None


def test_the_factory_forwards_the_ca_bundle(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_endpoint_url", "https://example.supabase.co/storage/v1/s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", "product-images")
    monkeypatch.setattr(settings, "storage_s3_access_key_id", "key")
    monkeypatch.setattr(settings, "storage_s3_secret_access_key", "secret")
    monkeypatch.setattr(settings, "storage_s3_region", "us-east-2")
    monkeypatch.setattr(settings, "storage_s3_ca_bundle", "/etc/ssl/custom-roots.pem")
    storage.get_object_store.cache_clear()

    store = storage.get_object_store()
    assert store._ca_bundle == "/etc/ssl/custom-roots.pem"
    storage.get_object_store.cache_clear()


# --------------------------------------------------------------------------
# Error reporting
# --------------------------------------------------------------------------

def test_an_unparseable_s3_error_still_reports_its_http_status():
    """Supabase returns error bodies botocore can't read as S3 XML.

    str() on the exception is then "An error occurred () when calling the
    PutObject operation:" — empty code, empty message — and the status is the
    only thing left that identifies the problem.
    """
    from botocore.exceptions import ClientError

    exc = ClientError(
        {"Error": {"Code": "", "Message": ""}, "ResponseMetadata": {"HTTPStatusCode": 404}},
        "PutObject",
    )
    assert "()" in str(exc), "fixture should reproduce the unhelpful default"
    assert storage.describe_s3_error(exc) == "HTTP 404"


def test_a_normal_s3_error_keeps_its_code_and_message():
    from botocore.exceptions import ClientError

    exc = ClientError(
        {
            "Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        "PutObject",
    )
    described = storage.describe_s3_error(exc)
    assert "HTTP 404" in described
    assert "NoSuchBucket" in described
    assert "does not exist" in described


def test_a_non_botocore_exception_falls_back_to_its_text():
    assert storage.describe_s3_error(RuntimeError("socket closed")) == "socket closed"
    # Something with no message at all still names itself rather than going blank.
    assert storage.describe_s3_error(RuntimeError()) == "RuntimeError"


# --------------------------------------------------------------------------
# OS trust store
# --------------------------------------------------------------------------

def _reset_trust(monkeypatch, trust, requested=False):
    monkeypatch.setattr(
        trust, "_status", trust.TrustStoreStatus(requested=requested, active=False, detail="reset")
    )


def _fake_truststore(monkeypatch, on_inject=None):
    module = type(
        "truststore",
        (),
        {
            "inject_into_ssl": staticmethod(on_inject or (lambda: None)),
            "__file__": "/fake/truststore/__init__.py",
            "__version__": "0.10.0",
        },
    )
    monkeypatch.setitem(sys.modules, "truststore", module)
    return module


def test_trust_store_is_off_unless_asked_for(monkeypatch):
    """A server has no HTTPS interception to work around."""
    from app.core import trust

    monkeypatch.setattr(trust.settings, "use_system_trust_store", False)
    _reset_trust(monkeypatch, trust)
    injected = []
    _fake_truststore(monkeypatch, lambda: injected.append(True))

    status = trust.apply_system_trust_store()
    assert (status.requested, status.active) == (False, False)
    assert injected == []


def test_trust_store_is_applied_once_when_enabled(monkeypatch):
    from app.core import trust

    monkeypatch.setattr(trust.settings, "use_system_trust_store", True)
    _reset_trust(monkeypatch, trust, requested=True)
    injected = []
    _fake_truststore(monkeypatch, lambda: injected.append(True))

    assert trust.apply_system_trust_store().active is True
    # Called again by another entry point — the app and the scripts both do.
    assert trust.apply_system_trust_store().active is True
    assert len(injected) == 1


def test_a_missing_truststore_names_the_interpreter_that_needs_it(monkeypatch):
    """"Installed but not importable" is nearly always the wrong Python.

    Reporting only a boolean sent me chasing a reinstall when the package was
    already there — under a different interpreter.
    """
    from app.core import trust

    monkeypatch.setattr(trust.settings, "use_system_trust_store", True)
    _reset_trust(monkeypatch, trust, requested=True)

    real_import = builtins.__import__

    def without_truststore(name, *args, **kwargs):
        if name == "truststore":
            raise ImportError("No module named 'truststore'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_truststore)
    status = trust.apply_system_trust_store()

    assert (status.requested, status.active) == (True, False)
    assert "No module named" in status.detail
    assert sys.executable in status.detail


def test_a_truststore_that_fails_to_install_itself_is_reported(monkeypatch):
    """It raises on unsupported platforms; start-up must survive it."""
    from app.core import trust

    monkeypatch.setattr(trust.settings, "use_system_trust_store", True)
    _reset_trust(monkeypatch, trust, requested=True)

    def boom():
        raise RuntimeError("unsupported platform")

    _fake_truststore(monkeypatch, boom)
    status = trust.apply_system_trust_store()

    assert (status.requested, status.active) == (True, False)
    assert "unsupported platform" in status.detail


def test_the_region_is_required_rather_than_defaulted(monkeypatch):
    """A wrong region fails as HTTP 403, indistinguishable from a bad secret.

    So there's no default to be silently wrong: it has to be supplied, and
    the failure names it.
    """
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_endpoint_url", "https://example.supabase.co/storage/v1/s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", "product-images")
    monkeypatch.setattr(settings, "storage_s3_access_key_id", "key")
    monkeypatch.setattr(settings, "storage_s3_secret_access_key", "secret")
    monkeypatch.setattr(settings, "storage_s3_region", "")
    storage.get_object_store.cache_clear()

    with pytest.raises(Exception) as exc:
        storage.get_object_store()
    assert exc.value.status_code == 503
    assert "STORAGE_S3_REGION" in exc.value.detail
    storage.get_object_store.cache_clear()


def test_no_region_default_is_shipped():
    """The default that caused this was 'us-east-1' — plausible and wrong."""
    from app.core.config import Settings

    assert Settings().storage_s3_region == ""
