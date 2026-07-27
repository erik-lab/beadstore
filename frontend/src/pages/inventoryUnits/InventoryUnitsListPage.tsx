import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit, Location } from "../../lib/types";
import { describeItem } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import { useSortableTable } from "../../lib/useSortableTable";

export function InventoryUnitsListPage() {
  const [search, setSearch] = useState("");
  const [locationId, setLocationId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const locations = useFetch(() => api.get<Location[]>("/locations"), []);
  const units = useFetch(
    () =>
      api.get<InventoryUnit[]>(
        `/inventory-units?${new URLSearchParams({
          ...(search ? { search } : {}),
          ...(locationId ? { location_id: locationId } : {}),
          ...(statusFilter ? { status: statusFilter } : {}),
        }).toString()}`
      ),
    [search, locationId, statusFilter]
  );

  const { sorted, toggleSort, indicator } = useSortableTable(units.data, [
    { key: "item", accessor: (u) => describeItem(u) },
    { key: "quantity", accessor: (u) => u.quantity },
    { key: "unit_type", accessor: (u) => u.unit_type },
    { key: "vendor_name", accessor: (u) => u.vendor_name },
    { key: "location_name", accessor: (u) => u.location_name },
    { key: "status", accessor: (u) => u.status },
    { key: "received_date", accessor: (u) => u.received_date },
  ]);

  return (
    <div>
      <div className="page-header">
        <h1>Inventory Units</h1>
        <Link className="btn-primary" to="/inventory/new">
          + New Inventory Unit
        </Link>
      </div>

      <div className="filter-bar">
        <input placeholder="Search inventory..." value={search} onChange={(e) => setSearch(e.target.value)} />
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
      {sorted && sorted.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => toggleSort("item")}>
                Item{indicator("item")}
              </th>
              <th className="sortable" onClick={() => toggleSort("quantity")}>
                Quantity{indicator("quantity")}
              </th>
              <th className="sortable" onClick={() => toggleSort("unit_type")}>
                Unit{indicator("unit_type")}
              </th>
              <th className="sortable" onClick={() => toggleSort("vendor_name")}>
                Vendor{indicator("vendor_name")}
              </th>
              <th className="sortable" onClick={() => toggleSort("location_name")}>
                Location{indicator("location_name")}
              </th>
              <th className="sortable" onClick={() => toggleSort("status")}>
                Status{indicator("status")}
              </th>
              <th className="sortable" onClick={() => toggleSort("received_date")}>
                Received{indicator("received_date")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link to={`/inventory/${u.id}`}>{describeItem(u)}</Link>
                </td>
                <td>{u.quantity}</td>
                <td>{u.unit_type}</td>
                <td>{u.vendor_name ?? "—"}</td>
                <td>{u.location_name ?? "—"}</td>
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
