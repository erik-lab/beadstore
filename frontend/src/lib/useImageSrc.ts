import { useEffect, useState } from "react";
import { api } from "./apiClient";

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
export function useImageSrc(url: string): { src: string | null; error: boolean } {
  const [src, setSrc] = useState<string | null>(() => (url.startsWith("http") ? url : null));
  const [error, setError] = useState(false);

  useEffect(() => {
    if (url.startsWith("http")) {
      setSrc(url);
      setError(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null);
    setError(false);

    api
      .getBlob(url)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  return { src, error };
}
