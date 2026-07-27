import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { ReceiptLine } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function DiscrepanciesPage() {
  const lines = useFetch(() => api.get<ReceiptLine[]>("/operations/receiving-discrepancies"), []);

  return (
    <div>
      <h1>Receiving Discrepancies</h1>
      {lines.loading && <Loading />}
      {lines.error && <ErrorState message={lines.error} />}
      {lines.data && lines.data.length === 0 && <EmptyState label="No receiving discrepancies." />}
      {lines.data && lines.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Received Qty</th>
              <th>Discrepancy</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {lines.data.map((l) => (
              <tr key={l.id}>
                <td>{l.unresolved_item_description ?? (l.product_id ? "Linked product" : "—")}</td>
                <td>
                  {l.received_quantity} {l.received_unit_type}
                </td>
                <td>
                  <StatusBadge status={l.receiving_status} />
                </td>
                <td>{l.discrepancy_notes ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
