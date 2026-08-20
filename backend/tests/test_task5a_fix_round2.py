import re

import pytest
from django.test import override_settings

from tests.test_checkout_domain import make_transaction, valid_payment
from tests.test_commerce_domain import make_variant
from tests.test_commerce_round1 import pending_order
from tests.test_task5a_admin_contracts import image_upload


@pytest.mark.django_db
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
def test_mobile_admin_user_tools_render_semantic_groups_without_orphan_separators(
    client, django_user_model
):
    owner = django_user_model.objects.create_superuser(email="round2-mobile@example.test")
    client.force_login(owner)

    response = client.get("/admin/")

    body = response.content.decode()
    user_tools = body.split('<div id="user-tools">', 1)[1].split("</div>", 1)[0]
    assert response.status_code == 200
    assert 'class="myc-session"' in user_tools
    assert 'class="myc-user-links"' in user_tools
    assert "</strong>." not in user_tools
    visible_tokens = re.sub(r"<[^>]+>", " ", user_tools).split()
    assert "/" not in visible_tokens
    assert "." not in visible_tokens


@pytest.mark.django_db
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
def test_page_two_changelist_cannot_bypass_global_reorder_with_duplicate_zero(
    client, django_user_model
):
    from landing.models import HeroSlide

    editor = django_user_model.objects.create_superuser(email="round2-order@example.test")
    client.force_login(editor)
    slides = HeroSlide.objects.bulk_create(
        [HeroSlide(title=f"Slide {index}", order=index) for index in range(205)]
    )
    page_two_first = slides[100]

    response = client.post(
        "/admin/landing/heroslide/?p=1",
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(page_two_first.pk),
            "form-0-order": "0",
            "_save": "Guardar",
        },
    )

    page_two_first.refresh_from_db()
    assert response.status_code in {200, 302}
    assert page_two_first.order == 100
    assert HeroSlide.objects.filter(order=0).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("desktop_image", "mobile_image", "expected_img", "expected_mobile_source"),
    (
        ("landing/desktop/only.jpg", "", "/media/landing/desktop/only.jpg", False),
        ("", "landing/mobile/only.jpg", "/media/landing/mobile/only.jpg", True),
        (
            "landing/desktop/both.jpg",
            "landing/mobile/both.jpg",
            "/media/landing/desktop/both.jpg",
            True,
        ),
    ),
)
def test_protected_preview_always_has_visible_image_fallback_for_each_media_shape(
    client,
    django_user_model,
    desktop_image,
    mobile_image,
    expected_img,
    expected_mobile_source,
):
    from landing.models import HeroSlide

    viewer = django_user_model.objects.create_superuser(email="round2-preview@example.test")
    client.force_login(viewer)
    slide = HeroSlide.objects.create(
        title="Fallback visible",
        desktop_image=desktop_image,
        mobile_image=mobile_image,
        alt_text="Imagen con fallback",
        focal_x="21.50",
        focal_y="68.25",
        safe_height_mobile=280,
        safe_height_tablet=420,
        safe_height_desktop=560,
    )

    response = client.get(f"/admin/landing/heroslide/{slide.pk}/preview/")

    body = response.content.decode()
    assert response.status_code == 200
    assert f'<img src="{expected_img}" alt="Imagen con fallback">' in body
    assert ('media="(max-width: 767px)"' in body) is expected_mobile_source
    assert "--focal-x:21.50%;--focal-y:68.25%" in body
    assert "--height-mobile:280px;--height-tablet:420px;--height-desktop:560px" in body


def test_derivative_widths_stop_at_configured_cap_and_never_duplicate_full_source(tmp_path):
    from django.core.files.storage import FileSystemStorage

    from config.media import generate_image_derivatives

    storage = FileSystemStorage(location=tmp_path, base_url="/media/")
    source = storage.save("source.png", image_upload(size=(2000, 1000)))

    with override_settings(MEDIA_RESPONSIVE_WIDTHS=(320, 640, 960, 1440)):
        manifest = generate_image_derivatives(
            storage=storage,
            name=source,
            supported_formats={"WEBP"},
        )

    assert [entry["width"] for entry in manifest["widths"]] == [320, 640, 960, 1440]
    assert all(
        "-2000." not in path
        for entry in manifest["widths"]
        for path in entry.values()
        if isinstance(path, str)
    )


