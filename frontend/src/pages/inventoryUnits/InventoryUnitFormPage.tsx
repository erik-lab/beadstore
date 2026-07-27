import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { InventoryUnit, Location, Product, Vendor } from "../../lib/types";
import { UNIT_TYPES } from "../../lib/types";

export function InventoryUnitFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const cancelTo = isEdit ? `/inventory/${id}` : "/inventory";

  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const locations = useFetch(() => api.get<Location[]>("/locations"), []);
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors?limit=200"), []);
  const existing = useFetch(
    () => (isEdit ? api.get<InventoryUnit>(`/inventory-units/${id}`) : Promise.resolve(null)),
    [id]
  );

  const [productId, setProductId] = useState("");
  const [unresolvedDescription, setUnresolvedDescription] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitType, setUnitType] = useState("strand");
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().slice(0, 10));
  const [locationId, setLocationId] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [costAmount, setCostAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      const u = existing.data;
      setProductId(u.product_id ?? "");
      setUnresolvedDescription(u.unresolved_description ?? "");
      setQuantity(String(u.quantity));
      setUnitType(u.unit_type);
      setReceivedDate(u.received_date);
      setLocationId(u.location_id ?? "");
      setVendorId(u.vendor_id ?? "");
      setCostAmount(u.cost_amount != null ? String(u.cost_amount) : "");
      setNotes(u.notes ?? "");
    }
  }, [existing.data]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!productId && !unresolvedDescription.trim()) {
      setError("Select a product, or describe the item if the product is not yet known.");
      return;
    }
    if (!quantity) {
      setError("Quantity is required.");
      return;
    }
    setSubmitting(true);
    const payload = {
      product_id: productId || null,
      unresolved_description: productId ? null : unresolvedDescription,
      quantity: Number(quantity),
      unit_type: unitType,
      received_date: receivedDate,
      location_id: locationId || null,
      vendor_id: vendorId || null,
      cost_amount: costAmount ? Number(costAmount) : null,
      notes: notes || null,
    };
    try {
      if (isEdit) {
        await api.patch(`/inventory-units/${id}`, payload);
        navigate(`/inventory/${id}`);
      } else {
        const created = await api.post<InventoryUnit>("/inventory-units", payload);
        navigate(`/inventory/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save inventory unit.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>{isEdit ? "Edit Inventory Unit" : "New Inventory Unit"}</h1>
      <form className="form-card" onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}

        <label>
          Product (leave blank and describe below if unknown)
          <select value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">Not yet known / unresolved</option>
            {products.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        {!productId && (
          <label className="required">
            Item description (used until product is matched)
            <input
              value={unresolvedDescription}
              onChange={(e) => setUnresolvedDescription(e.target.value)}
              placeholder="e.g. Bag of mixed clasps"
            />
          </label>
        )}

        <div className="field-grid">
          <label className="required">
            Quantity
            <input type="number" step="0.001" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </label>
          <label className="required">
            Unit Type
            <select value={unitType} onChange={(e) => setUnitType(e.target.value)}>
              {UNIT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="required">
            Received Date
            <input type="date" value={receivedDate} onChange={(e) => setReceivedDate(e.target.value)} />
          </label>
        </div>

        <div className="field-grid">
          <label>
            Location (optional)
            <select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Unknown / not set</option>
              {locations.data?.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vendor (optional)
            <select value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
              <option value="">Unknown / not set</option>
              {vendors.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Cost (optional)
            <input type="number" step="0.01" value={costAmount} onChange={(e) => setCostAmount(e.target.value)} />
          </label>
        </div>

        <label>
          Notes (optional)
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <div className="form-actions line-row">
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "Saving..." : "Save Inventory Unit"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate(cancelTo)}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
