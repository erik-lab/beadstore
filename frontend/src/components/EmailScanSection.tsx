import { Link } from "react-router-dom";
import type { EmailScanState } from "../lib/useEmailScan";

/** Renders the results table and email-view modal for one account's scan. */
export function EmailScanSection({ scan }: { scan: EmailScanState }) {
  const { account, results, error, busyId, viewing, recordedIds, viewEmail, recordOrder, closeViewing } = scan;
  const providerLabel = account.provider === "gmail" ? "Gmail" : "Outlook";

  return (
    <div>
      {error && <div className="alert alert-error">{error}</div>}

      {results && results.length === 0 && (
        <div className="alert alert-success">
          {providerLabel} scan complete — no likely order-confirmation emails found in the last 6 months.
        </div>
      )}

      {results && results.length > 0 && (
        <>
          <p className="page-subtitle">
            Found {results.length} candidate email{results.length === 1 ? "" : "s"}:
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th>From</th>
                <th>Subject</th>
                <th>Date</th>
                <th>Why it matched</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {results.map((email) => (
                <tr key={email.id}>
                  <td>{email.from_address}</td>
                  <td>
                    {email.subject}
                    {email.snippet && (
                      <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>{email.snippet}</div>
                    )}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {email.date ? new Date(email.date).toLocaleDateString() : "—"}
                  </td>
                  <td>
                    {email.match_reasons.map((reason) => (
                      <div key={reason} className="badge tone-info" style={{ marginRight: 4 }}>
                        {reason}
                      </div>
                    ))}
                  </td>
                  <td>
                    <div className="maintenance-row">
                      <button className="btn-secondary" onClick={() => viewEmail(email)} disabled={busyId !== null}>
                        {busyId === email.id ? "..." : "View"}
                      </button>
                      {recordedIds[email.id] ? (
                        <Link className="btn-secondary" to={`/purchase-orders/${recordedIds[email.id]}`}>
                          View Order
                        </Link>
                      ) : (
                        <button
                          className="btn-primary"
                          onClick={() => recordOrder(email)}
                          disabled={busyId !== null}
                        >
                          {busyId === email.id ? "Working..." : "Record Order"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {viewing && (
        <div className="modal-overlay" onClick={closeViewing}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{viewing.subject || "(no subject)"}</h2>
              <button className="btn-secondary" onClick={closeViewing}>
                Close
              </button>
            </div>
            <dl className="detail-grid">
              <dt>From</dt>
              <dd>{viewing.from_address || "—"}</dd>
              <dt>To</dt>
              <dd>{viewing.to_address || "—"}</dd>
              <dt>Date</dt>
              <dd>{viewing.date || "—"}</dd>
            </dl>
            <div className="modal-body">{viewing.body_text || "(no readable content)"}</div>
          </div>
        </div>
      )}
    </div>
  );
}
