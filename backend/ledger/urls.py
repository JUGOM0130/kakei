from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("transactions", views.TransactionViewSet, basename="transaction")
router.register(
    "recurring-payments", views.RecurringPaymentViewSet, basename="recurringpayment"
)

urlpatterns = [
    path("summary/monthly/", views.MonthlySummaryView.as_view()),
    *router.urls,
]
