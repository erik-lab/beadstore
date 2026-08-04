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
