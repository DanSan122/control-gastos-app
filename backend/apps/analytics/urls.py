from django.urls import path
from .views import AnalyticsView

urlpatterns = [path(f"analytics/{section}/", AnalyticsView.as_view(section=section), name=f"analytics-{section}") for section in ("dashboard", "evolution", "distribution", "comparison")]
