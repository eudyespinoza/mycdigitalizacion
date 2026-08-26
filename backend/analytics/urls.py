from django.urls import path

from analytics.views import AnalyticsEventView

urlpatterns = [
    path("events/", AnalyticsEventView.as_view(), name="analytics-events"),
]
