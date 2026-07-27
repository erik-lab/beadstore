import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit, Location } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function InventoryUnitsListPage() {
  const [locationId, setLocationId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const locations = useFetch(() => api.get<Location[]>("/locations"), []);
  const units = useFetch(
    () =>
      api.get<InventoryUnit[]>(
        `/inventory-units?${new URLSearchParams({
          ...(locationId ? { location_id: locationId } : {}),
          ...(statusFilter ? { status: statusFilter } : {}),
        }).toString()}`
      ),
    [locationId, statusFilter]
  );

  return (
    <div>
      <div className="page-header">
        <h1>Inventory Units</h1>
        <Link className="btn-primary" to="/inventory/new">
          + New Inventory Unit
        </Link>
      </div>

      <div className="filter-bar">
        <select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
          <option value="">All locations</option>
          {locations.data?.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.name}
            </option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="available">Available</option>
          <option value="reserved">Reserved</option>
          <option value="depleted">Depleted</option>
          <option value="damaged">Damaged</option>
          <option value="unresolved">Unresolved (needs product match)</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {units.loading && <Loading />}
      {units.error && <ErrorState message={units.error} />}
      {units.data && units.data.length === 0 && <EmptyState label="No inventory units found." />}
      {units.data && units.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Quantity</th>
              <th>Unit</th>
              <th>Status</th>
              <th>Received</th>
            </tr>
          </thead>
          <tbody>
            {units.data.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link to={`/inventory/${u.id}`}>
                    {u.product_id ? "Linked product" : u.unresolved_description ?? "Unresolved item"}
                  </Link>
                </td>
                <td>{u.quantity}</td>
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
    </div>
  );
}
