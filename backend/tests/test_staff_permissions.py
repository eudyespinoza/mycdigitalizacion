import pytest
from django.contrib.auth.models import Group


@pytest.mark.django_db
def test_staff_permission_groups_are_seeded_with_bounded_permissions():
    groups = {group.name: group for group in Group.objects.prefetch_related("permissions")}

    assert {"Owner", "Catalog", "Orders/Logistics", "Content"} <= groups.keys()
    assert groups["Owner"].permissions.filter(
        content_type__app_label="accounts", codename="view_customerprofile"
    ).exists()
    assert groups["Catalog"].permissions.filter(codename="change_product").exists()
    assert not groups["Catalog"].permissions.filter(codename="change_order").exists()
    assert groups["Orders/Logistics"].permissions.filter(codename="change_order").exists()
    assert groups["Content"].permissions.filter(codename="change_heroslide").exists()
