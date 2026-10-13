import hashlib
import json
from uuid import UUID

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.finance import FinancePagination, owner_lock
from apps.users.authentication import CSRFSafeSessionAuthentication
from .models import Transaction
from .periods import period_bounds
from .serializers import TransactionSerializer


class Conflict(APIException):
    status_code = 409
    default_detail = "La clave de idempotencia ya se utilizó con otro contenido."


class TransactionViewSet(viewsets.ModelViewSet):
    authentication_classes = [CSRFSafeSessionAuthentication]
    serializer_class = TransactionSerializer
    pagination_class = FinancePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        query = Transaction.objects.filter(owner=self.request.user).select_related("account", "destination_account", "area", "category", "subcategory")
        # Filtros solo en listas; no convierten un recurso propio en inaccesible al editar.
        if self.action != "list":
            return query
        params = self.request.query_params
        start, end = period_bounds(params, self.request.user, optional=True)
        if start:
            query = query.filter(occurred_at__gte=start, occurred_at__lt=end)
        for field in ("account", "area", "category", "subcategory"):
            if params.get(field):
                try:
                    value = UUID(params[field])
                except ValueError:
                    raise ValidationError({field: "UUID inválido."})
                query = query.filter(Q(account_id=value) | Q(destination_account_id=value)) if field == "account" else query.filter(**{f"{field}_id": value})
        for field, allowed in [("kind", ["INCOME", "EXPENSE", "TRANSFER"]), ("status", ["POSTED", "VOID"])]:
            if params.get(field):
                if params[field] not in allowed:
                    raise ValidationError({field: "Valor inválido."})
                query = query.filter(**{field: params[field]})
        if params.get("search"):
            query = query.filter(Q(description__icontains=params["search"]) | Q(reference__icontains=params["search"]))
        ordering = params.get("ordering", "-occurred_at")
        if ordering.lstrip("-") not in ("occurred_at", "created_at", "amount"):
            raise ValidationError({"ordering": "Ordenamiento no permitido."})
        return query.order_by(ordering, "id")

    def create(self, request, *args, **kwargs):
        if not isinstance(request.data, dict):
            raise ValidationError("Envía un objeto JSON.")
        if request.data.get("kind") == "TRANSFER":
            raise ValidationError({"kind": "Usa POST /transfers/ con Idempotency-Key."})
        with owner_lock(request.user):
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(owner=request.user)
            return Response(serializer.data, status=201)

    def partial_update(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        with owner_lock(request.user):
            instance = self.get_object()
            instance.status = "VOID"
            instance.save(update_fields=["status", "updated_at"])
            return Response(status=204)


class TransferView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]

    def post(self, request):
        if not isinstance(request.data, dict):
            raise ValidationError("Envía un objeto JSON.")
        try:
            key = UUID(request.headers.get("Idempotency-Key", ""))
        except ValueError:
            raise ValidationError({"idempotency_key": "Idempotency-Key debe ser un UUID."})
        # Huella del payload original: reintentos deben conservar exactamente su contenido.
        fingerprint = hashlib.sha256(json.dumps(request.data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with owner_lock(request.user):
            previous = Transaction.objects.filter(owner=request.user, idempotency_key=key).first()
            if previous:
                if previous.request_hash != fingerprint:
                    raise Conflict()
                return Response(TransactionSerializer(previous, context={"request": request}).data, status=200)
            payload = dict(request.data)
            if "kind" in payload and payload["kind"] != "TRANSFER":
                raise ValidationError({"kind": "Debe ser TRANSFER."})
            payload["kind"] = "TRANSFER"
            serializer = TransactionSerializer(data=payload, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save(owner=request.user, idempotency_key=key, request_hash=fingerprint)
            return Response(serializer.data, status=201)
