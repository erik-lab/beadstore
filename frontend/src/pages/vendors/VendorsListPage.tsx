import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Vendor } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function VendorsListPage() {
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors"), []);

  return (
    <div>
      <div className="page-header">
        <h1>Vendors</h1>
        <Link className="btn-primary" to="/vendors/new">
          + New Vendor
        </Link>
      </div>

      {vendors.loading && <Loading />}
      {vendors.error && <ErrorState message={vendors.error} />}
      {vendors.data && vendors.data.length === 0 && <EmptyState label="No vendors yet." />}
      {vendors.data && vendors.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Contact</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {vendors.data.map((v) => (
              <tr key={v.id}>
                <td>
                  <Link to={`/vendors/${v.id}`}>{v.name}</Link>
                </td>
                <td>{v.contact_name ?? "—"}</td>
                <td>
                  <StatusBadge status={v.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
