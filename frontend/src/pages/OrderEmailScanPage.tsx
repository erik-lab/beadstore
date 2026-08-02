import { useState } from "react";
import { api } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { Vendor } from "../lib/types";
import { scanGmailForOrderEmails, type CandidateEmail } from "../lib/gmailScan";

const CLIENT_ID = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ?? "";

export function OrderEmailScanPage() {
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors"), []);

  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<CandidateEmail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runScan() {
    setError(null);
    setScanning(true);
    setResults(null);
    try {
      const vendorNames = (vendors.data ?? []).map((v) => v.name);
      const candidates = await scanGmailForOrderEmails(CLIENT_ID, vendorNames);
      setResults(candidates);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The Gmail scan failed. Please try again.");
    } finally {
      setScanning(false);
    }
  }

  return (
    <div>
      <h1>Order Email Scan</h1>
      <p className="page-subtitle">
        Scans your Gmail inbox (last ~6 months) for emails that look like bead-supply order
        confirmations — from your known vendors or mentioning bead-related terms. This is a
        prototype: it only lists candidates, and it doesn't remember the Gmail connection, so
        you'll re-authorize each time you scan.
      </p>

      {!CLIENT_ID && (
        <div className="alert alert-warn">
          Gmail scanning isn't configured yet. An administrator needs to set the{" "}
          <code>VITE_GOOGLE_CLIENT_ID</code> environment variable to a Google OAuth client ID (with
          this site as an authorized JavaScript origin) and redeploy.
        </div>
      )}

      <div className="form-actions line-row">
        <button className="btn-primary" onClick={runScan} disabled={scanning || !CLIENT_ID}>
          {scanning ? "Scanning..." : "Connect Gmail & Scan"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {results && results.length === 0 && (
        <div className="alert alert-success">
          Scan complete — no likely order-confirmation emails found in the last 6 months.
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
              </tr>
            </thead>
            <tbody>
              {results.map((email) => (
                <tr key={email.id}>
                  <td>{email.from}</td>
                  <td>
                    {email.subject}
                    {email.snippet && (
                      <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>
                        {email.snippet}
                      </div>
                    )}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {email.date ? new Date(email.date).toLocaleDateString() : "—"}
                  </td>
                  <td>
                    {email.matchReasons.map((reason) => (
                      <div key={reason} className="badge tone-info" style={{ marginRight: 4 }}>
                        {reason}
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
