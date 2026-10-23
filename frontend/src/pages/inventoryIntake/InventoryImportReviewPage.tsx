import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import {
  bulkUpdateIntakeRows,
  commitIntakeBatch,
  getIntakeBatch,
  deleteIntakeBatch,
} from "../../lib/inventoryIntake";
import {
  INTAKE_SOURCE_LABELS,
  UNIT_TYPES,
  type IntakeBatchDetail,
  type IntakeCommitResult,
  type IntakeRow,
  type ProductCategory,
} from "../../lib/types";
import { Loading, ErrorState, EmptyState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import { IntakeRowCard } from "./IntakeRowCard";

/**
 * Review screen for one import: fix the flagged gaps, then save.
 *
 * The batch state here is always whatever the server last returned. Every
 * edit round-trips, so the counts, gap flags and "will create" list reflect
 * what a commit would actually do rather than a local approximation.
 */

interface BulkDraft {
  received_date: string;
  vendor_name: string;
  location_name: string;
  category_name: string;
  unit_type: string;
}

const EMPTY_BULK: BulkDraft = {
  received_date: "",
  vendor_name: "",
  location_name: "",
  category_name: "",
  unit_type: "",
};

function countsOf(rows: IntakeRow[]) {
  return {
    ready: rows.filter((r) => r.status === "ready").length,
    needsReview: rows.filter((r) => r.status === "needs_review").length,
    committed: rows.filter((r) => r.status === "committed").length,
    skipped: rows.filter((r) => r.status === "skipped").length,
  };
}

function describeResult(result: IntakeCommitResult): string {
  const parts = [`Saved ${result.committed} item${result.committed === 1 ? "" : "s"} to inventory.`];
  if (result.failed > 0) {
    parts.push(`${result.failed} couldn't be saved — see the notes on those rows.`);
  }
  if (result.remaining > 0) {
    parts.push(`${result.remaining} still need${result.remaining === 1 ? "s" : ""} attention.`);
  }
  return parts.join(" ");
}

export function InventoryImportReviewPage() {
  const { id = "" } = useParams();
  const loaded = useFetch(() => getIntakeBatch(id), [id]);
  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);

  const [batch, setBatch] = useState<IntakeBatchDetail | null>(null);
  const [bulk, setBulk] = useState<BulkDraft>(EMPTY_BULK);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IntakeCommitResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSource, setShowSource] = useState(false);

  useEffect(() => {
    if (loaded.data) setBatch(loaded.data);
  }, [loaded.data]);

  async function refresh() {
    try {
      setBatch(await getIntakeBatch(id));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not reload this import.");
    }
  }

  /**
   * Fold a single row's update into the batch, then refresh.
   *
   * The optimistic splice keeps the row's inputs responsive; the refresh that
   * follows picks up batch-level changes the edit may have caused, like the
   * "will create" list gaining or losing a name.
   */
  function handleRowChanged(updated: IntakeRow) {
    setBatch((prev) =>
      prev ? { ...prev, rows: prev.rows.map((r) => (r.id === updated.id ? updated : r)) } : prev,
    );
    setError(null);
    refresh();
  }

  async function applyBulk() {
    const changes = Object.fromEntries(
      Object.entries(bulk).filter(([, value]) => value !== ""),
    ) as Record<string, string>;
    if (Object.keys(changes).length === 0) {
      setError("Fill in at least one value to apply to every row.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      setBatch(await bulkUpdateIntakeRows(id, changes));
      setBulk(EMPTY_BULK);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not apply those values.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    setError(null);
    setBusy(true);
    try {
      const committed = await commitIntakeBatch(id);
      setResult(committed);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not save this import.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDiscard() {
    if (!confirm("Discard this import? Anything already saved to inventory stays.")) return;
    setBusy(true);
    try {
      await deleteIntakeBatch(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not discard this import.");
    } finally {
      setBusy(false);
    }
  }

  if (loaded.loading && !batch) return <Loading />;
  if (loaded.error && !batch) return <ErrorState message={loaded.error} />;
  if (!batch) return <ErrorState message="Import not found." />;

  const counts = countsOf(batch.rows);
  const willCreate = batch.will_create;
  const createsSomething =
    willCreate.categories.length + willCreate.vendors.length + willCreate.locations.length > 0;
  const categoryNames = (categories.data ?? []).map((c) => c.name);

  return (
    <div>
      <div className="page-header">
        <h1>Review Import</h1>
        <div className="page-actions">
          <Link className="btn-secondary" to="/inventory-import">
            Back to Imports
          </Link>
        </div>
      </div>
      <p className="page-subtitle">
        {batch.source_name ?? "Untitled import"} · {INTAKE_SOURCE_LABELS[batch.source_kind]} ·{" "}
        {new Date(batch.created_at).toLocaleString()} <StatusBadge status={batch.status} />
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {result && (
        <div className={result.failed > 0 ? "alert alert-warn" : "alert alert-success"}>
          {describeResult(result)}{" "}
          {result.committed > 0 && <Link to="/inventory">See inventory</Link>}
        </div>
      )}

      {batch.parser_notes && (
        <div className="alert alert-info">
          <strong>Worth knowing about this source:</strong> {batch.parser_notes}
        </div>
      )}

      <section className="detail-section">
        <h2>Where this stands</h2>
        <div className="form-card">
          <p>
            <strong>{counts.ready}</strong> ready to save · <strong>{counts.needsReview}</strong>{" "}
            needing something · <strong>{counts.committed}</strong> already saved ·{" "}
            <strong>{counts.skipped}</strong> skipped
          </p>
          {counts.needsReview > 0 && (
            <p className="page-subtitle">
              Rows marked <em>needed</em> are missing something required. Fill those in, or skip the
              rows you don't want — you can save the ready ones either way and come back to the rest.
            </p>
          )}

          {createsSomething && (
            <div className="alert alert-info">
              Saving will also create:
              {willCreate.categories.length > 0 && (
                <div>
                  New categories: <strong>{willCreate.categories.join(", ")}</strong>
                </div>
              )}
              {willCreate.vendors.length > 0 && (
                <div>
                  New vendors: <strong>{willCreate.vendors.join(", ")}</strong>
                </div>
              )}
              {willCreate.locations.length > 0 && (
                <div>
                  New locations: <strong>{willCreate.locations.join(", ")}</strong>
                </div>
              )}
              <div className="page-subtitle">
                If any of those are a misspelling of something you already have, fix the spelling on
                the row first so it matches instead of creating a duplicate.
              </div>
            </div>
          )}

          <div className="maintenance-row">
            <button className="btn-primary" onClick={handleCommit} disabled={busy || counts.ready === 0}>
              {busy ? "Working..." : `Save ${counts.ready} Item${counts.ready === 1 ? "" : "s"} to Inventory`}
            </button>
            {batch.status !== "discarded" && (
              <button className="btn-secondary" onClick={handleDiscard} disabled={busy}>
                Discard Import
              </button>
            )}
            {batch.raw_text && (
              <button className="btn-secondary" onClick={() => setShowSource(!showSource)}>
                {showSource ? "Hide original source" : "Show original source"}
              </button>
            )}
          </div>

          {showSource && batch.raw_text && <pre className="code-block">{batch.raw_text}</pre>}
        </div>
      </section>

      {batch.rows.some((r) => r.status !== "committed") && (
        <section className="detail-section">
          <h2>Fill in for every row</h2>
          <div className="form-card">
            <p className="page-subtitle">
              Handy when a source leaves out something that was obvious in context — the date, who
              it came from, or where it's stored. Applies to every row that isn't already saved.
            </p>
            <div className="line-row">
              <label>
                Date received
                <input
                  type="date"
                  value={bulk.received_date}
                  onChange={(e) => setBulk({ ...bulk, received_date: e.target.value })}
                />
              </label>
              <label>
                Vendor
                <input
                  value={bulk.vendor_name}
                  onChange={(e) => setBulk({ ...bulk, vendor_name: e.target.value })}
                />
              </label>
              <label>
                Storage location
                <input
                  value={bulk.location_name}
                  onChange={(e) => setBulk({ ...bulk, location_name: e.target.value })}
                />
              </label>
              <label>
                Category
                <input
                  list="bulk-categories"
                  value={bulk.category_name}
                  onChange={(e) => setBulk({ ...bulk, category_name: e.target.value })}
                />
                <datalist id="bulk-categories">
                  {categoryNames.map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
              </label>
              <label>
                Unit
                <select
                  value={bulk.unit_type}
                  onChange={(e) => setBulk({ ...bulk, unit_type: e.target.value })}
                >
                  <option value="">Leave as is</option>
                  {UNIT_TYPES.map((unit) => (
                    <option key={unit} value={unit}>
                      {unit}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="maintenance-row">
              <button className="btn-secondary" onClick={applyBulk} disabled={busy}>
                Apply to All Rows
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="detail-section">
        <h2>Items found ({batch.rows.length})</h2>
        {batch.rows.length === 0 && (
          <EmptyState label="The reader didn't find any inventory items in this source. Try a clearer source, or add the items by hand." />
        )}
        {batch.rows.map((row) => (
          <IntakeRowCard
            key={row.id}
            row={row}
            categories={categoryNames}
            onChanged={handleRowChanged}
            onError={setError}
          />
        ))}
      </section>
    </div>
  );
}
