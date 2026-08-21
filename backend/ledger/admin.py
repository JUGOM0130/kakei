from django.contrib import admin

from .models import (
    Category,
    Group,
    GroupMember,
    PaymentMethod,
    RecurringPayment,
    Settlement,
    Transaction,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "type", "name", "color", "sort_order"]
    list_filter = ["type"]


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "name", "sort_order"]


@admin.register(RecurringPayment)
class RecurringPaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "name",
        "amount",
        "day_of_month",
        "interval_months",
        "anchor_month",
        "is_shared",
        "is_active",
    ]
    list_filter = ["is_active", "interval_months"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "date",
        "category",
        "amount",
        "payment_method",
        "group",
        "payer_share_percent",
        "memo",
    ]
    list_filter = ["date"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "invite_code", "created_at"]


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ["id", "group", "user", "share_percent"]


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ["id", "group", "month", "from_user", "to_user", "amount"]
