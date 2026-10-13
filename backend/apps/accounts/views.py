from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.finance import OwnedViewSet
from apps.core.finance import owner_lock
from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(OwnedViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def list(self, request, *args, **kwargs):
        from apps.transactions.services import balances_for
        with owner_lock(request.user):
            page = self.paginate_queryset(self.get_queryset())
            context = {**self.get_serializer_context(), "balances": balances_for(page)}
            return self.get_paginated_response(self.get_serializer(page, many=True, context=context).data)

    def retrieve(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        with owner_lock(request.user):
            account = self.get_object()
            data = self.get_serializer(account).data
            return Response({"account": str(account.id), "currency": account.currency, "balance": data["balance"], "debt": data["debt"]})
