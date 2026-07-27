import { useState } from "react";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Hint } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";

export function HintsMaintenancePage() {
  const hints = useFetch(() => api.get<Hint[]>("/hints"), []);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [newPage, setNewPage] = useState("");
  const [newItemKey, setNewItemKey] = useState("");
  const [newText, setNewText] = useState("");

  function startEdit(hint: Hint) {
    setEditingId(hint.id);
    setDraftText(hint.text);
    setError(null);
  }

  async function saveEdit(hintId: string) {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/hints/${hintId}`, { text: draftText });
      setEditingId(null);
      hints.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save hint.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteHint(hintId: string) {
    setError(null);
    try {
      await api.delete(`/hints/${hintId}`);
      hints.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not delete hint.");
    }
  }

  async function addHint() {
    setError(null);
    if (!newPage.trim() || !newItemKey.trim() || !newText.trim()) {
      setError("Page, item key, and text are all required for a new hint.");
      return;
    }
    try {
      await api.post("/hints", { page: newPage.trim(), item_key: newItemKey.trim(), text: newText.trim() });
      setNewPage("");
      setNewItemKey("");
      setNewText("");
      hints.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not add hint.");
    }
  }

  return (
    <div>
      <h1>Hints Maintenance</h1>
      <p className="page-subtitle">
        Edit the text shown by the (i) icons throughout the app. Each hint is tied to a page and
        an item on that page.
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      {hints.loading && <Loading />}
      {hints.error && <ErrorState message={hints.error} />}
      {hints.data && hints.data.length === 0 && <EmptyState label="No hints yet." />}
      {hints.data && hints.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Page</th>
              <th>Item</th>
              <th>Text</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {hints.data.map((hint) => (
              <tr key={hint.id}>
                <td>{hint.page}</td>
                <td>{hint.item_key}</td>
                <td style={{ minWidth: 320 }}>
                  {editingId === hint.id ? (
                    <textarea value={draftText} onChange={(e) => setDraftText(e.target.value)} />
                  ) : (
                    hint.text
                  )}
                </td>
                <td>
                  {editingId === hint.id ? (
                    <div className="maintenance-row">
                      <button className="btn-primary" onClick={() => saveEdit(hint.id)} disabled={saving}>
                        Save
                      </button>
                      <button className="btn-secondary" onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="maintenance-row">
                      <button className="btn-secondary" onClick={() => startEdit(hint)}>
                        Edit
                      </button>
                      <button className="btn-secondary" onClick={() => deleteHint(hint.id)}>
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <section className="detail-section">
        <h2>Add a New Hint</h2>
        <div className="form-card">
          <label>
            Page
            <input value={newPage} onChange={(e) => setNewPage(e.target.value)} placeholder="e.g. dashboard" />
          </label>
          <label>
            Item key
            <input
              value={newItemKey}
              onChange={(e) => setNewItemKey(e.target.value)}
              placeholder="e.g. active_products"
            />
          </label>
          <label>
            Text
            <textarea value={newText} onChange={(e) => setNewText(e.target.value)} />
          </label>
          <button className="btn-primary" onClick={addHint}>
            Add Hint
          </button>
        </div>
      </section>
    </div>
  );
}
