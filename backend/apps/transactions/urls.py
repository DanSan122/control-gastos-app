from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.accounts.views import AccountViewSet
from apps.categories.views import AreaViewSet, CategoryViewSet, SubcategoryViewSet
from .views import TransactionViewSet, TransferView
from .reports import SummaryView

router = SimpleRouter()
router.register("accounts", AccountViewSet, basename="account")
router.register("areas", AreaViewSet, basename="area")
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubcategoryViewSet, basename="subcategory")
router.register("transactions", TransactionViewSet, basename="transaction")

urlpatterns = [path("", include(router.urls)), path("transfers/", TransferView.as_view()), path("reports/summary/", SummaryView.as_view())]
