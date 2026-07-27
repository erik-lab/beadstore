import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Location } from "../../lib/types";

export function LocationFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();

  const locations = useFetch(() => api.get<Location[]>("/locations"), []);
  const existing = useFetch(() => (isEdit ? api.get<Location>(`/locations/${id}`) : Promise.resolve(null)), [id]);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [parentId, setParentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setDescription(existing.data.description ?? "");
      setParentId(existing.data.parent_location_id ?? "");
    }
  }, [existing.data]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Location name is required.");
      return;
    }
    setSubmitting(true);
    const payload = { name, description: description || null, parent_location_id: parentId || null };
    try {
      if (isEdit) {
        await api.patch(`/locations/${id}`, payload);
      } else {
        await api.post<Location>("/locations", payload);
      }
      navigate("/locations");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save location.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>{isEdit ? "Edit Location" : "New Location"}</h1>
      <form className="form-card" onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}
        <label className="required">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Bin A3" />
        </label>
        <label>
          Description (optional)
          <input value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          Parent location (optional)
          <select value={parentId} onChange={(e) => setParentId(e.target.value)}>
            <option value="">None</option>
            {locations.data?.filter((l) => l.id !== id).map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Saving..." : "Save Location"}
        </button>
      </form>
    </div>
  );
}
