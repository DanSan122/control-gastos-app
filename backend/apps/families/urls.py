from django.urls import path, include
from rest_framework.routers import SimpleRouter
from apps.accounts.views import AccountViewSet
from apps.categories.views import AreaViewSet, CategoryViewSet, SubcategoryViewSet
from apps.transactions.views import TransactionViewSet, TransferView
from apps.transactions.reports import SummaryView
from apps.budgets.views import BudgetViewSet
from apps.analytics.views import AnalyticsView
from apps.reports.views import ReportView
from apps.audit.views import AuditViewSet
from .views import FamilyViewSet, MembersView, InvitationsView, family_finance_view

router = SimpleRouter()
router.register("families", FamilyViewSet, basename="family")
urlpatterns = [
    path("families/invitations/mine/", InvitationsView.as_view()),
    path(
        "families/invitations/<uuid:invitation_id>/<str:operation>/",
        InvitationsView.as_view(),
    ),
    path("families/<uuid:family_id>/members/", MembersView.as_view()),
    path(
        "families/<uuid:family_id>/members/<uuid:membership_id>/", MembersView.as_view()
    ),
    path("families/<uuid:family_id>/invitations/", InvitationsView.as_view()),
    path(
        "families/<uuid:family_id>/invitations/<uuid:invitation_id>/<str:operation>/",
        InvitationsView.as_view(),
    ),
    *router.urls,
]
prefix = "families/<uuid:family_id>/"
for resource, cls in (
    ("accounts", AccountViewSet),
    ("areas", AreaViewSet),
    ("categories", CategoryViewSet),
    ("subcategories", SubcategoryViewSet),
    ("transactions", TransactionViewSet),
    ("budgets", BudgetViewSet),
):
    urlpatterns += [
        path(
            prefix + resource + "/",
            family_finance_view(
                cls.as_view({"get": "list", "post": "create"}),
                movements=resource == "transactions",
            ),
        ),
        path(
            prefix + resource + "/<uuid:pk>/",
            family_finance_view(
                cls.as_view(
                    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
                ),
                movements=resource == "transactions",
            ),
        ),
    ]
urlpatterns += [
    path(
        prefix + "accounts/<uuid:pk>/balance/",
        family_finance_view(AccountViewSet.as_view({"get": "balance"})),
    ),
    path(
        prefix + "budgets/<uuid:pk>/progress/",
        family_finance_view(BudgetViewSet.as_view({"get": "progress"})),
    ),
    path(
        prefix + "transfers/",
        family_finance_view(TransferView.as_view(), movements=True),
    ),
    path(
        prefix + "dashboard/",
        family_finance_view(AnalyticsView.as_view(section="dashboard")),
    ),
    path(
        prefix + "analytics/",
        family_finance_view(AnalyticsView.as_view(section="dashboard")),
    ),
    path(prefix + "reports/summary/", family_finance_view(SummaryView.as_view())),
    path(prefix + "reports/preview/", family_finance_view(ReportView.as_view())),
    path(
        prefix + "audit/events/",
        family_finance_view(AuditViewSet.as_view({"get": "list"})),
    ),
] + [
    path(
        prefix + f"reports/export/{kind}/",
        family_finance_view(ReportView.as_view(export_format=kind)),
    )
    for kind in ("xlsx", "csv", "pdf")
]
urlpatterns += [
    path(
        prefix + f"analytics/{section}/",
        family_finance_view(AnalyticsView.as_view(section=section)),
    )
    for section in ("dashboard", "evolution", "distribution", "comparison")
]
