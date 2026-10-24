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
from app.core.trust import apply_system_trust_store

# Before storage imports boto3 and builds an SSL context.
_using_os_trust = apply_system_trust_store()

from app.core.storage import StorageError, get_object_store  # noqa: E402

settings = get_settings()

# A real key shape, under a prefix nothing else uses, so a leftover from a
# failed run is obvious and harmless.
TEST_KEY = f"products/storage-check/{uuid.uuid4()}.txt"
TEST_BODY = b"beadstore storage check"


def trust_store_state() -> str:
    """How TLS is being verified, as a line for the configuration block.

    Shown because the alternative is a single log warning above the output,
    which is easy to scroll past — and then the TLS advice below reads as if
    nothing had been configured at all.
    """
    if not settings.use_system_trust_store:
        return "false (using Python's own CA bundle)"
    if _using_os_trust:
        return "true (active — verifying against the OS certificate store)"
    return "true  <-- REQUESTED BUT truststore IS NOT INSTALLED, so it is NOT in effect"


def describe_configuration() -> None:
    print(f"USE_SYSTEM_TRUST_STORE {trust_store_state()}")
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
        bundle = settings.storage_s3_ca_bundle
        if bundle:
            exists = Path(bundle).is_file()
            print(f"STORAGE_S3_CA_BUNDLE  {bundle}{'' if exists else '   <-- FILE NOT FOUND'}")
        else:
            print("STORAGE_S3_CA_BUNDLE  (not set — using the default trust store)")
    print()


MISSING_PACKAGE_ADVICE = """Nothing is wrong with the configuration above — install the dependencies
and run this again:

  pip install -r requirements.txt"""

TRUSTSTORE_NOT_INSTALLED_ADVICE = """USE_SYSTEM_TRUST_STORE is on, which is the right setting for this machine,
but the truststore package isn't installed — so it fell back to Python's own
CA bundle and the certificate check failed exactly as before.

Install it and run this again:

  pip install truststore

On a machine where HTTPS is intercepted, pip needs the same bypass it always
does here:

  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org truststore

Nothing else in the configuration above needs changing, and there's no need to
put the CA bundle settings back."""

TLS_INTERCEPTION_ADVICE = """This is a TLS trust problem on THIS MACHINE, not a problem with the
configuration above, the bucket, or the credentials. Something local is
intercepting HTTPS (corporate proxy, VPN, or antivirus HTTPS scanning) and
presenting its own certificate, which Python doesn't trust. It's the same
cause as pip needing --trusted-host.

A deployed server almost certainly won't see this, so it does not block
deploying — only testing from here.

Fix it by pointing the S3 connection at a bundle that includes the
intercepting root. Export every root your machine already trusts — which is
why your browser is happy with these sites — from PowerShell:

  $out = "$HOME\\windows-roots.pem"
  Get-ChildItem Cert:\\LocalMachine\\Root, Cert:\\CurrentUser\\Root | ForEach-Object {
    "-----BEGIN CERTIFICATE-----"
    [Convert]::ToBase64String($_.RawData, 'InsertLineBreaks')
    "-----END CERTIFICATE-----"
  } | Set-Content $out

Then add the path to backend/.env, using a forward slash or a doubled
backslash so it isn't read as an escape:

  STORAGE_S3_CA_BUNDLE=C:/Users/<you>/windows-roots.pem

Note it is NOT botocore's usual AWS_CA_BUNDLE: this project's .env is read by
pydantic-settings into its own Settings object and never exported to the
process environment, so AWS_CA_BUNDLE placed there would be silently ignored.
(Setting it as a real machine environment variable would also work.)

The same interception will affect the Anthropic calls behind Import Inventory
and, later, Etsy. Those go through httpx rather than botocore, and read the
standard SSL_CERT_FILE variable — which has to be a real environment
variable, not a line in .env:

  setx SSL_CERT_FILE "C:\\Users\\<you>\\windows-roots.pem"

Or `pip install truststore` and have Python adopt the OS trust store for
every library at once. Do NOT disable certificate verification — that choice
would be carried into production, where the interception doesn't exist and
the risk is real."""

CONFIGURATION_ADVICE = """Common causes:
  - the bucket doesn't exist yet (create it in Supabase first)
  - STORAGE_S3_BUCKET doesn't match the bucket's name
  - the endpoint is wrong; it should look like
    https://<project-ref>.supabase.co/storage/v1/s3
  - the region doesn't match the one shown on the S3 Configuration page
  - the access key was revoked, or the secret was mistyped"""

# TLS is clearly working by the time these come back — the request reached
# Supabase and it answered. Keyed on status because Supabase returns error
# bodies botocore can't parse as S3 XML, leaving the code and message empty.
STATUS_ADVICE = {
    "HTTP 400": """Supabase rejected the request itself. Most often the region: it has to
match the one printed beside the endpoint on the S3 Configuration page, and
STORAGE_S3_REGION above is whatever you set (us-east-1 is only this app's
default, not necessarily yours). Worth checking the bucket name for stray
spaces or capitals too.""",
    "HTTP 403": """Supabase understood the request and refused it — so the endpoint and
bucket are reachable, and this is about the credentials. Either the access key
was revoked, the secret is mistyped or truncated, or the key belongs to a
different project than the endpoint.""",
    "HTTP 404": """The endpoint resolved but the bucket isn't there. Create a bucket in
Supabase Storage named exactly what STORAGE_S3_BUCKET says above — nothing in
this app creates it for you.""",
}


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
        # Don't hand over the CA-bundle instructions when the OS trust store
        # was asked for and simply isn't installed — that reads as "your
        # configuration is wrong" when the configuration is right and one
        # package is missing.
        if settings.use_system_trust_store and not _using_os_trust:
            return TRUSTSTORE_NOT_INSTALLED_ADVICE
        return TLS_INTERCEPTION_ADVICE
    for status_prefix, advice in STATUS_ADVICE.items():
        if status_prefix in message:
            return advice
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
