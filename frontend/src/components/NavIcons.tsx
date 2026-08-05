// Small monochrome outline icons for the sidebar nav — plain SVG (no icon
// library) so they inherit the link's text color in both light and dark
// themes via currentColor.
const ICON_PROPS = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function DashboardIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6 10v9h5v-5h2v5h5v-9" />
    </svg>
  );
}

export function ProductsIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M4 7l8-4 8 4-8 4-8-4z" />
      <path d="M4 7v10l8 4 8-4V7" />
      <path d="M12 11v10" />
    </svg>
  );
}

export function CatalogIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M20 13 13 20a2 2 0 0 1-2.8 0L4 13.8V5a1 1 0 0 1 1-1h8.8L20 10.2a2 2 0 0 1 0 2.8z" />
      <circle cx="8.5" cy="8.5" r="1.2" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function InventoryIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3 3 8l9 5 9-5-9-5z" />
      <path d="M3 12l9 5 9-5" />
      <path d="M3 16l9 5 9-5" />
    </svg>
  );
}

export function VendorsIcon() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <circle cx="17" cy="9" r="2.3" />
      <path d="M15.3 14.2a5 5 0 0 1 5.5 5" />
    </svg>
  );
}

export function OrdersIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="6" y="4" width="12" height="17" rx="1.5" />
      <path d="M9 3h6v3H9z" />
      <path d="M9 11h6M9 15h6M9 8h6" />
    </svg>
  );
}

export function ReceiveIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="1.5" y="7" width="12.5" height="9" rx="1" />
      <path d="M14 10h4l3 3v3h-7z" />
      <circle cx="6.5" cy="18" r="1.6" />
      <circle cx="17.5" cy="18" r="1.6" />
    </svg>
  );
}

export function MailIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 6.5l9 6.5 9-6.5" />
    </svg>
  );
}

export function LocationsIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 21s7-6.6 7-11.5A7 7 0 0 0 5 9.5C5 14.4 12 21 12 21z" />
      <circle cx="12" cy="9.5" r="2.3" />
    </svg>
  );
}

export function UtilitiesIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-2-2z" />
    </svg>
  );
}

export function SettingsIcon() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v3.2M12 17.8V21M4.2 4.2l2.3 2.3M17.5 17.5l2.3 2.3M3 12h3.2M17.8 12H21M4.2 19.8l2.3-2.3M17.5 6.5l2.3-2.3" />
    </svg>
  );
}
