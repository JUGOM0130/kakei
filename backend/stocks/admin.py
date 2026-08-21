from django.contrib import admin

from .models import Dividend, StockPrice, Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ["trade_date", "user", "code", "name", "side", "quantity", "price", "fee"]
    list_filter = ["side", "account_type"]
    search_fields = ["code", "name"]


@admin.register(Dividend)
class DividendAdmin(admin.ModelAdmin):
    list_display = ["received_date", "user", "code", "name", "amount"]
    search_fields = ["code", "name"]


@admin.register(StockPrice)
class StockPriceAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "price", "updated_at"]
