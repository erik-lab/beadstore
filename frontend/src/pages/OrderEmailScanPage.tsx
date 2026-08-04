import { api } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { Vendor } from "../lib/types";
import { gmailAdapter } from "../lib/gmailScan";
import { outlookAdapter } from "../lib/outlookScan";
import { EmailScanSection } from "../components/EmailScanSection";

export function OrderEmailScanPage() {
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors"), []);

  return (
    <div>
      <h1>Order Email Scan</h1>
      <p className="page-subtitle">
        Scan a connected email account for supplier order confirmations and turn them into
        supplier orders.
      </p>

      <EmailScanSection adapter={gmailAdapter} vendors={vendors.data ?? []} reloadVendors={vendors.reload} />
      <EmailScanSection adapter={outlookAdapter} vendors={vendors.data ?? []} reloadVendors={vendors.reload} />
    </div>
  );
}
