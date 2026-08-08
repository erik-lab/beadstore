import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useProfile } from "../auth/ProfileContext";
import { api } from "../lib/apiClient";
import { useFetch } from "../lib/useFetch";
import type { Hint } from "../lib/types";
import { InfoHint } from "../components/InfoHint";
import { ToastHost } from "../components/ToastHost";
import { Avatar } from "../components/Avatar";
import {
  CatalogIcon,
  DashboardIcon,
  InventoryIcon,
  MailIcon,
  OrdersIcon,
  PieceIcon,
  ProductsIcon,
  ReceiveIcon,
  SettingsIcon,
  UtilitiesIcon,
  VendorsIcon,
} from "../components/NavIcons";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true, hintKey: "dashboard", icon: DashboardIcon },
  { to: "/products", label: "Products", hintKey: "products", icon: ProductsIcon },
  { to: "/catalog-listings", label: "Catalog Listings", hintKey: "catalog-listings", icon: CatalogIcon },
  { to: "/inventory", label: "Inventory Units", hintKey: "inventory", icon: InventoryIcon },
  { to: "/pieces", label: "Piece Creations", hintKey: "pieces", icon: PieceIcon },
  { to: "/vendors", label: "Vendors", hintKey: "vendors", icon: VendorsIcon },
  { to: "/purchase-orders", label: "Supplier Orders", hintKey: "purchase-orders", icon: OrdersIcon },
  { to: "/receiving/quick-receive", label: "Quick Receive", hintKey: "quick-receive", icon: ReceiveIcon },
  { to: "/order-email-scan", label: "Order Email Scan", hintKey: "order-email-scan", icon: MailIcon },
  { to: "/utilities", label: "Utilities", hintKey: "utilities", icon: UtilitiesIcon },
  { to: "/settings", label: "Settings", hintKey: "settings", icon: SettingsIcon },
];

export function Layout() {
  const { session, signOut } = useAuth();
  const { profile } = useProfile();
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
                <span className="nav-link-main">
                  <span className="nav-link-icon">
                    <item.icon />
                  </span>
                  {item.label}
                </span>
                <InfoHint text={hintFor(item.hintKey)} />
              </span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-account">
            <Avatar avatarDataUrl={profile?.avatar_data_url} email={session?.user.email} />
            <div className="user-email">{session?.user.email}</div>
          </div>
          <button className="btn-secondary" onClick={() => signOut()}>
            Log out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
      <ToastHost />
    </div>
  );
}
