"""Role-based permission system."""

from enum import StrEnum
from functools import cache


class Permission(StrEnum):
    VIEW_COSTS = "view_costs"
    EXPORT_FINANCIAL_REPORTS = "export_financial_reports"
    RESOLVE_CRITICAL_ALERTS = "resolve_critical_alerts"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_SUPPLIERS = "manage_suppliers"
    MANAGE_STOCK = "manage_stock"
    MANAGE_HACCP = "manage_haccp"
    MANAGE_EQUIPMENT = "manage_equipment"
    MANAGE_PURCHASE_LISTS = "manage_purchase_lists"
    EXPORT_HACCP_PDF = "export_haccp_pdf"
    RESOLVE_OPERATIONAL_ALERTS = "resolve_operational_alerts"
    MANAGE_MEMBERS = "manage_members"
    EDIT_RESTAURANT = "edit_restaurant"
    VIEW_BILLING = "view_billing"
    CONFIGURE_ALERTS = "configure_alerts"
    SOFT_DELETE = "soft_delete"


_OPERATIONAL: frozenset[Permission] = frozenset(
    {
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_SUPPLIERS,
        Permission.MANAGE_STOCK,
        Permission.MANAGE_HACCP,
        Permission.MANAGE_EQUIPMENT,
        Permission.MANAGE_PURCHASE_LISTS,
        Permission.EXPORT_HACCP_PDF,
        Permission.RESOLVE_OPERATIONAL_ALERTS,
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "manager": frozenset(
        {
            Permission.VIEW_COSTS,
            Permission.EXPORT_FINANCIAL_REPORTS,
            Permission.RESOLVE_CRITICAL_ALERTS,
        }
    )
    | _OPERATIONAL,
    "chef": _OPERATIONAL,
}


@cache
def get_permissions(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: Permission) -> bool:
    return permission in get_permissions(role)
