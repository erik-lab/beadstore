import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, ProductCategory, ProductSubtype } from "../../lib/types";

const OTHER_VALUE = "__other__";

const ATTRIBUTE_FIELDS: { key: keyof Product; label: string }[] = [
  { key: "material", label: "Material" },
  { key: "color", label: "Color" },
  { key: "size", label: "Size" },
  { key: "shape", label: "Shape" },
  { key: "finish", label: "Finish" },
  { key: "hole_size", label: "Hole Size" },
  { key: "origin", label: "Origin" },
  { key: "strand_length", label: "Strand Length" },
  { key: "count", label: "Count" },
  { key: "grade", label: "Grade" },
  { key: "condition", label: "Condition" },
];

export function ProductFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const cancelTo = isEdit ? `/products/${id}` : "/products";

  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const existing = useFetch(
    () => (isEdit ? api.get<Product>(`/products/${id}`) : Promise.resolve(null)),
    [id]
  );

  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [subtypeId, setSubtypeId] = useState("");
  const [customSubtype, setCustomSubtype] = useState("");
  const [description, setDescription] = useState("");
  const [sku, setSku] = useState("");
  const [attributes, setAttributes] = useState<Record<string, string>>({});
  const [attributeOptions, setAttributeOptions] = useState<Record<string, string[]>>({});
  const [subtypes, setSubtypes] = useState<ProductSubtype[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      const p = existing.data;
      setName(p.name);
      setCategoryId(p.category_id);
      setSubtypeId(p.subtype_id ?? (p.custom_subtype ? OTHER_VALUE : ""));
      setCustomSubtype(p.custom_subtype ?? "");
      setDescription(p.description ?? "");
      setSku(p.sku ?? "");
      const attrs: Record<string, string> = {};
      for (const field of ATTRIBUTE_FIELDS) {
        const value = p[field.key];
        if (typeof value === "string") attrs[field.key] = value;
      }
      setAttributes(attrs);
    }
  }, [existing.data]);

  useEffect(() => {
    if (!categoryId || categoryId === OTHER_VALUE) {
      setSubtypes([]);
      return;
    }
    api.get<ProductSubtype[]>(`/product-categories/${categoryId}/subtypes`).then(setSubtypes);
  }, [categoryId]);

  // Hybrid pick lists: load every previously-used value for each optional
  // attribute once, so the user can pick a prior entry or type a new one.
  useEffect(() => {
    ATTRIBUTE_FIELDS.forEach((field) => {
      api
        .get<string[]>(`/products/attribute-options?field=${field.key}`)
        .then((options) => setAttributeOptions((prev) => ({ ...prev, [field.key]: options })))
        .catch(() => {
          // Attribute suggestions are a convenience, not required for the form to work.
        });
    });
  }, []);

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
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!categoryId) {
      setError("Category is required.");
      return;
    }
    if (categoryId === OTHER_VALUE && !newCategoryName.trim()) {
      setError("Enter a name for the new category.");
      return;
    }
    if (subtypeId === OTHER_VALUE && !customSubtype.trim()) {
      setError("Enter a custom subtype, or choose an existing one instead.");
      return;
    }

    setSubmitting(true);
    try {
      const resolvedCategoryId = await resolveCategoryId();
      const payload = {
        name,
        category_id: resolvedCategoryId,
        subtype_id: subtypeId && subtypeId !== OTHER_VALUE ? subtypeId : null,
        custom_subtype: subtypeId === OTHER_VALUE ? customSubtype.trim() : null,
        description: description || null,
        sku: sku || null,
        ...Object.fromEntries(ATTRIBUTE_FIELDS.map((f) => [f.key, attributes[f.key] || null])),
      };
      if (isEdit) {
        await api.patch(`/products/${id}`, payload);
        navigate(`/products/${id}`);
      } else {
        const created = await api.post<Product>("/products", payload);
        navigate(`/products/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save product.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>{isEdit ? "Edit Product" : "New Product"}</h1>
      <form className="form-card" onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}

        <label className="required">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        <label className="required">
          Category
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
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

        <label>
          Subtype (optional)
          <select value={subtypeId} onChange={(e) => setSubtypeId(e.target.value)}>
            <option value="">Unknown / not set</option>
            {subtypes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
            <option value={OTHER_VALUE}>Other (custom)...</option>
          </select>
        </label>

        {subtypeId === OTHER_VALUE && (
          <label>
            Custom subtype
            <input value={customSubtype} onChange={(e) => setCustomSubtype(e.target.value)} />
          </label>
        )}

        <label>
          Description (optional)
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>

        <label>
          SKU (optional)
          <input value={sku} onChange={(e) => setSku(e.target.value)} />
        </label>

        <fieldset>
          <legend>Optional attributes — leave blank if unknown</legend>
          <div className="field-grid">
            {ATTRIBUTE_FIELDS.map((field) => (
              <label key={field.key}>
                {field.label}
                <input
                  value={attributes[field.key] ?? ""}
                  onChange={(e) => setAttributes({ ...attributes, [field.key]: e.target.value })}
                  list={`attr-options-${field.key}`}
                  autoComplete="off"
                />
                <datalist id={`attr-options-${field.key}`}>
                  {(attributeOptions[field.key] ?? []).map((value) => (
                    <option key={value} value={value} />
                  ))}
                </datalist>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="form-actions line-row">
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "Saving..." : "Save Product"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate(cancelTo)}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
