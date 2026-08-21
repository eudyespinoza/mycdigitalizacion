from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from backoffice.integrations import resolved_configuration


class GoogleIdentityError(Exception):
    pass


def google_identity_configuration():
    configuration = resolved_configuration("google_identity")
    client_id = ""
    if configuration and configuration["enabled"]:
        client_id = str(configuration["public_config"].get("client_id") or "").strip()
    return {"enabled": bool(client_id), "client_id": client_id}


def verify_google_token(credential, client_id):
    try:
        return id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except (GoogleAuthError, ValueError) as exc:
        raise GoogleIdentityError("Google no pudo validar la credencial.") from exc
