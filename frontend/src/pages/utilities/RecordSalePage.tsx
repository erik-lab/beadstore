import { useState } from "react";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, Sale, SaleChannel, SaleDetail } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

// Deliberately no-frills — built for Patti to test/validate the new sales
// recording backend, not as a polished feature. Easy to delete: this file,
// its route in App.tsx, and its card in UtilitiesPage.tsx.

interface LineDraft {
  productId: string;
  quantity: string;
  unitPrice: string;
}

function emptyLine(): LineDraft {
  return { productId: "", quantity: "", unitPrice: "" };
}

export function RecordSalePage() {
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const sales = useFetch(() => api.get<Sale[]>("/sales?limit=20"), []);

  const [channel, setChannel] = useState<SaleChannel>("manual");
  const [externalOrderId, setExternalOrderId] = useState("");
  const [saleDate, setSaleDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
    const validLines = lines.filter((l) => l.productId && l.quantity);
    if (validLines.length === 0) {
      setError("Pick a product and quantity for at least one line.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post<SaleDetail>("/sales", {
        channel,
        external_order_id: externalOrderId || null,
        sale_date: saleDate,
        notes: notes || null,
        lines: validLines.map((l) => ({
          product_id: l.productId,
          quantity: Number(l.quantity),
          unit_price: l.unitPrice ? Number(l.unitPrice) : null,
        })),
      });
      setChannel("manual");
      setExternalOrderId("");
      setNotes("");
      setLines([emptyLine()]);
      sales.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not record sale.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>Record a Sale</h1>
      <p className="page-subtitle">
        Testing/validation tool for the new sales-recording backend — decrements inventory the same
        way a storefront or Etsy sale eventually will. No polish intended.
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="form-card">
        <label>
          Channel
          <select value={channel} onChange={(e) => setChannel(e.target.value as SaleChannel)}>
            <option value="manual">Manual</option>
            <option value="storefront">Storefront</option>
            <option value="etsy">Etsy</option>
          </select>
        </label>

        <label>
          External order ID (optional)
          <input value={externalOrderId} onChange={(e) => setExternalOrderId(e.target.value)} />
        </label>

        <label>
          Sale Date
          <input type="date" value={saleDate} onChange={(e) => setSaleDate(e.target.value)} />
        </label>

        <fieldset>
          <legend>Items Sold</legend>
          {lines.map((line, index) => (
            <div key={index} className="line-row">
              <select value={line.productId} onChange={(e) => updateLine(index, { productId: e.target.value })}>
                <option value="">Select product...</option>
                {products.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <input
                type="number"
                step="0.001"
                placeholder="Quantity"
                value={line.quantity}
                onChange={(e) => updateLine(index, { quantity: e.target.value })}
              />
              <input
                type="number"
                step="0.01"
                placeholder="Unit price (optional)"
                value={line.unitPrice}
                onChange={(e) => updateLine(index, { unitPrice: e.target.value })}
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
          {submitting ? "Recording..." : "Record Sale"}
        </button>
      </div>

      <section className="detail-section">
        <h2>Recent Sales</h2>
        {sales.loading && <Loading />}
        {sales.error && <ErrorState message={sales.error} />}
        {sales.data && sales.data.length === 0 && <EmptyState label="No sales recorded yet." />}
        {sales.data && sales.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Channel</th>
                <th>External Order ID</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sales.data.map((s) => (
                <tr key={s.id}>
                  <td>{s.sale_date}</td>
                  <td>{s.channel}</td>
                  <td>{s.external_order_id ?? "—"}</td>
                  <td>
                    <StatusBadge status={s.status} />
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
