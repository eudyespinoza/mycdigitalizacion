import json
from copy import deepcopy

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from accounts.models import CustomerProfile, Profile


def request_schema(operation, components):
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        return components["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def assert_error_schema(operation, status_code):
    response = operation["responses"][status_code]
    schema = response["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/Error")


def assert_validation_error_schema(operation, *, allows_domain_error=False):
    schema = operation["responses"]["400"]["content"]["application/json"]["schema"]
    if allows_domain_error:
        validation_schema, domain_schema = schema["oneOf"]
        assert domain_schema == {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "detail": {"type": "string"},
            },
            "required": ["code", "detail"],
            "additionalProperties": False,
        }
    else:
        validation_schema = schema
    assert validation_schema == {
        "type": "object",
        "additionalProperties": {"type": "array", "items": {"type": "string"}},
    }


def absolutize_local_refs(value):
    if isinstance(value, dict):
        converted = {
            key: (
                f"urn:openapi{item}"
                if key == "$ref" and item.startswith("#/")
                else absolutize_local_refs(item)
            )
            for key, item in value.items()
            if key != "nullable"
        }
        if value.get("nullable"):
            if "type" in converted:
                converted["type"] = [converted["type"], "null"]
            else:
                converted = {"anyOf": [converted, {"type": "null"}]}
        return converted
    if isinstance(value, list):
        return [absolutize_local_refs(item) for item in value]
    return value


