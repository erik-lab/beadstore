import { useEffect, useState } from "react";
import { ApiError } from "../../lib/apiClient";
import { skipIntakeRow, updateIntakeRow } from "../../lib/inventoryIntake";
import {
  INTAKE_FIELD_LABELS,
  PRODUCT_ATTRIBUTE_FIELDS,
  UNIT_TYPES,
  type IntakeRow,
} from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";

/**
 * One draft row, editable in place.
 *
 * Edits save when a field loses focus rather than on every keystroke, and the
 * server's response replaces the row — so the gap flags and ready/needs-review
 * status shown here are always the server's own verdict on what a commit would
 * require, never a guess made in the browser.
 */

type Draft = {
  product_name: string;
  category_name: string;
  subtype_name: string;
  quantity: string;
  unit_type: string;
  unit_cost: string;
  vendor_name: string;
  location_name: string;
  received_date: string;
  sku: string;
  description: string;
  notes: string;
};

function toDraft(row: IntakeRow): Draft {
  return {
    product_name: row.product_name ?? "",
    category_name: row.category_name ?? "",
    subtype_name: row.subtype_name ?? "",
    quantity: row.quantity == null ? "" : String(row.quantity),
    unit_type: row.unit_type ?? "",
    unit_cost: row.unit_cost == null ? "" : String(row.unit_cost),
    vendor_name: row.vendor_name ?? "",
    location_name: row.location_name ?? "",
    received_date: row.received_date ?? "",
    sku: row.sku ?? "",
    description: row.description ?? "",
    notes: row.notes ?? "",
  };
}

const NUMBER_FIELDS = new Set<keyof Draft>(["quantity", "unit_cost"]);

/** Draft field -> the API field whose gap flag it clears. */
const GAP_FIELD: Partial<Record<keyof Draft, string>> = {
  product_name: "product_name",
  category_name: "category_name",
  quantity: "quantity",
  unit_type: "unit_type",
  received_date: "received_date",
};

const CONFIDENCE_NOTE: Record<IntakeRow["confidence"], string | null> = {
  high: null,
  medium: "Some of this was inferred — worth a glance.",
  low: "The source was vague here; check every field.",
};

