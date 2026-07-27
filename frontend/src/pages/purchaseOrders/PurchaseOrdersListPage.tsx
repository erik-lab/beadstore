import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { PurchaseOrder } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function PurchaseOrdersListPage() {
  const [openOnly, setOpenOnly] = useState(false);
  const orders = useFetch(
    () => api.get<PurchaseOrder[]>(`/purchase-orders${openOnly ? "?open_only=true" : ""}`),
    [openOnly]
  );

  return (
    <div>
      <div className="page-header">
        <h1>Supplier Orders</h1>
        <div className="page-actions">
          <Link className="btn-secondary" to="/receiving/quick-receive">
            Receive without prior order
          </Link>
          <Link className="btn-primary" to="/purchase-orders/new">
            + New Supplier Order
          </Link>
        </div>
      </div>

      <div className="filter-bar">
        <label className="checkbox-label">
          <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} />
          Open orders only
        </label>
      </div>

      {orders.loading && <Loading />}
      {orders.error && <ErrorState message={orders.error} />}
      {orders.data && orders.data.length === 0 && <EmptyState label="No supplier orders yet." />}
      {orders.data && orders.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Order Date</th>
              <th>Vendor</th>
              <th>Status</th>
              <th>Retroactive</th>
            </tr>
          </thead>
          <tbody>
            {orders.data.map((po) => (
              <tr key={po.id}>
                <td>
                  <Link to={`/purchase-orders/${po.id}`}>{po.order_date}</Link>
                </td>
                <td>{po.vendor_name ?? "—"}</td>
                <td>
                  <StatusBadge status={po.status} />
                </td>
                <td>{po.is_retroactive ? "Yes" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
