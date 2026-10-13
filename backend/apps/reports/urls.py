from django.urls import path
from .views import ReportView

urlpatterns = [
    path("reports/", ReportView.as_view()),
    path("reports/preview/", ReportView.as_view()),
] + [
    path(f"reports/export/{kind}/", ReportView.as_view(export_format=kind))
    for kind in ("xlsx", "csv", "pdf")
]
