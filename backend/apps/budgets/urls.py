from rest_framework.routers import SimpleRouter
from .views import BudgetViewSet

router = SimpleRouter()
router.register("budgets", BudgetViewSet, basename="budget")
urlpatterns = router.urls
