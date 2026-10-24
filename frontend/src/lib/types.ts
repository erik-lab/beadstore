export type UnitType =
  | "strand"
  | "container"
  | "bag"
  | "tube"
  | "count"
  | "gram"
  | "ounce"
  | "piece"
  | "pair"
  | "set"
  | "unknown"
  | "other"
  | "lot";

export type Theme = "system" | "light" | "dark";

export interface Profile {
  id: string;
  email: string;
  display_name: string | null;
  avatar_data_url: string | null;
  theme: Theme;
}

export type EmailProvider = "gmail" | "outlook";
export type EmailAccountStatus = "active" | "needs_reauth";

export interface EmailAccount {
  id: string;
  provider: EmailProvider;
  email_address: string;
  label: string | null;
  status: EmailAccountStatus;
  created_at: string;
}

export type ActiveArchivedStatus = "active" | "archived";
export type InventoryUnitStatus = "available" | "reserved" | "depleted" | "damaged" | "unresolved" | "archived";
export type PurchaseOrderStatus = "draft" | "submitted" | "partially_received" | "received" | "closed" | "cancelled";
export type PurchaseOrderLineStatus = "expected" | "partially_received" | "received" | "discrepancy" | "cancelled";
export type ReceivingStatus = "matched" | "overage" | "shortage" | "substitution" | "damaged" | "unresolved";
export type CatalogListingStatus = "draft" | "ready" | "published" | "retired" | "archived";
export type AvailableQuantityMode = "manual" | "derived_from_inventory" | "not_tracked";
export type PublishReadiness = "missing_photos" | "needs_pricing" | "needs_description" | "ready";
export type ProductSourceType = "purchased" | "assembled";
export type PieceCostSource = "manual" | "estimated_from_components";
export type PieceCreationStatus = "active" | "cancelled";
export type SaleChannel = "manual" | "storefront" | "etsy";
export type SaleStatus = "recorded" | "cancelled";

export interface SaleLine {
  id: string;
  sale_id: string;
  catalog_listing_id: string | null;
  product_id: string;
  product_name?: string | null;
  product_sku?: string | null;
  quantity: number;
  unit_price: number | null;
}

