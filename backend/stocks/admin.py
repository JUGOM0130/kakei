from django.contrib import admin

from .models import Dividend, StockInfo, StockPrice, Trade, Watch


@admin.register(Watch)
class WatchAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "name", "kind", "target_price"]


@admin.register(StockInfo)
class StockInfoAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "settlement_month"]


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
