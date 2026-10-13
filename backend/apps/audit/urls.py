from rest_framework.routers import SimpleRouter
from .views import AuditViewSet

router = SimpleRouter()
router.register("audit/events", AuditViewSet, basename="audit-event")
urlpatterns = router.urls
