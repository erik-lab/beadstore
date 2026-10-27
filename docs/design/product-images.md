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

### iPhone formats

Two traps, both found by Patti's phone rather than by design:

- **MPO.** An iPhone HDR or Portrait shot is an MPO — several JPEGs in one
  container. Pillow decodes its first frame without complaint; the
  accepted-formats list was the only thing rejecting them. Since everything is
  re-encoded anyway, accepting MPO *is* the conversion.
- **HEIC.** Pillow cannot decode HEIC on its own, and HEIC is an iPhone's
  default. It was listed as supported and in the file picker's `accept` while
  being impossible to upload — the worst of both. `pillow-heif` now provides
  the decoder, registered on first use; without the package a `.heic` upload
  gets a 503 naming it, plus the Settings > Camera > Formats > "Most
  Compatible" workaround that needs no server change.

The picker's `accept` also lists bare extensions, because iOS doesn't reliably
supply a MIME type and the picker otherwise greys those photos out.

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

## When a photo won't load

A photo is two things: a `product_images` row and an object in the storage
backend, and they can diverge. The usual way is **switching backends**: photos
uploaded while `STORAGE_BACKEND=local` are files on one machine's disk, while
the row lives in the shared database — so every other machine, and the
deployed app, has the row and no file. It presents as a photo that won't load
on one device and loads fine on another.

```bash
cd backend && python -m scripts.check_product_images
```

Lists every photo whose file is missing from the configured backend. To
rescue them instead of re-uploading by hand:

```bash
python -m scripts.check_product_images --copy-from-local /path/to/old/uploads
```

The directory defaults to `STORAGE_LOCAL_ROOT` and is worth giving explicitly,
since the old location usually isn't where that setting now points.

The UI reports the underlying reason rather than a flat "couldn't load", so a
502 naming storage is distinguishable from a network blip — that distinction
is what made this diagnosable at all.

### Why development uses the same bucket as production

The tempting fix, when photos won't load locally, is to point the machine back
at local storage so the files reappear. Don't: it trades one broken view for
two.

Every environment here shares **one Supabase database**, so the
`product_images` rows are shared whether the files are or not. Local storage
means photos uploaded on the PC exist only on the PC, and photos uploaded
anywhere else are broken on it — in both directions, permanently, for every
new photo. One shared bucket is what keeps rows and files agreeing.

`STORAGE_BACKEND=local` is for a machine working against its own local
database, which is the only situation where files living locally is coherent.
The real separation to want eventually is a second Supabase project for
development — database *and* bucket — rather than splitting storage from the
database it's indexed by.

## Checking a deployment's storage

```bash
cd backend && python -m scripts.check_storage
```

Prints the resolved configuration (never the secret), then writes, reads,
stat-checks and deletes a test object. Exits non-zero on failure and names the
usual causes — missing bucket, wrong endpoint shape, mismatched region,
revoked key. Deliberately independent of auth, products and the UI, so it
isolates storage from everything layered on top of it.

## UI

- **Product page → Photos.** Add, reorder, describe, remove. The first photo
  carries a "Main photo" badge, and on the second photo the "move up" button
  reads "Make main" instead, since that's what the move actually does.
- **New-product form → Photos.** Files can be picked while entering the
  product, but can't be uploaded until it has an id, so they're held and sent
  straight after the create. A failure there doesn't lose the product: it
  lands on the detail page with a note naming what failed, where it can be
  retried. The edit form has no picker — photos are managed on the detail
  page, where reordering and removal live too.

Uploads run **sequentially**, not in parallel: each posts a base64 body of up
to ~20MB, and the order they complete in is the order the photos end up in.

### Serving an authenticated image

An `<img src>` cannot carry an Authorization header, so a private image can't
simply be pointed at the API. `useImageSrc` handles the two cases the server
returns:

- an **absolute URL** (public bucket, CDN) is used as-is — no auth, no bytes
  through the API, normal browser caching
- a **path relative to the API root** is fetched through the API client, with
  its auth header and 401 retry, and handed to the browser as an object URL

Object URLs are revoked on unmount and on change, or every photo viewed would
stay pinned in memory for the life of the tab.

The `url` field being API-root-relative rather than absolute-from-origin
matters: `VITE_API_BASE_URL` already ends in `/api/v1`, so a path including
that prefix would have been requested as `/api/v1/api/v1/...` and every image
would have 404'd.

## Not done yet
- **No Etsy image push.** `uploadListingImage` plus
  `updateListing(state=active)` is what finally makes a listing visible; see
  the pre-flight checklist in `api-tiers-work-plan.md`.
- **`products.image_url` / `image_status` / `media_notes` still exist** and are
  still unused. They predate this table and were left alone rather than
  dropped as a side effect; removing them is its own decision.
- **Nothing pushes photos to Etsy yet.** `uploadListingImage` plus
  `updateListing(state=active)` is the step that makes a listing visible; see
  the pre-flight checklist in `api-tiers-work-plan.md`.

The Supabase backend **has** now been verified against a real bucket, by
`scripts.check_storage` writing, reading back, stat-checking and deleting an
object. The automated tests still drive `LocalObjectStore` only — there is no
Supabase to reach from CI — so `S3ObjectStore`'s coverage remains its wiring:
path-style addressing, the checksum options, the CA bundle, credential
validation, and error reporting.

What that first real connection cost is worth recording, because all of it was
diagnosis rather than code:

| Symptom | Actual cause |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` | HTTPS interception on the dev machine; fixed with `USE_SYSTEM_TRUST_STORE` |
| ...still failing after setting `AWS_CA_BUNDLE` in `.env` | that name is never read from `.env` — pydantic-settings doesn't export to `os.environ` |
| "truststore isn't installed" when it was | installed under a different interpreter than the one running |
| `HTTP 403` with no code | botocore couldn't parse Supabase's error body; the status was being discarded too |
| `InvalidAccessKeyId` | a stray character in the key id |
| `SignatureDoesNotMatch` | the secret truncated to 63 of 64 characters on paste |
| `NoSuchBucket` | the bucket existed under a different name |

Each one was slower than it needed to be because the error reporting threw
away the fact that identified it. The script now names the interpreter, states
the trust-store status, describes the secret's shape without printing it, and
quotes the service's own error code — which is why the last two were one
round each.
