import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Vendor } from "../../lib/types";

export function VendorFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();

  const existing = useFetch(() => (isEdit ? api.get<Vendor>(`/vendors/${id}`) : Promise.resolve(null)), [id]);

  const [name, setName] = useState("");
  const [contactName, setContactName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setContactName(existing.data.contact_name ?? "");
      setEmail(existing.data.email ?? "");
      setPhone(existing.data.phone ?? "");
      setNotes(existing.data.notes ?? "");
    }
  }, [existing.data]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Vendor name is required.");
      return;
    }
    setSubmitting(true);
    const payload = {
      name,
      contact_name: contactName || null,
      email: email || null,
      phone: phone || null,
      notes: notes || null,
    };
    try {
      if (isEdit) {
        await api.patch(`/vendors/${id}`, payload);
        navigate(`/vendors/${id}`);
      } else {
        const created = await api.post<Vendor>("/vendors", payload);
        navigate(`/vendors/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save vendor.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>{isEdit ? "Edit Vendor" : "New Vendor"}</h1>
      <form className="form-card" onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}
        <label className="required">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Contact name (optional)
          <input value={contactName} onChange={(e) => setContactName(e.target.value)} />
        </label>
        <label>
          Email (optional)
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Phone (optional)
          <input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label>
          Notes (optional)
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Saving..." : "Save Vendor"}
        </button>
      </form>
    </div>
  );
}
