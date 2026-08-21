import calendar
import re
import secrets
from collections import defaultdict
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .ocr import OcrUnavailableError, ocr_pdf

from .models import (
    AccountBalance,
    Category,
    Group,
    GroupMember,
    MerchantRule,
    PaymentMethod,
    Preference,
    RecurringPayment,
    Settlement,
    Transaction,
)
from .serializers import (
    AccountBalanceSerializer,
    CategorySerializer,
    GroupCreateSerializer,
    GroupJoinSerializer,
    GroupShareSerializer,
    ImportSerializer,
    ImportSuggestSerializer,
    PaymentMethodSerializer,
    PreferenceSerializer,
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
        member = get_membership(user)
        if self.action == "list":
            # 一覧: 自分の親レベル取引 + 相手の共有分 (相手の共有内訳行も行として見える)
            cond = Q(user=user, parent__isnull=True)
            if member:
                cond |= Q(group=member.group) & ~Q(user=user)
        else:
            # 個別取得/編集: 自分の全取引 (内訳行含む) + 共有分
            cond = Q(user=user)
            if member:
                cond |= Q(group=member.group)
        qs = (
            Transaction.objects.filter(cond)
            .select_related("category", "user", "payment_method")
            .prefetch_related("items__category")
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
        tx = serializer.save()
        # 親の日付変更は内訳行に追随させる
        if tx.parent_id is None:
            tx.items.exclude(date=tx.date).update(date=tx.date)

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied("共有相手の記録は削除できません。")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="items-share")
    def items_share(self, request, pk=None):
        """内訳行の共有設定を一括変更する"""
        tx = self.get_object()
        if tx.user_id != request.user.id:
            raise PermissionDenied("共有相手の記録は編集できません。")
        shared = bool(request.data.get("shared"))
        if shared:
            member = get_membership(request.user)
            if member is None:
                return Response(
                    {"detail": "グループに参加していないため共有できません。"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            share = request.data.get("payer_share_percent")
            if share is None:
                share = member.share_percent
            share = int(share)
            if not 0 <= share <= 100:
                return Response(
                    {"detail": "負担割合は 0〜100 で指定してください。"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updated = tx.items.update(group=member.group, payer_share_percent=share)
        else:
            updated = tx.items.update(group=None, payer_share_percent=None)
        return Response({"updated": updated})


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
            payment_method=rp.payment_method,
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

        # 親子取引 (カード内訳) に対応するため Python 側で集計する。
        # 合計・支払方法別は親レベルの金額を1回だけ数え、
        # カテゴリ内訳は内訳行のカテゴリ + 残額を親カテゴリに割り当てる。
        month_txs = list(
            Transaction.objects.filter(user=user, date__range=(first, last)).select_related(
                "category", "payment_method"
            )
        )
        children_by_parent = defaultdict(list)
        top_txs = []
        for tx in month_txs:
            if tx.parent_id:
                children_by_parent[tx.parent_id].append(tx)
            else:
                top_txs.append(tx)

        # 「前月の給料で当月をやりくり」設定: 収入は前月分を表示・収支計算に使う
        pref = Preference.objects.filter(user=user).first()
        use_prev_income = pref.use_prev_month_income if pref else False
        income_month = month
        if use_prev_income:
            prev_day = first - timedelta(days=1)
            income_month = f"{prev_day.year}-{prev_day.month:02d}"

        income_total = expense_total = 0
        category_totals = {}
        method_totals = {}

        def add_category(category, amount):
            entry = category_totals.setdefault(
                category.id,
                {
                    "category_id": category.id,
                    "name": category.name,
                    "color": category.color,
                    "type": category.type,
                    "total": 0,
                },
            )
            entry["total"] += amount

        for tx in top_txs:
            if tx.category.type == Category.Type.INCOME:
                if use_prev_income:
                    continue  # 当月の収入は翌月のやりくり原資として扱う
                income_total += tx.amount
            else:
                expense_total += tx.amount
                method = method_totals.setdefault(
                    tx.payment_method_id,
                    {
                        "id": tx.payment_method_id,
                        "name": tx.payment_method.name if tx.payment_method else "未設定",
                        "total": 0,
                    },
                )
                method["total"] += tx.amount

            kids = children_by_parent.get(tx.id, [])
            if kids:
                remainder = tx.amount
                for child in kids:
                    add_category(child.category, child.amount)
                    remainder -= child.amount
                if remainder > 0:
                    add_category(tx.category, remainder)
            else:
                add_category(tx.category, tx.amount)

        income_by_category, expense_by_category = [], []
        for entry in sorted(category_totals.values(), key=lambda e: -e["total"]):
            type_ = entry.pop("type")
            if type_ == Category.Type.INCOME:
                income_by_category.append(entry)
            else:
                expense_by_category.append(entry)

        if use_prev_income:
            # 前月の収入をやりくり原資として集計
            prev_first, prev_last = month_range(income_month)
            prev_rows = (
                Transaction.objects.filter(
                    user=user,
                    parent__isnull=True,
                    date__range=(prev_first, prev_last),
                    category__type=Category.Type.INCOME,
                )
                .values("category_id", "category__name", "category__color")
                .annotate(total=Sum("amount"))
                .order_by("-total")
            )
            income_by_category = [
                {
                    "category_id": row["category_id"],
                    "name": row["category__name"],
                    "color": row["category__color"],
                    "total": row["total"],
                }
                for row in prev_rows
            ]
            income_total = sum(row["total"] for row in prev_rows)

        payment_methods = sorted(method_totals.values(), key=lambda m: -m["total"])

        # 定期支払: その月が支払対象月のものだけを予定として並べる
        paid_txs = {
            tx.recurring_payment_id: tx for tx in month_txs if tx.recurring_payment_id
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

        # 口座残高の想定額 (基準残高 + 基準日より後の収支累計 ± 精算)
        anchor = AccountBalance.objects.filter(user=user).first()
        if anchor is None:
            balance_forecast = {"anchor": None}
        else:
            rows = (
                Transaction.objects.filter(
                    user=user, parent__isnull=True, date__gt=anchor.as_of_date
                )
                .values("category__type")
                .annotate(total=Sum("amount"))
            )
            income_after = expense_after = 0
            for row in rows:
                if row["category__type"] == Category.Type.INCOME:
                    income_after = row["total"]
                else:
                    expense_after = row["total"]
            received = (
                Settlement.objects.filter(
                    to_user=user, created_at__date__gt=anchor.as_of_date
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )
            paid_out = (
                Settlement.objects.filter(
                    from_user=user, created_at__date__gt=anchor.as_of_date
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )
            projected = anchor.amount + income_after - expense_after + received - paid_out
            balance_forecast = {
                "anchor": {"amount": anchor.amount, "as_of_date": str(anchor.as_of_date)},
                "projected": projected,
                "unpaid_recurring": remaining_total,
                "after_required": projected - remaining_total,
            }

        # 支払合計予想: 未払いの固定費を支出に上乗せして月末見込みを表示する設定
        forecast_expense = pref.forecast_expense if pref else False
        expense_actual = expense_total
        if forecast_expense:
            expense_total = expense_total + remaining_total

        return Response(
            {
                "month": month,
                "income_month": income_month,
                "income_total": income_total,
                "expense_total": expense_total,
                "expense_forecast": {
                    "enabled": forecast_expense,
                    "actual": expense_actual,
                    "unpaid_recurring": remaining_total,
                },
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
                "balance_forecast": balance_forecast,
            }
        )


class ImportOcrView(APIView):
    """画像 PDF をアップロードして OCR で明細の行データに変換する"""

    parser_classes = [MultiPartParser]

    def post(self, request):
        f = request.FILES.get("file")
        if f is None:
            return Response(
                {"detail": "ファイルがありません。"}, status=status.HTTP_400_BAD_REQUEST
            )
        if f.size > 15 * 1024 * 1024:
            return Response(
                {"detail": "ファイルが大きすぎます (15MB まで)。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        head = f.read(5)
        f.seek(0)
        if head != b"%PDF-":
            return Response(
                {"detail": "PDF ファイルではありません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            rows = ocr_pdf(f.read())
        except OcrUnavailableError as e:
            return Response(
                {"detail": f"サーバーに OCR ツールが未導入です ({e})。"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            return Response(
                {"detail": "OCR 処理に失敗しました。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"rows": rows, "max_pages": 3})


class ImportSuggestView(APIView):
    """CSV取込プレビュー用: 店名ごとの学習済み設定と、二重取込の注意情報を返す"""

    def post(self, request):
        serializer = ImportSuggestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        query_rows = data.get("rows")
        if query_rows is None:
            query_rows = [{"merchant": m, "amount": None} for m in data.get("merchants", [])]

        merchants = {r["merchant"] for r in query_rows}
        rules = list(
            MerchantRule.objects.filter(user=request.user, merchant__in=merchants)
            .select_related("category")
            .order_by("-updated_at")
        )

        def rule_payload(rule):
            return {
                "category_id": rule.category_id,
                "shared": rule.shared,
                "payer_share_percent": rule.payer_share_percent,
                "recurring_payment_id": rule.recurring_payment_id,
            }

        def resolve(merchant, amount):
            """完全一致 (店名+金額) > 金額なしルール > 同店名の最新ルール"""
            candidates = [r for r in rules if r.merchant == merchant]
            if not candidates:
                return None
            if amount is not None:
                exact = next((r for r in candidates if r.amount == amount), None)
                if exact:
                    return rule_payload(exact)
            wildcard = next((r for r in candidates if r.amount is None), None)
            if wildcard:
                return rule_payload(wildcard)
            return rule_payload(candidates[0])  # updated_at 降順の先頭

        # 行ごとの解決結果 (入力 rows と同じ順序)
        row_suggestions = [resolve(r["merchant"], r.get("amount")) for r in query_rows]
        # 旧形式 (店名キー) も維持
        suggestions = {}
        for r, s in zip(query_rows, row_suggestions):
            if s and r["merchant"] not in suggestions:
                suggestions[r["merchant"]] = s

        existing_statement = False
        paid_recurring = {}
        method = data.get("payment_method_id")
        month = data.get("month")
        if month:
            first, last = month_range(month)
            if method:
                existing_statement = Transaction.objects.filter(
                    user=request.user,
                    parent__isnull=True,
                    payment_method=method,
                    date__range=(first, last),
                    items__isnull=False,
                ).exists()
            # その月に既に支払記録がある定期支払 (二重計上防止の判定用)
            for tx in Transaction.objects.filter(
                user=request.user,
                recurring_payment__isnull=False,
                date__range=(first, last),
            ):
                paid_recurring[str(tx.recurring_payment_id)] = (
                    "standalone" if tx.parent_id is None else "imported"
                )

        return Response(
            {
                "suggestions": suggestions,
                "row_suggestions": row_suggestions,
                "existing_statement": existing_statement,
                "paid_recurring": paid_recurring,
            }
        )


class ImportTransactionsView(APIView):
    """CSV取込の本体: カード請求(親)+内訳行を一括作成し、店名ルールを学習する"""

    def post(self, request):
        serializer = ImportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        member = get_membership(request.user)
        parent_data = data["parent"]
        month_first, month_last = month_range(parent_data["date"].strftime("%Y-%m"))

        with transaction.atomic():
            parent = Transaction.objects.create(
                user=request.user,
                category=parent_data["category_id"],
                amount=parent_data["amount"],
                date=parent_data["date"],
                memo=parent_data.get("memo", ""),
                payment_method=data["payment_method_id"],
            )
            for row in data["rows"]:
                # 定期支払への紐付け時の二重計上防止:
                # 「支払済にする」で作られた単独記録があれば置き換え (削除)、
                # 既に別の取込 (内訳行) で記録済みならこの行は紐付けない
                rp = row.get("recurring_payment_id")
                if rp is not None:
                    existing = Transaction.objects.filter(
                        user=request.user,
                        recurring_payment=rp,
                        date__range=(month_first, month_last),
                    )
                    if existing.filter(parent__isnull=False).exists():
                        row["recurring_payment_id"] = None
                    else:
                        existing.filter(parent__isnull=True).delete()
                shared = row["shared"] and member is not None
                share = None
                if shared:
                    share = row.get("payer_share_percent")
                    if share is None:
                        share = member.share_percent
                Transaction.objects.create(
                    user=request.user,
                    parent=parent,
                    category=row["category_id"],
                    amount=row["amount"],
                    date=parent.date,
                    memo=f"{row['used_date'].month}/{row['used_date'].day} {row['merchant']}",
                    group=member.group if shared else None,
                    payer_share_percent=share,
                    # 定期支払に紐付けると、その月の固定費が支払済扱いになる
                    recurring_payment=row.get("recurring_payment_id"),
                )
                # 店名+金額の完全一致で学習 (同じ店名でも金額ごとに別カテゴリにできる。
                # 例: ＥＴＣカード売上 1,190円 → 通勤ETC)
                MerchantRule.objects.update_or_create(
                    user=request.user,
                    merchant=row["merchant"],
                    amount=row["amount"],
                    defaults={
                        "category": row["category_id"],
                        "shared": row["shared"],
                        "payer_share_percent": row.get("payer_share_percent"),
                        "recurring_payment": row.get("recurring_payment_id"),
                    },
                )

        return Response(
            TransactionSerializer(parent, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PreferenceView(APIView):
    """ユーザー設定 (前月収入でやりくり など)"""

    def get(self, request):
        pref, _ = Preference.objects.get_or_create(user=request.user)
        return Response(PreferenceSerializer(pref).data)

    def put(self, request):
        pref, _ = Preference.objects.get_or_create(user=request.user)
        serializer = PreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BalanceView(APIView):
    """口座残高 (基準残高) の取得・登録"""

    def get(self, request):
        balance = AccountBalance.objects.filter(user=request.user).first()
        return Response(
            {"balance": AccountBalanceSerializer(balance).data if balance else None}
        )

    def put(self, request):
        serializer = AccountBalanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AccountBalance.objects.update_or_create(
            user=request.user, defaults=serializer.validated_data
        )
        return Response({"detail": "更新しました。"})


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
