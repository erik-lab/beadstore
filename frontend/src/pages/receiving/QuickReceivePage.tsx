import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, ReceiveResult, Vendor } from "../../lib/types";
import { UNIT_TYPES, describeItem } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";

interface LineDraft {
  productId: string;
  description: string;
  quantity: string;
  unitType: string;
  unitCost: string;
}

function emptyLine(): LineDraft {
  return { productId: "", description: "", quantity: "", unitType: "strand", unitCost: "" };
}

export function QuickReceivePage() {
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors?limit=200"), []);
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);

  const [vendorId, setVendorId] = useState("");
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ReceiveResult | null>(null);

  const unknownVendor = vendors.data?.find((v) => v.name === "Unknown Vendor");

  function updateLine(index: number, patch: Partial<LineDraft>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, emptyLine()]);
  }

  function removeLine(index: number) {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit() {
    setError(null);
    const vendor = vendorId || unknownVendor?.id;
    if (!vendor) {
      setError("Choose a vendor, or wait for 'Unknown Vendor' to load and select it.");
      return;
    }
    const validLines = lines.filter((l) => l.productId || l.description.trim());
    if (validLines.length === 0) {
      setError("Enter at least one received item.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post<ReceiveResult>("/receiving/quick-receive", {
        vendor_id: vendor,
        received_date: receivedDate,
        notes: notes || null,
        lines: validLines.map((l) => ({
          product_id: l.productId || null,
          unresolved_item_description: l.productId ? null : l.description,
          received_quantity: Number(l.quantity),
          received_unit_type: l.unitType,
          unit_cost: l.unitCost ? Number(l.unitCost) : null,
        })),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not record receipt.");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div>
        <h1>Received Without Prior Order — Saved</h1>
        <div className="alert alert-success">
          A supplier order and receipt were created automatically and marked as created during
          receiving, so this stays traceable just like a normal order.
        </div>
        <h2>What Was Recorded</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Received Qty</th>
              <th>Status</th>
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
              </tr>
            ))}
          </tbody>
        </table>
        <Link className="btn-primary" to={`/purchase-orders/${result.purchase_order_id}`}>
          View created supplier order
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Receive Without Prior Order</h1>
      <p className="page-subtitle">
        Use this when items showed up without a supplier order already entered. A retroactive supplier order and
        receipt will be created automatically.
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="form-card">
        <label>
          Vendor / source
          <select value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
            <option value="">
              {unknownVendor ? "Unknown Vendor (default)" : "Loading vendors..."}
            </option>
            {vendors.data
              ?.filter((v) => v.name !== "Unknown Vendor")
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
          </select>
        </label>

        <label>
          Received Date
          <input type="date" value={receivedDate} onChange={(e) => setReceivedDate(e.target.value)} />
        </label>

        <fieldset>
          <legend>Received Items</legend>
          {lines.map((line, index) => (
            <div key={index} className="line-row">
              <select value={line.productId} onChange={(e) => updateLine(index, { productId: e.target.value })}>
                <option value="">Not yet known / unresolved</option>
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
              <input
                type="number"
                step="0.001"
                placeholder="Quantity"
                value={line.quantity}
                onChange={(e) => updateLine(index, { quantity: e.target.value })}
              />
              <select value={line.unitType} onChange={(e) => updateLine(index, { unitType: e.target.value })}>
                {UNIT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                type="number"
                step="0.01"
                placeholder="Cost (optional)"
                value={line.unitCost}
                onChange={(e) => updateLine(index, { unitCost: e.target.value })}
              />
              <button type="button" className="btn-secondary" onClick={() => removeLine(index)}>
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="btn-secondary" onClick={addLine}>
            + Add Item
          </button>
        </fieldset>

        <label>
          Notes (optional)
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <button className="btn-primary" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Saving..." : "Record Receipt"}
        </button>
      </div>
    </div>
  );
}
