from apps.core.scope import scoped, scope_timezone
import hashlib
import json
from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.finance import FinancePagination, owner_lock
from apps.users.authentication import CSRFSafeSessionAuthentication
from .models import Transaction
from .filters import filtered_transactions
from .serializers import TransactionSerializer
from .creation import create_movement


class Conflict(APIException):
    status_code = 409
    default_detail = "La clave de idempotencia ya se utilizó con otro contenido."


class TransactionViewSet(viewsets.ModelViewSet):
    authentication_classes = [CSRFSafeSessionAuthentication]
    serializer_class = TransactionSerializer
    pagination_class = FinancePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        query = scoped(Transaction.objects, self.request.user).select_related("owner", "account", "destination_account", "area", "category", "subcategory")
        # Filtros solo en listas; no convierten un recurso propio en inaccesible al editar.
        if self.action != "list":
            return query
        return filtered_transactions(self.request.user, self.request.query_params)

    def create(self, request, *args, **kwargs):
        if not isinstance(request.data, dict):
            raise ValidationError("Envía un objeto JSON.")
        if request.data.get("kind") == "TRANSFER":
            raise ValidationError({"kind": "Usa POST /transfers/ con Idempotency-Key."})
        with owner_lock(request.user):
            movement = create_movement(request.user, request.data, request=request)
            return Response(self.get_serializer(movement).data, status=201)

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
            previous = scoped(Transaction.objects, request.user).filter(idempotency_key=key).first()
            if previous:
                if previous.request_hash != fingerprint:
                    raise Conflict()
                return Response(TransactionSerializer(previous, context={"request": request}).data, status=200)
            payload = dict(request.data)
            if "kind" in payload and payload["kind"] != "TRANSFER":
                raise ValidationError({"kind": "Debe ser TRANSFER."})
            payload["kind"] = "TRANSFER"
            movement = create_movement(request.user, payload, request=request, idempotency_key=key, request_hash=fingerprint)
            return Response(TransactionSerializer(movement, context={"request": request}).data, status=201)
