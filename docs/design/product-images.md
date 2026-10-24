# Product Images

## Why a storage backend at all

Render's web-service filesystem is **ephemeral** — anything written to disk is
gone on the next deploy. So photos can't just be saved next to the app. The
alternatives were weighed as:

| Option | Verdict |
|---|---|
| Render ephemeral disk | Non-starter. Photos vanish on every deploy. |
| Render Persistent Disk | Works, but pins the service to a single instance and **disables zero-downtime deploys**. A bad trade for photos. |
| Postgres (`bytea`, or data URLs as the avatars do) | Supabase's free DB is 500MB; ~500 products × 2 photos eats most of it and bloats every backup. |
| **Supabase Storage** | **Chosen.** Already in the stack, free tier is 1GB, S3-compatible, identical behaviour from localhost and Render. No new vendor. |
| Cloudflare R2 / S3 | Fine, but a new vendor and another billing relationship for no gain. |

## The adapter

`app/core/storage.py` defines `ObjectStore` with five operations —
`put`/`get`/`delete`/`exists`/`public_url` — and two implementations:

- **`LocalObjectStore`** writes under `STORAGE_LOCAL_ROOT`. No credentials, no
  setup, creates its directory on demand. Development only.
- **`S3ObjectStore`** talks to any S3-compatible endpoint; here, Supabase
  Storage. `boto3` is imported lazily so a virtualenv without it still runs
  the whole app on local storage.

`public_url` is how a public bucket keeps image traffic off the API process:
when it returns a URL, the client fetches from the CDN directly; when it
returns `None` (always, for local), the app serves the bytes from
`GET /products/images/{id}/file`.

### The credential, and a rule revised

Supabase Storage can be reached two ways. Its own REST API authenticates with
the **service-role key** — which bypasses every row-level security policy in
the database. An earlier decision in this project was that no `.env` should
ever hold that key, and storing photos is not a good enough reason to break
it.

Supabase also exposes an **S3 endpoint with storage-scoped access keys**
(Project Settings → Storage → S3 access keys). Those can do nothing but
storage. That's why this talks S3 rather than the simpler REST API: it keeps
the intent of the original rule while still working from Render.

### Key safety

Keys look like `products/<product id>/<image id>.jpg`. They're generated
server-side and never derived from an uploaded filename — but they're
validated anyway, against a deliberately strict pattern that forbids dots
entirely, so `..`, a leading `/` and a drive letter are impossible rather
than filtered. `LocalObjectStore` additionally re-checks that the resolved
path is inside its root, since a symlink could point outside one.

Local writes go to a temporary name and are renamed into place, so a crash
mid-write can't leave a half-file that reads as a valid image.

## Processing on the way in

Every upload is **decoded and re-encoded** rather than stored as it arrived.
That costs CPU and buys three things:

1. **Metadata is dropped.** Phone photos carry GPS coordinates in EXIF, and
   these images go onto a public Etsy listing. Rebuilding the file from pixels
   is the reliable way to lose that — more reliable than stripping tags from a
   format with several places to hide them.
2. **It proves the file is an image.** A successful decode is a stronger
   check than a declared content type or magic bytes.
3. **Oversized photos shrink once**, here, rather than every viewer
   downloading 12 megapixels of bead. Capped at 2400px, since Etsy wants
   ≥2000px on the short side for its zoom and there's no point holding more.

Orientation is applied **before** metadata is discarded: phones record
rotation as an EXIF tag instead of rotating pixels, so dropping EXIF first
would leave photos sideways on Etsy.

Transparency is preserved by keeping those images as PNG — flattening a
cut-out product shot onto white would ruin it. Everything else becomes
progressive JPEG at quality 88.

Limits: 15MB per upload, 50M pixels decoded (a small file can decompress into
an enormous bitmap), 10 images per product because that's Etsy's ceiling.

## Ordering

One `sort_order` column, lowest first, and the first image is the primary one
— what Etsy shows in search results. Deliberately **not** a second
`is_primary` flag: two sources of truth for "which is first" is how they end
up disagreeing. "Make this the main photo" is a reorder.

A partial reorder keeps the images it omits, placed after the ones listed, so
a short list can't silently drop photos. Deleting compacts the remaining
orders back to 0..n-1.

## Duplicate detection

`checksum` is the sha256 of the **processed** bytes, so re-uploading the same
photo to the same product is refused rather than silently duplicated. The same
photo on two different products is fine.

A consequence worth knowing: because the hash is of the processed output, two
photos that differ only in ways JPEG quantisation discards count as the same
image. That's arguably correct — they are identical by the time they're
stored — and it caught out the first version of the tests, where
"different" solid-colour fixtures compressed to byte-identical files.

## Failure handling

- A failed storage write aborts the upload; no database row is created.
- A failed database commit **deletes the object** it just wrote, so nothing is
  orphaned in the bucket.
- A delete removes the row first, then the object. The reverse order risks a
  row pointing at a missing file; this way the worst case is an orphaned
  object, which costs a little space and nothing else.

## API

| Endpoint | Does |
|---|---|
| `GET /products/{id}/images` | list, ordered, primary first |
| `POST /products/{id}/images` | upload one photo (base64 JSON) |
| `PATCH /products/{id}/images/reorder` | set order; first becomes primary |
| `PATCH /products/images/{id}` | edit alt text |
| `DELETE /products/images/{id}` | remove photo and file |
| `GET /products/images/{id}/file` | serve bytes (private buckets, and local) |

Uploads are base64 in JSON, matching how the order-email scan and inventory
import already submit files, and keeping `python-multipart` out of the
dependency list.

`storage_key` and `checksum` are deliberately **not** in the API response:
internal details the client has no use for, and the key is the one value that
shouldn't be echoed out where it could be fed back into a storage call.

Serving responses carry `Cache-Control: private, max-age=31536000, immutable`
— the bytes at a given image id never change, because an edit uploads a new
image.

## Checking a deployment's storage

```bash
cd backend && python -m scripts.check_storage
```

Prints the resolved configuration (never the secret), then writes, reads,
stat-checks and deletes a test object. Exits non-zero on failure and names the
usual causes — missing bucket, wrong endpoint shape, mismatched region,
revoked key. Deliberately independent of auth, products and the UI, so it
isolates storage from everything layered on top of it.

## Not done yet

- **No UI.** Upload from the product page is the next piece.
- **No Etsy image push.** `uploadListingImage` plus
  `updateListing(state=active)` is what finally makes a listing visible; see
  the pre-flight checklist in `api-tiers-work-plan.md`.
- **`products.image_url` / `image_status` / `media_notes` still exist** and are
  still unused. They predate this table and were left alone rather than
  dropped as a side effect; removing them is its own decision.
- **The Supabase backend is untested against real Supabase.** Everything here
  is driven against `LocalObjectStore`, which the tests exercise for real
  rather than mocking. `S3ObjectStore`'s wiring — path-style addressing,
  lazy boto3 import, credential validation — is covered, but no call has ever
  reached a Supabase bucket from this environment. Same honesty as the Etsy
  simulator: first real upload is the test.
