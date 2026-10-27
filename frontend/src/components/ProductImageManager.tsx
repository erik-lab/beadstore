import { useRef, useState } from "react";
import { ApiError } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import { useImageSrc } from "../lib/useImageSrc";
import {
  ImageTooLargeError,
  MAX_IMAGES_PER_PRODUCT,
  deleteProductImage,
  listProductImages,
  reorderProductImages,
  updateProductImage,
  uploadProductImage,
} from "../lib/productImages";
import type { ProductImage } from "../lib/types";
import { Loading, EmptyState, ErrorState } from "./States";

// Includes the iPhone formats explicitly. Safari reports a Portrait or HDR
// shot as image/jpeg but the file is an MPO container, and HEIC needs naming
// too or the picker greys those photos out entirely. The extensions are
// listed as well because iOS doesn't always supply a MIME type.
export const IMAGE_FILE_ACCEPT =
  "image/jpeg,image/png,image/webp,image/heic,image/heif,image/tiff,image/mpo," +
  ".jpg,.jpeg,.png,.webp,.heic,.heif,.tif,.tiff,.mpo";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ImageTooLargeError) return err.message;
  if (err instanceof ApiError) return String(err.detail);
  return err instanceof Error ? err.message : fallback;
}

/** One photo: the picture, its alt text, and the controls that act on it. */
function ImageCard({
  image,
  index,
  total,
  busy,
  onMove,
  onDelete,
  onAltTextSaved,
  onError,
}: {
  image: ProductImage;
  index: number;
  total: number;
  busy: boolean;
  onMove: (image: ProductImage, direction: -1 | 1) => void;
  onDelete: (image: ProductImage) => void;
  onAltTextSaved: (image: ProductImage) => void;
  onError: (message: string) => void;
}) {
  const { src, error } = useImageSrc(image.url);
  const [altText, setAltText] = useState(image.alt_text ?? "");
  const [savingAlt, setSavingAlt] = useState(false);

  async function commitAltText() {
    const trimmed = altText.trim();
    if (trimmed === (image.alt_text ?? "")) return;
    setSavingAlt(true);
    try {
      onAltTextSaved(await updateProductImage(image.id, trimmed || null));
    } catch (err) {
      onError(errorMessage(err, "Could not save the description."));
      setAltText(image.alt_text ?? "");
    } finally {
      setSavingAlt(false);
    }
  }

  return (
    <div className="image-card">
      <div className="image-card-preview">
        {error ? (
          // The reason, not just the fact. A 502 naming storage means the
          // file isn't in the bucket — which is what happens to photos
          // uploaded before the storage backend was switched, and is
          // otherwise indistinguishable from a network blip.
          <div className="state state-error" style={{ fontSize: 12, padding: 8 }}>
            Couldn't load this image — {error}
          </div>
        ) : src ? (
          <img src={src} alt={image.alt_text ?? ""} />
        ) : (
          <div className="state state-loading">Loading...</div>
        )}
        {image.is_primary && <span className="badge tone-good image-card-flag">Main photo</span>}
      </div>

      <div className="image-card-body">
        <label>
          Description (optional)
          <input
            value={altText}
            placeholder="What's in the photo"
            disabled={busy || savingAlt}
            onChange={(e) => setAltText(e.target.value)}
            onBlur={commitAltText}
          />
        </label>

        <p className="page-subtitle">
          {image.width && image.height ? `${image.width}x${image.height} · ` : ""}
          {(image.byte_size / 1024).toFixed(0)}KB
          {image.original_filename ? ` · ${image.original_filename}` : ""}
        </p>

        <div className="maintenance-row">
          <button
            className="btn-secondary"
            onClick={() => onMove(image, -1)}
            disabled={busy || index === 0}
            title={index === 1 ? "Make this the main photo" : "Move earlier"}
          >
            {index === 1 ? "Make main" : "Move up"}
          </button>
          <button
            className="btn-secondary"
            onClick={() => onMove(image, 1)}
            disabled={busy || index === total - 1}
          >
            Move down
          </button>
          <button className="btn-secondary" onClick={() => onDelete(image)} disabled={busy}>
            Remove
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Manage a product's photos: add, order, describe, remove.
 *
 * The first photo is the primary one — what Etsy shows in search results —
 * so ordering is a real feature here rather than decoration, and "Make main"
 * is just a move to the front.
 */
export function ProductImageManager({ productId }: { productId: string }) {
  const images = useFetch(() => listProductImages(productId), [productId]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const list = images.data ?? [];
  const atLimit = list.length >= MAX_IMAGES_PER_PRODUCT;

  async function handleFiles(files: FileList) {
    setError(null);
    setBusy(true);
    const picked = Array.from(files);
    const room = MAX_IMAGES_PER_PRODUCT - list.length;
    const toUpload = picked.slice(0, Math.max(room, 0));
    const failures: string[] = [];

    try {
      // Sequential, not parallel: each upload posts a base64 body of up to
      // ~20MB, and the order they finish in decides the photo order.
      for (const [index, file] of toUpload.entries()) {
        setProgress(`Uploading ${index + 1} of ${toUpload.length}...`);
        try {
          await uploadProductImage(productId, file);
        } catch (err) {
          failures.push(`${file.name}: ${errorMessage(err, "upload failed")}`);
        }
      }

      if (picked.length > toUpload.length) {
        failures.push(
          `Only ${MAX_IMAGES_PER_PRODUCT} photos are allowed per product, so ` +
            `${picked.length - toUpload.length} were skipped.`,
        );
      }
      if (failures.length > 0) setError(failures.join(" · "));
      images.reload();
    } finally {
      setBusy(false);
      setProgress(null);
      // Cleared so picking the same file again still fires a change event.
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleMove(image: ProductImage, direction: -1 | 1) {
    const order = list.map((i) => i.id);
    const from = order.indexOf(image.id);
    const to = from + direction;
    if (from < 0 || to < 0 || to >= order.length) return;
    order.splice(to, 0, ...order.splice(from, 1));

    setError(null);
    setBusy(true);
    try {
      await reorderProductImages(productId, order);
      images.reload();
    } catch (err) {
      setError(errorMessage(err, "Could not reorder the photos."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(image: ProductImage) {
    if (!confirm("Remove this photo? This can't be undone.")) return;
    setError(null);
    setBusy(true);
    try {
      await deleteProductImage(image.id);
      images.reload();
    } catch (err) {
      setError(errorMessage(err, "Could not remove the photo."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="page-subtitle">
        The first photo is the main one — it's what shows in a listing's search results. Photos are
        resized and have their camera data (including location) removed when they're added.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="maintenance-row">
        <button
          className="btn-secondary"
          onClick={() => fileInputRef.current?.click()}
          disabled={busy || atLimit}
        >
          {busy ? (progress ?? "Working...") : "Add Photos"}
        </button>
        {atLimit && (
          <span className="page-subtitle">
            {MAX_IMAGES_PER_PRODUCT} photos is the maximum — remove one to add another.
          </span>
        )}
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept={IMAGE_FILE_ACCEPT}
        multiple
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) handleFiles(e.target.files);
        }}
      />

      {images.loading && <Loading />}
      {images.error && <ErrorState message={images.error} />}
      {images.data && list.length === 0 && (
        <EmptyState label="No photos yet. A listing can't go live on Etsy without at least one." />
      )}

      {list.length > 0 && (
        <div className="image-grid">
          {list.map((image, index) => (
            <ImageCard
              key={image.id}
              image={image}
              index={index}
              total={list.length}
              busy={busy}
              onMove={handleMove}
              onDelete={handleDelete}
              onAltTextSaved={() => images.reload()}
              onError={setError}
            />
          ))}
        </div>
      )}
    </div>
  );
}
