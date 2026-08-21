from rest_framework import serializers

from .models import (
    Category,
    GroupMember,
    PaymentMethod,
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


class TransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = UserCategoryField(source="category", write_only=True)
    payment_method = PaymentMethodSerializer(read_only=True)
    payment_method_id = UserPaymentMethodField(
        source="payment_method", write_only=True, required=False, allow_null=True
    )
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

    def get_payer(self, obj):
        return {"id": obj.user_id, "username": obj.user.username}

    def get_is_mine(self, obj):
        return obj.user_id == self.context["request"].user.id

    def get_is_shared(self, obj):
        return obj.group_id is not None

    def validate(self, attrs):
        shared = attrs.pop("shared", None)
        if shared is None:
            return attrs
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
        return attrs


class RecurringPaymentSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = UserCategoryField(source="category", write_only=True)

    class Meta:
        model = RecurringPayment
        fields = [
            "id",
            "name",
            "amount",
            "category",
            "category_id",
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
