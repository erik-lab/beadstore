import { Link } from "react-router-dom";
import { api } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { OperationsSummary } from "../lib/types";
import { Loading, ErrorState } from "../components/States";

const CARDS: { key: keyof OperationsSummary; label: string; to: string }[] = [
  { key: "active_products", label: "Active Products", to: "/products" },
  { key: "inventory_on_hand", label: "Inventory Units On Hand", to: "/operations/inventory-on-hand" },
  { key: "open_orders", label: "Open Supplier Orders", to: "/operations/open-orders" },
  { key: "unresolved_items", label: "Items Needing Product Match", to: "/operations/unresolved-items" },
  { key: "receiving_discrepancies", label: "Receiving Discrepancies", to: "/operations/receiving-discrepancies" },
  { key: "total_receipts", label: "Total Receipts Recorded", to: "/purchase-orders" },
];

export function DashboardPage() {
  const summary = useFetch(() => api.get<OperationsSummary>("/operations/summary"), []);

  return (
    <div>
      <h1>Dashboard</h1>
      {summary.loading && <Loading />}
      {summary.error && <ErrorState message={summary.error} />}
      {summary.data && (
        <div className="card-grid">
          {CARDS.map((card) => (
            <Link key={card.key} to={card.to} className="stat-card">
              <div className="stat-value">{summary.data![card.key]}</div>
              <div className="stat-label">{card.label}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
