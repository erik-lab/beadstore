import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit } from "../../lib/types";
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
          {u.product_id ? (
            <Link to={`/products/${u.product_id}`}>View product</Link>
          ) : (
            u.unresolved_description ?? "—"
          )}
        </dd>
        <dt>Quantity</dt>
        <dd>
          {u.quantity} {u.unit_type}
        </dd>
        <dt>Received Date</dt>
        <dd>{u.received_date}</dd>
        <dt>Cost</dt>
        <dd>{u.cost_amount != null ? `$${u.cost_amount}` : "—"}</dd>
        <dt>Notes</dt>
        <dd>{u.notes ?? "—"}</dd>
      </dl>
    </div>
  );
}
