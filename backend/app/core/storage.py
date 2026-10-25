"""Where uploaded files actually live.

Render's web-service filesystem is ephemeral — anything written to disk is
gone on the next deploy — so product photos can't simply be saved next to the
app. A persistent disk would work but pins the service to one instance and
disables zero-downtime deploys, and Postgres is the wrong place for a few
hundred megabytes of JPEG.

So: object storage, behind this interface. Local dev writes to a folder (no
credentials, nothing to set up); Render points at Supabase Storage, which is
already in the stack and speaks S3. The calling code never knows which.

Keys are relative paths like `products/<uuid>/<uuid>.jpg`. They're generated
server-side, never taken from a filename, and validated here anyway — a key
is the one thing in this module that could otherwise escape its directory.
"""
import re
import shutil
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()

# Deliberately strict: lowercase segments, no dots at all, so "..", a leading
# "/" and a Windows drive letter are all impossible rather than filtered.
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_.-]*)+$")


class StorageError(Exception):
    """The backing store failed. Callers turn this into a 502-ish response."""


def validate_key(key: str) -> str:
    if not key or ".." in key or not KEY_PATTERN.match(key):
        raise ValueError(f"Unsafe or malformed storage key: {key!r}")
    return key


class ObjectStore(ABC):
    """The storage operations the app needs, and no more."""

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    def public_url(self, key: str) -> str | None:
        """A URL a browser can fetch directly, if the store offers one.

        None means the app serves the bytes itself. Local dev always returns
        None; a public Supabase bucket returns a CDN URL, which keeps image
        traffic off the API process.
        """
        return None


class LocalObjectStore(ObjectStore):
    """Files under a directory on disk. For local development.

    Not for Render: the filesystem there doesn't survive a deploy. The
    directory is created on demand so a fresh clone needs no setup step.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        # Belt and braces: the key pattern already forbids traversal, but a
        # symlink inside the root could still point outside it.
        if not path.is_relative_to(self.root):
            raise ValueError(f"Storage key escapes the storage root: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written to a temporary name and moved into place, so a crash
        # mid-write can't leave a half-file that reads as a valid image.
        temporary = path.with_suffix(path.suffix + ".partial")
        try:
            temporary.write_bytes(data)
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError(f"Could not write {key}: {exc}") from exc

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise StorageError(f"No stored file at {key}")
        except OSError as exc:
            raise StorageError(f"Could not read {key}: {exc}") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"Could not delete {key}: {exc}") from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def clear(self) -> None:
        """Remove everything. Tests only — never called by the app."""
        if self.root.exists():
            shutil.rmtree(self.root)


def describe_s3_error(exc: Exception) -> str:
    """Pull the HTTP status and error code out of a botocore exception.

    `str()` on a ClientError can read "An error occurred () when calling the
    PutObject operation:" — empty code, empty message — whenever the service
    returns an error body botocore can't parse as S3 XML, which Supabase
    does. The status code is then the only thing that identifies the problem,
    and it's sitting in the response dict.
    """
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return str(exc) or exc.__class__.__name__

    error = response.get("Error") or {}
    metadata = response.get("ResponseMetadata") or {}
    parts = []
    if status_code := metadata.get("HTTPStatusCode"):
        parts.append(f"HTTP {status_code}")
    if code := error.get("Code"):
        parts.append(f"code {code}")
    if message := error.get("Message"):
        parts.append(message)
    if not parts:
        return str(exc) or exc.__class__.__name__
    return ", ".join(parts)


class S3ObjectStore(ObjectStore):
    """S3-compatible object storage — Supabase Storage in this project.

    Supabase exposes an S3 endpoint and issues access keys scoped to storage
    alone, which is why this talks S3 rather than Supabase's own REST API:
    that API authenticates with the service-role key, and a key that can
    bypass every row-level policy in the database does not belong in the
    app's environment just to store photos.

    boto3 is imported lazily so a virtualenv without it still runs the whole
    app on local storage.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        region: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        public_base_url: str = "",
        ca_bundle: str = "",
    ):
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self._endpoint_url = endpoint_url
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._ca_bundle = ca_bundle
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError:
                raise StorageError(
                    "Object storage needs the boto3 package on the server "
                    "(pip install -r requirements.txt)."
                )
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                # Supabase's S3 endpoint expects path-style addressing; the
                # virtual-host style boto3 prefers would resolve the bucket
                # as a subdomain and fail.
                config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
                # A CA bundle when one is configured, otherwise botocore's
                # default trust store. Never False: disabling verification
                # would travel to production, where the local interception
                # this works around doesn't exist and the risk is real.
                verify=self._ca_bundle or None,
            )
        return self._client

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=validate_key(key), Body=data, ContentType=content_type
            )
        except Exception as exc:  # noqa: BLE001 - boto3 raises a wide family
            raise StorageError(f"Could not upload {key}: {describe_s3_error(exc)}") from exc

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=validate_key(key))
            return response["Body"].read()
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not fetch {key}: {describe_s3_error(exc)}") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=validate_key(key))
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not delete {key}: {describe_s3_error(exc)}") from exc

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=validate_key(key))
            return True
        except Exception:  # noqa: BLE001 - a 404 is an exception here too
            return False

    def public_url(self, key: str) -> str | None:
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{validate_key(key)}"


@lru_cache
def get_object_store() -> ObjectStore:
    """The store this deployment uses, per STORAGE_BACKEND."""
    backend = (settings.storage_backend or "local").lower()
    if backend == "local":
        return LocalObjectStore(settings.storage_local_root)
    if backend == "s3":
        missing = [
            name
            for name, value in (
                ("STORAGE_S3_ENDPOINT_URL", settings.storage_s3_endpoint_url),
                # Required rather than defaulted: it's signed into the
                # request, so a wrong one is a 403 that looks like a
                # credential problem.
                ("STORAGE_S3_REGION", settings.storage_s3_region),
                ("STORAGE_S3_BUCKET", settings.storage_s3_bucket),
                ("STORAGE_S3_ACCESS_KEY_ID", settings.storage_s3_access_key_id),
                ("STORAGE_S3_SECRET_ACCESS_KEY", settings.storage_s3_secret_access_key),
            )
            if not value
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Object storage is selected but not configured. Missing: "
                    + ", ".join(missing)
                ),
            )
        return S3ObjectStore(
            endpoint_url=settings.storage_s3_endpoint_url,
            region=settings.storage_s3_region,
            bucket=settings.storage_s3_bucket,
            access_key_id=settings.storage_s3_access_key_id,
            secret_access_key=settings.storage_s3_secret_access_key,
            public_base_url=settings.storage_public_base_url,
            ca_bundle=settings.storage_s3_ca_bundle,
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unknown STORAGE_BACKEND '{backend}' — expected 'local' or 's3'.",
    )
