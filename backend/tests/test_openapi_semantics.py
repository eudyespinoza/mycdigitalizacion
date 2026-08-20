import json

import pytest


def request_schema(operation, components):
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        return components["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


@pytest.mark.django_db
def test_openapi_describes_real_auth_cart_checkout_and_all_v1_operations(client):
    response = client.get("/api/v1/schema/?format=json")
    assert response.status_code == 200
    schema = json.loads(response.content)
    paths = schema["paths"]
    expected_paths = {
        "/api/v1/storefront/home/",
        "/api/v1/categories/",
        "/api/v1/products/",
        "/api/v1/products/{slug}/",
        "/api/v1/search/",
        "/api/v1/auth/csrf/",
        "/api/v1/auth/register/",
        "/api/v1/auth/email-verify/",
        "/api/v1/auth/login/",
        "/api/v1/auth/logout/",
        "/api/v1/customers/me/",
        "/api/v1/cart/",
        "/api/v1/addresses/",
        "/api/v1/addresses/{id}/",
        "/api/v1/billing-profiles/",
        "/api/v1/billing-profiles/{id}/",
        "/api/v1/orders/",
        "/api/v1/orders/{public_id}/",
        "/api/v1/identity/status/",
        "/api/v1/checkout/",
    }
    assert expected_paths <= paths.keys()
    for path in expected_paths:
        for operation in paths[path].values():
            assert operation["responses"]

    components = schema["components"]
    register = request_schema(paths["/api/v1/auth/register/"]["post"], components)
    assert set(register["required"]) == {"email", "password", "consent_version"}
    assert register["properties"]["email"]["format"] == "email"
    assert {"201", "400", "409"} <= paths["/api/v1/auth/register/"]["post"][
        "responses"
    ].keys()

    verify = request_schema(paths["/api/v1/auth/email-verify/"]["post"], components)
    assert set(verify["required"]) == {"email", "code"}
    assert {"200", "400", "429"} <= paths["/api/v1/auth/email-verify/"]["post"][
        "responses"
    ].keys()

    login = request_schema(paths["/api/v1/auth/login/"]["post"], components)
    assert set(login["required"]) == {"email", "password"}
    assert "cart_token" in login["properties"]
    assert {"200", "400", "403"} <= paths["/api/v1/auth/login/"]["post"][
        "responses"
    ].keys()

    assert "204" in paths["/api/v1/auth/logout/"]["post"]["responses"]
    checkout = paths["/api/v1/checkout/"]["post"]
    assert "requestBody" not in checkout
    assert "503" in checkout["responses"]
    assert "200" not in checkout["responses"]

    cart_post = request_schema(paths["/api/v1/cart/"]["post"], components)
    assert {"variant_id", "quantity", "coupon"} <= cart_post["properties"].keys()
