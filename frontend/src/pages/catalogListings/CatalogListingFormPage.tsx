import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { CatalogListing, Product } from "../../lib/types";

export function CatalogListingFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const existing = useFetch(
    () => (isEdit ? api.get<CatalogListing>(`/catalog-listings/${id}`) : Promise.resolve(null)),
    [id]
  );

  const [productId, setProductId] = useState(searchParams.get("productId") ?? "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setProductId(existing.data.product_id);
      setTitle(existing.data.title);
      setDescription(existing.data.listing_description ?? "");
      setPrice(existing.data.price != null ? String(existing.data.price) : "");
    }
  }, [existing.data]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!productId || !title.trim()) {
      setError("Product and title are required.");
      return;
    }
    setSubmitting(true);
    const payload = {
      product_id: productId,
      title,
      listing_description: description || null,
      price: price ? Number(price) : null,
    };
    try {
      if (isEdit) {
        await api.patch(`/catalog-listings/${id}`, payload);
        navigate(`/catalog-listings/${id}`);
      } else {
        const created = await api.post<CatalogListing>("/catalog-listings", payload);
        navigate(`/catalog-listings/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save listing.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>{isEdit ? "Edit Catalog Listing" : "New Catalog Listing"}</h1>
      <form className="form-card" onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}
        <label className="required">
          Product
          <select value={productId} onChange={(e) => setProductId(e.target.value)} required disabled={isEdit}>
            <option value="">Select product...</option>
            {products.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="required">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label>
          Listing description (optional)
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          Price (optional)
          <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
        </label>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Saving..." : "Save Listing"}
        </button>
      </form>
    </div>
  );
}
