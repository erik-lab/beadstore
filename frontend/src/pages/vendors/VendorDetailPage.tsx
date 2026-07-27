import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { PurchaseOrder, Vendor } from "../../lib/types";
import { Loading, ErrorState, EmptyState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function VendorDetailPage() {
  const { id } = useParams();
  const vendor = useFetch(() => api.get<Vendor>(`/vendors/${id}`), [id]);
  const orders = useFetch(() => api.get<PurchaseOrder[]>(`/purchase-orders?vendor_id=${id}`), [id]);

  if (vendor.loading) return <Loading />;
  if (vendor.error) return <ErrorState message={vendor.error} />;
  if (!vendor.data) return null;
  const v = vendor.data;

  return (
    <div>
      <div className="page-header">
        <h1>{v.name}</h1>
        <Link className="btn-secondary" to={`/vendors/${v.id}/edit`}>
          Edit
        </Link>
      </div>
      <StatusBadge status={v.status} />
      <dl className="detail-grid">
        <dt>Contact</dt>
        <dd>{v.contact_name ?? "—"}</dd>
        <dt>Email</dt>
        <dd>{v.email ?? "—"}</dd>
        <dt>Phone</dt>
        <dd>{v.phone ?? "—"}</dd>
        <dt>Notes</dt>
        <dd>{v.notes ?? "—"}</dd>
      </dl>

      <section className="detail-section">
        <h2>Supplier Orders</h2>
        {orders.data && orders.data.length === 0 && <EmptyState label="No orders for this vendor yet." />}
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
      </section>
    </div>
  );
}
