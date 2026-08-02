import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { PurchaseOrder, Vendor } from "../lib/types";
import {
  scanGmailForOrderEmails,
  fetchEmailDetail,
  type CandidateEmail,
  type EmailDetail,
} from "../lib/gmailScan";
import { parseOrderEmail } from "../lib/orderEmailParse";

const CLIENT_ID = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ?? "";

export function OrderEmailScanPage() {
  const navigate = useNavigate();
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors"), []);

  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<CandidateEmail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Per-row busy state ("view" or "record" in flight) keyed by message id.
  const [busyId, setBusyId] = useState<string | null>(null);
  const [viewing, setViewing] = useState<EmailDetail | null>(null);
  const [recordedIds, setRecordedIds] = useState<Record<string, string>>({});

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

  async function viewEmail(email: CandidateEmail) {
    setError(null);
    setBusyId(email.id);
    try {
      setViewing(await fetchEmailDetail(CLIENT_ID, email.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the email.");
    } finally {
      setBusyId(null);
    }
  }

  async function recordOrder(email: CandidateEmail) {
    setError(null);
    setBusyId(email.id);
    try {
      const detail = await fetchEmailDetail(CLIENT_ID, email.id);
      const parsed = parseOrderEmail(detail, vendors.data ?? []);

      // Find or create the vendor.
      let vendorId = parsed.vendorMatch?.id;
      if (!vendorId) {
        const name = parsed.suggestedVendorName;
        const existing = (vendors.data ?? []).find(
          (v) => v.name.trim().toLowerCase() === name.trim().toLowerCase()
        );
        if (existing) {
          vendorId = existing.id;
        } else {
          const created = await api.post<Vendor>("/vendors", {
            name,
            notes: "Created automatically from an order email scan.",
          });
          vendorId = created.id;
          vendors.reload();
        }
      }

      // Parsed line items; if nothing could be read, fall back to one line
      // from the subject so the order is still created and fixable by hand.
      const lines =
        parsed.lines.length > 0
          ? parsed.lines.map((line) => ({
              expected_item_description: line.description,
              expected_quantity: line.quantity,
              expected_unit_type: "unknown",
              unit_cost: line.unitCost,
            }))
          : [
              {
                expected_item_description: `(from email) ${detail.subject}`.slice(0, 300),
                expected_quantity: null,
                expected_unit_type: "unknown",
                unit_cost: null,
              },
            ];

      const order = await api.post<PurchaseOrder>("/purchase-orders", {
        vendor_id: vendorId,
        order_date: parsed.orderDate,
        notes: `Created from Gmail scan.\nEmail: "${detail.subject}" from ${detail.from} on ${detail.date}.${
          parsed.lines.length === 0
            ? "\nNo line items could be read from the email — please edit the order lines."
            : ""
        }`,
        lines,
      });

      setRecordedIds((prev) => ({ ...prev, [email.id]: order.id }));
      navigate(`/purchase-orders/${order.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? String(err.detail)
          : err instanceof Error
            ? err.message
            : "Could not record the order."
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1>Order Email Scan</h1>
      <p className="page-subtitle">
        Scans your Gmail inbox (last ~6 months) for emails that look like bead-supply order
        confirmations — from your known vendors or mentioning bead-related terms. Use View to read
        an email, or Record Order to turn it into a supplier order (best-effort parsing — review
        the created order and fix anything it misread). The Gmail connection isn't remembered;
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
                <th></th>
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
                  <td>
                    <div className="maintenance-row">
                      <button
                        className="btn-secondary"
                        onClick={() => viewEmail(email)}
                        disabled={busyId !== null}
                      >
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
        <div className="modal-overlay" onClick={() => setViewing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{viewing.subject || "(no subject)"}</h2>
              <button className="btn-secondary" onClick={() => setViewing(null)}>
                Close
              </button>
            </div>
            <dl className="detail-grid">
              <dt>From</dt>
              <dd>{viewing.from || "—"}</dd>
              <dt>To</dt>
              <dd>{viewing.to || "—"}</dd>
              <dt>Date</dt>
              <dd>{viewing.date || "—"}</dd>
            </dl>
            <div className="modal-body">{viewing.bodyText || "(no readable content)"}</div>
          </div>
        </div>
      )}
    </div>
  );
}
