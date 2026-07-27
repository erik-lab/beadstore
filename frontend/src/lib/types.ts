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

export type ActiveArchivedStatus = "active" | "archived";
export type InventoryUnitStatus = "available" | "reserved" | "depleted" | "damaged" | "unresolved" | "archived";
export type PurchaseOrderStatus = "draft" | "submitted" | "partially_received" | "received" | "closed" | "cancelled";
export type PurchaseOrderLineStatus = "expected" | "partially_received" | "received" | "discrepancy" | "cancelled";
export type ReceivingStatus = "matched" | "overage" | "shortage" | "substitution" | "damaged" | "unresolved";
export type CatalogListingStatus = "draft" | "ready" | "published" | "retired" | "archived";
export type AvailableQuantityMode = "manual" | "derived_from_inventory" | "not_tracked";
export type PublishReadiness = "missing_photos" | "needs_pricing" | "needs_description" | "ready";

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
  sku: string | null;
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
  status: ActiveArchivedStatus;
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
