import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { CatalogListing } from "../../lib/types";
import { Loading, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function CatalogListingDetailPage() {
  const { id } = useParams();
  const listing = useFetch(() => api.get<CatalogListing>(`/catalog-listings/${id}`), [id]);

  if (listing.loading) return <Loading />;
  if (listing.error) return <ErrorState message={listing.error} />;
  if (!listing.data) return null;
  const l = listing.data;

  return (
    <div>
      <div className="page-header">
        <h1>{l.title}</h1>
        <Link className="btn-secondary" to={`/catalog-listings/${l.id}/edit`}>
          Edit
        </Link>
      </div>
      <StatusBadge status={l.status} />
      {l.featured && <span className="badge tone-info">Featured</span>}
      {l.publish_readiness && <StatusBadge status={l.publish_readiness} />}

      <div className="detail-section">
        <h2>Listing</h2>
        <dl className="detail-grid">
          <dt>Short description</dt>
          <dd>{l.short_description ?? "—"}</dd>
          <dt>Full description</dt>
          <dd>{l.listing_description ?? "—"}</dd>
          <dt>Price</dt>
          <dd>{l.price != null ? `$${l.price}` : "—"}</dd>
          <dt>Sales unit</dt>
          <dd>{l.sales_unit ?? "—"}</dd>
          <dt>Quantity per listing</dt>
          <dd>{l.quantity_per_listing ?? "—"}</dd>
          <dt>Available quantity</dt>
          <dd>
            {l.available_quantity_mode === "manual" && (l.manual_available_quantity ?? "—")}
            {l.available_quantity_mode === "derived_from_inventory" && "Derived from inventory"}
            {l.available_quantity_mode === "not_tracked" && "Not tracked"}
          </dd>
          <dt>Category override</dt>
          <dd>{l.category_override_name ?? "—"}</dd>
          <dt>Subtype override</dt>
          <dd>{l.subtype_override ?? "—"}</dd>
          <dt>Tags</dt>
          <dd>{l.tags ?? "—"}</dd>
          <dt>Collection/theme</dt>
          <dd>{l.collection_theme ?? "—"}</dd>
          <dt>Sort order</dt>
          <dd>{l.sort_order}</dd>
          <dt>SEO title</dt>
          <dd>{l.seo_title ?? "—"}</dd>
          <dt>SEO description</dt>
          <dd>{l.seo_description ?? "—"}</dd>
          <dt>Listing notes</dt>
          <dd>{l.listing_notes ?? "—"}</dd>
        </dl>
      </div>

      <div className="detail-section">
        <h2>Underlying Product</h2>
        <p className="page-subtitle">
          The listing above is how this shows up in the catalog. The product record below is the underlying
          inventory item it's linked to — its name and description are separate from the listing's.
        </p>
        <dl className="detail-grid">
          <dt>Product name</dt>
          <dd>{l.product_name ?? "—"}</dd>
          <dt>Product description</dt>
          <dd>{l.product_description ?? "—"}</dd>
          <dt>Product SKU</dt>
          <dd>{l.product_sku ?? "—"}</dd>
          <dt>Product record</dt>
          <dd>
            <Link to={`/products/${l.product_id}`}>View product</Link>
          </dd>
        </dl>
      </div>
    </div>
  );
}
