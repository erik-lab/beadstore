import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import { useDictation } from "../../lib/useDictation";
import {
  FileTooLargeError,
  deleteIntakeBatch,
  listIntakeBatches,
  parseIntakeFile,
  parseIntakeText,
} from "../../lib/inventoryIntake";
import { INTAKE_SOURCE_LABELS } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

const ACCEPTED_FILES = ".csv,.tsv,.txt,.md,.xlsx,.xlsm,.docx,.pdf,.png,.jpg,.jpeg,.gif,.webp,.html";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof FileTooLargeError) return err.message;
  if (err instanceof ApiError) return String(err.detail);
  return err instanceof Error ? err.message : fallback;
}

export function InventoryImportPage() {
  const navigate = useNavigate();
  const batches = useFetch(() => listIntakeBatches(), []);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  // Tracks whether the current text box content came from speech, so the
  // batch is labelled correctly even if Patti tidies up the wording after.
  const [dictated, setDictated] = useState(false);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const dictation = useDictation((chunk) => {
    setDictated(true);
    setText((prev) => (prev ? `${prev.trimEnd()} ${chunk.trim()}` : chunk.trim()));
  });

  async function startImport(run: () => Promise<{ id: string }>, label: string) {
    setError(null);
    setWorking(label);
    try {
      const batch = await run();
      navigate(`/inventory-import/${batch.id}`);
    } catch (err) {
      setError(errorMessage(err, "Could not read that source. Try again."));
    } finally {
      setWorking(null);
    }
  }

  function handleParseText() {
    if (dictation.listening) dictation.stop();
    const trimmed = text.trim();
    if (!trimmed) {
      setError("Type, paste or dictate something first.");
      return;
    }
    startImport(() => parseIntakeText(trimmed, dictated ? "voice" : "paste"), "text");
  }

  function handleFile(file: File) {
    startImport(() => parseIntakeFile(file), "file");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleDiscard(id: string) {
    if (!confirm("Discard this import? Anything already saved to inventory stays.")) return;
    try {
      await deleteIntakeBatch(id);
      batches.reload();
    } catch (err) {
      setError(errorMessage(err, "Could not discard that import."));
    }
  }

  const busy = working !== null;

  return (
    <div>
      <div className="page-header">
        <h1>Import Inventory</h1>
      </div>

      <h2>What is this</h2>
      <p className="page-subtitle">
        Turns inventory details from almost any source into draft records you can check before
        anything is saved. Upload a spreadsheet, a Word document, a PDF invoice or a photo of a
        packing slip; or type, paste or speak the details. AI reads the source and fills in as much
        as it can, flags what's missing, and leaves everything editable. Nothing reaches your
        products or inventory until you review the draft and press Save.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <section className="detail-section">
        <h2>Type, paste or speak</h2>
        <div className="form-card">
          <label>
            Inventory details
            <textarea
              rows={6}
              value={text + (dictation.interim ? ` ${dictation.interim}` : "")}
              placeholder={
                "Anything goes — a tidy list or a sentence:\n" +
                "5 strands of 8mm matte black round Czech glass from Fire Mountain, $3.50 each, bin 4\n" +
                "2 bags of size 11 silver-lined seed beads"
              }
              onChange={(e) => {
                setText(e.target.value);
                setDictated(false);
              }}
              disabled={busy}
            />
          </label>

          <div className="maintenance-row">
            <button className="btn-primary" onClick={handleParseText} disabled={busy}>
              {working === "text" ? "Reading..." : "Read These Details"}
            </button>

            {dictation.supported ? (
              <button
                className="btn-secondary"
                onClick={dictation.listening ? dictation.stop : dictation.start}
                disabled={busy}
              >
                {dictation.listening ? "Stop Dictating" : "Dictate"}
              </button>
            ) : (
              <span className="page-subtitle">
                Dictation needs Chrome, Edge or Safari — in this browser, type or paste instead.
              </span>
            )}

            {text && !busy && (
              <button
                className="btn-secondary"
                onClick={() => {
                  setText("");
                  setDictated(false);
                }}
              >
                Clear
              </button>
            )}
          </div>

          {dictation.listening && (
            <div className="scan-status">
              Listening — say one item at a time, then press Stop Dictating. You can fix the wording
              before reading it in.
            </div>
          )}
          {dictation.error && <div className="alert alert-warn">{dictation.error}</div>}
        </div>
      </section>

      <section className="detail-section">
        <h2>Upload a file</h2>
        <div className="form-card">
          <p className="page-subtitle">
            Spreadsheets (.xlsx, .csv), Word documents (.docx), PDFs, photos and plain text. One
            file at a time, up to about 7MB.
          </p>
          <div className="maintenance-row">
            <button
              className="btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={busy}
            >
              {working === "file" ? "Reading..." : "Choose File"}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILES}
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
        </div>
      </section>

      <section className="detail-section">
        <h2>Recent imports</h2>
        {batches.loading && <Loading />}
        {batches.error && <ErrorState message={batches.error} />}
        {batches.data && batches.data.length === 0 && (
          <EmptyState label="No imports yet. Start one above." />
        )}
        {batches.data && batches.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Came from</th>
                <th>Started</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {batches.data.map((batch) => (
                <tr key={batch.id}>
                  <td>
                    <Link to={`/inventory-import/${batch.id}`}>{batch.source_name ?? "Untitled import"}</Link>
                  </td>
                  <td>{INTAKE_SOURCE_LABELS[batch.source_kind]}</td>
                  <td>{new Date(batch.created_at).toLocaleString()}</td>
                  <td>
                    <StatusBadge status={batch.status} />
                  </td>
                  <td>
                    <div className="maintenance-row">
                      <Link className="btn-secondary" to={`/inventory-import/${batch.id}`}>
                        {batch.status === "draft" ? "Review" : "View"}
                      </Link>
                      {batch.status !== "discarded" && (
                        <button className="btn-secondary" onClick={() => handleDiscard(batch.id)}>
                          Discard
                        </button>
                      )}
                    </div>
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
