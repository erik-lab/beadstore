import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { ReceiptLine } from "../../lib/types";
import { describeItem } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function DiscrepanciesPage() {
  const lines = useFetch(() => api.get<ReceiptLine[]>("/operations/receiving-discrepancies"), []);

  return (
    <div>
      <h1>Receiving Discrepancies</h1>
      <p className="page-subtitle">
        Received items that didn't cleanly match what was expected — shortages, overages, damaged
        items, substitutions, or items still needing a product match.
      </p>
      {lines.loading && <Loading />}
      {lines.error && <ErrorState message={lines.error} />}
      {lines.data && lines.data.length === 0 && <EmptyState label="No receiving discrepancies." />}
      {lines.data && lines.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Vendor</th>
              <th>Received</th>
              <th>Received Qty</th>
              <th>Discrepancy</th>
              <th>Notes</th>
              <th>Supplier Order</th>
            </tr>
          </thead>
          <tbody>
            {lines.data.map((l) => (
              <tr key={l.id}>
                <td>{describeItem(l)}</td>
                <td>{l.vendor_name ?? "—"}</td>
                <td>{l.received_date ?? "—"}</td>
                <td>
                  {l.received_quantity} {l.received_unit_type}
                </td>
                <td>
                  <StatusBadge status={l.receiving_status} />
                </td>
                <td>{l.discrepancy_notes ?? "—"}</td>
                <td>
                  {l.purchase_order_id ? (
                    <Link to={`/purchase-orders/${l.purchase_order_id}`}>View order</Link>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
