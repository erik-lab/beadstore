import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, PurchaseOrder, Vendor } from "../../lib/types";
import { UNIT_TYPES } from "../../lib/types";

interface DraftLine {
  productId: string;
  description: string;
  quantity: string;
  unitType: string;
  unitCost: string;
}

function emptyLine(): DraftLine {
  return { productId: "", description: "", quantity: "", unitType: "strand", unitCost: "" };
}

export function PurchaseOrderFormPage() {
  const navigate = useNavigate();
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors?limit=200"), []);
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);

  const [vendorId, setVendorId] = useState("");
  const [orderDate, setOrderDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  function addLine() {
    setLines((prev) => [...prev, emptyLine()]);
  }

  function removeLine(index: number) {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!vendorId) {
      setError("Vendor is required (choose 'Unknown Vendor' if not known).");
      return;
    }
    const validLines = lines.filter((l) => l.productId || l.description.trim());
    for (const line of validLines) {
      if (!line.productId && !line.description.trim()) {
        setError("Each line needs a product or a description.");
        return;
      }
    }
    setSubmitting(true);
    try {
      const created = await api.post<PurchaseOrder>("/purchase-orders", {
        vendor_id: vendorId,
        order_date: orderDate,
        notes: notes || null,
        lines: validLines.map((l) => ({
          product_id: l.productId || null,
          expected_item_description: l.productId ? null : l.description,
          expected_quantity: l.quantity ? Number(l.quantity) : null,
          expected_unit_type: l.quantity ? l.unitType : null,
          unit_cost: l.unitCost ? Number(l.unitCost) : null,
        })),
      });
      navigate(`/purchase-orders/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not create supplier order.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>New Supplier Order</h1>
      <form className="form-card" onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}

        <label className="required">
          Vendor
          <select value={vendorId} onChange={(e) => setVendorId(e.target.value)} required>
            <option value="">Select vendor...</option>
            {vendors.data?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Order Date
          <input type="date" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} />
        </label>

        <label>
          Notes (optional)
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <fieldset>
          <legend>Expected Order Lines</legend>
          {lines.map((line, index) => (
            <div key={index} className="line-row">
              <select value={line.productId} onChange={(e) => updateLine(index, { productId: e.target.value })}>
                <option value="">Free-text item (not yet a product)</option>
                {products.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {!line.productId && (
                <input
                  placeholder="Describe expected item"
                  value={line.description}
                  onChange={(e) => updateLine(index, { description: e.target.value })}
                />
              )}
              <input
                type="number"
                step="0.001"
                placeholder="Expected qty"
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
                placeholder="Unit cost"
                value={line.unitCost}
                onChange={(e) => updateLine(index, { unitCost: e.target.value })}
              />
              <button type="button" className="btn-secondary" onClick={() => removeLine(index)}>
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="btn-secondary" onClick={addLine}>
            + Add Line
          </button>
        </fieldset>

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Saving..." : "Create Supplier Order"}
        </button>
      </form>
    </div>
  );
}
