import calendar
import re
import secrets
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Category,
    Group,
    GroupMember,
    PaymentMethod,
    RecurringPayment,
    Settlement,
    Transaction,
)
from .serializers import (
    CategorySerializer,
    GroupCreateSerializer,
    GroupJoinSerializer,
    GroupShareSerializer,
    PaymentMethodSerializer,
    PaySerializer,
    RecurringPaymentSerializer,
    SettleSerializer,
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


def get_membership(user):
    return GroupMember.objects.filter(user=user).select_related("group").first()


def round_share(amount, percent):
    return int(amount * percent / 100 + 0.5)


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
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({"name": "同じ種別に同名のカテゴリが既にあります。"})

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
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


class PaymentMethodViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentMethodSerializer

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({"name": "同名の支払方法が既にあります。"})

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise ValidationError({"name": "同名の支払方法が既にあります。"})

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "使用中の支払方法は削除できません。"},
                status=status.HTTP_409_CONFLICT,
            )


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        user = self.request.user
        cond = Q(user=user)
        member = get_membership(user)
        if member:
            # グループ共有の記録は相手の分も見える
            cond |= Q(group=member.group)
        qs = Transaction.objects.filter(cond).select_related(
            "category", "user", "payment_method"
        )
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
        payment_method = params.get("payment_method")
        if payment_method:
            qs = qs.filter(payment_method_id=payment_method)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.id:
            raise PermissionDenied("共有相手の記録は編集できません。")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied("共有相手の記録は削除できません。")
        instance.delete()


class RecurringPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = RecurringPaymentSerializer

    def get_queryset(self):
        qs = RecurringPayment.objects.filter(user=self.request.user).select_related(
            "category"
        )
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

        if not rp.is_due_in(first):
            return Response(
                {"detail": "この月は支払対象月ではありません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
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

        group = None
        share = None
        if rp.is_shared:
            member = get_membership(request.user)
            if member:
                group = member.group
                share = rp.payer_share_percent

        tx = Transaction.objects.create(
            user=request.user,
            category=rp.category,
            amount=amount,
            date=pay_date,
            memo=rp.name,
            group=group,
            payer_share_percent=share,
            recurring_payment=rp,
        )
        return Response(
            TransactionSerializer(tx, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def build_shared_summary(user, member, first, last):
    """共有支払いの立替・負担・精算サマリーを組み立てる (2人グループ前提)。"""
    if member is None:
        return {"enabled": False}

    group = member.group
    others = [m for m in group.members.select_related("user") if m.user_id != user.id]
    partner = others[0].user if others else None

    shared_txs = Transaction.objects.filter(group=group, date__range=(first, last))
    total = my_paid = my_burden = 0
    for tx in shared_txs:
        total += tx.amount
        pct = tx.payer_share_percent if tx.payer_share_percent is not None else 50
        if tx.user_id == user.id:
            my_paid += tx.amount
            my_burden += round_share(tx.amount, pct)
        else:
            my_burden += round_share(tx.amount, 100 - pct)

    partner_paid = total - my_paid
    partner_burden = total - my_burden
    diff = my_paid - my_burden  # 正: 相手→自分に渡す / 負: 自分→相手に渡す

    transfer = None
    if partner and diff != 0:
        if diff > 0:
            transfer = {
                "from": partner.username,
                "to": user.username,
                "amount": diff,
                "direction": "receive",
            }
        else:
            transfer = {
                "from": user.username,
                "to": partner.username,
                "amount": -diff,
                "direction": "pay",
            }

    settlement = Settlement.objects.filter(group=group, month=first).first()

    return {
        "enabled": True,
        "group_name": group.name,
        "partner": {"id": partner.id, "username": partner.username} if partner else None,
        "total": total,
        "my_paid": my_paid,
        "partner_paid": partner_paid,
        "my_burden": my_burden,
        "partner_burden": partner_burden,
        "transfer": transfer,
        "settlement": (
            {
                "id": settlement.id,
                "amount": settlement.amount,
                "from": settlement.from_user.username,
                "to": settlement.to_user.username,
            }
            if settlement
            else None
        ),
    }


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

        # 支払方法別の支出合計 (カード別の請求予定額)
        by_method = (
            month_txs.filter(category__type=Category.Type.EXPENSE)
            .values("payment_method_id", "payment_method__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )
        payment_methods = [
            {
                "id": row["payment_method_id"],
                "name": row["payment_method__name"] or "未設定",
                "total": row["total"],
            }
            for row in by_method
        ]

        # 定期支払: その月が支払対象月のものだけを予定として並べる
        paid_txs = {
            tx.recurring_payment_id: tx
            for tx in month_txs.filter(recurring_payment__isnull=False)
        }
        required_total = paid_total = remaining_total = 0
        items = []
        for rp in RecurringPayment.objects.filter(user=user, is_active=True).select_related(
            "category"
        ):
            if not rp.is_due_in(first):
                continue
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
                    "interval_months": rp.interval_months,
                    "category": {
                        "id": rp.category_id,
                        "name": rp.category.name,
                        "color": rp.category.color,
                    },
                    "paid": tx is not None,
                    "transaction_id": tx.id if tx else None,
                }
            )

        member = get_membership(user)

        return Response(
            {
                "month": month,
                "income_total": income_total,
                "expense_total": expense_total,
                "balance": income_total - expense_total,
                "income_by_category": income_by_category,
                "expense_by_category": expense_by_category,
                "payment_methods": payment_methods,
                "recurring": {
                    "required_total": required_total,
                    "paid_total": paid_total,
                    "remaining_total": remaining_total,
                    "items": items,
                },
                "shared": build_shared_summary(user, member, first, last),
            }
        )


class GroupView(APIView):
    """自分のグループの取得・作成・負担割合の変更"""

    def get(self, request):
        member = get_membership(request.user)
        if member is None:
            return Response({"group": None})
        group = member.group
        members = [
            {
                "id": m.user_id,
                "username": m.user.username,
                "share_percent": m.share_percent,
                "is_me": m.user_id == request.user.id,
            }
            for m in group.members.select_related("user")
        ]
        return Response(
            {
                "group": {
                    "id": group.id,
                    "name": group.name,
                    "invite_code": group.invite_code,
                    "members": members,
                }
            }
        )

    def post(self, request):
        if get_membership(request.user):
            return Response(
                {"detail": "既にグループに参加しています。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = Group.objects.create(
            name=serializer.validated_data["name"],
            invite_code=secrets.token_hex(4).upper(),
        )
        GroupMember.objects.create(group=group, user=request.user)
        return Response({"detail": "作成しました。"}, status=status.HTTP_201_CREATED)

    def patch(self, request):
        member = get_membership(request.user)
        if member is None:
            return Response(
                {"detail": "グループに参加していません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = GroupShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        share = serializer.validated_data["share_percent"]
        member.share_percent = share
        member.save(update_fields=["share_percent"])
        # 2人グループ: 相手のデフォルトは残りの割合に揃える
        member.group.members.exclude(user=request.user).update(share_percent=100 - share)
        return Response({"detail": "更新しました。"})


class GroupJoinView(APIView):
    def post(self, request):
        if get_membership(request.user):
            return Response(
                {"detail": "既にグループに参加しています。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = GroupJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invite_code"].strip().upper()
        group = Group.objects.filter(invite_code=code).first()
        if group is None:
            return Response(
                {"detail": "招待コードが見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if group.members.count() >= Group.MAX_MEMBERS:
            return Response(
                {"detail": f"このグループは満員です ({Group.MAX_MEMBERS}人まで)。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 参加者のデフォルト負担割合は既存メンバーの残り
        existing = group.members.first()
        share = 100 - existing.share_percent if existing else 50
        GroupMember.objects.create(group=group, user=request.user, share_percent=share)
        return Response({"detail": "参加しました。"}, status=status.HTTP_201_CREATED)


class GroupLeaveView(APIView):
    def post(self, request):
        member = get_membership(request.user)
        if member is None:
            return Response(
                {"detail": "グループに参加していません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        group = member.group
        member.delete()
        if not group.members.exists():
            group.delete()
        return Response({"detail": "退出しました。"})


class SettleView(APIView):
    """今月の精算を記録する"""

    def post(self, request):
        member = get_membership(request.user)
        if member is None:
            return Response(
                {"detail": "グループに参加していません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SettleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        first, last = month_range(serializer.validated_data["month"])

        shared = build_shared_summary(request.user, member, first, last)
        transfer = shared.get("transfer")
        if not transfer:
            return Response(
                {"detail": "精算する差額がありません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partner = shared["partner"]
        if transfer["direction"] == "receive":
            from_id, to_id = partner["id"], request.user.id
        else:
            from_id, to_id = request.user.id, partner["id"]
        try:
            with transaction.atomic():
                settlement = Settlement.objects.create(
                    group=member.group,
                    month=first,
                    from_user_id=from_id,
                    to_user_id=to_id,
                    amount=transfer["amount"],
                )
        except IntegrityError:
            return Response(
                {"detail": "この月は既に精算済みです。"}, status=status.HTTP_409_CONFLICT
            )
        return Response({"id": settlement.id}, status=status.HTTP_201_CREATED)


class SettlementDeleteView(APIView):
    def delete(self, request, pk):
        member = get_membership(request.user)
        settlement = Settlement.objects.filter(pk=pk).first()
        if settlement is None or member is None or settlement.group_id != member.group_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        settlement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
