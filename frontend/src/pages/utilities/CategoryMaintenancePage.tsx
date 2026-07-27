import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { ProductCategory, ProductSubtype } from "../../lib/types";
import { Loading, ErrorState } from "../../components/States";

export function CategoryMaintenancePage() {
  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const [subtypesByCategory, setSubtypesByCategory] = useState<Record<string, ProductSubtype[]>>({});
  const [error, setError] = useState<string | null>(null);

  const [newCategoryName, setNewCategoryName] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [categoryDraft, setCategoryDraft] = useState("");

  const [newSubtypeName, setNewSubtypeName] = useState<Record<string, string>>({});
  const [editingSubtypeId, setEditingSubtypeId] = useState<string | null>(null);
  const [subtypeDraft, setSubtypeDraft] = useState("");

  async function loadSubtypes(categoryId: string) {
    const subtypes = await api.get<ProductSubtype[]>(`/product-categories/${categoryId}/subtypes`);
    setSubtypesByCategory((prev) => ({ ...prev, [categoryId]: subtypes }));
  }

  const categoriesData = categories.data;

  // Load subtypes for every category once the category list arrives (or a
  // new category is added), without doing so as a render-time side effect.
  useEffect(() => {
    categoriesData?.forEach((c) => {
      if (!(c.id in subtypesByCategory)) loadSubtypes(c.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoriesData]);

  async function addCategory() {
    setError(null);
    if (!newCategoryName.trim()) {
      setError("Category name is required.");
      return;
    }
    try {
      await api.post("/product-categories", { name: newCategoryName.trim() });
      setNewCategoryName("");
      categories.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not add category.");
    }
  }

  async function saveCategory(categoryId: string) {
    setError(null);
    try {
      await api.patch(`/product-categories/${categoryId}`, { name: categoryDraft });
      setEditingCategoryId(null);
      categories.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not rename category.");
    }
  }

  async function addSubtype(categoryId: string) {
    setError(null);
    const name = newSubtypeName[categoryId]?.trim();
    if (!name) {
      setError("Subtype name is required.");
      return;
    }
    try {
      await api.post("/product-subtypes", { category_id: categoryId, name });
      setNewSubtypeName((prev) => ({ ...prev, [categoryId]: "" }));
      loadSubtypes(categoryId);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not add subtype.");
    }
  }

  async function saveSubtype(categoryId: string, subtypeId: string) {
    setError(null);
    try {
      await api.patch(`/product-subtypes/${subtypeId}`, { name: subtypeDraft });
      setEditingSubtypeId(null);
      loadSubtypes(categoryId);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not rename subtype.");
    }
  }

  return (
    <div>
      <h1>Product Categories</h1>
      <p className="page-subtitle">Manage the categories and subtypes available when creating a product.</p>
      {error && <div className="alert alert-error">{error}</div>}

      {categories.loading && <Loading />}
      {categories.error && <ErrorState message={categories.error} />}

      {categoriesData?.map((category) => (
        <section key={category.id} className="detail-section">
          <div className="maintenance-row">
            {editingCategoryId === category.id ? (
              <>
                <input className="grow" value={categoryDraft} onChange={(e) => setCategoryDraft(e.target.value)} />
                <button className="btn-primary" onClick={() => saveCategory(category.id)}>
                  Save
                </button>
                <button className="btn-secondary" onClick={() => setEditingCategoryId(null)}>
                  Cancel
                </button>
              </>
            ) : (
              <>
                <h2 style={{ margin: 0 }}>{category.name}</h2>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setEditingCategoryId(category.id);
                    setCategoryDraft(category.name);
                  }}
                >
                  Rename
                </button>
              </>
            )}
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Subtype</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(subtypesByCategory[category.id] ?? []).map((subtype) => (
                <tr key={subtype.id}>
                  <td>
                    {editingSubtypeId === subtype.id ? (
                      <input value={subtypeDraft} onChange={(e) => setSubtypeDraft(e.target.value)} />
                    ) : (
                      subtype.name
                    )}
                  </td>
                  <td>
                    {editingSubtypeId === subtype.id ? (
                      <div className="maintenance-row">
                        <button className="btn-primary" onClick={() => saveSubtype(category.id, subtype.id)}>
                          Save
                        </button>
                        <button className="btn-secondary" onClick={() => setEditingSubtypeId(null)}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        className="btn-secondary"
                        onClick={() => {
                          setEditingSubtypeId(subtype.id);
                          setSubtypeDraft(subtype.name);
                        }}
                      >
                        Rename
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="line-row">
            <input
              placeholder="New subtype name"
              value={newSubtypeName[category.id] ?? ""}
              onChange={(e) => setNewSubtypeName((prev) => ({ ...prev, [category.id]: e.target.value }))}
            />
            <button className="btn-secondary" onClick={() => addSubtype(category.id)}>
              + Add Subtype
            </button>
          </div>
        </section>
      ))}

      <section className="detail-section">
        <h2>Add a New Category</h2>
        <div className="line-row">
          <input
            placeholder="New category name"
            value={newCategoryName}
            onChange={(e) => setNewCategoryName(e.target.value)}
          />
          <button className="btn-primary" onClick={addCategory}>
            + Add Category
          </button>
        </div>
      </section>
    </div>
  );
}
