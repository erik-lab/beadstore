"""Prove the configured object storage actually works.

Round-trips a small test file through whatever STORAGE_BACKEND points at, and
cleans up after itself. No auth, no product, no browser — so when an upload
fails, this says whether the problem is the storage configuration or
everything else.

Run with: python -m scripts.check_storage

Add --debug to print the raw HTTP exchange, which is the only way to see the
error the service actually sent when botocore can't parse it into a code.

Exits non-zero on failure, so it also works as a smoke check after a deploy
(the Render shell is a fine place to run it).
"""
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.trust import apply_system_trust_store

# Before storage imports boto3 and builds an SSL context.
_trust = apply_system_trust_store()

from app.core.storage import StorageError, get_object_store  # noqa: E402

settings = get_settings()

# A real key shape, under a prefix nothing else uses, so a leftover from a
# failed run is obvious and harmless.
TEST_KEY = f"products/storage-check/{uuid.uuid4()}.txt"
TEST_BODY = b"beadstore storage check"


def describe_secret(secret: str) -> str:
    """Describe the secret's shape without printing any of it.

    The secret is the one input this check can't verify against the service,
    and a signature rejection says nothing about which character is wrong.
    Its shape is checkable though, and that catches what actually goes wrong
    when copying one: surrounding quotes, a stray character, a truncated
    paste.

    Reports the length rather than asserting a required one. Supabase's S3
    secrets have been 64 hexadecimal characters, but that isn't something this
    can verify, and insisting on it would be worse than useless if they ever
    differ — it would send someone fixing a secret that was already right.
    """
    if not secret:
        return "NOT SET"

    notes = []
    stripped = secret.strip()
    if secret != stripped:
        notes.append("it has leading/trailing whitespace — remove that")
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'":
        notes.append("it looks wrapped in quotes — .env values don't need them")

    non_hex = sorted({char for char in stripped if char not in "0123456789abcdefABCDEF"})
    shape = f"{len(stripped)} characters"
    if non_hex:
        shape += f", not all hexadecimal (contains {non_hex})"
    else:
        shape += ", all hexadecimal"
    if len(stripped) != 64 or non_hex:
        shape += " — Supabase's have been 64 hex characters, so this is worth a second look"

    return "set: " + shape + ("; " + "; ".join(notes) if notes else "")


def describe_configuration() -> None:
    # The interpreter, because "installed but not importable" almost always
    # means installed under a different Python than the one running this.
    print(f"PYTHON                {sys.executable}")
    if not _trust.requested:
        print("USE_SYSTEM_TRUST_STORE false (using Python's own CA bundle)")
    elif _trust.active:
        print(f"USE_SYSTEM_TRUST_STORE true (active) — {_trust.detail}")
    else:
        print("USE_SYSTEM_TRUST_STORE true  <-- REQUESTED BUT NOT IN EFFECT")
        print(f"                      {_trust.detail}")
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
        print(f"                      secret {describe_secret(settings.storage_s3_secret_access_key)}")
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

TRUSTSTORE_NOT_ACTIVE_ADVICE = """USE_SYSTEM_TRUST_STORE is on, which is the right setting for this machine,
but it did not take effect, so TLS fell back to Python's own CA bundle and
failed exactly as before. The reason:

  {detail}

If you believe truststore IS installed, it is most likely installed for a
different Python than the one running this. Install it for THIS interpreter
specifically:

  "{python}" -m pip install truststore

adding the usual bypass if pip itself is blocked by the interception:

  "{python}" -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org truststore

Check which one it landed under with:

  "{python}" -c "import truststore, sys; print(sys.executable); print(truststore.__file__)"

Nothing else in the configuration above needs changing, and there is no need
to put the CA bundle settings back."""

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
    "HTTP 403": """Supabase understood the request and refused it, so the endpoint is
reachable and TLS is fine — what it rejected was the signature.

Check the REGION first, not the credentials. An AWS SigV4 request signs the
region into it, so a wrong region produces exactly this 403 and looks nothing
like a region problem. STORAGE_S3_REGION is printed above; it has to match the
value shown beside the endpoint on Supabase's S3 Configuration page.

If the region is already right, then it is the credentials:
  - the secret mistyped or truncated when copied (it's only shown once)
  - the access key revoked
  - the key belonging to a different project than the endpoint

The service's own error code is quoted in the failure line above when it
sends one. --debug shows the whole exchange if it doesn't.""",
    "HTTP 404": """The endpoint resolved but the bucket isn't there. Create a bucket in
Supabase Storage named exactly what STORAGE_S3_BUCKET says above — nothing in
this app creates it for you.""",
}


INVALID_ACCESS_KEY_ADVICE = """Supabase does not recognise the access key id at all — so this is not the
region, the secret, or the bucket. That key does not exist in the project the
endpoint points at.

The endpoint above names the project (the <project-ref> in its hostname). Open
that project in Supabase, go to Storage -> S3 Configuration -> Access keys,
and check the key id listed there matches STORAGE_S3_ACCESS_KEY above.

The usual cause is a key created in a DIFFERENT Supabase project than the one
the endpoint and database belong to — easy to do with more than one project
open. The other is a key since revoked. Either way, generate a key in this
project and copy both halves; the secret is only shown once."""


SIGNATURE_MISMATCH_ADVICE = """Supabase recognised the access key id — so the key exists and the project is
right — but the signature computed from the SECRET didn't match. In order of
likelihood:

1. The secret is wrong. Most often a stray character picked up when copying,
   or a truncated paste. It's only displayed once, so if there's any doubt,
   generate a new key pair and copy both halves again. A Supabase S3 secret
   is 64 hexadecimal characters with nothing else in it — worth checking
   the length and that it has no quotes, spaces or line breaks around it in
   .env.
2. The region doesn't match the project's. It's signed into the request, so a
   wrong one fails here too, identically.

Note the secret is the only input not echoed in the configuration above —
deliberately — so it's also the one thing this check can't verify for you."""


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
        if _trust.requested and not _trust.active:
            return TRUSTSTORE_NOT_ACTIVE_ADVICE.format(
                detail=_trust.detail, python=sys.executable
            )
        return TLS_INTERCEPTION_ADVICE
    # The service's own code, when it reached us, beats guessing from status.
    if "InvalidAccessKeyId" in message:
        return INVALID_ACCESS_KEY_ADVICE
    if "SignatureDoesNotMatch" in message:
        return SIGNATURE_MISMATCH_ADVICE
    for status_prefix, advice in STATUS_ADVICE.items():
        if status_prefix in message:
            return advice
    return CONFIGURATION_ADVICE


def enable_wire_logging() -> None:
    """Dump the raw HTTP exchange botocore is having.

    Needed because Supabase returns error bodies botocore can't parse as S3
    XML, so the code and message come back empty and the real reason —
    SignatureDoesNotMatch, InvalidAccessKeyId — is only in the response body.

    This prints request headers, which include the access key id and the
    request signature. It does NOT print the secret, and a signature is
    single-use, but redact before pasting it anywhere public.
    """
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    for name in ("botocore", "urllib3"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    print("--debug: raw HTTP exchange follows. Request headers include the access")
    print("key id and the request signature (not the secret) — redact before sharing.\n")


def main() -> int:
    if "--debug" in sys.argv:
        enable_wire_logging()
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
