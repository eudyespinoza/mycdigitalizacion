import csv
import io

from openpyxl import Workbook

from commerce.models import StaffExportAudit


def spreadsheet_safe(value):
    text = str(value if value is not None else "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _serialize_rows(headers, rows, export_format):
    if export_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue().encode("utf-8-sig")
    if export_format == "xlsx":
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Export")
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    raise ValueError("Export format must be csv or xlsx")


def _record_export(*, actor, resource, export_format, filters, rows, sensitive):
    StaffExportAudit.objects.create(
        actor=actor,
        resource=resource,
        export_format=export_format,
        filters=dict(filters or {}),
        row_count=len(rows),
        included_sensitive_data=sensitive,
    )


def export_billing_profiles(queryset, *, actor, export_format, filters):
    sensitive = actor.has_perm("accounts.view_sensitive_fiscal_data")
    rows = [
        (
            spreadsheet_safe(profile.label),
            spreadsheet_safe(profile.legal_name),
            spreadsheet_safe(profile.tax_condition),
            profile.get_cuit() if sensitive else profile.masked_cuit,
        )
        for profile in queryset.select_related("customer__user").order_by("pk")
    ]
    _record_export(
        actor=actor,
        resource="billing_profiles",
        export_format=export_format,
        filters=filters,
        rows=rows,
        sensitive=sensitive,
    )
    return _serialize_rows(("label", "legal_name", "tax_condition", "cuit"), rows, export_format)


def export_orders(queryset, *, actor, export_format, filters):
    if not actor.has_perm("commerce.export_order"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Order export permission is required")
    sensitive = actor.has_perm("commerce.view_sensitive_order_data")
    rows = []
    for order in queryset.select_related("user").order_by("pk"):
        email = order.user.email if sensitive else "***"
        rows.append(
            (
                str(order.public_id),
                spreadsheet_safe(email),
                order.identity_status,
                order.payment_status,
                order.fulfillment_status,
                str(order.total_snapshot),
            )
        )
    _record_export(
        actor=actor,
        resource="orders",
        export_format=export_format,
        filters=filters,
        rows=rows,
        sensitive=sensitive,
    )
    return _serialize_rows(
        ("order_id", "email", "identity", "payment", "fulfillment", "total"),
        rows,
        export_format,
    )
