export interface HintLocation {
  page: string;
  itemKey: string;
  label: string;
}

// The exact (page, item_key) pairs the app actually looks up hints for.
// Keep this in sync with every InfoHint call site (Layout.tsx sidebar nav,
// etc.) — a hint saved under any other page/item combination will never be
// shown anywhere, no matter how it's worded.
export const HINT_LOCATIONS: HintLocation[] = [
  { page: "sidebar", itemKey: "dashboard", label: "Sidebar — Dashboard link" },
  { page: "sidebar", itemKey: "products", label: "Sidebar — Products link" },
  { page: "sidebar", itemKey: "catalog-listings", label: "Sidebar — Catalog Listings link" },
  { page: "sidebar", itemKey: "inventory", label: "Sidebar — Inventory Units link" },
  { page: "sidebar", itemKey: "pieces", label: "Sidebar — Piece Creations link" },
  { page: "sidebar", itemKey: "vendors", label: "Sidebar — Vendors link" },
  { page: "sidebar", itemKey: "purchase-orders", label: "Sidebar — Supplier Orders link" },
  { page: "sidebar", itemKey: "quick-receive", label: "Sidebar — Quick Receive link" },
  { page: "sidebar", itemKey: "order-email-scan", label: "Sidebar — Order Email Scan link" },
  { page: "sidebar", itemKey: "utilities", label: "Sidebar — Utilities link" },
  { page: "sidebar", itemKey: "settings", label: "Sidebar — Settings link" },
];

export function findHintLocation(page: string, itemKey: string): HintLocation | undefined {
  return HINT_LOCATIONS.find((loc) => loc.page === page && loc.itemKey === itemKey);
}
