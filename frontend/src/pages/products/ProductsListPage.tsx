import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, ProductCategory } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

export function ProductsListPage() {
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");

  const categories = useFetch(() => api.get<ProductCategory[]>("/product-categories"), []);
  const products = useFetch(
    () =>
      api.get<Product[]>(
        `/products?${new URLSearchParams({
          ...(search ? { search } : {}),
          ...(categoryId ? { category_id: categoryId } : {}),
        }).toString()}`
      ),
    [search, categoryId]
  );

  return (
    <div>
      <div className="page-header">
        <h1>Products</h1>
        <Link className="btn-primary" to="/products/new">
          + New Product
        </Link>
      </div>

      <div className="filter-bar">
        <input placeholder="Search by name..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">All categories</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {products.loading && <Loading />}
      {products.error && <ErrorState message={products.error} />}
      {products.data && products.data.length === 0 && <EmptyState label="No products yet." />}
      {products.data && products.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Material</th>
              <th>Color</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {products.data.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link to={`/products/${p.id}`}>{p.name}</Link>
                </td>
                <td>{p.material ?? "—"}</td>
                <td>{p.color ?? "—"}</td>
                <td>
                  <StatusBadge status={p.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
