from django.contrib import admin

from .models import Category, RecurringPayment, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "type", "name", "color", "sort_order"]
    list_filter = ["type"]


@admin.register(RecurringPayment)
class RecurringPaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "name", "amount", "day_of_month", "is_active"]
    list_filter = ["is_active"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "date", "category", "amount", "memo", "recurring_payment"]
    list_filter = ["date"]
