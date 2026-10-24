"""Prove the configured object storage actually works.

Round-trips a small test file through whatever STORAGE_BACKEND points at, and
cleans up after itself. No auth, no product, no browser — so when an upload
fails, this says whether the problem is the storage configuration or
everything else.

Run with: python -m scripts.check_storage

Exits non-zero on failure, so it also works as a smoke check after a deploy
(the Render shell is a fine place to run it).
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.storage import StorageError, get_object_store

settings = get_settings()

# A real key shape, under a prefix nothing else uses, so a leftover from a
# failed run is obvious and harmless.
TEST_KEY = f"products/storage-check/{uuid.uuid4()}.txt"
TEST_BODY = b"beadstore storage check"


def describe_configuration() -> None:
    backend = (settings.storage_backend or "local").lower()
    print(f"STORAGE_BACKEND       {backend}")
    if backend == "local":
        root = Path(settings.storage_local_root).resolve()
        print(f"STORAGE_LOCAL_ROOT    {root}")
        print("\nNote: local storage is for development only — Render's filesystem")
        print("is wiped on every deploy, so photos saved there would disappear.")
    else:
        print(f"STORAGE_S3_ENDPOINT   {settings.storage_s3_endpoint_url or '(not set)'}")
        print(f"STORAGE_S3_REGION     {settings.storage_s3_region or '(not set)'}")
        print(f"STORAGE_S3_BUCKET     {settings.storage_s3_bucket or '(not set)'}")
        # Never print the secret; show just enough of the id to tell two apart.
        key_id = settings.storage_s3_access_key_id
        print(f"STORAGE_S3_ACCESS_KEY {key_id[:4] + '...' if key_id else '(not set)'}")
        print(f"                      secret {'set' if settings.storage_s3_secret_access_key else 'NOT SET'}")
        print(f"STORAGE_PUBLIC_BASE   {settings.storage_public_base_url or '(not set — bytes served by the API)'}")
    print()


MISSING_PACKAGE_ADVICE = """Nothing is wrong with the configuration above — install the dependencies
and run this again:

  pip install -r requirements.txt"""

TLS_INTERCEPTION_ADVICE = """This is a TLS trust problem on THIS MACHINE, not a problem with the
configuration above, the bucket, or the credentials. Something local is
intercepting HTTPS (corporate proxy, VPN, or antivirus HTTPS scanning) and
presenting its own certificate, which Python doesn't trust. It's the same
cause as pip needing --trusted-host.

A deployed server almost certainly won't see this, so it does not block
deploying — only testing from here.

To fix it locally, point the AWS SDK at a bundle that includes the
intercepting root. botocore reads AWS_CA_BUNDLE, so no code change is needed.
Exporting every root your machine already trusts is the reliable way to get
one, from PowerShell:

  $out = "$HOME\\windows-roots.pem"
  Get-ChildItem Cert:\\LocalMachine\\Root, Cert:\\CurrentUser\\Root | ForEach-Object {
    "-----BEGIN CERTIFICATE-----"
    [Convert]::ToBase64String($_.RawData, 'InsertLineBreaks')
    "-----END CERTIFICATE-----"
  } | Set-Content $out

Then add to backend/.env:

  AWS_CA_BUNDLE=C:\\Users\\<you>\\windows-roots.pem

Alternatively `pip install truststore` and have Python use the OS trust store
directly, which fixes this for every library at once rather than just the AWS
SDK. Do NOT disable certificate verification — that would be carried into
production, where the interception doesn't exist and the risk is real."""

CONFIGURATION_ADVICE = """Common causes:
  - the bucket doesn't exist yet (create it in Supabase first)
  - STORAGE_S3_BUCKET doesn't match the bucket's name
  - the endpoint is wrong; it should look like
    https://<project-ref>.supabase.co/storage/v1/s3
  - the region doesn't match the one shown on the S3 Configuration page
  - the access key was revoked, or the secret was mistyped"""


def advice_for(exc: Exception) -> str:
    """Advice matched to the failure, not a list of everything it could be.

    Printing the bucket-and-credentials checklist under an error that was
    really a missing package, or a local certificate problem, sends you
    looking in the wrong place — which it did twice before this existed.
    """
    message = str(exc)
    if "pip install" in message:
        return MISSING_PACKAGE_ADVICE
    if "CERTIFICATE_VERIFY_FAILED" in message or "SSL" in message:
        return TLS_INTERCEPTION_ADVICE
    return CONFIGURATION_ADVICE


def main() -> int:
    describe_configuration()

    try:
        store = get_object_store()
    except Exception as exc:  # noqa: BLE001 - an HTTPException from the factory
        print(f"FAILED to build the storage client: {getattr(exc, 'detail', exc)}")
        return 1

    print(f"Using {type(store).__name__}")
    print(f"Test key: {TEST_KEY}\n")

    try:
        print("  writing...  ", end="", flush=True)
        store.put(TEST_KEY, TEST_BODY, "text/plain")
        print("ok")

        print("  reading...  ", end="", flush=True)
        fetched = store.get(TEST_KEY)
        if fetched != TEST_BODY:
            print(f"MISMATCH — wrote {len(TEST_BODY)} bytes, read back {len(fetched)}")
            return 1
        print("ok")

        print("  exists...   ", end="", flush=True)
        if not store.exists(TEST_KEY):
            print("FAILED — the file was written but exists() says no")
            return 1
        print("ok")

        public = store.public_url(TEST_KEY)
        if public:
            print(f"  public URL: {public}")

        print("  deleting... ", end="", flush=True)
        store.delete(TEST_KEY)
        if store.exists(TEST_KEY):
            print("FAILED — still there after delete")
            return 1
        print("ok")

    except StorageError as exc:
        print("FAILED")
        print(f"\n{exc}\n")
        print(advice_for(exc))
        # Best-effort tidy-up, in case the write succeeded and a later step failed.
        try:
            store.delete(TEST_KEY)
        except StorageError:
            pass
        return 1

    print("\nStorage is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
