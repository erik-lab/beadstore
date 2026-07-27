import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, ProductCategory, ProductSubtype } from "../../lib/types";

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

  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const existing = useFetch(
    () => (isEdit ? api.get<Product>(`/products/${id}`) : Promise.resolve(null)),
    [id]
  );

  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [subtypeId, setSubtypeId] = useState("");
  const [description, setDescription] = useState("");
  const [sku, setSku] = useState("");
  const [attributes, setAttributes] = useState<Record<string, string>>({});
  const [subtypes, setSubtypes] = useState<ProductSubtype[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      const p = existing.data;
      setName(p.name);
      setCategoryId(p.category_id);
      setSubtypeId(p.subtype_id ?? "");
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
    if (!categoryId) {
      setSubtypes([]);
      return;
    }
    api.get<ProductSubtype[]>(`/product-categories/${categoryId}/subtypes`).then(setSubtypes);
  }, [categoryId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !categoryId) {
      setError("Name and category are required.");
      return;
    }
    setSubmitting(true);
    const payload = {
      name,
      category_id: categoryId,
      subtype_id: subtypeId || null,
      description: description || null,
      sku: sku || null,
      ...Object.fromEntries(ATTRIBUTE_FIELDS.map((f) => [f.key, attributes[f.key] || null])),
    };
    try {
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
          </select>
        </label>

        <label>
          Subtype (optional)
          <select value={subtypeId} onChange={(e) => setSubtypeId(e.target.value)}>
            <option value="">Unknown / not set</option>
            {subtypes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>

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
                />
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Saving..." : "Save Product"}
        </button>
      </form>
    </div>
  );
}
