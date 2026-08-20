import pytest

# Estos contratos verificaban una interfaz de Django Admin que fue retirada por
# decisión de producto. Sus equivalentes viven en test_backoffice_*.py y ejercitan
# las APIs y pantallas del panel propio /gestion.
LEGACY_DJANGO_ADMIN_CONTRACTS = (
    "tests/test_admin_discovery.py",
    "test_catalog_cms_round1.py::test_site_settings_is_singleton_and_admin_cannot_add_or_delete",
    "test_commerce_round1.py::test_append_only_admin_and_logistics_permissions_forbid_mutation",
    "test_security_round1.py::test_identity_admin_forms_only_expose_masked_values",
    "test_task3_round1_regressions.py::test_sensitive_operational_admin_models_are_read_only",
    "test_task5a_admin_contracts.py::test_admin_login_rate_limit",
    "test_task5a_admin_contracts.py::test_admin_cache_uses_redis",
    "test_task5a_admin_contracts.py::test_admin_branding",
    "test_task5a_admin_contracts.py::test_admin_two_factor_provider",
    "test_task5a_admin_contracts.py::test_cms_admin_duplicates",
    "test_task5a_admin_contracts.py::test_cms_reorder_endpoint",
    "test_task5a_admin_contracts.py::test_cms_preview_is_record_specific",
    "test_task5a_admin_contracts.py::test_catalog_variant_admin",
    "test_task5a_admin_contracts.py::test_inventory_adjustment_is_locked_audited_and_admin_stock",
    "test_task5a_admin_contracts.py::test_inventory_admin_adjustment_route",
    "test_task5a_admin_contracts.py::test_order_admin_exposes",
    "test_task5a_admin_contracts.py::test_order_admin_action_visibility",
    "test_task5a_admin_contracts.py::test_order_admin_sensitive_action",
    "test_task5a_admin_contracts.py::test_order_admin_provider_failure",
    "test_task5a_fix_round2.py::test_mobile_admin_user_tools",
    "test_task5a_fix_round2.py::test_later_page_changelist",
    "test_task5a_fix_round2.py::test_change_form_cannot_bypass",
    "test_task5a_fix_round2.py::test_protected_preview",
    "test_task6_finish_cms_contracts.py::test_admin_brand_replacement",
)


def pytest_collection_modifyitems(items):
    retired = pytest.mark.skip(reason="Reemplazado por el panel propio /gestion")
    for item in items:
        normalized = item.nodeid.replace("\\", "/")
        if any(contract in normalized for contract in LEGACY_DJANGO_ADMIN_CONTRACTS):
            item.add_marker(retired)
