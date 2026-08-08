import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import { createPieceCreation } from "../../lib/pieceCreations";
import type { InventoryUnit, Product, ProductCategory } from "../../lib/types";

const OTHER_VALUE = "__other__";
const NEW_PRODUCT_VALUE = "__new__";

interface ComponentDraft {
  inventoryUnitId: string;
  quantityUsed: string;
}

function emptyComponent(): ComponentDraft {
  return { inventoryUnitId: "", quantityUsed: "" };
}

function unitLabel(unit: InventoryUnit): string {
  const cost = unit.cost_amount != null ? ` — $${unit.cost_amount.toFixed(2)}/${unit.unit_type}` : "";
  return `${unit.product_name ?? unit.unresolved_description ?? "(unknown item)"} — ${unit.quantity} ${unit.unit_type} available${cost} (recv ${unit.received_date})`;
}

export function PieceCreationFormPage() {
  const navigate = useNavigate();
  const products = useFetch(() => api.get<Product[]>("/products?limit=200"), []);
  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const availableUnits = useFetch(
    () => api.get<InventoryUnit[]>("/inventory-units?status=available&limit=200"),
    []
  );

  const [productChoice, setProductChoice] = useState(NEW_PRODUCT_VALUE);
  const [newProductName, setNewProductName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [createdDate, setCreatedDate] = useState(new Date().toISOString().slice(0, 10));
  const [quantityProduced, setQuantityProduced] = useState("1");
  const [manualCost, setManualCost] = useState("");
  const [notes, setNotes] = useState("");
  const [components, setComponents] = useState<ComponentDraft[]>([emptyComponent()]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateComponent(index: number, patch: Partial<ComponentDraft>) {
    setComponents((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  }

  function addComponent() {
    setComponents((prev) => [...prev, emptyComponent()]);
  }

  function removeComponent(index: number) {
    setComponents((prev) => prev.filter((_, i) => i !== index));
  }

  const unitsById = new Map((availableUnits.data ?? []).map((u) => [u.id, u]));
  const validComponents = components.filter((c) => c.inventoryUnitId && c.quantityUsed);
  const allCostsKnown = validComponents.every((c) => unitsById.get(c.inventoryUnitId)?.cost_amount != null);
  const estimatedCost = validComponents.reduce((sum, c) => {
    const unit = unitsById.get(c.inventoryUnitId);
    const qty = Number(c.quantityUsed) || 0;
    return sum + (unit?.cost_amount ?? 0) * qty;
  }, 0);

  async function resolveCategoryId(): Promise<string> {
    if (categoryId !== OTHER_VALUE) return categoryId;
    const trimmed = newCategoryName.trim();
    const existingMatch = categories.data?.find((c) => c.name.toLowerCase() === trimmed.toLowerCase());
    if (existingMatch) return existingMatch.id;
    const created = await api.post<ProductCategory>("/product-categories", { name: trimmed });
    return created.id;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    for (const c of components) {
      if ((c.inventoryUnitId && !c.quantityUsed) || (!c.inventoryUnitId && c.quantityUsed)) {
        setError("Each component row needs both an item and a quantity — remove any incomplete rows.");
        return;
      }
    }

    let productId = productChoice;
    setSubmitting(true);
    try {
      if (productChoice === NEW_PRODUCT_VALUE) {
        if (!newProductName.trim()) {
          setError("Enter a name for the new piece.");
          setSubmitting(false);
          return;
        }
        if (!categoryId) {
          setError("Choose a category for the new piece.");
          setSubmitting(false);
          return;
        }
        if (categoryId === OTHER_VALUE && !newCategoryName.trim()) {
          setError("Enter a name for the new category.");
          setSubmitting(false);
          return;
        }
        const resolvedCategoryId = await resolveCategoryId();
        const createdProduct = await api.post<Product>("/products", {
          name: newProductName.trim(),
          category_id: resolvedCategoryId,
          source_type: "assembled",
        });
        productId = createdProduct.id;
      }

      await createPieceCreation({
        product_id: productId,
        created_date: createdDate,
        quantity_produced: Number(quantityProduced) || 1,
        creation_cost: manualCost ? Number(manualCost) : null,
        notes: notes || null,
        components: validComponents.map((c) => ({
          inventory_unit_id: c.inventoryUnitId,
          quantity_used: Number(c.quantityUsed),
        })),
      });
      navigate("/pieces");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not record this piece.");
    } finally {
      setSubmitting(false);
    }
  }

  const pieceProducts = (products.data ?? []).filter((p) => p.source_type === "assembled");
  const otherProducts = (products.data ?? []).filter((p) => p.source_type !== "assembled");

  return (
    <div>
      <h1>Create a Piece</h1>
      <p className="page-subtitle">
        Record a piece you made — jewelry assembled from materials already in inventory, as opposed to
        something bought ready-made for resale. Linking the components used is optional; if you do, their
        cost is added up automatically (you can still override it), and the quantities used are deducted
        from inventory.
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {(products.error || categories.error || availableUnits.error) && (
        <div className="alert alert-error">
          Could not load {[
            products.error && "products",
            categories.error && "categories",
            availableUnits.error && "available inventory",
          ]
            .filter(Boolean)
            .join(", ")}
          . Try reloading the page.
        </div>
      )}

      <form className="form-card" onSubmit={handleSubmit}>
        <label className="required">
          Piece
          <select value={productChoice} onChange={(e) => setProductChoice(e.target.value)}>
            <option value={NEW_PRODUCT_VALUE}>New piece...</option>
            {pieceProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} (remake)
              </option>
            ))}
            {otherProducts.length > 0 && <option disabled>──────────</option>}
            {otherProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        {productChoice === NEW_PRODUCT_VALUE && (
          <>
            <label className="required">
              Name
              <input value={newProductName} onChange={(e) => setNewProductName(e.target.value)} />
            </label>
            <label className="required">
              Category
              <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">Select category...</option>
                {categories.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
                <option value={OTHER_VALUE}>Other (add new category)...</option>
              </select>
            </label>
            {categoryId === OTHER_VALUE && (
              <label className="required">
                New category name
                <input value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} />
              </label>
            )}
          </>
        )}

        <div className="field-grid">
          <label>
            Date made
            <input type="date" value={createdDate} onChange={(e) => setCreatedDate(e.target.value)} />
          </label>
          <label>
            Quantity made
            <input
              type="number"
              min="1"
              step="1"
              value={quantityProduced}
              onChange={(e) => setQuantityProduced(e.target.value)}
            />
          </label>
        </div>

        <fieldset>
          <legend>Components used (optional)</legend>
          {components.map((c, i) => (
            <div key={i} className="line-row">
              <select
                value={c.inventoryUnitId}
                onChange={(e) => updateComponent(i, { inventoryUnitId: e.target.value })}
                style={{ minWidth: 320 }}
              >
                <option value="">Select an item...</option>
                {(availableUnits.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {unitLabel(u)}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                step="0.001"
                placeholder="Qty used"
                value={c.quantityUsed}
                onChange={(e) => updateComponent(i, { quantityUsed: e.target.value })}
                style={{ width: 100 }}
              />
              <button type="button" className="btn-secondary" onClick={() => removeComponent(i)}>
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="btn-secondary" onClick={addComponent}>
            Add Component
          </button>
        </fieldset>

        <label>
          Cost to make {validComponents.length > 0 && "(leave blank to use the estimate below)"}
          <input
            type="number"
            min="0"
            step="0.01"
            placeholder={
              validComponents.length > 0 && allCostsKnown ? `Estimated: $${estimatedCost.toFixed(2)}` : "$"
            }
            value={manualCost}
            onChange={(e) => setManualCost(e.target.value)}
          />
        </label>
        {validComponents.length > 0 && !allCostsKnown && (
          <p className="page-subtitle" style={{ marginTop: -8 }}>
            Some selected components don't have a known cost, so an estimate isn't available — enter a cost
            above if you'd like one recorded.
          </p>
        )}

        <label>
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <div className="form-actions line-row">
          <button className="btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Saving..." : "Record Piece"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate("/pieces")}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