export function IntakeRowCard({
  row,
  categories,
  onChanged,
  onError,
}: {
  row: IntakeRow;
  /** Existing category names, offered as suggestions. */
  categories: string[];
  onChanged: (row: IntakeRow) => void;
  onError: (message: string) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(row));
  const [attributes, setAttributes] = useState<Record<string, string>>(() => ({ ...row.attributes }));
  const [saving, setSaving] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  // Re-sync when the row changes underneath us — after a bulk fill or a
  // commit attempt, the server's version wins over local edits in progress.
  useEffect(() => {
    setDraft(toDraft(row));
    setAttributes({ ...row.attributes });
  }, [row]);

  const locked = row.status === "committed";
  const missing = new Set(row.missing_fields);

  async function save(changes: Record<string, unknown>) {
    setSaving(true);
    try {
      onChanged(await updateIntakeRow(row.id, changes));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Could not save that change.");
      // Put the inputs back to the last known-good server state so the screen
      // doesn't show an edit that wasn't stored.
      setDraft(toDraft(row));
      setAttributes({ ...row.attributes });
    } finally {
      setSaving(false);
    }
  }

  function commitField(field: keyof Draft) {
    const value = draft[field].trim();
    const original = toDraft(row)[field];
    if (value === original) return;

    if (NUMBER_FIELDS.has(field)) {
      if (value === "") {
        save({ [field]: null });
        return;
      }
      const parsed = Number(value);
      if (Number.isNaN(parsed) || parsed < 0) {
        onError(`"${value}" isn't a number ${field === "quantity" ? "of units" : "of dollars"}.`);
        setDraft(toDraft(row));
        return;
      }
      save({ [field]: parsed });
      return;
    }
    save({ [field]: value === "" ? null : value });
  }

  function commitAttributes() {
    const cleaned = Object.fromEntries(
      Object.entries(attributes)
        .map(([key, value]) => [key, value.trim()])
        .filter(([, value]) => value !== ""),
    );
    if (JSON.stringify(cleaned) === JSON.stringify(row.attributes)) return;
    save({ attributes: cleaned });
  }

  async function toggleSkip() {
    setSaving(true);
    try {
      onChanged(await skipIntakeRow(row.id, row.status !== "skipped"));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Could not change that row.");
    } finally {
      setSaving(false);
    }
  }

  function field(label: string, name: keyof Draft, extra?: { type?: string; step?: string }) {
    const isMissing = GAP_FIELD[name] ? missing.has(GAP_FIELD[name]!) : false;
    return (
      <label className={isMissing ? "field-needed" : undefined}>
        {label}
        {isMissing && <span className="badge tone-warn" style={{ marginLeft: 6 }}>needed</span>}
        <input
          type={extra?.type ?? "text"}
          step={extra?.step}
          value={draft[name]}
          disabled={locked || saving}
          onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
          onBlur={() => commitField(name)}
        />
      </label>
    );
  }

  const unusedAttributes = PRODUCT_ATTRIBUTE_FIELDS.filter((f) => !(f.key in attributes));
  const confidenceNote = CONFIDENCE_NOTE[row.confidence];

  return (
    <div className="form-card" style={row.status === "skipped" ? { opacity: 0.6 } : undefined}>
      <div className="page-header">
        <h3 style={{ margin: 0 }}>
          {draft.product_name || <em>Unnamed item</em>}
        </h3>
        <div className="maintenance-row">
          {saving && <span className="page-subtitle">Saving...</span>}
          <StatusBadge status={row.status} />
          {!locked && (
            <button className="btn-secondary" onClick={toggleSkip} disabled={saving}>
              {row.status === "skipped" ? "Include" : "Skip"}
            </button>
          )}
        </div>
      </div>

      {row.commit_error && (
        <div className="alert alert-error">Couldn't save this row: {row.commit_error}</div>
      )}

      {row.missing_fields.length > 0 && (
        <div className="alert alert-warn">
          Still needed: {row.missing_fields.map((f) => INTAKE_FIELD_LABELS[f] ?? f).join(", ")}
        </div>
      )}

      {row.matched_product_id && (
        <div className="alert alert-info">
          Adds stock to the existing product
          <strong> {row.matched_product_name ?? "already on file"}</strong> — no new product is created.
        </div>
      )}

      {confidenceNote && !locked && <p className="page-subtitle">{confidenceNote}</p>}
      {row.notes && <p className="page-subtitle">Note from the reader: {row.notes}</p>}

      <div className="line-row">
        {field("Item name", "product_name")}
        <label className={missing.has("category_name") ? "field-needed" : undefined}>
          Category
          {missing.has("category_name") && (
            <span className="badge tone-warn" style={{ marginLeft: 6 }}>needed</span>
          )}
          <input
            list={`intake-categories-${row.id}`}
            value={draft.category_name}
            disabled={locked || saving || Boolean(row.matched_product_id)}
            onChange={(e) => setDraft({ ...draft, category_name: e.target.value })}
            onBlur={() => commitField("category_name")}
          />
          <datalist id={`intake-categories-${row.id}`}>
            {categories.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </label>
        {field("Subtype", "subtype_name")}
      </div>

      <div className="line-row">
        {field("Quantity", "quantity", { type: "number", step: "0.001" })}
        <label className={missing.has("unit_type") ? "field-needed" : undefined}>
          Unit
          {missing.has("unit_type") && (
            <span className="badge tone-warn" style={{ marginLeft: 6 }}>needed</span>
          )}
          <select
            value={UNIT_TYPES.includes(draft.unit_type as never) ? draft.unit_type : ""}
            disabled={locked || saving}
            onChange={(e) => {
              setDraft({ ...draft, unit_type: e.target.value });
              save({ unit_type: e.target.value || null });
            }}
          >
            <option value="">Pick a unit...</option>
            {UNIT_TYPES.map((unit) => (
              <option key={unit} value={unit}>
                {unit}
              </option>
            ))}
          </select>
          {/* The reader's guess is kept visible when it isn't a real unit, so
              there's a hint about what the source actually said. */}
          {draft.unit_type && !UNIT_TYPES.includes(draft.unit_type as never) && (
            <span className="page-subtitle">Source said "{draft.unit_type}" — pick the closest match.</span>
          )}
        </label>
        {field("Cost per unit ($)", "unit_cost", { type: "number", step: "0.01" })}
        {field("Date received", "received_date", { type: "date" })}
      </div>

      <div className="line-row">
        {field("Vendor", "vendor_name")}
        {field("Storage location", "location_name")}
        {field("SKU / item code", "sku")}
      </div>

      <div className="maintenance-row">
        <button className="btn-secondary" onClick={() => setShowDetails(!showDetails)}>
          {showDetails ? "Hide details" : "Description, attributes & source"}
        </button>
      </div>

      {showDetails && (
        <>
          <label>
            Description
            <textarea
              rows={2}
              value={draft.description}
              disabled={locked || saving}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              onBlur={() => commitField("description")}
            />
          </label>

          <fieldset disabled={locked || saving}>
            <legend>Attributes</legend>
            {Object.keys(attributes).length === 0 && (
              <p className="page-subtitle">None picked up from the source.</p>
            )}
            <div className="line-row">
              {Object.entries(attributes).map(([key, value]) => (
                <label key={key}>
                  {PRODUCT_ATTRIBUTE_FIELDS.find((f) => f.key === key)?.label ?? key}
                  <input
                    value={value}
                    onChange={(e) => setAttributes({ ...attributes, [key]: e.target.value })}
                    onBlur={commitAttributes}
                  />
                </label>
              ))}
            </div>
            {unusedAttributes.length > 0 && (
              <label>
                Add an attribute
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) setAttributes({ ...attributes, [e.target.value]: "" });
                  }}
                >
                  <option value="">Pick one...</option>
                  {unusedAttributes.map((f) => (
                    <option key={String(f.key)} value={String(f.key)}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </fieldset>

          {row.raw_fragment && (
            <div>
              <strong>From the source:</strong>
              <pre className="page-subtitle" style={{ whiteSpace: "pre-wrap", margin: "4px 0 0" }}>
                {row.raw_fragment}
              </pre>
            </div>
          )}

          {locked && row.created_inventory_unit_id && (
            <p className="page-subtitle">
              Saved as inventory — open it from the{" "}
              <a href={`/inventory/${row.created_inventory_unit_id}`}>inventory unit</a> page.
            </p>
          )}
        </>
      )}
    </div>
  );
}
