from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("trades", views.TradeViewSet, basename="stock-trade")
router.register("dividends", views.DividendViewSet, basename="stock-dividend")

urlpatterns = [
    path("positions/", views.PositionsView.as_view()),
    path("prices/<str:code>/", views.PriceView.as_view()),
    path("summary/", views.SummaryView.as_view()),
    *router.urls,
]
