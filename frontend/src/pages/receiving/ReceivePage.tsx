import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, PurchaseOrder, ReceiveResult } from "../../lib/types";
import { UNIT_TYPES, describeItem } from "../../lib/types";
import { Loading, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

interface LineDraft {
  purchaseOrderLineId: string | null;
  productId: string;
  description: string;
  expectedQuantity: number | null;
  expectedUnitType: string | null;
  receivedQuantity: string;
  receivedUnitType: string;
  status: string; // "" = auto-detect
  notes: string;
}

export function ReceivePage() {
  const { id } = useParams();
  const po = useFetch(() => api.get<PurchaseOrder>(`/purchase-orders/${id}`), [id]);
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);

  const [lines, setLines] = useState<LineDraft[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReceiveResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const orderLines = po.data?.lines;

  useEffect(() => {
    if (orderLines) {
      setLines(
        orderLines
          .filter((l) => l.status !== "cancelled")
          .map((l) => ({
            purchaseOrderLineId: l.id,
            productId: l.product_id ?? "",
            description: l.expected_item_description ?? "",
            expectedQuantity: l.expected_quantity,
            expectedUnitType: l.expected_unit_type,
            receivedQuantity: l.expected_quantity != null ? String(l.expected_quantity) : "",
            receivedUnitType: l.expected_unit_type ?? "strand",
            status: "",
            notes: "",
          }))
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderLines]);

  if (po.loading || !products.data || lines === null) return <Loading />;
  if (po.error) return <ErrorState message={po.error} />;
  if (!po.data) return null;
  const order = po.data;

  function updateLine(index: number, patch: Partial<LineDraft>) {
    setLines((prev) => (prev ? prev.map((l, i) => (i === index ? { ...l, ...patch } : l)) : prev));
  }

  function addExtraLine() {
    setLines((prev) => [
      ...(prev ?? []),
      {
        purchaseOrderLineId: null,
        productId: "",
        description: "",
        expectedQuantity: null,
        expectedUnitType: null,
        receivedQuantity: "",
        receivedUnitType: "strand",
        status: "",
        notes: "",
      },
    ]);
  }

  async function handleSubmit() {
    setError(null);
    if (!lines) return;
    const payloadLines = lines
      .filter((l) => l.receivedQuantity !== "")
      .map((l) => ({
        purchase_order_line_id: l.purchaseOrderLineId,
        product_id: l.productId || null,
        unresolved_item_description: l.productId ? null : l.description || null,
        received_quantity: Number(l.receivedQuantity),
        received_unit_type: l.receivedUnitType,
        receiving_status: l.status || null,
        discrepancy_notes: l.notes || null,
      }));

    for (const line of payloadLines) {
      if (!line.product_id && !line.unresolved_item_description) {
        setError("Every received line needs either a linked product or a description.");
        return;
      }
    }
    if (payloadLines.length === 0) {
      setError("Enter at least one received quantity.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.post<ReceiveResult>(`/purchase-orders/${id}/receipts`, { lines: payloadLines });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not record receipt.");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    const isOpen = ["draft", "submitted", "partially_received"].includes(result.purchase_order_status);
    return (
      <div>
        <h1>Receipt Recorded</h1>
        <div className="alert alert-success">
          This supplier order is now{" "}
          <strong>
            {result.purchase_order_status === "partially_received"
              ? "Partially Received — still open"
              : result.purchase_order_status === "received"
                ? "fully Received"
                : result.purchase_order_status}
          </strong>
          {isOpen && result.purchase_order_status === "partially_received"
            ? ". More items are still expected on this order."
            : "."}
        </div>
        <h2>What Was Recorded</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Received Qty</th>
              <th>Reconciliation</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {result.receipt.lines.map((line) => (
              <tr key={line.id}>
                <td>{describeItem(line)}</td>
                <td>
                  {line.received_quantity} {line.received_unit_type}
                </td>
                <td>
                  <StatusBadge status={line.receiving_status} />
                </td>
                <td>{line.discrepancy_notes ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Link className="btn-primary" to={`/purchase-orders/${id}`}>
          Back to order
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Receive Items — Order {order.order_date}</h1>
      {error && <div className="alert alert-error">{error}</div>}
      <table className="data-table">
        <thead>
          <tr>
            <th>Item</th>
            <th>Expected</th>
            <th>Received Qty</th>
            <th>Unit</th>
            <th>Discrepancy Override</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {lines?.map((line, index) => (
            <tr key={index}>
              <td>
                {line.purchaseOrderLineId ? (
                  line.productId ? (
                    products.data?.find((p) => p.id === line.productId)?.name ?? "Linked product"
                  ) : (
                    line.description || "Free-text item"
                  )
                ) : (
                  <div className="line-row">
                    <select value={line.productId} onChange={(e) => updateLine(index, { productId: e.target.value })}>
                      <option value="">Unresolved / describe below</option>
                      {products.data?.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    {!line.productId && (
                      <input
                        placeholder="Describe item"
                        value={line.description}
                        onChange={(e) => updateLine(index, { description: e.target.value })}
                      />
                    )}
                  </div>
                )}
              </td>
              <td>
                {line.expectedQuantity ?? "—"} {line.expectedUnitType ?? ""}
              </td>
              <td>
                <input
                  type="number"
                  step="0.001"
                  value={line.receivedQuantity}
                  onChange={(e) => updateLine(index, { receivedQuantity: e.target.value })}
                />
              </td>
              <td>
                <select
                  value={line.receivedUnitType}
                  onChange={(e) => updateLine(index, { receivedUnitType: e.target.value })}
                >
                  {UNIT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <select value={line.status} onChange={(e) => updateLine(index, { status: e.target.value })}>
                  <option value="">Auto-detect</option>
                  <option value="matched">Matched</option>
                  <option value="shortage">Shortage</option>
                  <option value="overage">Overage</option>
                  <option value="substitution">Substitution</option>
                  <option value="damaged">Damaged</option>
                  <option value="unresolved">Unresolved</option>
                </select>
              </td>
              <td>
                <input
                  placeholder="Optional notes"
                  value={line.notes}
                  onChange={(e) => updateLine(index, { notes: e.target.value })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <button className="btn-secondary" onClick={addExtraLine}>
        + Add unexpected item received
      </button>

      <div className="form-actions">
        <button className="btn-primary" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Recording..." : "Record Receipt"}
        </button>
      </div>
    </div>
  );
}
