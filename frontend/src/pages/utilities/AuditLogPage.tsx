import { Fragment, useState } from "react";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { AuditLogEntry, AuditLogPage as AuditLogPageData } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

const PAGE_SIZE = 50;

function formatChanges(entry: AuditLogEntry): string {
  try {
    const parsed = JSON.parse(entry.changes);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return entry.changes;
  }
}

export function AuditLogPage() {
  const [tableName, setTableName] = useState("");
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const tables = useFetch(() => api.get<string[]>("/audit-logs/tables"), []);
  const logs = useFetch(
    () =>
      api.get<AuditLogPageData>(
        `/audit-logs?limit=${PAGE_SIZE}&offset=${offset}${tableName ? `&table_name=${tableName}` : ""}`
      ),
    [tableName, offset]
  );

  function changeTable(value: string) {
    setTableName(value);
    setOffset(0);
    setExpandedId(null);
  }

  return (
    <div>
      <h1>Audit Log</h1>
      <p className="page-subtitle">
        Every create, edit, and delete made in the app, in order, with who made it. Click a row to
        see exactly what changed.
      </p>

      <div className="form-card" style={{ marginBottom: 16 }}>
        <label>
          Table
          <select value={tableName} onChange={(e) => changeTable(e.target.value)}>
            <option value="">All tables</option>
            {tables.data?.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>

      {logs.loading && <Loading />}
      {logs.error && <ErrorState message={logs.error} />}
      {logs.data && logs.data.items.length === 0 && <EmptyState label="No activity recorded yet." />}
      {logs.data && logs.data.items.length > 0 && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Table</th>
                <th>Action</th>
                <th>By</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {logs.data.items.map((entry) => (
                <Fragment key={entry.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                    <td>{entry.table_name}</td>
                    <td>
                      <StatusBadge status={entry.action} />
                    </td>
                    <td>{entry.actor_email ?? "—"}</td>
                    <td>{expandedId === entry.id ? "Hide" : "View"}</td>
                  </tr>
                  {expandedId === entry.id && (
                    <tr>
                      <td colSpan={5}>
                        <pre className="code-block">{formatChanges(entry)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>

          <div className="line-row" style={{ marginTop: 12 }}>
            <button
              className="btn-secondary"
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
            >
              Previous
            </button>
            <span className="page-subtitle">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, logs.data.total)} of {logs.data.total}
            </span>
            <button
              className="btn-secondary"
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= logs.data.total}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
