"""Permission matrix regression tests. Must never regress."""
from app.core.permissions import Permission, has_permission


def test_owner_has_all_permissions():
    for perm in Permission:
        assert has_permission("owner", perm), f"Owner missing {perm}"


def test_manager_sees_costs():
    assert has_permission("manager", Permission.VIEW_COSTS)
    assert has_permission("manager", Permission.EXPORT_FINANCIAL_REPORTS)
    assert has_permission("manager", Permission.RESOLVE_CRITICAL_ALERTS)


def test_chef_cannot_see_costs():
    assert not has_permission("chef", Permission.VIEW_COSTS)
    assert not has_permission("chef", Permission.EXPORT_FINANCIAL_REPORTS)
    assert not has_permission("chef", Permission.RESOLVE_CRITICAL_ALERTS)


def test_chef_can_do_operations():
    assert has_permission("chef", Permission.MANAGE_STOCK)
    assert has_permission("chef", Permission.MANAGE_PRODUCTS)
    assert has_permission("chef", Permission.MANAGE_HACCP)
    assert has_permission("chef", Permission.EXPORT_HACCP_PDF)
    assert has_permission("chef", Permission.MANAGE_PURCHASE_LISTS)


def test_manager_can_do_operations():
    assert has_permission("manager", Permission.MANAGE_STOCK)
    assert has_permission("manager", Permission.MANAGE_PRODUCTS)
    assert has_permission("manager", Permission.EXPORT_HACCP_PDF)


def test_only_owner_manages_members():
    assert has_permission("owner", Permission.MANAGE_MEMBERS)
    assert not has_permission("manager", Permission.MANAGE_MEMBERS)
    assert not has_permission("chef", Permission.MANAGE_MEMBERS)


def test_only_owner_soft_deletes():
    assert has_permission("owner", Permission.SOFT_DELETE)
    assert not has_permission("manager", Permission.SOFT_DELETE)
    assert not has_permission("chef", Permission.SOFT_DELETE)


def test_only_owner_edits_restaurant():
    assert has_permission("owner", Permission.EDIT_RESTAURANT)
    assert not has_permission("manager", Permission.EDIT_RESTAURANT)
    assert not has_permission("chef", Permission.EDIT_RESTAURANT)


def test_only_owner_views_billing():
    assert has_permission("owner", Permission.VIEW_BILLING)
    assert not has_permission("manager", Permission.VIEW_BILLING)
    assert not has_permission("chef", Permission.VIEW_BILLING)


def test_unknown_role_has_no_permissions():
    for perm in Permission:
        assert not has_permission("unknown_role", perm)
