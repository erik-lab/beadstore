import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { CatalogListing, InventoryUnit, Product } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function ProductDetailPage() {
  const { id } = useParams();
  const product = useFetch(() => api.get<Product>(`/products/${id}`), [id]);
  const inventoryUnits = useFetch(() => api.get<InventoryUnit[]>(`/products/${id}/inventory-units`), [id]);
  const catalogListings = useFetch(() => api.get<CatalogListing[]>(`/products/${id}/catalog-listings`), [id]);

  if (product.loading) return <Loading />;
  if (product.error) return <ErrorState message={product.error} />;
  if (!product.data) return <EmptyState label="Product not found." />;

  const p = product.data;

  return (
    <div>
      <div className="page-header">
        <h1>{p.name}</h1>
        <div className="page-actions">
          <Link className="btn-secondary" to={`/products/${p.id}/edit`}>
            Edit
          </Link>
          <Link className="btn-primary" to={`/catalog-listings/new?productId=${p.id}`}>
            + Catalog Listing
          </Link>
        </div>
      </div>
      <StatusBadge status={p.status} />

      <section className="detail-section">
        <h2>Product Details</h2>
        <dl className="detail-grid">
          <dt>SKU</dt>
          <dd>{p.sku ?? "—"}</dd>
          <dt>Description</dt>
          <dd>{p.description ?? "—"}</dd>
          <dt>Material</dt>
          <dd>{p.material ?? "—"}</dd>
          <dt>Color</dt>
          <dd>{p.color ?? "—"}</dd>
          <dt>Size</dt>
          <dd>{p.size ?? "—"}</dd>
          <dt>Shape</dt>
          <dd>{p.shape ?? "—"}</dd>
          <dt>Finish</dt>
          <dd>{p.finish ?? "—"}</dd>
          <dt>Hole Size</dt>
          <dd>{p.hole_size ?? "—"}</dd>
          <dt>Origin</dt>
          <dd>{p.origin ?? "—"}</dd>
          <dt>Strand Length</dt>
          <dd>{p.strand_length ?? "—"}</dd>
          <dt>Count</dt>
          <dd>{p.count ?? "—"}</dd>
          <dt>Grade</dt>
          <dd>{p.grade ?? "—"}</dd>
          <dt>Condition</dt>
          <dd>{p.condition ?? "—"}</dd>
        </dl>
      </section>

      <section className="detail-section">
        <h2>Inventory Units (stock on hand)</h2>
        {inventoryUnits.loading && <Loading />}
        {inventoryUnits.data && inventoryUnits.data.length === 0 && (
          <EmptyState label="No inventory units recorded for this product yet." />
        )}
        {inventoryUnits.data && inventoryUnits.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Quantity</th>
                <th>Unit</th>
                <th>Status</th>
                <th>Received</th>
              </tr>
            </thead>
            <tbody>
              {inventoryUnits.data.map((u) => (
                <tr key={u.id}>
                  <td>
                    <Link to={`/inventory/${u.id}`}>{u.quantity}</Link>
                  </td>
                  <td>{u.unit_type}</td>
                  <td>
                    <StatusBadge status={u.status} />
                  </td>
                  <td>{u.received_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="detail-section">
        <h2>Catalog Listings</h2>
        {catalogListings.loading && <Loading />}
        {catalogListings.data && catalogListings.data.length === 0 && (
          <EmptyState label="No catalog listings yet for this product." />
        )}
        {catalogListings.data && catalogListings.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Price</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {catalogListings.data.map((l) => (
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
      </section>
    </div>
  );
}
