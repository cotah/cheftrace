"""Domain enums for ChefTrace — TEXT+CHECK pattern (not Postgres native enums)."""

from enum import StrEnum


class UnitKind(StrEnum):
    KG = "kg"
    G = "g"
    L = "l"
    ML = "ml"
    UNIT = "unit"


class MovementKind(StrEnum):
    RECEIVE = "receive"
    MANUAL_IN = "manual_in"
    MANUAL_OUT = "manual_out"
    ADJUSTMENT = "adjustment"
    DISCARD = "discard"
    CONSUME = "consume"


class LotStatus(StrEnum):
    ACTIVE = "active"
    DEPLETED = "depleted"
    EXPIRED = "expired"
    DISCARDED = "discarded"


class MovementSource(StrEnum):
    MANUAL = "manual"
    PURCHASE_LIST = "purchase_list"
    POS = "pos"
    OCR = "ocr"
    RECIPE = "recipe"


class AuditEntity(StrEnum):
    STOCK_LOT = "stock_lot"
    HACCP_TEMPLATE = "haccp_template"
    EQUIPMENT = "equipment"
    PRODUCT = "product"
    RECIPE = "recipe"
    POS_EVENT = "pos_event"


class AuditAction(StrEnum):
    EXPIRY_EDIT = "expiry_edit"
    TEMPLATE_CHANGE = "template_change"
    EQUIPMENT_CHANGE = "equipment_change"
    PRODUCT_CHANGE = "product_change"
    RECIPE_CHANGE = "recipe_change"
    POS_PROCESSED = "pos_processed"
    POS_DISMISSED = "pos_dismissed"


class ExpiryReason(StrEnum):
    TYPO = "typo"
    SUPPLIER_ERROR = "supplier_error"
    INSPECTION_FINDING = "inspection_finding"
    OTHER = "other"


class PurchaseListType(StrEnum):
    FOOD = "food"
    BEVERAGE = "beverage"
    NON_FOOD = "non_food"
    MIXED = "mixed"


class PurchaseListStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"


class PurchaseListItemStatus(StrEnum):
    PENDING = "pending"
    RECEIVED = "received"
    PARTIAL = "partial"
    NOT_RECEIVED = "not_received"


class InvoiceStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class InvoiceLineItemStatus(StrEnum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class POSProvider(StrEnum):
    SQUARE = "square"


class POSConfirmationMode(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"


class POSEventStatus(StrEnum):
    PENDING = "pending"
    NEEDS_MAPPING = "needs_mapping"
    PENDING_APPROVAL = "pending_approval"
    PROCESSED = "processed"
    INSUFFICIENT_STOCK = "insufficient_stock"
    FAILED = "failed"
    IGNORED = "ignored"
