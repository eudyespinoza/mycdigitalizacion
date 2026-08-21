import pytest
from django.core.exceptions import ValidationError

from tests.test_task5a_admin_contracts import image_upload


def test_brand_uploads_use_the_hardened_image_validator():
    from landing.models import SiteSettings

    with pytest.raises(ValidationError, match="MIME"):
        SiteSettings(
            logo=image_upload("spoofed-logo.jpg", content_type="image/jpeg")
        ).full_clean()
    with pytest.raises(ValidationError, match="MIME"):
        SiteSettings(
            favicon=image_upload("spoofed-favicon.jpg", content_type="image/jpeg")
        ).full_clean()


@pytest.mark.django_db
def test_home_contract_exposes_complete_campaign_policy_and_brand_fallback(client):
    from landing.models import HeroSlide, PromotionPopup, PromotionSlide

    HeroSlide.objects.create(
        title="Hero dos",
        body="Segundo mensaje",
        interval_ms=7100,
        pause_on_reduced_motion=True,
        focal_x=31,
        focal_y=69,
        safe_height_mobile=321,
        safe_height_tablet=421,
        safe_height_desktop=521,
        starts_at=None,
        ends_at=None,
        order=2,
    )
    PromotionSlide.objects.create(
        title="Promoción",
        interval_ms=8300,
        pause_on_reduced_motion=False,
        order=3,
    )
    PromotionPopup.objects.create(
        title="Popup",
        frequency="weekly",
        display_delay_ms=2400,
        dismissible=False,
        version=4,
        focal_x=20,
        focal_y=80,
        safe_height_mobile=322,
        safe_height_tablet=422,
        safe_height_desktop=522,
        order=4,
    )

    response = client.get("/api/v1/storefront/home/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["settings"] == {
        "public_name": "mycdigitalizacion",
        "announcement": "",
        "contact_email": "",
        "pickup_enabled": True,
        "pickup_label": "Retiro en tienda",
        "pickup_address": "",
        "pickup_hours": "",
        "instagram_url": "",
        "facebook_url": "",
        "tiktok_url": "",
        "youtube_url": "",
        "linkedin_url": "",
        "whatsapp_enabled": False,
        "whatsapp_number": "",
        "whatsapp_message": "",
        "theme_palette": "pulso",
        "theme_structure": "#020530",
        "theme_action": "#BD1D59",
        "theme_wayfinding": "#007F96",
        "theme_background": "#FFFFFF",
        "theme_text": "#020530",
        "logo_url": "/brand/mycdigitalizacion-logo.png",
        "logo_responsive_sources": [],
        "favicon_url": "/brand/mycdigitalizacion-logo.png",
    }
    hero = payload["hero_slides"][0]
    assert hero["interval_ms"] == 7100
    assert hero["pause_on_reduced_motion"] is True
    assert hero["focal_x"] == "31.00"
    assert hero["focal_y"] == "69.00"
    assert hero["safe_height_mobile"] == 321
    assert hero["safe_height_tablet"] == 421
    assert hero["safe_height_desktop"] == 521
    assert hero["desktop_image_url"] == ""
    assert hero["mobile_image_url"] == ""
    assert hero["desktop_responsive_sources"] == []
    assert hero["mobile_responsive_sources"] == []
    assert hero["starts_at"] is None
    assert hero["ends_at"] is None
    promotion = payload["promotion_slides"][0]
    assert promotion["interval_ms"] == 8300
    assert promotion["pause_on_reduced_motion"] is False
    popup = payload["promotion_popups"][0]
    assert popup["frequency"] == "weekly"
    assert popup["display_delay_ms"] == 2400
    assert popup["dismissible"] is False
    assert popup["version"] == 4
    assert popup["focal_x"] == "20.00"
    assert popup["focal_y"] == "80.00"
    assert popup["desktop_responsive_sources"] == []
    assert popup["mobile_responsive_sources"] == []


@pytest.mark.django_db
def test_admin_brand_replacement_updates_api_preview_and_cleans_old_assets(
    client, django_user_model, settings, tmp_path
):
    from landing.models import SiteSettings

    settings.MEDIA_ROOT = tmp_path
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
    owner = django_user_model.objects.create_superuser(email="brand-owner@example.test")
    client.force_login(owner)
    site_settings = SiteSettings.objects.create()
    change_url = "/admin/landing/sitesettings/1/change/"

    first = client.post(
        change_url,
        {
            "public_name": "mycdigitalizacion",
            "announcement": "",
            "contact_email": "",
            "pickup_enabled": "on",
            "pickup_label": "Retiro en tienda",
            "pickup_address": "",
            "pickup_hours": "",
            "logo": image_upload("supplied-logo.png", size=(640, 320)),
            "favicon": image_upload("supplied-favicon.png", size=(64, 64)),
            "_save": "Guardar",
        },
    )

    assert first.status_code == 302
    site_settings.refresh_from_db()
    first_logo = site_settings.logo.name
    first_favicon = site_settings.favicon.name
    first_derivatives = [
        path
        for source in site_settings.logo_derivatives["widths"]
        for key, path in source.items()
        if key != "width"
    ]
    api = client.get("/api/v1/storefront/home/").json()["settings"]
    assert api["logo_url"] == f"/media/{first_logo}"
    assert [source["width"] for source in api["logo_responsive_sources"]] == [320]
    assert api["favicon_url"] == f"/media/{first_favicon}"
    preview = client.get(change_url)
    assert preview.status_code == 200
    assert api["logo_url"] in preview.content.decode()
    assert api["favicon_url"] in preview.content.decode()

    second = client.post(
        change_url,
        {
            "public_name": "mycdigitalizacion",
            "announcement": "",
            "contact_email": "",
            "pickup_enabled": "on",
            "pickup_label": "Retiro en tienda",
            "pickup_address": "",
            "pickup_hours": "",
            "logo": image_upload("replacement-logo.png", size=(960, 480)),
            "favicon": image_upload("replacement-favicon.png", size=(96, 96)),
            "_save": "Guardar",
        },
    )

    assert second.status_code == 302
    site_settings.refresh_from_db()
    assert site_settings.logo.name != first_logo
    assert site_settings.favicon.name != first_favicon
    assert not site_settings.logo.storage.exists(first_logo)
    assert not site_settings.favicon.storage.exists(first_favicon)
    assert all(not site_settings.logo.storage.exists(path) for path in first_derivatives)
    replaced_api = client.get("/api/v1/storefront/home/").json()["settings"]
    assert replaced_api["logo_url"] == site_settings.logo.url
    assert replaced_api["favicon_url"] == site_settings.favicon.url
    assert [
        source["width"] for source in replaced_api["logo_responsive_sources"]
    ] == [320, 640]


def test_openapi_documents_brand_assets_and_popup_version(client):
    schema = client.get("/api/v1/schema/?format=json").json()
    components = schema["components"]["schemas"]
    site_settings = components["SiteSettings"]
    popup = components["PromotionPopup"]

    assert site_settings["properties"]["logo_url"]["type"] == "string"
    assert site_settings["properties"]["favicon_url"]["type"] == "string"
    responsive = site_settings["properties"]["logo_responsive_sources"]
    assert responsive["type"] == "array"
    assert responsive["items"]["$ref"].endswith("/ResponsiveMediaSource")
    assert popup["properties"]["version"]["type"] == "integer"
    assert popup["properties"]["version"]["minimum"] == 1
