from .models import Category, PaymentMethod

# (type, name, color)
DEFAULT_CATEGORIES = [
    (Category.Type.EXPENSE, "食費", "#ef5350"),
    (Category.Type.EXPENSE, "日用品", "#ff7043"),
    (Category.Type.EXPENSE, "住居", "#7e57c2"),
    (Category.Type.EXPENSE, "水道光熱", "#29b6f6"),
    (Category.Type.EXPENSE, "通信", "#26a69a"),
    (Category.Type.EXPENSE, "交通", "#66bb6a"),
    (Category.Type.EXPENSE, "医療", "#ec407a"),
    (Category.Type.EXPENSE, "娯楽", "#ffa726"),
    (Category.Type.EXPENSE, "交際費", "#ab47bc"),
    (Category.Type.EXPENSE, "その他", "#90a4ae"),
    (Category.Type.INCOME, "給与", "#4caf50"),
    (Category.Type.INCOME, "賞与", "#8bc34a"),
    (Category.Type.INCOME, "その他", "#9e9e9e"),
]


DEFAULT_PAYMENT_METHODS = ["現金"]


def seed_default_categories(user):
    Category.objects.bulk_create(
        Category(user=user, type=type_, name=name, color=color, sort_order=i)
        for i, (type_, name, color) in enumerate(DEFAULT_CATEGORIES)
    )
    PaymentMethod.objects.bulk_create(
        PaymentMethod(user=user, name=name, sort_order=i)
        for i, name in enumerate(DEFAULT_PAYMENT_METHODS)
    )
