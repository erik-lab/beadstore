import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { CatalogListing, Product, ProductCategory } from "../../lib/types";

const UNIT_TYPES = [
  "strand",
  "container",
  "bag",
  "tube",
  "count",
  "gram",
  "ounce",
  "piece",
  "pair",
  "set",
  "unknown",
  "other",
];

export function CatalogListingFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const cancelTo = isEdit ? `/catalog-listings/${id}` : "/catalog-listings";

  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const existing = useFetch(
    () => (isEdit ? api.get<CatalogListing>(`/catalog-listings/${id}`) : Promise.resolve(null)),
    [id]
  );

  const [productId, setProductId] = useState(searchParams.get("productId") ?? "");
  const [title, setTitle] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState("draft");
  const [salesUnit, setSalesUnit] = useState("");
  const [quantityPerListing, setQuantityPerListing] = useState("");
  const [availableQuantityMode, setAvailableQuantityMode] = useState("not_tracked");
  const [manualAvailableQuantity, setManualAvailableQuantity] = useState("");
  const [categoryOverrideId, setCategoryOverrideId] = useState("");
  const [subtypeOverride, setSubtypeOverride] = useState("");
  const [tags, setTags] = useState("");
  const [collectionTheme, setCollectionTheme] = useState("");
  const [featured, setFeatured] = useState(false);
  const [sortOrder, setSortOrder] = useState("0");
  const [seoTitle, setSeoTitle] = useState("");
  const [seoDescription, setSeoDescription] = useState("");
  const [listingNotes, setListingNotes] = useState("");
  const [publishReadiness, setPublishReadiness] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      const l = existing.data;
      setProductId(l.product_id);
      setTitle(l.title);
      setShortDescription(l.short_description ?? "");
      setDescription(l.listing_description ?? "");
      setPrice(l.price != null ? String(l.price) : "");
      setStatus(l.status === "archived" ? "draft" : l.status);
      setSalesUnit(l.sales_unit ?? "");
      setQuantityPerListing(l.quantity_per_listing != null ? String(l.quantity_per_listing) : "");
      setAvailableQuantityMode(l.available_quantity_mode);
      setManualAvailableQuantity(l.manual_available_quantity != null ? String(l.manual_available_quantity) : "");
      setCategoryOverrideId(l.category_override_id ?? "");
      setSubtypeOverride(l.subtype_override ?? "");
      setTags(l.tags ?? "");
      setCollectionTheme(l.collection_theme ?? "");
      setFeatured(l.featured);
      setSortOrder(String(l.sort_order));
      setSeoTitle(l.seo_title ?? "");
      setSeoDescription(l.seo_description ?? "");
      setListingNotes(l.listing_notes ?? "");
      setPublishReadiness(l.publish_readiness ?? "");
    }
  }, [existing.data]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!productId || !title.trim()) {
      setError("Product and listing title are required.");
      return;
    }
    setSubmitting(true);
    const payload = {
      product_id: productId,
      title,
      short_description: shortDescription || null,
      listing_description: description || null,
      price: price ? Number(price) : null,
      status,
      sales_unit: salesUnit || null,
      quantity_per_listing: quantityPerListing ? Number(quantityPerListing) : null,
      available_quantity_mode: availableQuantityMode,
      manual_available_quantity: manualAvailableQuantity ? Number(manualAvailableQuantity) : null,
      category_override_id: categoryOverrideId || null,
      subtype_override: subtypeOverride || null,
      tags: tags || null,
      collection_theme: collectionTheme || null,
      featured,
      sort_order: sortOrder ? Number(sortOrder) : 0,
      seo_title: seoTitle || null,
      seo_description: seoDescription || null,
      listing_notes: listingNotes || null,
      publish_readiness: publishReadiness || null,
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
          Listing title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>

        <label>
          Short description (optional)
          <input value={shortDescription} onChange={(e) => setShortDescription(e.target.value)} />
        </label>

        <label>
          Full description (optional)
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>

        <label>
          Price (optional)
          <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
        </label>

        <label>
          Listing status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="draft">Draft</option>
            <option value="ready">Ready</option>
            <option value="published">Published</option>
            <option value="retired">Retired</option>
          </select>
        </label>

        <label>
          Sales unit (optional)
          <select value={salesUnit} onChange={(e) => setSalesUnit(e.target.value)}>
            <option value="">Not set</option>
            {UNIT_TYPES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>

        <label>
          Quantity per listing (optional)
          <input
            type="number"
            step="0.001"
            value={quantityPerListing}
            onChange={(e) => setQuantityPerListing(e.target.value)}
          />
        </label>

        <label>
          Available quantity behavior
          <select value={availableQuantityMode} onChange={(e) => setAvailableQuantityMode(e.target.value)}>
            <option value="not_tracked">Not tracked</option>
            <option value="manual">Manual</option>
            <option value="derived_from_inventory">Derive from inventory</option>
          </select>
        </label>

        {availableQuantityMode === "manual" && (
          <label>
            Manual available quantity
            <input
              type="number"
              step="0.001"
              value={manualAvailableQuantity}
              onChange={(e) => setManualAvailableQuantity(e.target.value)}
            />
          </label>
        )}

        <label>
          Category/subcategory override (optional)
          <select value={categoryOverrideId} onChange={(e) => setCategoryOverrideId(e.target.value)}>
            <option value="">Use product's category</option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Subtype override (optional)
          <input value={subtypeOverride} onChange={(e) => setSubtypeOverride(e.target.value)} />
        </label>

        <label>
          Tags (optional, comma-separated)
          <input value={tags} onChange={(e) => setTags(e.target.value)} />
        </label>

        <label>
          Collection/theme (optional)
          <input value={collectionTheme} onChange={(e) => setCollectionTheme(e.target.value)} />
        </label>

        <label className="checkbox-label">
          <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} />
          Featured
        </label>

        <label>
          Sort order
          <input type="number" step="1" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
        </label>

        <label>
          SEO title (optional)
          <input value={seoTitle} onChange={(e) => setSeoTitle(e.target.value)} />
        </label>

        <label>
          SEO description (optional)
          <input value={seoDescription} onChange={(e) => setSeoDescription(e.target.value)} />
        </label>

        <label>
          Listing notes (optional)
          <textarea value={listingNotes} onChange={(e) => setListingNotes(e.target.value)} />
        </label>

        <label>
          Publish readiness (optional)
          <select value={publishReadiness} onChange={(e) => setPublishReadiness(e.target.value)}>
            <option value="">Not set</option>
            <option value="missing_photos">Missing photos</option>
            <option value="needs_pricing">Needs pricing</option>
            <option value="needs_description">Needs description</option>
            <option value="ready">Ready</option>
          </select>
        </label>

        <div className="form-actions line-row">
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "Saving..." : "Save Listing"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate(cancelTo)}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
