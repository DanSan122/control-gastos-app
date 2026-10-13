from django.conf import settings
from datetime import timedelta
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.finance import FinancePagination, owner_lock
from apps.transactions.serializers import TransactionSerializer
from apps.users.authentication import CSRFSafeSessionAuthentication
from .services import report_query, summary
from .throttles import ReportThrottle


class ReportView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]
    throttle_classes = [ReportThrottle]
    export_format = None

    def get(self, request):
        with owner_lock(request.user):
            rows, start, end, granularity = report_query(
                request.user, request.query_params
            )
            total = rows.count()
            limit = (
                settings.REPORT_PDF_ROWS
                if self.export_format == "pdf"
                else settings.REPORT_EXPORT_ROWS
            )
            if self.export_format and total > limit:
                raise ValidationError(
                    {
                        "export": f"Máximo {limit} movimientos. Reduce el rango o los filtros."
                    }
                )
            data = summary(
                rows,
                start,
                end,
                granularity,
                request.user,
                request.query_params,
            )
            if not self.export_format:
                pagination = FinancePagination()
                page = pagination.paginate_queryset(rows, request, view=self)
                response = Response(
                    {
                        **data,
                        "movements": {
                            "count": total,
                            "next": pagination.get_next_link(),
                            "previous": pagination.get_previous_link(),
                            "results": TransactionSerializer(
                                page, many=True
                            ).data,
                        },
                    }
                )
            else:
                from .exporters import export_csv, export_xlsx, export_pdf

                detail = list(rows)
                exporter, content_type = {
                    "csv": (export_csv, "text/csv; charset=utf-8"),
                    "xlsx": (
                        export_xlsx,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                    "pdf": (export_pdf, "application/pdf"),
                }[self.export_format]
                # Materialize a consistent snapshot, then release owner_lock before rendering.
                response = (exporter, content_type, detail, data)
        if isinstance(response, tuple):
            exporter, content_type, detail, data = response
            response = HttpResponse(
                exporter(detail, data), content_type=content_type
            )
            response["Content-Disposition"] = (
                f'attachment; filename="controlgastos-{start.date()}-{end.date() - timedelta(days=1)}.{self.export_format}"'
            )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
