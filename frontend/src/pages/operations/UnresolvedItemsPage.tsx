import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit, Product } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";

export function UnresolvedItemsPage() {
  const units = useFetch(() => api.get<InventoryUnit[]>("/operations/unresolved-items"), []);
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const [resolving, setResolving] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  async function resolveUnit(unit: InventoryUnit) {
    const productId = selectedProduct[unit.id];
    if (!productId) {
      setError("Choose a product to match this item to.");
      return;
    }
    setResolving(unit.id);
    setError(null);
    try {
      if (unit.receipt_line_id) {
        // Resolves the receipt line and its linked inventory unit together, so the
        // receiving history and current stock stay consistent with each other.
        await api.patch(`/receipt-lines/${unit.receipt_line_id}/resolve?product_id=${productId}`);
      } else {
        // Manually-entered inventory unit with no receipt behind it — nothing else to sync.
        await api.patch(`/inventory-units/${unit.id}`, { product_id: productId, status: "available" });
      }
      units.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not resolve item.");
    } finally {
      setResolving(null);
    }
  }

  return (
    <div>
      <h1>Items Needing Product Match</h1>
      <p className="page-subtitle">
        These stock records were received without a matching product. Match each one to an
        existing product, or add the product first if it doesn't exist yet.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {units.loading && <Loading />}
      {units.error && <ErrorState message={units.error} />}
      {units.data && units.data.length === 0 && <EmptyState label="Nothing needs product matching right now." />}
      {units.data && units.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Description</th>
              <th>Quantity</th>
              <th>Vendor</th>
              <th>Received</th>
              <th>Supplier Order</th>
              <th>Match to Product</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {units.data.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link to={`/inventory/${u.id}`}>{u.unresolved_description ?? "Unresolved item"}</Link>
                </td>
                <td>
                  {u.quantity} {u.unit_type}
                </td>
                <td>{u.vendor_name ?? "—"}</td>
                <td>
                  {u.received_date}
                  {u.receipt_received_date ? ` (receipt: ${u.receipt_received_date})` : ""}
                </td>
                <td>
                  {u.purchase_order_id ? (
                    <Link to={`/purchase-orders/${u.purchase_order_id}`}>View order</Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  <select
                    value={selectedProduct[u.id] ?? ""}
                    onChange={(e) => setSelectedProduct({ ...selectedProduct, [u.id]: e.target.value })}
                  >
                    <option value="">Select product...</option>
                    {products.data?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button className="btn-secondary" onClick={() => resolveUnit(u)} disabled={resolving === u.id}>
                    {resolving === u.id ? "Matching..." : "Match"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
