import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { Hint } from "../lib/types";
import { InfoHint } from "../components/InfoHint";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true, hintKey: "dashboard" },
  { to: "/products", label: "Products", hintKey: "products" },
  { to: "/catalog-listings", label: "Catalog Listings", hintKey: "catalog-listings" },
  { to: "/inventory", label: "Inventory Units", hintKey: "inventory" },
  { to: "/vendors", label: "Vendors", hintKey: "vendors" },
  { to: "/purchase-orders", label: "Supplier Orders", hintKey: "purchase-orders" },
  { to: "/receiving/quick-receive", label: "Quick Receive", hintKey: "quick-receive" },
  { to: "/locations", label: "Locations", hintKey: "locations" },
  { to: "/utilities", label: "Utilities", hintKey: "utilities" },
];

export function Layout() {
  const { session, signOut } = useAuth();
  const hints = useFetch(() => api.get<Hint[]>("/hints?page=sidebar"), []);
  const hintFor = (key: string) => hints.data?.find((h) => h.item_key === key)?.text;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-title">Patti Back Office</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
              <span className="nav-link-label">
                {item.label}
                <InfoHint text={hintFor(item.hintKey)} />
              </span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-email">{session?.user.email}</div>
          <button className="btn-secondary" onClick={() => signOut()}>
            Log out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