def test_derivative_storage_failure_removes_every_partial_write(tmp_path):
    from django.core.files.storage import FileSystemStorage

    from config.media import generate_image_derivatives

    class FailingSecondDerivativeStorage(FileSystemStorage):
        derivative_writes = 0

        def save(self, name, content, max_length=None):
            if name != "source.png":
                self.derivative_writes += 1
                if self.derivative_writes == 2:
                    raise OSError("synthetic storage failure")
            return super().save(name, content, max_length=max_length)

    storage = FailingSecondDerivativeStorage(location=tmp_path, base_url="/media/")
    source = storage.save("source.png", image_upload(size=(640, 360)))

    with override_settings(MEDIA_RESPONSIVE_WIDTHS=(320, 640)):
        with pytest.raises(OSError, match="synthetic storage failure"):
            generate_image_derivatives(
                storage=storage,
                name=source,
                supported_formats={"WEBP"},
            )

    assert sorted(path.name for path in tmp_path.rglob("*") if path.is_file()) == ["source.png"]


@pytest.mark.django_db
@pytest.mark.parametrize("media_kind", ("landing", "catalog"))
def test_image_replacement_rolls_back_database_and_storage_when_publication_fails(
    tmp_path, monkeypatch, media_kind
):
    storage_settings = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path), "base_url": "/media/"},
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    with override_settings(
        MEDIA_ROOT=tmp_path,
        STORAGES=storage_settings,
        MEDIA_RESPONSIVE_WIDTHS=(80, 160),
    ):
        if media_kind == "landing":
            from landing import models as media_models

            instance = media_models.HeroSlide.objects.create(
                title="Atomic hero",
                alt_text="Original",
                desktop_image=image_upload(size=(160, 90)),
            )
            source_field = "desktop_image"
            derivatives_field = "desktop_derivatives"
        else:
            from catalog import models as media_models

            instance = media_models.ProductMedia.objects.create(
                product=make_variant(sku="ATOMIC-MEDIA").product,
                alt_text="Original",
                file=image_upload(size=(160, 90)),
            )
            source_field = "file"
            derivatives_field = "derivatives"

        old_source = getattr(instance, source_field).name
        old_derivatives = getattr(instance, derivatives_field)
        expected_paths = {old_source}
        expected_paths.update(
            path
            for entry in old_derivatives["widths"]
            for key, path in entry.items()
            if key != "width"
        )

        def fail_publication(**kwargs):
            raise OSError("derivative publication failed")

        monkeypatch.setattr(media_models, "generate_image_derivatives", fail_publication)
        setattr(instance, source_field, image_upload("replacement.png", size=(120, 68)))

        with pytest.raises(OSError, match="derivative publication failed"):
            instance.save()

        persisted = type(instance).objects.get(pk=instance.pk)
        assert getattr(persisted, source_field).name == old_source
        actual_paths = {
            path.relative_to(tmp_path).as_posix()
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        assert actual_paths == expected_paths


@pytest.mark.django_db
def test_admin_refund_retry_reuses_provider_key_and_reconciles_after_local_rollback(
    django_user_model, monkeypatch
):
    from commerce import payments
    from commerce.admin_services import perform_order_admin_action
    from commerce.models import Cart, CartLine, Refund

    customer = django_user_model.objects.create_user(email="refund-loss@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="REFUND-LOSS"), quantity=1)
    order = pending_order(cart)
    payment = make_transaction(order)
    payments.apply_payment(transaction=payment, payment=valid_payment(payment))
    operator = django_user_model.objects.create_superuser(email="refund-operator@example.test")

    class IdempotentProvider:
        def __init__(self):
            self.requests = []
            self.operations = {}

        def refund(self, payment_id, *, amount, idempotency_key):
            del payment_id, amount
            self.requests.append(idempotency_key)
            return self.operations.setdefault(
                idempotency_key,
                {"id": f"provider-refund-{len(self.operations) + 1}", "status": "approved"},
            )

    provider = IdempotentProvider()
    real_transition = payments.transition_order_status
    lose_local_commit = True

    def fail_once_after_provider_success(**kwargs):
        nonlocal lose_local_commit
        if lose_local_commit:
            lose_local_commit = False
            raise RuntimeError("synthetic local commit loss")
        return real_transition(**kwargs)

    monkeypatch.setattr(payments, "transition_order_status", fail_once_after_provider_success)
    action = {
        "action": "refund",
        "order": order,
        "actor": operator,
        "reason": "Reembolso solicitado por cliente",
        "adapters": {"payment": provider},
    }

    with pytest.raises(RuntimeError, match="synthetic local commit loss"):
        perform_order_admin_action(**action)
    assert Refund.objects.count() == 0

    perform_order_admin_action(**action)

    refund = Refund.objects.get(order=order)
    assert provider.requests[0] == provider.requests[1]
    assert len(provider.operations) == 1
    assert refund.provider_refund_id == "provider-refund-1"
    assert refund.status == "approved"
    assert order.audit_events.filter(kind="admin_refund_completed").count() == 1
