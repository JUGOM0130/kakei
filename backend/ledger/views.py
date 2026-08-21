import calendar
import re
from datetime import date

from django.db import IntegrityError
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, RecurringPayment, Transaction
from .serializers import (
    CategorySerializer,
    PaySerializer,
    RecurringPaymentSerializer,
    TransactionSerializer,
)

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def month_range(month_str):
    """'YYYY-MM' → (月初日, 月末日)"""
    if not month_str or not MONTH_RE.match(month_str):
        raise ValidationError({"month": "YYYY-MM 形式で指定してください。"})
    year, month = map(int, month_str.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        qs = Category.objects.filter(user=self.request.user)
        type_ = self.request.query_params.get("type")
        if type_ in Category.Type.values:
            qs = qs.filter(type=type_)
        return qs

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({"name": "同じ種別に同名のカテゴリが既にあります。"})

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({"name": "同じ種別に同名のカテゴリが既にあります。"})

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "使用中のカテゴリは削除できません。"},
                status=status.HTTP_409_CONFLICT,
            )


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user).select_related("category")
        params = self.request.query_params
        month = params.get("month")
        if month:
            first, last = month_range(month)
            qs = qs.filter(date__range=(first, last))
        category = params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        type_ = params.get("type")
        if type_ in Category.Type.values:
            qs = qs.filter(category__type=type_)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RecurringPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = RecurringPaymentSerializer

    def get_queryset(self):
        qs = RecurringPayment.objects.filter(user=self.request.user).select_related("category")
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=is_active == "true")
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        rp = self.get_object()
        serializer = PaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        first, last = month_range(serializer.validated_data["month"])

        if Transaction.objects.filter(
            user=request.user, recurring_payment=rp, date__range=(first, last)
        ).exists():
            return Response(
                {"detail": "この月は既に支払済です。"}, status=status.HTTP_409_CONFLICT
            )

        pay_date = serializer.validated_data.get("date") or first.replace(
            day=min(rp.day_of_month, last.day)
        )
        amount = serializer.validated_data.get("amount") or rp.amount
        tx = Transaction.objects.create(
            user=request.user,
            category=rp.category,
            amount=amount,
            date=pay_date,
            memo=rp.name,
            recurring_payment=rp,
        )
        return Response(
            TransactionSerializer(tx, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MonthlySummaryView(APIView):
    def get(self, request):
        month = request.query_params.get("month")
        first, last = month_range(month)
        user = request.user

        month_txs = Transaction.objects.filter(user=user, date__range=(first, last))
        by_category = (
            month_txs.values(
                "category_id", "category__name", "category__type", "category__color"
            )
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        income_total = expense_total = 0
        income_by_category, expense_by_category = [], []
        for row in by_category:
            item = {
                "category_id": row["category_id"],
                "name": row["category__name"],
                "color": row["category__color"],
                "total": row["total"],
            }
            if row["category__type"] == Category.Type.INCOME:
                income_total += row["total"]
                income_by_category.append(item)
            else:
                expense_total += row["total"]
                expense_by_category.append(item)

        # 定期支払: 有効なテンプレートを予定として並べ、当月の生成済み Transaction で支払済判定
        paid_txs = {
            tx.recurring_payment_id: tx
            for tx in month_txs.filter(recurring_payment__isnull=False)
        }
        required_total = paid_total = remaining_total = 0
        items = []
        for rp in RecurringPayment.objects.filter(user=user, is_active=True).select_related(
            "category"
        ):
            tx = paid_txs.get(rp.id)
            required_total += rp.amount
            if tx:
                paid_total += tx.amount
            else:
                remaining_total += rp.amount
            items.append(
                {
                    "id": rp.id,
                    "name": rp.name,
                    "amount": rp.amount,
                    "day_of_month": rp.day_of_month,
                    "category": {
                        "id": rp.category_id,
                        "name": rp.category.name,
                        "color": rp.category.color,
                    },
                    "paid": tx is not None,
                    "transaction_id": tx.id if tx else None,
                }
            )

        return Response(
            {
                "month": month,
                "income_total": income_total,
                "expense_total": expense_total,
                "balance": income_total - expense_total,
                "income_by_category": income_by_category,
                "expense_by_category": expense_by_category,
                "recurring": {
                    "required_total": required_total,
                    "paid_total": paid_total,
                    "remaining_total": remaining_total,
                    "items": items,
                },
            }
        )
