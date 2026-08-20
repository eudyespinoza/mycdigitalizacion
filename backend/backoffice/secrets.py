import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    master_key = settings.CONFIG_ENCRYPTION_MASTER_KEY
    if not master_key:
        raise ImproperlyConfigured("Falta la clave maestra de configuración")
    digest = hashlib.sha256(master_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_secret_map(values):
    normalized = {str(key): str(value) for key, value in values.items() if str(value)}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return _fernet().encrypt(payload).decode() if normalized else ""


def unseal_secret_map(ciphertext):
    if not ciphertext:
        return {}
    try:
        payload = _fernet().decrypt(ciphertext.encode())
        decoded = json.loads(payload.decode())
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured("No se pudo leer la configuración cifrada") from exc
    if not isinstance(decoded, dict) or any(
        not isinstance(value, str) for value in decoded.values()
    ):
        raise ImproperlyConfigured("La configuración cifrada tiene un formato inválido")
    return decoded
