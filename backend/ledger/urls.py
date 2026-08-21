from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("payment-methods", views.PaymentMethodViewSet, basename="paymentmethod")
router.register("transactions", views.TransactionViewSet, basename="transaction")
router.register(
    "recurring-payments", views.RecurringPaymentViewSet, basename="recurringpayment"
)

urlpatterns = [
    path("summary/monthly/", views.MonthlySummaryView.as_view()),
    path("balance/", views.BalanceView.as_view()),
    path("import/suggest/", views.ImportSuggestView.as_view()),
    path("import/transactions/", views.ImportTransactionsView.as_view()),
    path("group/", views.GroupView.as_view()),
    path("group/join/", views.GroupJoinView.as_view()),
    path("group/leave/", views.GroupLeaveView.as_view()),
    path("settlements/", views.SettleView.as_view()),
    path("settlements/<int:pk>/", views.SettlementDeleteView.as_view()),
    *router.urls,
]
