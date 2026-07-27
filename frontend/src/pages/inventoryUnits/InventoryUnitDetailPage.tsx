import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit } from "../../lib/types";
import { describeItem } from "../../lib/types";
import { Loading, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function InventoryUnitDetailPage() {
  const { id } = useParams();
  const unit = useFetch(() => api.get<InventoryUnit>(`/inventory-units/${id}`), [id]);

  if (unit.loading) return <Loading />;
  if (unit.error) return <ErrorState message={unit.error} />;
  if (!unit.data) return null;
  const u = unit.data;

  return (
    <div>
      <div className="page-header">
        <h1>Inventory Unit</h1>
        <Link className="btn-secondary" to={`/inventory/${u.id}/edit`}>
          Edit
        </Link>
      </div>
      <StatusBadge status={u.status} />
      {u.status === "unresolved" && (
        <div className="alert alert-warn">This item still needs to be matched to a product.</div>
      )}
      <dl className="detail-grid">
        <dt>Item</dt>
        <dd>
          {u.product_id ? <Link to={`/products/${u.product_id}`}>{describeItem(u)}</Link> : describeItem(u)}
        </dd>
        <dt>Quantity</dt>
        <dd>
          {u.quantity} {u.unit_type}
        </dd>
        <dt>Vendor</dt>
        <dd>{u.vendor_id ? <Link to={`/vendors/${u.vendor_id}`}>{u.vendor_name ?? "View vendor"}</Link> : "—"}</dd>
        <dt>Location</dt>
        <dd>{u.location_name ?? "—"}</dd>
        <dt>Supplier Order</dt>
        <dd>
          {u.purchase_order_id ? (
            <Link to={`/purchase-orders/${u.purchase_order_id}`}>View supplier order</Link>
          ) : (
            "—"
          )}
        </dd>
        <dt>Received Date</dt>
        <dd>{u.received_date}</dd>
        <dt>Receipt Recorded</dt>
        <dd>{u.receipt_received_date ?? "—"}</dd>
        <dt>Cost</dt>
        <dd>{u.cost_amount != null ? `$${u.cost_amount}` : "—"}</dd>
        <dt>Notes</dt>
        <dd>{u.notes ?? "—"}</dd>
      </dl>
    </div>
  );
}
