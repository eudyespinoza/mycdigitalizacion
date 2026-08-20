import pytest
from django.db import connection

pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def test_catalog_and_management_performance_indexes_exist():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL indexes only")
    required = {
        "cat_prod_live_cat_idx",
        "cat_prod_live_brand_idx",
        "cat_prod_search_gin",
        "cat_prod_name_trgm",
        "cat_variant_sku_trgm",
        "comm_res_active_idx",
        "comm_order_mgmt_idx",
        "comm_promo_schedule_idx",
        "acct_user_email_trgm",
        "acct_prof_first_trgm",
        "acct_prof_last_trgm",
        "acct_prof_phone_trgm",
        "bo_audit_resource_idx",
        "land_hero_schedule_idx",
        "land_promo_schedule_idx",
        "land_popup_schedule_idx",
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
        existing = {row[0] for row in cursor.fetchall()}

    assert required <= existing


def test_pg_trgm_extension_is_available_for_fuzzy_search():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL extensions only")
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        assert cursor.fetchone() == (1,)
