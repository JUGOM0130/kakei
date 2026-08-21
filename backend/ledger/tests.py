from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .defaults import DEFAULT_CATEGORIES, seed_default_categories
from .models import Category, RecurringPayment, Transaction

User = get_user_model()


class BaseTestCase(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="testpass12345")
        self.bob = User.objects.create_user("bob", password="testpass12345")
        seed_default_categories(self.alice)
        seed_default_categories(self.bob)
        self.alice_food = Category.objects.get(user=self.alice, name="食費")
        self.alice_salary = Category.objects.get(
            user=self.alice, name="給与", type=Category.Type.INCOME
        )
        self.alice_housing = Category.objects.get(user=self.alice, name="住居")


class RegisterTests(APITestCase):
    def test_register_seeds_default_categories_and_logs_in(self):
        res = self.client.post(
            "/api/auth/register/",
            {"username": "newuser", "password": "goodpass12345"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(username="newuser")
        self.assertEqual(user.categories.count(), len(DEFAULT_CATEGORIES))
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "newuser")


class IsolationTests(BaseTestCase):
    def test_users_cannot_see_each_others_data(self):
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=1000, date="2026-08-01"
        )
        self.client.force_login(self.bob)
        res = self.client.get("/api/transactions/", {"month": "2026-08"})
        self.assertEqual(res.json(), [])
        tx_id = Transaction.objects.get(user=self.alice).id
        self.assertEqual(self.client.get(f"/api/transactions/{tx_id}/").status_code, 404)

    def test_cannot_use_other_users_category(self):
        self.client.force_login(self.bob)
        res = self.client.post(
            "/api/transactions/",
            {"category_id": self.alice_food.id, "amount": 500, "date": "2026-08-01"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class CategoryTests(BaseTestCase):
    def test_delete_category_in_use_returns_409(self):
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=1000, date="2026-08-01"
        )
        self.client.force_login(self.alice)
        res = self.client.delete(f"/api/categories/{self.alice_food.id}/")
        self.assertEqual(res.status_code, 409)

    def test_duplicate_category_name_returns_400(self):
        self.client.force_login(self.alice)
        res = self.client.post(
            "/api/categories/", {"name": "食費", "type": "expense"}, format="json"
        )
        self.assertEqual(res.status_code, 400)


class SummaryTests(BaseTestCase):
    def test_summary_totals_and_recurring(self):
        Transaction.objects.create(
            user=self.alice, category=self.alice_salary, amount=300000, date="2026-08-25"
        )
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=1500, date="2026-08-03"
        )
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=2500, date="2026-08-10"
        )
        # 前月分は含まれない
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=9999, date="2026-07-31"
        )
        rent = RecurringPayment.objects.create(
            user=self.alice,
            name="家賃",
            amount=70000,
            category=self.alice_housing,
            day_of_month=27,
        )
        RecurringPayment.objects.create(
            user=self.alice,
            name="サブスク",
            amount=1980,
            category=self.alice_food,
            day_of_month=1,
        )

        self.client.force_login(self.alice)
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertEqual(data["income_total"], 300000)
        self.assertEqual(data["expense_total"], 4000)
        self.assertEqual(data["balance"], 296000)
        self.assertEqual(data["recurring"]["required_total"], 71980)
        self.assertEqual(data["recurring"]["paid_total"], 0)
        self.assertEqual(data["recurring"]["remaining_total"], 71980)

        # 支払済にする
        res = self.client.post(
            f"/api/recurring-payments/{rent.id}/pay/", {"month": "2026-08"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["date"], "2026-08-27")

        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertEqual(data["recurring"]["paid_total"], 70000)
        self.assertEqual(data["recurring"]["remaining_total"], 1980)
        rent_item = next(i for i in data["recurring"]["items"] if i["id"] == rent.id)
        self.assertTrue(rent_item["paid"])

        # 二重払いは 409
        res = self.client.post(
            f"/api/recurring-payments/{rent.id}/pay/", {"month": "2026-08"}, format="json"
        )
        self.assertEqual(res.status_code, 409)

        # 生成された取引を削除すると未払いに戻る
        self.client.delete(f"/api/transactions/{rent_item['transaction_id']}/")
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        rent_item = next(i for i in data["recurring"]["items"] if i["id"] == rent.id)
        self.assertFalse(rent_item["paid"])

    def test_pay_day_clamped_to_month_end(self):
        rp = RecurringPayment.objects.create(
            user=self.alice,
            name="月末払い",
            amount=5000,
            category=self.alice_housing,
            day_of_month=31,
        )
        self.client.force_login(self.alice)
        res = self.client.post(
            f"/api/recurring-payments/{rp.id}/pay/", {"month": "2026-02"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["date"], "2026-02-28")

    def test_summary_requires_valid_month(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get("/api/summary/monthly/").status_code, 400)
        self.assertEqual(
            self.client.get("/api/summary/monthly/", {"month": "2026-13"}).status_code, 400
        )
