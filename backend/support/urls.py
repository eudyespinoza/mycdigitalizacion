from django.urls import path

from support.views import (
    SupportAccessView,
    SupportAttachmentDownloadView,
    SupportCaseClaimView,
    SupportCaseDetailView,
    SupportCaseListCreateView,
    SupportConfigurationView,
    SupportMessageCreateView,
)

urlpatterns = [
    path("configuration/", SupportConfigurationView.as_view(), name="support-configuration"),
    path("cases/", SupportCaseListCreateView.as_view(), name="support-case-list-create"),
    path("cases/<uuid:public_id>/", SupportCaseDetailView.as_view(), name="support-case-detail"),
    path(
        "cases/<uuid:public_id>/messages/",
        SupportMessageCreateView.as_view(),
        name="support-message-create",
    ),
    path(
        "cases/<uuid:public_id>/claim/", SupportCaseClaimView.as_view(), name="support-case-claim"
    ),
    path("access/", SupportAccessView.as_view(), name="support-access"),
    path(
        "attachments/<uuid:public_id>/",
        SupportAttachmentDownloadView.as_view(),
        name="support-attachment-download",
    ),
]
