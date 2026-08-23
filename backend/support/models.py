import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_case_number(kind):
    prefixes = {
        SupportCase.Kind.CONSULTATION: "CON",
        SupportCase.Kind.PROBLEM: "PRO",
    }
    try:
        prefix = prefixes[kind]
    except KeyError as error:
        raise ValueError("Unsupported support case kind") from error
    return f"{prefix}-{timezone.localdate().year}-{secrets.token_hex(7).upper()}"


class SupportCase(models.Model):
    class Kind(models.TextChoices):
        CONSULTATION = "consultation", "Consulta"
        PROBLEM = "problem", "Problema"

    class Status(models.TextChoices):
        NEW = "new", "New"
        WAITING_STAFF = "waiting_staff", "Waiting staff"
        WAITING_CUSTOMER = "waiting_customer", "Waiting customer"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case_number = models.CharField(max_length=24, unique=True, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    subject = models.CharField(max_length=180)
    category = models.CharField(max_length=32)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_cases",
    )
    contact_name = models.CharField(max_length=180, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_email_normalized = models.CharField(max_length=254, blank=True, db_index=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    order = models.ForeignKey(
        "commerce.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_cases",
    )
    product = models.ForeignKey(
        "catalog.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_cases",
    )
    source_url = models.URLField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_cases",
    )
    recovery_code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    customer_last_read_at = models.DateTimeField(null=True, blank=True)
    staff_last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=("consultation", "problem")),
                name="sup_case_kind_valid",
            )
        ]
        indexes = [
            models.Index(
                fields=("kind", "status", "priority", "-updated_at", "-id"),
                name="sup_case_inbox_idx",
            ),
            models.Index(
                fields=("assigned_to", "-updated_at", "-id"),
                name="sup_case_assignee_idx",
            ),
            models.Index(fields=("contact_email_normalized",), name="sup_case_email_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = generate_case_number(self.kind)
        self.contact_email_normalized = self.contact_email.strip().lower()
        return super().save(*args, **kwargs)


class SupportMessage(models.Model):
    class AuthorRole(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        GUEST = "guest", "Guest"
        STAFF = "staff", "Staff"

    case = models.ForeignKey(SupportCase, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_messages",
    )
    author_role = models.CharField(max_length=16, choices=AuthorRole.choices)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    idempotency_key = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("case", "idempotency_key"), name="sup_message_case_idem_uniq"
            )
        ]
        indexes = [models.Index(fields=("case", "created_at", "id"), name="sup_message_case_idx")]


class SupportAttachment(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    message = models.ForeignKey(
        SupportMessage, on_delete=models.CASCADE, related_name="attachments"
    )
    storage_key = models.CharField(max_length=512, unique=True)
    original_name = models.CharField(max_length=255)
    detected_mime_type = models.CharField(max_length=100)
    extension = models.CharField(max_length=16)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    thumbnail_storage_key = models.CharField(max_length=512, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_support_attachments",
    )


class SupportGuestSession(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    token_hash = models.CharField(max_length=128, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class SupportGuestAccess(models.Model):
    session = models.ForeignKey(
        SupportGuestSession, on_delete=models.CASCADE, related_name="case_accesses"
    )
    case = models.ForeignKey(
        SupportCase, on_delete=models.CASCADE, related_name="guest_accesses"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("session", "case"), name="sup_guest_access_uniq")
        ]
