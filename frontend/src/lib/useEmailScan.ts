import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "./apiClient";
import type { CandidateEmail, EmailDetail, EmailProviderAdapter } from "./emailScanTypes";
import { loadScanState, saveScanState } from "./emailScanStore";
import { parseOrderEmail } from "./orderEmailParse";
import { showToast } from "./toastBus";
import type { PurchaseOrder, Vendor } from "./types";

export interface EmailScanState {
  adapter: EmailProviderAdapter;
  scanning: boolean;
  results: CandidateEmail[] | null;
  error: string | null;
  busyId: string | null;
  viewing: EmailDetail | null;
  recordedIds: Record<string, string>;
  runScan: () => Promise<void>;
  viewEmail: (email: CandidateEmail) => Promise<void>;
  recordOrder: (email: CandidateEmail) => Promise<void>;
  closeViewing: () => void;
}

/** All scan/view/record state and actions for one email provider adapter. */
export function useEmailScan(adapter: EmailProviderAdapter, vendors: Vendor[], reloadVendors: () => void): EmailScanState {
  const navigate = useNavigate();

  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<CandidateEmail[] | null>(() => loadScanState(adapter.id).results);
  const [error, setError] = useState<string | null>(null);

  // Per-row busy state ("view" or "record" in flight) keyed by message id.
  const [busyId, setBusyId] = useState<string | null>(null);
  const [viewing, setViewing] = useState<EmailDetail | null>(null);
  const [recordedIds, setRecordedIds] = useState<Record<string, string>>(
    () => loadScanState(adapter.id).recordedIds
  );

  // Kept in sessionStorage (not persisted across the scan/error/busy states,
  // which are meaningless once you've navigated away) so leaving Order Email
  // Scan and coming back still shows the same candidate list.
  useEffect(() => {
    saveScanState(adapter.id, { results, recordedIds });
  }, [adapter.id, results, recordedIds]);

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

  return {
    adapter,
    scanning,
    results,
    error,
    busyId,
    viewing,
    recordedIds,
    runScan,
    viewEmail,
    recordOrder,
    closeViewing: () => setViewing(null),
  };
}
