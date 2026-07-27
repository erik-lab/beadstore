import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import type { Product, ProductCategory } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import { useSortableTable } from "../../lib/useSortableTable";

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

  const { sorted, toggleSort, indicator } = useSortableTable(products.data, [
    { key: "name", accessor: (p) => p.name },
    { key: "category_name", accessor: (p) => p.category_name },
    { key: "subtype_name", accessor: (p) => p.subtype_name },
    { key: "material", accessor: (p) => p.material },
    { key: "color", accessor: (p) => p.color },
    { key: "status", accessor: (p) => p.status },
  ]);

  return (
    <div>
      <div className="page-header">
        <h1>Products</h1>
        <Link className="btn-primary" to="/products/new">
          + New Product
        </Link>
      </div>

      <div className="filter-bar">
        <input placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)} />
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
      {sorted && sorted.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => toggleSort("name")}>
                Name{indicator("name")}
              </th>
              <th className="sortable" onClick={() => toggleSort("category_name")}>
                Category{indicator("category_name")}
              </th>
              <th className="sortable" onClick={() => toggleSort("subtype_name")}>
                Subtype{indicator("subtype_name")}
              </th>
              <th className="sortable" onClick={() => toggleSort("material")}>
                Material{indicator("material")}
              </th>
              <th className="sortable" onClick={() => toggleSort("color")}>
                Color{indicator("color")}
              </th>
              <th className="sortable" onClick={() => toggleSort("status")}>
                Status{indicator("status")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link to={`/products/${p.id}`}>{p.name}</Link>
                </td>
                <td>{p.category_name ?? "—"}</td>
                <td>{p.subtype_name ?? "—"}</td>
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
