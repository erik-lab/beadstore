import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, PurchaseOrder, Receipt, Vendor } from "../../lib/types";
import { UNIT_TYPES } from "../../lib/types";
import { Loading, ErrorState, EmptyState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function PurchaseOrderDetailPage() {
  const { id } = useParams();
  const po = useFetch(() => api.get<PurchaseOrder>(`/purchase-orders/${id}`), [id]);
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors?limit=200"), []);
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const receipts = useFetch(() => api.get<Receipt[]>(`/purchase-orders/${id}/receipts`), [id]);

  const [productId, setProductId] = useState("");
  const [description, setDescription] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitType, setUnitType] = useState("strand");
  const [addingLine, setAddingLine] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (po.loading) return <Loading />;
  if (po.error) return <ErrorState message={po.error} />;
  if (!po.data) return null;
  const order = po.data;
  const vendorName = vendors.data?.find((v) => v.id === order.vendor_id)?.name ?? "—";
  const canEditLines = order.status === "draft" || order.status === "submitted";
  const canReceive = !["cancelled", "closed"].includes(order.status);

  async function addLine(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!productId && !description.trim()) {
      setError("Enter a product or a description for the line.");
      return;
    }
    try {
      await api.post(`/purchase-orders/${id}/lines`, {
        product_id: productId || null,
        expected_item_description: productId ? null : description,
        expected_quantity: quantity ? Number(quantity) : null,
        expected_unit_type: quantity ? unitType : null,
      });
      setProductId("");
      setDescription("");
      setQuantity("");
      setAddingLine(false);
      po.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not add line.");
    }
  }

  async function markOrdered() {
    setActionError(null);
    try {
      await api.post(`/purchase-orders/${id}/mark-ordered`);
      po.reload();
    } catch (err) {
      setActionError(err instanceof ApiError ? String(err.detail) : "Could not update order.");
    }
  }

  async function cancelOrder() {
    setActionError(null);
    try {
      await api.post(`/purchase-orders/${id}/cancel`);
      po.reload();
    } catch (err) {
      setActionError(err instanceof ApiError ? String(err.detail) : "Could not cancel order.");
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Supplier Order — {order.order_date}</h1>
        <div className="page-actions">
          {order.status === "draft" && (
            <button className="btn-secondary" onClick={markOrdered}>
              Mark as Ordered
            </button>
          )}
          {canReceive && (
            <Link className="btn-primary" to={`/purchase-orders/${order.id}/receive`}>
              Receive Items
            </Link>
          )}
          {!["cancelled", "received", "closed"].includes(order.status) && (
            <button className="btn-secondary" onClick={cancelOrder}>
              Cancel Order
            </button>
          )}
        </div>
      </div>
      <StatusBadge status={order.status} />
      {order.is_retroactive && <span className="badge tone-info">Created during receiving</span>}
      {actionError && <div className="alert alert-error">{actionError}</div>}

      <dl className="detail-grid">
        <dt>Vendor</dt>
        <dd>
          <Link to={`/vendors/${order.vendor_id}`}>{vendorName}</Link>
        </dd>
        <dt>Notes</dt>
        <dd>{order.notes ?? "—"}</dd>
      </dl>

      <section className="detail-section">
        <h2>Expected Order Lines</h2>
        {order.lines && order.lines.length === 0 && <EmptyState label="No lines added yet." />}
        {order.lines && order.lines.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Expected Qty</th>
                <th>Unit</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {order.lines.map((line) => (
                <tr key={line.id}>
                  <td>
                    {line.product_id ? (
                      <Link to={`/products/${line.product_id}`}>View product</Link>
                    ) : (
                      line.expected_item_description ?? "—"
                    )}
                  </td>
                  <td>{line.expected_quantity ?? "—"}</td>
                  <td>{line.expected_unit_type ?? "—"}</td>
                  <td>
                    <StatusBadge status={line.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {canEditLines && (
          <div className="inline-form">
            {!addingLine ? (
              <button className="btn-secondary" onClick={() => setAddingLine(true)}>
                + Add Line
              </button>
            ) : (
              <form className="line-row" onSubmit={addLine}>
                {error && <div className="alert alert-error">{error}</div>}
                <select value={productId} onChange={(e) => setProductId(e.target.value)}>
                  <option value="">Free-text item</option>
                  {products.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                {!productId && (
                  <input
                    placeholder="Describe expected item"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                )}
                <input
                  type="number"
                  step="0.001"
                  placeholder="Expected qty"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                />
                <select value={unitType} onChange={(e) => setUnitType(e.target.value)}>
                  {UNIT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <button type="submit" className="btn-primary">
                  Add
                </button>
              </form>
            )}
          </div>
        )}
      </section>

      <section className="detail-section">
        <h2>Receipts</h2>
        {receipts.data && receipts.data.length === 0 && <EmptyState label="No receipts recorded yet." />}
        {receipts.data && receipts.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Received Date</th>
                <th>Lines</th>
              </tr>
            </thead>
            <tbody>
              {receipts.data.map((r) => (
                <tr key={r.id}>
                  <td>{r.received_date}</td>
                  <td>{r.lines.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
