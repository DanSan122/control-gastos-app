from django.urls import include, path
from apps.users.admin_site import site

urlpatterns = [
    path("admin/", site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.transactions.urls")),
    path("api/v1/", include("apps.budgets.urls")),
    path("api/v1/", include("apps.analytics.urls")),
]