def assert_runtime_response_matches(schema, path, method, response):
    status_code = str(response.status_code)
    documented = schema["paths"][path][method]["responses"][status_code]
    content = documented.get("content", {})
    if not content:
        assert not response.headers.get("Content-Type", "").startswith("application/json")
        return
    if not response.content:
        raise AssertionError("documented response has a body but runtime returned none")
    assert response.headers["Content-Type"].startswith("application/json")
    response_schema = deepcopy(content["application/json"]["schema"])
    registry = Registry().with_resource(
        "urn:openapi",
        Resource.from_contents(
            absolutize_local_refs(schema), default_specification=DRAFT202012
        ),
    )
    Draft202012Validator(
        absolutize_local_refs(response_schema), registry=registry
    ).validate(response.json())


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
        "/api/v1/addresses/{id}/confirm/",
        "/api/v1/billing-profiles/",
        "/api/v1/billing-profiles/{id}/",
        "/api/v1/orders/",
        "/api/v1/orders/{public_id}/",
        "/api/v1/identity/status/",
        "/api/v1/identity/validate/",
        "/api/v1/identity/manual-review/{id}/",
        "/api/v1/locations/postal-lookup/",
        "/api/v1/locations/geocode/",
        "/api/v1/locations/reverse-geocode/",
        "/api/v1/shipping/quote/",
        "/api/v1/checkout/",
        "/api/v1/checkout/{public_id}/resume/",
        "/api/v1/payments/mercadopago/webhook/",
        "/api/v1/payments/{external_reference}/status/",
        "/api/v1/orders/{public_id}/shipment/",
        "/api/v1/orders/{public_id}/label/",
        "/api/v1/orders/{public_id}/tracking/",
        "/api/v1/orders/{public_id}/refund/",
    }
    assert expected_paths <= paths.keys()
    for path in expected_paths:
        for operation in paths[path].values():
            assert operation["responses"]

    components = schema["components"]
    register = request_schema(paths["/api/v1/auth/register/"]["post"], components)
    assert set(register["required"]) == {"email", "password", "consent_version"}
    assert {"first_name", "last_name", "phone"} <= set(register["properties"])
    assert register["properties"]["email"]["format"] == "email"
    assert set(paths["/api/v1/auth/register/"]["post"]["responses"]) == {
        "201",
        "400",
        "409",
    }

    verify = request_schema(paths["/api/v1/auth/email-verify/"]["post"], components)
    assert set(verify["required"]) == {"email", "code"}
    assert set(paths["/api/v1/auth/email-verify/"]["post"]["responses"]) == {
        "200",
        "400",
        "429",
    }

    login = request_schema(paths["/api/v1/auth/login/"]["post"], components)
    assert set(login["required"]) == {"email", "password"}
    assert "cart_token" in login["properties"]
    assert set(paths["/api/v1/auth/login/"]["post"]["responses"]) == {
        "200",
        "400",
        "403",
    }

    assert set(paths["/api/v1/auth/csrf/"]["get"]["responses"]) == {"200"}
    assert set(paths["/api/v1/auth/logout/"]["post"]["responses"]) == {"204", "403"}
    checkout = paths["/api/v1/checkout/"]["post"]
    checkout_request = request_schema(checkout, components)
    assert set(checkout_request["required"]) == {
        "fulfillment_method",
        "billing_profile_id",
        "consent",
        "idempotency_key",
    }
    assert {"address_id", "shipping_quote_id"} <= checkout_request["properties"].keys()
    assert {"201", "202", "400", "403", "422", "501", "502", "503"} == set(
        checkout["responses"]
    )

    webhook = paths["/api/v1/payments/mercadopago/webhook/"]["post"]
    assert any(
        parameter["name"] == "data.id"
        and parameter["in"] == "query"
        and parameter["required"] is True
        for parameter in webhook["parameters"]
    )

    cart_post = request_schema(paths["/api/v1/cart/"]["post"], components)
    assert {"variant_id", "quantity", "coupon"} <= cart_post["properties"].keys()

    protected_contracts = {
        ("/api/v1/customers/me/", "get"): {"200", "403"},
        ("/api/v1/customers/me/", "patch"): {"200", "400", "403"},
        ("/api/v1/billing-profiles/", "get"): {"200", "403"},
        ("/api/v1/billing-profiles/", "post"): {"201", "400", "403"},
        ("/api/v1/billing-profiles/{id}/", "get"): {"200", "403", "404"},
        ("/api/v1/billing-profiles/{id}/", "put"): {
            "200",
            "400",
            "403",
            "404",
        },
        ("/api/v1/billing-profiles/{id}/", "patch"): {
            "200",
            "400",
            "403",
            "404",
        },
        ("/api/v1/billing-profiles/{id}/", "delete"): {"204", "403", "404"},
        ("/api/v1/addresses/", "get"): {"200", "403"},
        ("/api/v1/addresses/", "post"): {"201", "400", "403"},
        ("/api/v1/addresses/{id}/", "get"): {"200", "403", "404"},
        ("/api/v1/addresses/{id}/", "put"): {"200", "400", "403", "404"},
        ("/api/v1/addresses/{id}/", "patch"): {"200", "400", "403", "404"},
        ("/api/v1/addresses/{id}/", "delete"): {"204", "403", "404"},
        ("/api/v1/addresses/{id}/confirm/", "post"): {
            "200",
            "400",
            "403",
            "404",
            "409",
        },
        ("/api/v1/orders/", "get"): {"200", "403"},
        ("/api/v1/orders/{public_id}/", "get"): {"200", "403", "404"},
        ("/api/v1/identity/status/", "get"): {"200", "403"},
        ("/api/v1/checkout/", "post"): {
            "201",
            "202",
            "400",
            "403",
            "422",
            "501",
            "502",
            "503",
        },
    }
    for (path, method), expected_statuses in protected_contracts.items():
        operation = paths[path][method]
        assert set(operation["responses"]) == expected_statuses, (path, method)
        for error_status in expected_statuses & {"403", "404"}:
            assert_error_schema(operation, error_status)

    cart_contracts = {
        "get": {"200", "404"},
        "post": {"201", "400", "404"},
        "patch": {"200", "400", "404"},
        "delete": {"200", "400", "404"},
    }
    for method, expected_statuses in cart_contracts.items():
        assert set(paths["/api/v1/cart/"][method]["responses"]) == expected_statuses

    for path, method in (
        ("/api/v1/auth/register/", "post"),
        ("/api/v1/billing-profiles/", "post"),
        ("/api/v1/billing-profiles/{id}/", "put"),
        ("/api/v1/billing-profiles/{id}/", "patch"),
        ("/api/v1/addresses/", "post"),
        ("/api/v1/addresses/{id}/", "put"),
        ("/api/v1/addresses/{id}/", "patch"),
    ):
        assert_validation_error_schema(paths[path][method])

    for path, method in (
        ("/api/v1/auth/email-verify/", "post"),
        ("/api/v1/auth/login/", "post"),
        ("/api/v1/cart/", "post"),
    ):
        assert_validation_error_schema(paths[path][method], allows_domain_error=True)
    assert_validation_error_schema(paths["/api/v1/cart/"]["patch"])
    assert_validation_error_schema(paths["/api/v1/cart/"]["delete"])

    assert_error_schema(paths["/api/v1/auth/register/"]["post"], "409")
    checkout_error = paths["/api/v1/checkout/"]["post"]["responses"]["503"]
    checkout_schema = checkout_error["content"]["application/json"]["schema"]
    assert checkout_schema["$ref"].endswith("/CheckoutProviderError")


