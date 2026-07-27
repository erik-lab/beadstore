import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit, Location, ProductCategory } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function InventoryOnHandPage() {
  const [categoryId, setCategoryId] = useState("");
  const [locationId, setLocationId] = useState("");

  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const locations = useFetch(() => api.get<Location[]>("/locations"), []);
  const units = useFetch(
    () =>
      api.get<InventoryUnit[]>(
        `/operations/inventory-on-hand?${new URLSearchParams({
          ...(categoryId ? { category_id: categoryId } : {}),
          ...(locationId ? { location_id: locationId } : {}),
        }).toString()}`
      ),
    [categoryId, locationId]
  );

  return (
    <div>
      <h1>Inventory On Hand</h1>
      <div className="filter-bar">
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">All categories</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
          <option value="">All locations</option>
          {locations.data?.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      </div>

      {units.loading && <Loading />}
      {units.error && <ErrorState message={units.error} />}
      {units.data && units.data.length === 0 && <EmptyState label="No inventory on hand for this filter." />}
      {units.data && units.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Quantity</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {units.data.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link to={`/inventory/${u.id}`}>
                    {u.product_id ? "Linked product" : u.unresolved_description ?? "Unresolved"}
                  </Link>
                </td>
                <td>
                  {u.quantity} {u.unit_type}
                </td>
                <td>
                  <StatusBadge status={u.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
