"""Find product photos whose file is missing from the storage backend.

A photo is two things: a `product_images` row and an object in the storage
backend. Those can diverge, and the usual way is switching backends: photos
uploaded while STORAGE_BACKEND=local are files on one machine's disk, while
the row lives in the shared database — so every other machine, and the
deployed app, has the row and no file. It shows up as a photo that won't
load, with nothing obviously wrong.

Run with: python -m scripts.check_product_images

    --copy-from-local [DIR]
                        for each missing object, look in DIR and upload it to
                        the configured backend. How to rescue photos uploaded
                        before the switch instead of re-uploading them by
                        hand. DIR defaults to STORAGE_LOCAL_ROOT, and is worth
                        giving explicitly when the old directory isn't the
                        one that setting now points at.

Exits non-zero if anything is still missing afterwards.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.trust import apply_system_trust_store

apply_system_trust_store()

from app.core.db import SessionLocal  # noqa: E402
from app.core.storage import LocalObjectStore, StorageError, get_object_store  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.product_image import ProductImage  # noqa: E402

settings = get_settings()


def main() -> int:
    copy_from_local = "--copy-from-local" in sys.argv
    source_root = Path(settings.storage_local_root)
    if copy_from_local:
        position = sys.argv.index("--copy-from-local")
        following = sys.argv[position + 1 : position + 2]
        if following and not following[0].startswith("-"):
            source_root = Path(following[0])
    source_root = source_root.resolve()

    store = get_object_store()
    backend = (settings.storage_backend or "local").lower()
    local_default = Path(settings.storage_local_root).resolve()

    print(f"Storage backend: {backend} ({type(store).__name__})")
    if copy_from_local:
        # The question isn't which backend is configured, it's whether the
        # source is somewhere other than where we'd be writing.
        if isinstance(store, LocalObjectStore) and store.root == source_root:
            print(
                "--copy-from-local has nowhere to copy from: the configured backend is already\n"
                f"this same directory ({source_root}). Give the old directory explicitly, as\n"
                "  --copy-from-local /path/to/old/uploads"
            )
            return 1
        print(f"Recovering from: {source_root}")
    print()

    db = SessionLocal()
    try:
        images = (
            db.query(ProductImage, Product.name)
            .join(Product, ProductImage.product_id == Product.id)
            .order_by(Product.name, ProductImage.sort_order)
            .all()
        )
        if not images:
            print("No product photos recorded at all.")
            return 0

        # Only consulted with --copy-from-local, and built directly rather
        # than through the factory, which returns the *configured* store.
        local = LocalObjectStore(source_root)

        present, missing, recovered, unrecoverable = 0, [], 0, []
        for image, product_name in images:
            try:
                exists = store.exists(image.storage_key)
            except StorageError as exc:
                print(f"Could not check storage at all: {exc}")
                return 1

            if exists:
                present += 1
                continue

            missing.append((image, product_name))
            if not copy_from_local:
                continue

            if not local.exists(image.storage_key):
                unrecoverable.append((image, product_name))
                continue
            try:
                store.put(image.storage_key, local.get(image.storage_key), image.content_type)
                recovered += 1
                print(f"  recovered  {product_name}  {image.storage_key}")
            except StorageError as exc:
                unrecoverable.append((image, product_name))
                print(f"  FAILED     {product_name}  {image.storage_key}: {exc}")

        print(f"{len(images)} photo(s) recorded; {present} present in storage.")

        if not missing:
            print("\nEvery photo's file is where it should be.")
            return 0

        if copy_from_local:
            print(f"{recovered} recovered from local storage.")
            still_missing = unrecoverable
        else:
            still_missing = missing

        if still_missing:
            print(f"\n{len(still_missing)} photo(s) have no file in this backend:\n")
            for image, product_name in still_missing:
                print(f"  {product_name}  —  {image.storage_key}")
            print(
                "\nThese were almost certainly uploaded while STORAGE_BACKEND was set to\n"
                "something else — most often 'local', which stores files on one machine's\n"
                "disk while the row lives in the shared database. The row is real; the file\n"
                "just isn't here."
            )
            if not copy_from_local and backend != "local":
                print(
                    "\nIf the files are still on this machine from before the switch, run:\n"
                    f"  python -m scripts.check_product_images --copy-from-local {local_default}\n"
                    "Otherwise remove the photos in the UI and upload them again."
                )
            else:
                print("\nRemove them in the UI and upload again.")

            if backend != "local":
                # The tempting fix is to switch this machine back to local
                # storage so the files reappear. That trades one broken view
                # for two, and is worth saying before anyone tries it.
                print(
                    "\nDon't fix this by switching STORAGE_BACKEND back to 'local'. Every\n"
                    "environment shares one database, so the rows are shared whether the files\n"
                    "are or not: local storage would make these six load here and stay broken\n"
                    "everywhere else, and break every NEW photo on the other side too. One\n"
                    "shared bucket is what keeps rows and files agreeing."
                )
            return 1

        print("\nAll recovered.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