export interface Sale {
  id: string;
  channel: SaleChannel;
  external_order_id: string | null;
  sale_date: string;
  status: SaleStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SaleDetail extends Sale {
  lines: SaleLine[];
}

export type EtsyAccountStatus = "active" | "needs_reauth";
export type EtsySyncStatus = "not_synced" | "pending" | "synced" | "error";

export interface EtsyAccount {
  id: string;
  shop_id: string;
  shop_name: string | null;
  scopes: string;
  status: EtsyAccountStatus;
  created_at: string;
}

export interface EtsyListingSync {
  id: string;
  catalog_listing_id: string;
  etsy_shop_id: string;
  etsy_listing_id: string | null;
  sync_status: EtsySyncStatus;
  last_synced_at: string | null;
  last_error: string | null;
}

/**
 * A pickable Etsy-side value — shipping profile, return policy or taxonomy
 * category. The id is Etsy's own numeric id as a string; these can only come
 * from the connected shop, which is why they're fetched rather than typed.
 */
export interface EtsyOption {
  id: string;
  label: string;
}

export interface EtsyPullResult {
  created: number;
  skipped_unmapped: number;
  skipped_duplicate: number;
}

export interface ProductCategory {
  id: string;
  name: string;
}

export interface ProductSubtype {
  id: string;
  category_id: string;
  name: string;
}

export interface Vendor {
  id: string;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  notes: string | null;
  status: ActiveArchivedStatus;
}

export interface Product {
  id: string;
  name: string;
  category_id: string;
  category_name?: string | null;
  subtype_id: string | null;
  subtype_name?: string | null;
  custom_subtype?: string | null;
  description: string | null;
  /** The shop's own generated code — barcoded, sent to Etsy, never edited. */
  sku: string | null;
  /** Whatever the supplier calls it. Not unique; vendors reuse codes. */
  vendor_sku: string | null;
  material: string | null;
  color: string | null;
  size: string | null;
  shape: string | null;
  finish: string | null;
  hole_size: string | null;
  origin: string | null;
  strand_length: string | null;
  count: string | null;
  grade: string | null;
  condition: string | null;
  manufacturing_method: string | null;
  design_motif: string | null;
  hole_configuration: string | null;
  cut_style: string | null;
  status: ActiveArchivedStatus;
  source_type: ProductSourceType;
}

export type AuditAction = "create" | "update" | "delete";

export interface AuditLogEntry {
  id: string;
  table_name: string;
  record_id: string;
  action: AuditAction;
  changes: string;
  actor_id: string | null;
  actor_email: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface CatalogListing {
  id: string;
  product_id: string;
  title: string;
  short_description: string | null;
  listing_description: string | null;
  price: number | null;
  status: CatalogListingStatus;

  sales_unit: UnitType | null;
  quantity_per_listing: number | null;
  available_quantity_mode: AvailableQuantityMode;
  manual_available_quantity: number | null;
  derived_available_quantity?: number | null;

  category_override_id: string | null;
  category_override_name?: string | null;
  subtype_override: string | null;
  tags: string | null;
  collection_theme: string | null;

  featured: boolean;
  sort_order: number;

  seo_title: string | null;
  seo_description: string | null;
  listing_notes: string | null;
  publish_readiness: PublishReadiness | null;

  product_name?: string | null;
  product_description?: string | null;
  product_sku?: string | null;
}

export interface Location {
  id: string;
  name: string;
  description: string | null;
  parent_location_id: string | null;
  status: ActiveArchivedStatus;
}

export interface PieceComponent {
  id: string;
  inventory_unit_id: string;
  product_name: string | null;
  product_sku: string | null;
  quantity_used: number;
  unit_cost_at_use: number | null;
}

export interface PieceCreation {
  id: string;
  product_id: string;
  product_name: string | null;
  product_sku: string | null;
  created_date: string;
  quantity_produced: number;
  creation_cost: number | null;
  cost_source: PieceCostSource;
  status: PieceCreationStatus;
  resulting_inventory_unit_id: string | null;
  notes: string | null;
  components: PieceComponent[];
  created_at: string;
}

export interface InventoryUnit {
  id: string;
  product_id: string | null;
  product_name?: string | null;
  product_sku?: string | null;
  unresolved_description: string | null;
  quantity: number;
  unit_type: UnitType;
  status: InventoryUnitStatus;
  received_date: string;
  cost_amount: number | null;
  cost_currency: string | null;
  vendor_id: string | null;
  vendor_name?: string | null;
  purchase_order_id: string | null;
  receipt_line_id: string | null;
  receipt_received_date?: string | null;
  location_id: string | null;
  location_name?: string | null;
  notes: string | null;
}

export interface PurchaseOrderLine {
  id: string;
  purchase_order_id: string;
  product_id: string | null;
  product_name?: string | null;
  product_sku?: string | null;
  expected_item_description: string | null;
  expected_quantity: number | null;
  expected_unit_type: UnitType | null;
  unit_cost: number | null;
  status: PurchaseOrderLineStatus;
  order_date?: string | null;
  vendor_name?: string | null;
}

export interface PurchaseOrder {
  id: string;
  vendor_id: string;
  vendor_name?: string | null;
  status: PurchaseOrderStatus;
  order_date: string;
  expected_date: string | null;
  is_retroactive: boolean;
  notes: string | null;
  lines?: PurchaseOrderLine[];
}

export interface ReceiptLine {
  id: string;
  receipt_id: string;
  purchase_order_line_id: string | null;
  product_id: string | null;
  product_name?: string | null;
  product_sku?: string | null;
  unresolved_item_description: string | null;
  received_quantity: number;
  received_unit_type: UnitType;
  receiving_status: ReceivingStatus;
  discrepancy_notes: string | null;
  inventory_unit_id: string | null;
  location_id: string | null;
  location_name?: string | null;
  purchase_order_id?: string | null;
  received_date?: string | null;
  vendor_name?: string | null;
}

export interface Receipt {
  id: string;
  purchase_order_id: string;
  received_date: string;
  notes: string | null;
  lines: ReceiptLine[];
}

export interface ReceiveResult {
  receipt: Receipt;
  purchase_order_id: string;
  purchase_order_status: string;
  summary: Record<string, number>;
}

export interface Hint {
  id: string;
  page: string;
  item_key: string;
  text: string;
}

export interface OperationsSummary {
  active_products: number;
  inventory_on_hand: number;
  open_orders: number;
  unresolved_items: number;
  receiving_discrepancies: number;
  total_receipts: number;
}

export const UNIT_TYPES: UnitType[] = [
  "strand",
  "container",
  "bag",
  "tube",
  "count",
  "gram",
  "ounce",
  "piece",
  "pair",
  "set",
  "unknown",
  "other",
];

/**
 * The product attribute columns, in the order the product form shows them.
 * Shared so the product form and inventory import can't drift apart.
 */
export const PRODUCT_ATTRIBUTE_FIELDS: { key: keyof Product; label: string }[] = [
  { key: "material", label: "Material" },
  { key: "color", label: "Color" },
  { key: "size", label: "Size" },
  { key: "shape", label: "Shape" },
  { key: "finish", label: "Finish" },
  { key: "hole_size", label: "Hole Size" },
  { key: "origin", label: "Origin" },
  { key: "strand_length", label: "Strand Length" },
  { key: "count", label: "Count" },
  { key: "grade", label: "Grade" },
  { key: "condition", label: "Condition" },
  { key: "manufacturing_method", label: "Manufacturing Method" },
  { key: "design_motif", label: "Design Motif" },
  { key: "hole_configuration", label: "Hole Configuration" },
  { key: "cut_style", label: "Cut Style" },
];

export type IntakeSourceKind = "paste" | "spreadsheet" | "document" | "voice";
export type IntakeBatchStatus = "draft" | "committed" | "discarded";
export type IntakeRowStatus = "needs_review" | "ready" | "committed" | "skipped";
export type IntakeConfidence = "high" | "medium" | "low";
export type IntakeNameMatch = "existing" | "new" | "ambiguous";

/** How each match verdict is shown beside the field it describes. */
export const INTAKE_MATCH_DISPLAY: Record<
  IntakeNameMatch,
  { label: string; tone: string; title: string }
> = {
  existing: {
    label: "on file",
    tone: "tone-muted",
    title: "Matches something you already have — nothing new will be created.",
  },
  new: {
    label: "new",
    tone: "tone-warn",
    title:
      "Nothing on file matches this, so saving will create it. If it's a misspelling of something you already have, fix it here and the badge will change to “on file”.",
  },
  ambiguous: {
    label: "matches more than one",
    tone: "tone-bad",
    title:
      "This name matches more than one product, so it can't be matched automatically. Make the name specific, or change the category.",
  },
};

/** One proposed inventory record, staged for review before it's committed. */
export interface IntakeRow {
  id: string;
  batch_id: string;
  row_index: number;
  /** The snippet of the source this row came from, for checking a value. */
  raw_fragment: string | null;
  product_name: string | null;
  category_name: string | null;
  subtype_name: string | null;
  /** Set when this row tops up an existing product instead of creating one. */
  matched_product_id: string | null;
  matched_product_name: string | null;
  quantity: number | null;
  unit_type: string | null;
  unit_cost: number | null;
  vendor_name: string | null;
  location_name: string | null;
  received_date: string | null;
  sku: string | null;
  description: string | null;
  notes: string | null;
  attributes: Record<string, string>;
  /** Required fields still empty — computed server-side, never sent up. */
  missing_fields: string[];
  /**
   * Per-field verdict on whether a name lines up with master data already on
   * file, keyed by field name. Absent for a field that's blank. Lets the
   * review screen point at the row with the odd spelling, which the
   * batch-level `will_create` list can't.
   */
  name_matches: Record<string, IntakeNameMatch | undefined>;
  confidence: IntakeConfidence;
  status: IntakeRowStatus;
  commit_error: string | null;
  created_product_id: string | null;
  created_inventory_unit_id: string | null;
}

/** Master data that committing a batch would add, shown for confirmation. */
export interface IntakeNamesToCreate {
  categories: string[];
  vendors: string[];
  locations: string[];
  products: string[];
}

export interface IntakeBatch {
  id: string;
  source_kind: IntakeSourceKind;
  source_name: string | null;
  status: IntakeBatchStatus;
  parser_notes: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntakeBatchDetail extends IntakeBatch {
  raw_text: string | null;
  rows: IntakeRow[];
  will_create: IntakeNamesToCreate;
}

export interface IntakeCommitResult {
  batch_id: string;
  committed: number;
  failed: number;
  remaining: number;
  batch_status: IntakeBatchStatus;
}

export const INTAKE_SOURCE_LABELS: Record<IntakeSourceKind, string> = {
  paste: "Typed or pasted",
  spreadsheet: "Spreadsheet",
  document: "Document",
  voice: "Dictated",
};

/** Field names the server reports as gaps, in words Patti would use. */
export const INTAKE_FIELD_LABELS: Record<string, string> = {
  product_name: "Item name",
  category_name: "Category",
  quantity: "Quantity",
  unit_type: "Unit",
  received_date: "Date received",
};

export const PO_STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
  draft: "Draft",
  submitted: "Ordered",
  partially_received: "Partially Received",
  received: "Received",
  closed: "Closed",
  cancelled: "Cancelled",
};

/**
 * Human-readable label for anything that's either linked to a product or still a
 * free-text description ("unresolved") — used everywhere a list/detail view would
 * otherwise show a bare ID or the generic word "product".
 */
export function describeItem(item: {
  product_name?: string | null;
  product_sku?: string | null;
  unresolved_description?: string | null;
  expected_item_description?: string | null;
  unresolved_item_description?: string | null;
}): string {
  if (item.product_name) {
    return item.product_sku ? `${item.product_name} (SKU: ${item.product_sku})` : item.product_name;
  }
  const freeText = item.unresolved_description ?? item.expected_item_description ?? item.unresolved_item_description;
  return freeText ? `Unresolved: ${freeText}` : "Unresolved item";
}
