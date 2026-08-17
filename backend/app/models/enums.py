import enum


class UnitType(str, enum.Enum):
    strand = "strand"
    container = "container"
    bag = "bag"
    tube = "tube"
    count = "count"
    gram = "gram"
    ounce = "ounce"
    piece = "piece"
    pair = "pair"
    set = "set"
    unknown = "unknown"
    other = "other"
    lot = "lot"


class ActiveArchivedStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class CatalogListingStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    published = "published"
    retired = "retired"
    archived = "archived"


class AvailableQuantityMode(str, enum.Enum):
    manual = "manual"
    derived_from_inventory = "derived_from_inventory"
    not_tracked = "not_tracked"


class PublishReadiness(str, enum.Enum):
    missing_photos = "missing_photos"
    needs_pricing = "needs_pricing"
    needs_description = "needs_description"
    ready = "ready"


class InventoryUnitStatus(str, enum.Enum):
    available = "available"
    reserved = "reserved"
    depleted = "depleted"
    damaged = "damaged"
    unresolved = "unresolved"
    archived = "archived"


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"  # UI label: "Ordered"
    partially_received = "partially_received"
    received = "received"
    closed = "closed"
    cancelled = "cancelled"


class PurchaseOrderLineStatus(str, enum.Enum):
    expected = "expected"
    partially_received = "partially_received"
    received = "received"
    discrepancy = "discrepancy"
    cancelled = "cancelled"


class ReceivingStatus(str, enum.Enum):
    matched = "matched"
    overage = "overage"
    shortage = "shortage"
    substitution = "substitution"
    damaged = "damaged"
    unresolved = "unresolved"


class InventoryAdjustmentType(str, enum.Enum):
    manual_correction = "manual_correction"
    damaged = "damaged"
    lost = "lost"
    count_correction = "count_correction"
    other = "other"
    consumed_in_piece = "consumed_in_piece"
    sold = "sold"


class ImageStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    available = "available"


class EmailProvider(str, enum.Enum):
    gmail = "gmail"
    outlook = "outlook"


class EmailAccountStatus(str, enum.Enum):
    active = "active"
    # The stored refresh token was rejected on last use (revoked access,
    # expired grant, password change, etc.) — needs the user to reconnect.
    needs_reauth = "needs_reauth"


class ProductSourceType(str, enum.Enum):
    # How a product enters inventory in the first place: bought from a
    # vendor (the default, existing behavior) vs. assembled in-house from
    # other products via a PieceCreation. Purely for filtering/reporting —
    # doesn't change how the product itself behaves once it exists. Named
    # distinctly from Product.origin (that column is the free-text
    # geographic/material origin attribute, e.g. "Czech Republic").
    purchased = "purchased"
    assembled = "assembled"


class PieceCostSource(str, enum.Enum):
    manual = "manual"
    estimated_from_components = "estimated_from_components"


class PieceCreationStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"


class ApiClientKind(str, enum.Enum):
    # Which "face" of the API this credential is for — see
    # docs/design/api-tiers-work-plan.md. `internal` is unused today (staff
    # auth is Supabase, not an API key) but reserved for a future
    # machine-to-machine internal integration.
    internal = "internal"
    storefront = "storefront"
    etsy = "etsy"


class ApiClientStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class SaleChannel(str, enum.Enum):
    manual = "manual"
    storefront = "storefront"
    etsy = "etsy"


class SaleStatus(str, enum.Enum):
    recorded = "recorded"
    cancelled = "cancelled"


class EtsyAccountStatus(str, enum.Enum):
    active = "active"
    needs_reauth = "needs_reauth"


class EtsySyncStatus(str, enum.Enum):
    not_synced = "not_synced"
    pending = "pending"
    synced = "synced"
    error = "error"