@pytest.mark.django_db
def test_openapi_documents_public_and_management_support_contracts(client):
    schema = client.get("/api/v1/schema/?format=json").json()
    paths = schema["paths"]

    public_paths = {
        "/api/v1/support/configuration/": {"get"},
        "/api/v1/support/cases/": {"get", "post"},
        "/api/v1/support/cases/{public_id}/": {"get"},
        "/api/v1/support/cases/{public_id}/messages/": {"post"},
        "/api/v1/support/cases/{public_id}/claim/": {"post"},
        "/api/v1/support/access/": {"post"},
        "/api/v1/support/attachments/{public_id}/": {"get"},
    }
    management_paths = {
        "/api/v1/management/support/assignees/": {"get"},
        "/api/v1/management/support/cases/": {"get"},
        "/api/v1/management/support/cases/{public_id}/": {"get", "patch"},
        "/api/v1/management/support/cases/{public_id}/messages/": {"post"},
        "/api/v1/management/support/summary/": {"get"},
        "/api/v1/management/support/attachments/{public_id}/": {"get"},
    }
    for path, methods in {**public_paths, **management_paths}.items():
        assert path in paths
        assert methods <= paths[path].keys()
        for method in methods:
            assert paths[path][method]["responses"]

    for path in (
        "/api/v1/support/cases/",
        "/api/v1/support/cases/{public_id}/messages/",
        "/api/v1/management/support/cases/{public_id}/messages/",
    ):
        operation = paths[path]["post"]
        multipart_schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
        if "$ref" in multipart_schema:
            multipart_schema = schema["components"]["schemas"][multipart_schema["$ref"].rsplit("/", 1)[-1]]
        properties = multipart_schema["properties"]
        assert "attachments" in properties
        assert "idempotency_key" in properties

    created = paths["/api/v1/support/cases/"]["post"]["responses"]["201"]
    created_schema = created["content"]["application/json"]["schema"]
    created_schema = schema["components"]["schemas"][created_schema["$ref"].rsplit("/", 1)[-1]]
    assert "recovery_code" in created_schema["properties"]
    assert "recovery_code" not in created_schema.get("required", [])

    for component_name in ("SupportCaseSummary", "SupportCaseDetail"):
        assert "recovery_code" not in schema["components"]["schemas"][component_name]["properties"]

    for path, method in (
        ("/api/v1/support/cases/{public_id}/", "get"),
        ("/api/v1/support/access/", "post"),
        ("/api/v1/support/cases/{public_id}/claim/", "post"),
    ):
        response_schema = paths[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        component = schema["components"]["schemas"][response_schema["$ref"].rsplit("/", 1)[-1]]
        assert "recovery_code" not in component["properties"]

    for path in (
        "/api/v1/support/attachments/{public_id}/",
        "/api/v1/management/support/attachments/{public_id}/",
    ):
        operation = paths[path]["get"]
        response = operation["responses"]["200"]
        content = response.get("content", {})
        assert "application/octet-stream" in content
        assert content["application/octet-stream"]["schema"] == {
            "type": "string",
            "format": "binary",
        }
        assert "privad" in response["description"].lower()
        assert operation["security"]

    management_attachment = paths[
        "/api/v1/management/support/attachments/{public_id}/"
    ]["get"]
    assert {} not in management_attachment["security"]


@pytest.mark.django_db
def test_runtime_payloads_match_their_documented_response_schemas(client):
    schema_response = client.get("/api/v1/schema/?format=json")
    schema = json.loads(schema_response.content)
    user = get_user_model().objects.create_user(
        email="openapi-runtime@example.test",
        password="Correct-Horse-Battery-Staple-42",
        email_verified_at=timezone.now(),
    )
    Profile.objects.create(user=user)
    CustomerProfile.objects.create(user=user, consent_version="privacy-v1")

    unauthenticated = (
        ("/api/v1/customers/me/", "get", client.get("/api/v1/customers/me/")),
        ("/api/v1/billing-profiles/", "get", client.get("/api/v1/billing-profiles/")),
        ("/api/v1/addresses/", "get", client.get("/api/v1/addresses/")),
        ("/api/v1/orders/", "get", client.get("/api/v1/orders/")),
        ("/api/v1/identity/status/", "get", client.get("/api/v1/identity/status/")),
        ("/api/v1/checkout/", "post", client.post("/api/v1/checkout/", {})),
    )
    for path, method, response in unauthenticated:
        assert response.status_code == 403
        assert_runtime_response_matches(schema, path, method, response)

    client.force_login(user)
    authenticated = (
        ("/api/v1/customers/me/", "get", client.get("/api/v1/customers/me/")),
        ("/api/v1/billing-profiles/", "get", client.get("/api/v1/billing-profiles/")),
        ("/api/v1/addresses/", "get", client.get("/api/v1/addresses/")),
        ("/api/v1/orders/", "get", client.get("/api/v1/orders/")),
        ("/api/v1/identity/status/", "get", client.get("/api/v1/identity/status/")),
        ("/api/v1/checkout/", "post", client.post("/api/v1/checkout/", {})),
        (
            "/api/v1/billing-profiles/",
            "post",
            client.post("/api/v1/billing-profiles/", {"cuit": "invalid"}),
        ),
        ("/api/v1/addresses/", "post", client.post("/api/v1/addresses/", {})),
        ("/api/v1/orders/{public_id}/", "get", client.get("/api/v1/orders/invalid/")),
    )
    for path, method, response in authenticated:
        assert_runtime_response_matches(schema, path, method, response)

    client.logout()
    cart_and_auth = (
        ("/api/v1/auth/csrf/", "get", client.get("/api/v1/auth/csrf/")),
        (
            "/api/v1/auth/register/",
            "post",
            client.post("/api/v1/auth/register/", {"email": "invalid"}),
        ),
        (
            "/api/v1/auth/email-verify/",
            "post",
            client.post("/api/v1/auth/email-verify/", {"email": "invalid", "code": "x"}),
        ),
        (
            "/api/v1/auth/login/",
            "post",
            client.post(
                "/api/v1/auth/login/",
                {"email": "invalid", "password": "wrong"},
            ),
        ),
        ("/api/v1/cart/", "get", client.get("/api/v1/cart/")),
        (
            "/api/v1/cart/",
            "post",
            client.post("/api/v1/cart/", {"variant_id": 999999, "quantity": 1}),
        ),
        (
            "/api/v1/cart/",
            "post",
            client.post("/api/v1/cart/", {"variant_id": "invalid", "quantity": 1}),
        ),
        (
            "/api/v1/cart/",
            "patch",
            client.patch(
                "/api/v1/cart/",
                json.dumps({"variant_id": "invalid", "quantity": 1}),
                content_type="application/json",
            ),
        ),
        (
            "/api/v1/cart/",
            "delete",
            client.delete(
                "/api/v1/cart/",
                json.dumps({"variant_id": "invalid"}),
                content_type="application/json",
            ),
        ),
        (
            "/api/v1/cart/",
            "get",
            client.get("/api/v1/cart/", HTTP_X_CART_TOKEN="invalid"),
        ),
    )
    for path, method, response in cart_and_auth:
        assert_runtime_response_matches(schema, path, method, response)

    non_field_error = client.post("/api/v1/cart/", {})
    assert non_field_error.json() == {
        "non_field_errors": ["Provide either variant_id or coupon"]
    }
    assert_runtime_response_matches(
        schema, "/api/v1/cart/", "post", non_field_error
    )

    domain_errors = (
        (
            "/api/v1/auth/email-verify/",
            "post",
            client.post(
                "/api/v1/auth/email-verify/",
                {"email": "missing@example.test", "code": "123456"},
            ),
            {
                "code": "invalid_verification_challenge",
                "detail": "Invalid or expired verification challenge",
            },
        ),
        (
            "/api/v1/auth/login/",
            "post",
            client.post(
                "/api/v1/auth/login/",
                {"email": "missing@example.test", "password": "wrong"},
            ),
            {"code": "invalid_credentials", "detail": "Invalid credentials"},
        ),
        (
            "/api/v1/cart/",
            "post",
            client.post("/api/v1/cart/", {"variant_id": 999999, "quantity": 1}),
            {"code": "unknown_variant", "detail": "Unknown variant"},
        ),
        (
            "/api/v1/cart/",
            "post",
            client.post("/api/v1/cart/", {"coupon": "MISSING"}),
            {"code": "invalid_coupon", "detail": "Coupon is invalid"},
        ),
    )
    for path, method, response, expected_payload in domain_errors:
        assert response.json() == expected_payload
        assert_runtime_response_matches(schema, path, method, response)

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_rejection = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": "missing@example.test", "password": "wrong"},
    )
    assert csrf_rejection.status_code == 403
    assert_runtime_response_matches(
        schema, "/api/v1/auth/login/", "post", csrf_rejection
    )
