import base64
import hashlib
import hmac
import re

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE
    )
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)


class EmailVerificationChallenge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="verification_challenges", on_delete=models.CASCADE
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, *, user, code):
        if not re.fullmatch(r"\d{6}", code):
            raise ValidationError("Verification codes must contain exactly six digits")
        now = timezone.now()
        return cls.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=now + timezone.timedelta(minutes=15),
        )

    def verify(self, code, *, now=None):
        checked_at = now or timezone.now()
        return (
            self.consumed_at is None
            and checked_at <= self.expires_at
            and check_password(code, self.code_hash)
        )


def _fernet():
    digest = hashlib.sha256(settings.PERSONAL_DATA_ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _identifier_hash(value):
    return hmac.new(
        settings.PERSONAL_DATA_ENCRYPTION_KEY.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="customer_profile", on_delete=models.CASCADE
    )
    consent_version = models.CharField(max_length=64)
    consented_at = models.DateTimeField(default=timezone.now)
    dni_encrypted = models.TextField(blank=True)
    dni_hash = models.CharField(max_length=64, blank=True, db_index=True)
    cuit_encrypted = models.TextField(blank=True)
    cuit_hash = models.CharField(max_length=64, blank=True, db_index=True)

    def set_dni(self, value):
        normalized = "".join(filter(str.isdigit, value))
        self.dni_encrypted = _fernet().encrypt(normalized.encode()).decode()
        self.dni_hash = _identifier_hash(normalized)

    def get_dni(self):
        return _fernet().decrypt(self.dni_encrypted.encode()).decode() if self.dni_encrypted else ""

    def set_cuit(self, value):
        normalized = "".join(filter(str.isdigit, value))
        self.cuit_encrypted = _fernet().encrypt(normalized.encode()).decode()
        self.cuit_hash = _identifier_hash(normalized)

    def get_cuit(self):
        return (
            _fernet().decrypt(self.cuit_encrypted.encode()).decode() if self.cuit_encrypted else ""
        )

    @property
    def masked_dni(self):
        value = self.get_dni()
        return f"{'•' * max(0, len(value) - 4)}{value[-4:]}" if value else ""

    @property
    def masked_cuit(self):
        value = self.get_cuit()
        return f"••-••••••••-{value[-1]}" if value else ""


class BillingProfile(models.Model):
    customer = models.ForeignKey(
        CustomerProfile, related_name="billing_profiles", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=200)
    tax_condition = models.CharField(max_length=64)
    cuit_encrypted = models.TextField(blank=True)
    cuit_hash = models.CharField(max_length=64, blank=True, db_index=True)
    is_default = models.BooleanField(default=False)

    def set_cuit(self, value):
        normalized = "".join(filter(str.isdigit, value))
        self.cuit_encrypted = _fernet().encrypt(normalized.encode()).decode()
        self.cuit_hash = _identifier_hash(normalized)

    @property
    def masked_cuit(self):
        if not self.cuit_encrypted:
            return ""
        value = _fernet().decrypt(self.cuit_encrypted.encode()).decode()
        return f"••-••••••••-{value[-1]}"
