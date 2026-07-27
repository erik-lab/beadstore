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
      <dl className="detail-grid">
        <dt>Price</dt>
        <dd>{l.price != null ? `$${l.price}` : "—"}</dd>
        <dt>Description</dt>
        <dd>{l.listing_description ?? "—"}</dd>
        <dt>Product</dt>
        <dd>
          <Link to={`/products/${l.product_id}`}>View product</Link>
        </dd>
      </dl>
    </div>
  );
}
