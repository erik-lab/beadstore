import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { CatalogListing } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function CatalogListingsListPage() {
  const listings = useFetch(() => api.get<CatalogListing[]>("/catalog-listings"), []);

  return (
    <div>
      <div className="page-header">
        <h1>Catalog Listings</h1>
        <Link className="btn-primary" to="/catalog-listings/new">
          + New Listing
        </Link>
      </div>

      {listings.loading && <Loading />}
      {listings.error && <ErrorState message={listings.error} />}
      {listings.data && listings.data.length === 0 && <EmptyState label="No catalog listings yet." />}
      {listings.data && listings.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Price</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {listings.data.map((l) => (
              <tr key={l.id}>
                <td>
                  <Link to={`/catalog-listings/${l.id}`}>{l.title}</Link>
                </td>
                <td>{l.price != null ? `$${l.price}` : "—"}</td>
                <td>
                  <StatusBadge status={l.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
