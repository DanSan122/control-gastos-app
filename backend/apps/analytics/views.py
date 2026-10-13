from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.finance import owner_lock
from apps.users.authentication import CSRFSafeSessionAuthentication
from .services import analytics


class AnalyticsView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]
    section = "dashboard"

    def get(self, request):
        with owner_lock(request.user):
            return Response(analytics(request.query_params, request.user, request, self.section))
