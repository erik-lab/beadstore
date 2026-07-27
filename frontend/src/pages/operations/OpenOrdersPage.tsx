import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { PurchaseOrder } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function OpenOrdersPage() {
  const orders = useFetch(() => api.get<PurchaseOrder[]>("/operations/open-orders"), []);

  return (
    <div>
      <h1>Open Supplier Orders</h1>
      {orders.loading && <Loading />}
      {orders.error && <ErrorState message={orders.error} />}
      {orders.data && orders.data.length === 0 && <EmptyState label="No open supplier orders." />}
      {orders.data && orders.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Order Date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.data.map((po) => (
              <tr key={po.id}>
                <td>
                  <Link to={`/purchase-orders/${po.id}`}>{po.order_date}</Link>
                </td>
                <td>
                  <StatusBadge status={po.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
