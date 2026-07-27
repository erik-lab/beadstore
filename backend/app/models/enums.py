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
    retired = "retired"
    archived = "archived"


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


class ImageStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    available = "available"
