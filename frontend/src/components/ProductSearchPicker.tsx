import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { Product } from "../lib/types";

/**
 * Search the catalog and tie an import row to a product that already exists.
 *
 * A dropdown of every product is the wrong shape here — the list only grows,
 * and the reviewer usually arrives knowing roughly what they're looking for
 * because the import flagged the name as new or ambiguous. So: type a few
 * letters, pick from the matches.
 *
 * Searching server-side rather than filtering a preloaded list means it keeps
 * working when the catalog outgrows one page of results.
 */
export function ProductSearchPicker({
  initialQuery,
  onPick,
  onCancel,
}: {
  /** Seeded with the row's current name, which is usually close. */
  initialQuery: string;
  onPick: (product: Product) => void;
  onCancel: () => void;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<Product[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setSearching(true);
      setError(null);
      try {
        const found = await api.get<Product[]>(
          `/products?search=${encodeURIComponent(trimmed)}&status=active&limit=20`,
        );
        if (!cancelled) setResults(found);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? String(err.detail) : "Could not search products.");
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  return (
    <div className="form-card" style={{ marginTop: 8 }}>
      <label>
        Find an existing product
        <input
          autoFocus
          value={query}
          placeholder="Type part of a product name..."
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>

      {error && <div className="alert alert-error">{error}</div>}
      {searching && <p className="page-subtitle">Searching...</p>}

      {query.trim().length < 2 && (
        <p className="page-subtitle">Type at least two letters to search.</p>
      )}

      {results && results.length === 0 && !searching && (
        <p className="page-subtitle">
          No active product matches that. Close this and leave the name as it is to create a new
          product.
        </p>
      )}

      {results && results.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Category</th>
              <th>SKU</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {results.map((product) => (
              <tr key={product.id}>
                <td>{product.name}</td>
                <td>{product.category_name ?? "—"}</td>
                <td>{product.sku ?? "—"}</td>
                <td>
                  <button type="button" className="btn-secondary" onClick={() => onPick(product)}>
                    Use this
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="maintenance-row">
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Close
        </button>
      </div>
    </div>
  );
}
