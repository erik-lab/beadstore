import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import { cancelPieceCreation } from "../../lib/pieceCreations";
import type { PieceCreation } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function PieceCreationsListPage() {
  const pieces = useFetch(() => api.get<PieceCreation[]>("/piece-creations"), []);

  async function handleCancel(id: string) {
    if (!confirm("Cancel this piece creation? Any linked components will be returned to inventory.")) return;
    try {
      await cancelPieceCreation(id);
      pieces.reload();
    } catch (err) {
      alert(err instanceof ApiError ? String(err.detail) : "Could not cancel this piece creation.");
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Piece Creations</h1>
        <div className="page-actions">
          <Link className="btn-primary" to="/pieces/new">
            Create a Piece
          </Link>
        </div>
      </div>
      <p className="page-subtitle">
        Pieces you've made from materials in inventory, as opposed to items bought ready-made for resale.
      </p>

      {pieces.loading && <Loading />}
      {pieces.error && <ErrorState message={pieces.error} />}
      {pieces.data && pieces.data.length === 0 && <EmptyState label="No pieces recorded yet." />}
      {pieces.data && pieces.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Piece</th>
              <th>Date</th>
              <th>Qty</th>
              <th>Cost</th>
              <th>Components</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pieces.data.map((pc) => (
              <tr key={pc.id}>
                <td>{pc.product_name}</td>
                <td>{pc.created_date}</td>
                <td>{pc.quantity_produced}</td>
                <td>
                  {pc.creation_cost != null ? `$${pc.creation_cost.toFixed(2)}` : "—"}
                  {pc.cost_source === "estimated_from_components" && (
                    <span className="badge tone-info" style={{ marginLeft: 6 }}>
                      estimated
                    </span>
                  )}
                </td>
                <td>{pc.components.length}</td>
                <td>
                  <StatusBadge status={pc.status} />
                </td>
                <td>
                  {pc.status === "active" && (
                    <button className="btn-secondary" onClick={() => handleCancel(pc.id)}>
                      Cancel
                    </button>
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
