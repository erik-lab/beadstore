import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/apiClient";
import type { CandidateEmail, EmailDetail, EmailProviderAdapter } from "../lib/emailScanTypes";
import { parseOrderEmail } from "../lib/orderEmailParse";
import { showToast } from "../lib/toastBus";
import type { PurchaseOrder, Vendor } from "../lib/types";

interface EmailScanSectionProps {
  adapter: EmailProviderAdapter;
  vendors: Vendor[];
  reloadVendors: () => void;
}

export function EmailScanSection({ adapter, vendors, reloadVendors }: EmailScanSectionProps) {
  const navigate = useNavigate();

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
      const vendorNames = vendors.map((v) => v.name);
      const candidates = await adapter.scanForOrderEmails(vendorNames);
      setResults(candidates);
    } catch (err) {
      setError(err instanceof Error ? err.message : `The ${adapter.label} scan failed. Please try again.`);
    } finally {
      setScanning(false);
    }
  }

  async function viewEmail(email: CandidateEmail) {
    setError(null);
    setBusyId(email.id);
    try {
      setViewing(await adapter.fetchEmailDetail(email.id));
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
      const detail = await adapter.fetchEmailDetail(email.id);
      const parsed = await parseOrderEmail(detail, vendors);

      // Find or create the vendor.
      let vendorId = parsed.vendorMatch?.id;
      if (!vendorId) {
        const name = parsed.suggestedVendorName;
        const existing = vendors.find((v) => v.name.trim().toLowerCase() === name.trim().toLowerCase());
        if (existing) {
          vendorId = existing.id;
        } else {
          const created = await api.post<Vendor>("/vendors", {
            name,
            notes: `Created automatically from an ${adapter.label} order email scan.`,
          });
          vendorId = created.id;
          reloadVendors();
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
        notes: `Created from ${adapter.label} scan (parsed ${parsed.parsedByAi ? "by AI" : "with basic pattern matching"}).\nEmail: "${detail.subject}" from ${detail.from} on ${detail.date}.${
          parsed.lines.length === 0
            ? "\nNo line items could be read from the email — please edit the order lines."
            : ""
        }`,
        lines,
      });

      setRecordedIds((prev) => ({ ...prev, [email.id]: order.id }));

      const moveResult = await adapter.moveEmailToOrdersFolder(email.id);
      if (!moveResult.moved) {
        showToast(moveResult.message, moveResult.reason === "permission" ? "warn" : "error");
      }

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
    <div className="detail-section">
      <h2>{adapter.label}</h2>
      <p className="page-subtitle">
        Scans your {adapter.label} inbox (last ~6 months) for emails that look like bead-supply
        order confirmations — from your known vendors or mentioning bead-related terms. Use View
        to read an email, or Record Order to turn it into a supplier order. Record Order uses AI
        to read the order details and item list from the email body and any attached
        invoice/receipt (PDF or image) — review the created order and fix anything it misread.
        Once recorded, the email is moved out of your inbox into a folder called &ldquo;
        {adapter.ordersFolderName}&rdquo; (created automatically the first time). The{" "}
        {adapter.label} connection isn't remembered; you'll re-authorize each time you scan.
      </p>

      {!adapter.configured && <div className="alert alert-warn">{adapter.notConfiguredMessage}</div>}

      <div className="form-actions line-row">
        <button className="btn-primary" onClick={runScan} disabled={scanning || !adapter.configured}>
          {scanning ? "Scanning..." : `Connect ${adapter.label} & Scan`}
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
                      <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>{email.snippet}</div>
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
