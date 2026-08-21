from django.db.models import Sum
from rest_framework import serializers

from .models import (
    AccountBalance,
    Category,
    GroupMember,
    PaymentMethod,
    Preference,
    RecurringPayment,
    Transaction,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "type", "color", "sort_order"]


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["id", "name", "sort_order"]


class UserCategoryField(serializers.PrimaryKeyRelatedField):
    """リクエストユーザー所有のカテゴリのみ参照可能にする(他人のカテゴリIDは 400)。"""

    def get_queryset(self):
        return Category.objects.filter(user=self.context["request"].user)


class UserPaymentMethodField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.context["request"].user)


class UserRecurringPaymentField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return RecurringPayment.objects.filter(user=self.context["request"].user)


class UserParentTransactionField(serializers.PrimaryKeyRelatedField):
    """内訳の親: 自分の親レベル取引のみ (孫は構造上作れない)。"""

    def get_queryset(self):
        return Transaction.objects.filter(
            user=self.context["request"].user, parent__isnull=True
        )


class TransactionItemSerializer(serializers.ModelSerializer):
    """内訳行のネスト表示用"""

    category = CategorySerializer(read_only=True)
    is_shared = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ["id", "amount", "memo", "category", "is_shared", "payer_share_percent"]

    def get_is_shared(self, obj):
        return obj.group_id is not None


class TransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = UserCategoryField(source="category", write_only=True)
    payment_method = PaymentMethodSerializer(read_only=True)
    payment_method_id = UserPaymentMethodField(
        source="payment_method", write_only=True, required=False, allow_null=True
    )
    parent = UserParentTransactionField(required=False, allow_null=True)
    items = TransactionItemSerializer(many=True, read_only=True)
    # 共有支払い: shared=true で自分のグループに共有される
    shared = serializers.BooleanField(write_only=True, required=False)
    payer_share_percent = serializers.IntegerField(
        min_value=0, max_value=100, required=False, allow_null=True
    )
    payer = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "date",
            "memo",
            "category",
            "category_id",
            "payment_method",
            "payment_method_id",
            "parent",
            "items",
            "shared",
            "is_shared",
            "payer_share_percent",
            "payer",
            "is_mine",
            "recurring_payment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["recurring_payment", "created_at", "updated_at"]
        extra_kwargs = {"date": {"required": False}}

    def get_payer(self, obj):
        return {"id": obj.user_id, "username": obj.user.username}

    def get_is_mine(self, obj):
        return obj.user_id == self.context["request"].user.id

    def get_is_shared(self, obj):
        return obj.group_id is not None

    def validate(self, attrs):
        # --- 共有指定の解決 ---
        shared = attrs.pop("shared", None)
        if shared is not None:
            if shared:
                member = (
                    GroupMember.objects.filter(user=self.context["request"].user)
                    .select_related("group")
                    .first()
                )
                if member is None:
                    raise serializers.ValidationError(
                        {"shared": "グループに参加していないため共有できません。"}
                    )
                attrs["group"] = member.group
                if attrs.get("payer_share_percent") is None:
                    attrs["payer_share_percent"] = member.share_percent
            else:
                attrs["group"] = None
                attrs["payer_share_percent"] = None

        # --- 親子 (カード内訳) の検証 ---
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent is not None:
            category = attrs.get("category", getattr(self.instance, "category", None))
            if parent.category.type != Category.Type.EXPENSE or (
                category and category.type != Category.Type.EXPENSE
            ):
                raise serializers.ValidationError(
                    {"parent": "内訳は支出の取引にのみ追加できます。"}
                )
            if self.instance and self.instance.items.exists():
                raise serializers.ValidationError(
                    {"parent": "内訳を持つ取引を内訳行にはできません。"}
                )
            if attrs.get("payment_method") is not None:
                raise serializers.ValidationError(
                    {"payment_method_id": "内訳行に支払方法は設定できません (親に含まれます)。"}
                )
            # 内訳合計 ≤ 親金額
            amount = attrs.get("amount", getattr(self.instance, "amount", 0))
            siblings = parent.items.all()
            if self.instance:
                siblings = siblings.exclude(pk=self.instance.pk)
            used = siblings.aggregate(total=Sum("amount"))["total"] or 0
            if used + amount > parent.amount:
                raise serializers.ValidationError(
                    {
                        "amount": f"内訳の合計が親の金額 (¥{parent.amount:,}) を超えます "
                        f"(残り ¥{parent.amount - used:,})。"
                    }
                )
            # 日付は常に親と同じ
            attrs["date"] = parent.date
        else:
            if not attrs.get("date", getattr(self.instance, "date", None)):
                raise serializers.ValidationError({"date": "日付を入力してください。"})

        # 内訳を持つ親は本体を共有できない (共有は内訳行で行う)
        has_items = self.instance is not None and self.instance.items.exists()
        if has_items:
            if attrs.get("group") is not None:
                raise serializers.ValidationError(
                    {"shared": "内訳がある取引は本体を共有できません。内訳行ごとに共有してください。"}
                )
            new_amount = attrs.get("amount", self.instance.amount)
            items_total = self.instance.items.aggregate(total=Sum("amount"))["total"] or 0
            if new_amount < items_total:
                raise serializers.ValidationError(
                    {"amount": f"内訳の合計 (¥{items_total:,}) を下回る金額にはできません。"}
                )
        return attrs


class RecurringPaymentSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = UserCategoryField(source="category", write_only=True)
    payment_method = PaymentMethodSerializer(read_only=True)
    payment_method_id = UserPaymentMethodField(
        source="payment_method", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = RecurringPayment
        fields = [
            "id",
            "name",
            "amount",
            "category",
            "category_id",
            "payment_method",
            "payment_method_id",
            "day_of_month",
            "interval_months",
            "anchor_month",
            "is_shared",
            "payer_share_percent",
            "is_active",
            "memo",
        ]

    def validate(self, attrs):
        interval = attrs.get(
            "interval_months", getattr(self.instance, "interval_months", 1)
        )
        anchor = attrs.get("anchor_month", getattr(self.instance, "anchor_month", None))
        if interval > 1 and anchor is None:
            raise serializers.ValidationError(
                {"anchor_month": "間隔が毎月以外の場合は該当月の指定が必要です。"}
            )
        if anchor is not None:
            attrs["anchor_month"] = anchor.replace(day=1)
        if attrs.get("is_shared"):
            user = self.context["request"].user
            if not GroupMember.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {"is_shared": "グループに参加していないため共有できません。"}
                )
        return attrs


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preference
        fields = ["use_prev_month_income"]


class AccountBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountBalance
        fields = ["amount", "as_of_date", "updated_at"]
        read_only_fields = ["updated_at"]


class ImportRowSerializer(serializers.Serializer):
    merchant = serializers.CharField(max_length=200)
    used_date = serializers.DateField()
    amount = serializers.IntegerField(min_value=1)
    category_id = UserCategoryField()
    shared = serializers.BooleanField(default=False)
    payer_share_percent = serializers.IntegerField(
        min_value=0, max_value=100, required=False, allow_null=True
    )
    # この行を定期支払 (固定費) の支払として扱う
    recurring_payment_id = UserRecurringPaymentField(required=False, allow_null=True)


class ImportParentSerializer(serializers.Serializer):
    date = serializers.DateField()
    amount = serializers.IntegerField(min_value=1)
    category_id = UserCategoryField()
    memo = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )


class ImportSerializer(serializers.Serializer):
    payment_method_id = UserPaymentMethodField()
    parent = ImportParentSerializer()
    rows = ImportRowSerializer(many=True)

    def validate(self, attrs):
        if not attrs["rows"]:
            raise serializers.ValidationError({"rows": "取込む明細がありません。"})
        rows_total = sum(r["amount"] for r in attrs["rows"])
        if rows_total > attrs["parent"]["amount"]:
            raise serializers.ValidationError(
                {
                    "parent": f"明細の合計 (¥{rows_total:,}) が請求合計 "
                    f"(¥{attrs['parent']['amount']:,}) を超えています。"
                }
            )
        if any(r["shared"] for r in attrs["rows"]):
            user = self.context["request"].user
            if not GroupMember.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {"rows": "グループに参加していないため共有できません。"}
                )
        return attrs


class ImportSuggestRowSerializer(serializers.Serializer):
    merchant = serializers.CharField(max_length=200)
    amount = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class ImportSuggestSerializer(serializers.Serializer):
    # 店名+金額のペアで問い合わせる (金額付きルールの完全一致判定のため)
    rows = ImportSuggestRowSerializer(many=True, required=False)
    merchants = serializers.ListField(
        child=serializers.CharField(max_length=200),
        allow_empty=True,
        max_length=1000,
        required=False,
    )
    payment_method_id = UserPaymentMethodField(required=False, allow_null=True)
    month = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$", required=False)


class PaySerializer(serializers.Serializer):
    month = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$")
    date = serializers.DateField(required=False)
    amount = serializers.IntegerField(required=False, min_value=1)


class GroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)


class GroupJoinSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=8)


class GroupShareSerializer(serializers.Serializer):
    share_percent = serializers.IntegerField(min_value=0, max_value=100)


class SettleSerializer(serializers.Serializer):
    month = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$")
