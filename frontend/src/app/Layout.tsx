import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/products", label: "Products" },
  { to: "/catalog-listings", label: "Catalog Listings" },
  { to: "/inventory", label: "Inventory Units" },
  { to: "/vendors", label: "Vendors" },
  { to: "/purchase-orders", label: "Supplier Orders" },
  { to: "/receiving/quick-receive", label: "Quick Receive" },
  { to: "/locations", label: "Locations" },
];

export function Layout() {
  const { session, signOut } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-title">Patti Back Office</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
              {item.label}
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
