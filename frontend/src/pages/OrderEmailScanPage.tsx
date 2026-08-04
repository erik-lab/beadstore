import { api } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { Vendor } from "../lib/types";
import { gmailAdapter } from "../lib/gmailScan";
import { outlookAdapter } from "../lib/outlookScan";
import { useEmailScan } from "../lib/useEmailScan";
import { EmailScanSection } from "../components/EmailScanSection";

export function OrderEmailScanPage() {
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors"), []);
  const vendorList = vendors.data ?? [];

  const gmailScan = useEmailScan(gmailAdapter, vendorList, vendors.reload);
  const outlookScan = useEmailScan(outlookAdapter, vendorList, vendors.reload);

  return (
    <div>
      <h1>Order Email Scan</h1>

      <h2>What is this</h2>
      <p className="page-subtitle">
        Scans a connected email inbox (last ~6 months) for emails that look like bead-supply
        order confirmations — from your known vendors or mentioning bead-related terms. Use View
        to read an email, or Record Order to turn it into a supplier order. Record Order uses AI
        to read the order details and item list from the email body and any attached
        invoice/receipt (PDF or image) — review the created order and fix anything it misread.
        Once recorded, the email is moved out of the inbox into a folder created automatically the
        first time it's needed. Nothing about the email connection is remembered; you'll
        re-authorize each time you scan.
      </p>

      <div className="form-actions line-row">
        <button
          className="btn-primary"
          onClick={gmailScan.runScan}
          disabled={gmailScan.scanning || !gmailAdapter.configured}
        >
          {gmailScan.scanning ? "Scanning..." : "Connect Gmail & Scan"}
        </button>
        <button
          className="btn-primary"
          onClick={outlookScan.runScan}
          disabled={outlookScan.scanning || !outlookAdapter.configured}
        >
          {outlookScan.scanning ? "Scanning..." : "Connect Outlook & Scan"}
        </button>
      </div>

      <EmailScanSection scan={gmailScan} />
      <EmailScanSection scan={outlookScan} />
    </div>
  );
}
