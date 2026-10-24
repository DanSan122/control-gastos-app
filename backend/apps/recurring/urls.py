from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import RuleViewSet, ExecutionViewSet, UpcomingView

router = SimpleRouter()
router.register("recurring/rules", RuleViewSet, basename="recurring-rule")
router.register(
    "recurring/executions", ExecutionViewSet, basename="recurring-execution"
)
urlpatterns = [
    path("recurring/upcoming/", UpcomingView.as_view()),
    *router.urls,
]
