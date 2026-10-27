import { useEffect, useState } from "react";
import { ApiError, api } from "./apiClient";

/**
 * Turn a ProductImage's `url` into something an <img src> can use.
 *
 * Two cases, because the server returns whichever applies:
 *
 * - **An absolute URL** — a public bucket's CDN. Used as-is: no auth needed,
 *   no bytes through the API, and the browser caches it normally.
 * - **A path relative to the API root** — a private bucket, and local
 *   development always. An <img src> can't send an Authorization header, so
 *   the bytes are fetched here and handed over as an object URL.
 *
 * Object URLs are revoked on unmount and whenever the url changes, or every
 * viewed photo would be pinned in memory for the life of the tab.
 */
export function useImageSrc(url: string): { src: string | null; error: string | null } {
  const [src, setSrc] = useState<string | null>(() => (url.startsWith("http") ? url : null));
  // The message, not a boolean. A photo that won't load has several causes
  // that need different answers — most usefully, a file missing from the
  // storage backend entirely, which happens to anything uploaded before the
  // backend was switched and reads identically to a network problem.
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (url.startsWith("http")) {
      setSrc(url);
      setError(null);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null);
    setError(null);

    api
      .getBlob(url)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? `${err.status}: ${String(err.detail)}`
            : err instanceof Error
              ? err.message
              : "Could not load this image.",
        );
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  return { src, error };
}
