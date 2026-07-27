import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { CatalogListing } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import { useSortableTable } from "../../lib/useSortableTable";

export function CatalogListingsListPage() {
  const [search, setSearch] = useState("");

  const listings = useFetch(
    () =>
      api.get<CatalogListing[]>(
        `/catalog-listings?${new URLSearchParams({ ...(search ? { search } : {}) }).toString()}`
      ),
    [search]
  );

  const { sorted, toggleSort, indicator } = useSortableTable(listings.data, [
    { key: "title", accessor: (l) => l.title },
    { key: "product_name", accessor: (l) => l.product_name },
    { key: "price", accessor: (l) => l.price },
    { key: "status", accessor: (l) => l.status },
  ]);

  return (
    <div>
      <div className="page-header">
        <h1>Catalog Listings</h1>
        <Link className="btn-primary" to="/catalog-listings/new">
          + New Listing
        </Link>
      </div>

      <div className="filter-bar">
        <input placeholder="Search listings..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {listings.loading && <Loading />}
      {listings.error && <ErrorState message={listings.error} />}
      {listings.data && listings.data.length === 0 && <EmptyState label="No catalog listings yet." />}
      {sorted && sorted.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => toggleSort("title")}>
                Listing Title{indicator("title")}
              </th>
              <th className="sortable" onClick={() => toggleSort("product_name")}>
                Product{indicator("product_name")}
              </th>
              <th className="sortable" onClick={() => toggleSort("price")}>
                Price{indicator("price")}
              </th>
              <th className="sortable" onClick={() => toggleSort("status")}>
                Status{indicator("status")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((l) => (
              <tr key={l.id}>
                <td>
                  <Link to={`/catalog-listings/${l.id}`}>{l.title}</Link>
                </td>
                <td>{l.product_name ?? "—"}</td>
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
