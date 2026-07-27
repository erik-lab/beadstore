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

  async function resolveUnit(unitId: string) {
    const productId = selectedProduct[unitId];
    if (!productId) {
      setError("Choose a product to match this item to.");
      return;
    }
    setResolving(unitId);
    setError(null);
    try {
      await api.patch(`/inventory-units/${unitId}`, { product_id: productId, status: "available" });
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
      <p className="page-subtitle">These inventory units were received without a matching product.</p>
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
                  <button className="btn-secondary" onClick={() => resolveUnit(u.id)} disabled={resolving === u.id}>
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
