from rest_framework import serializers

from .models import Category, RecurringPayment, Transaction


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "type", "color", "sort_order"]


class UserCategoryField(serializers.PrimaryKeyRelatedField):
    """リクエストユーザー所有のカテゴリのみ参照可能にする(他人のカテゴリIDは 400)。"""

    def get_queryset(self):
        return Category.objects.filter(user=self.context["request"].user)


class TransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = UserCategoryField(source="category", write_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "date",
            "memo",
            "category",
            "category_id",
            "recurring_payment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["recurring_payment", "created_at", "updated_at"]


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
            "is_active",
            "memo",
        ]


class PaySerializer(serializers.Serializer):
    month = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$")
    date = serializers.DateField(required=False)
    amount = serializers.IntegerField(required=False, min_value=1)
