import { useState } from "react";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Hint } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { HINT_LOCATIONS, findHintLocation } from "../../lib/hintLocations";

export function HintsMaintenancePage() {
  const hints = useFetch(() => api.get<Hint[]>("/hints"), []);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [newLocationKey, setNewLocationKey] = useState("");
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
    if (!newLocationKey || !newText.trim()) {
      setError("Choose a location and enter text for the new hint.");
      return;
    }
    const [page, itemKey] = newLocationKey.split("::");
    try {
      await api.post("/hints", { page, item_key: itemKey, text: newText.trim() });
      setNewLocationKey("");
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
        Edit the text shown by the (i) icons throughout the app. Each hint is tied to one specific
        spot in the app, listed below by name — a hint saved for a spot that isn't in this list
        won't show up anywhere.
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      {hints.loading && <Loading />}
      {hints.error && <ErrorState message={hints.error} />}
      {hints.data && hints.data.length === 0 && <EmptyState label="No hints yet." />}
      {hints.data && hints.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Location</th>
              <th>Text</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {hints.data.map((hint) => {
              const location = findHintLocation(hint.page, hint.item_key);
              return (
                <tr key={hint.id}>
                  <td>
                    {location ? (
                      location.label
                    ) : (
                      <>
                        <span className="badge tone-warn">Not shown anywhere</span>
                        <div style={{ fontSize: 12, marginTop: 4 }}>
                          page: {hint.page}, item: {hint.item_key}
                        </div>
                      </>
                    )}
                  </td>
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
              );
            })}
          </tbody>
        </table>
      )}

      <section className="detail-section">
        <h2>Add a New Hint</h2>
        <div className="form-card">
          <label>
            Location
            <select value={newLocationKey} onChange={(e) => setNewLocationKey(e.target.value)}>
              <option value="">Select a spot in the app...</option>
              {HINT_LOCATIONS.map((loc) => (
                <option key={`${loc.page}::${loc.itemKey}`} value={`${loc.page}::${loc.itemKey}`}>
                  {loc.label}
                </option>
              ))}
            </select>
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
