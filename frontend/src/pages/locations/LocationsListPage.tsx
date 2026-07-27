import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Location } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function LocationsListPage() {
  const locations = useFetch(() => api.get<Location[]>("/locations"), []);

  return (
    <div>
      <div className="page-header">
        <h1>Locations &amp; Containers</h1>
        <Link className="btn-primary" to="/locations/new">
          + New Location
        </Link>
      </div>

      {locations.loading && <Loading />}
      {locations.error && <ErrorState message={locations.error} />}
      {locations.data && locations.data.length === 0 && <EmptyState label="No locations set up yet." />}
      {locations.data && locations.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {locations.data.map((loc) => (
              <tr key={loc.id}>
                <td>{loc.name}</td>
                <td>{loc.description ?? "—"}</td>
                <td>
                  <StatusBadge status={loc.status} />
                </td>
                <td>
                  <Link to={`/locations/${loc.id}/edit`}>Edit</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
