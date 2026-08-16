import { Link } from "react-router-dom";

const UTILITIES = [
  {
    to: "/utilities/hints",
    title: "Hints Maintenance",
    description: "Edit the info-icon blurbs shown throughout the app.",
  },
  {
    to: "/utilities/categories",
    title: "Product Categories",
    description: "Rename product categories and subtypes, or add new ones.",
  },
  {
    to: "/locations",
    title: "Locations",
    description: "Manage storage locations used for inventory units.",
  },
  {
    to: "/utilities/audit-log",
    title: "Audit Log",
    description: "See every create, edit, and delete made in the app, and who made it.",
  },
  {
    to: "/utilities/record-sale",
    title: "Record a Sale",
    description: "Testing tool: record a sale and see it decrement inventory. No frills.",
  },
];

export function UtilitiesPage() {
  return (
    <div>
      <h1>Utilities</h1>
      <p className="page-subtitle">Administrative tools for maintaining the app itself.</p>
      <div className="card-grid">
        {UTILITIES.map((item) => (
          <Link key={item.to} to={item.to} className="stat-card">
            <div className="stat-label" style={{ fontWeight: 600, color: "var(--text-h)", fontSize: 15 }}>
              {item.title}
            </div>
            <div className="stat-label">{item.description}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
