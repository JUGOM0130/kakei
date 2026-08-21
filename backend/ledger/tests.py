from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .defaults import DEFAULT_CATEGORIES, seed_default_categories
from .models import Category, Group, GroupMember, RecurringPayment, Transaction

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


class GroupTests(BaseTestCase):
    def _create_and_join(self):
        self.client.force_login(self.alice)
        self.assertEqual(
            self.client.post("/api/group/", {"name": "我が家"}, format="json").status_code,
            201,
        )
        code = self.client.get("/api/group/").json()["group"]["invite_code"]
        self.client.force_login(self.bob)
        res = self.client.post("/api/group/join/", {"invite_code": code}, format="json")
        self.assertEqual(res.status_code, 201)
        return code

    def test_group_join_and_capacity(self):
        code = self._create_and_join()
        carol = User.objects.create_user("carol", password="testpass12345")
        self.client.force_login(carol)
        res = self.client.post("/api/group/join/", {"invite_code": code}, format="json")
        self.assertEqual(res.status_code, 400)  # 満員

    def test_cannot_join_twice(self):
        code = self._create_and_join()
        self.client.force_login(self.bob)
        res = self.client.post("/api/group/join/", {"invite_code": code}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_share_percent_update_syncs_partner(self):
        self._create_and_join()
        self.client.force_login(self.alice)
        self.client.patch("/api/group/", {"share_percent": 70}, format="json")
        data = self.client.get("/api/group/").json()["group"]
        shares = {m["username"]: m["share_percent"] for m in data["members"]}
        self.assertEqual(shares["alice"], 70)
        self.assertEqual(shares["bob"], 30)


class SharedTransactionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.group = Group.objects.create(name="我が家", invite_code="ABCD1234")
        GroupMember.objects.create(group=self.group, user=self.alice, share_percent=50)
        GroupMember.objects.create(group=self.group, user=self.bob, share_percent=50)
        self.bob_food = Category.objects.get(user=self.bob, name="食費")

    def test_shared_transaction_visible_but_not_editable_by_partner(self):
        self.client.force_login(self.alice)
        res = self.client.post(
            "/api/transactions/",
            {
                "category_id": self.alice_food.id,
                "amount": 10000,
                "date": "2026-08-05",
                "shared": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        tx_id = res.json()["id"]
        self.assertTrue(res.json()["is_shared"])
        self.assertEqual(res.json()["payer_share_percent"], 50)

        # 相手からも見える
        self.client.force_login(self.bob)
        listed = self.client.get("/api/transactions/", {"month": "2026-08"}).json()
        self.assertEqual(len(listed), 1)
        self.assertFalse(listed[0]["is_mine"])
        # 編集・削除は不可
        self.assertEqual(
            self.client.patch(
                f"/api/transactions/{tx_id}/", {"amount": 1}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.delete(f"/api/transactions/{tx_id}/").status_code, 403)

    def test_private_transaction_not_visible_to_partner(self):
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=500, date="2026-08-01"
        )
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get("/api/transactions/", {"month": "2026-08"}).json(), []
        )

    def test_shared_summary_and_settlement(self):
        # alice が 10000 を折半で、bob が 3000 を bob70% で支払い
        Transaction.objects.create(
            user=self.alice,
            category=self.alice_food,
            amount=10000,
            date="2026-08-05",
            group=self.group,
            payer_share_percent=50,
        )
        Transaction.objects.create(
            user=self.bob,
            category=self.bob_food,
            amount=3000,
            date="2026-08-10",
            group=self.group,
            payer_share_percent=70,
        )
        self.client.force_login(self.alice)
        shared = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()[
            "shared"
        ]
        # alice: 立替10000 / 負担 5000 + 3000*30% = 5900 → bob から 4100 受取
        self.assertEqual(shared["my_paid"], 10000)
        self.assertEqual(shared["partner_paid"], 3000)
        self.assertEqual(shared["my_burden"], 5900)
        self.assertEqual(shared["partner_burden"], 7100)
        self.assertEqual(shared["transfer"]["amount"], 4100)
        self.assertEqual(shared["transfer"]["direction"], "receive")
        self.assertIsNone(shared["settlement"])

        # 精算記録
        res = self.client.post("/api/settlements/", {"month": "2026-08"}, format="json")
        self.assertEqual(res.status_code, 201)
        # 二重精算は 409
        res = self.client.post("/api/settlements/", {"month": "2026-08"}, format="json")
        self.assertEqual(res.status_code, 409)
        shared = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()[
            "shared"
        ]
        self.assertEqual(shared["settlement"]["amount"], 4100)
        self.assertEqual(shared["settlement"]["from"], "bob")

    def test_shared_requires_group(self):
        carol = User.objects.create_user("carol", password="testpass12345")
        seed_default_categories(carol)
        self.client.force_login(carol)
        res = self.client.post(
            "/api/transactions/",
            {
                "category_id": Category.objects.get(user=carol, name="食費").id,
                "amount": 100,
                "date": "2026-08-01",
                "shared": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class RecurringIntervalTests(BaseTestCase):
    def test_interval_due_months(self):
        # 固定資産税: 4ヶ月ごと、2026-05 が該当月 → 5月/9月/翌1月が対象
        rp = RecurringPayment.objects.create(
            user=self.alice,
            name="固定資産税",
            amount=40000,
            category=self.alice_housing,
            day_of_month=30,
            interval_months=4,
            anchor_month="2026-05-01",
        )
        self.client.force_login(self.alice)
        for month, due in [
            ("2026-05", True),
            ("2026-06", False),
            ("2026-09", True),
            ("2027-01", True),
            ("2026-04", False),  # 該当月より前
        ]:
            items = self.client.get("/api/summary/monthly/", {"month": month}).json()[
                "recurring"
            ]["items"]
            self.assertEqual(
                any(i["id"] == rp.id for i in items), due, f"month={month}"
            )

        # 対象外の月への pay は 400
        res = self.client.post(
            f"/api/recurring-payments/{rp.id}/pay/", {"month": "2026-06"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            f"/api/recurring-payments/{rp.id}/pay/", {"month": "2026-09"}, format="json"
        )
        self.assertEqual(res.status_code, 201)

    def test_interval_requires_anchor(self):
        self.client.force_login(self.alice)
        res = self.client.post(
            "/api/recurring-payments/",
            {
                "name": "水道",
                "amount": 5000,
                "category_id": self.alice_housing.id,
                "day_of_month": 26,
                "interval_months": 2,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class PaymentMethodTests(BaseTestCase):
    def test_default_payment_method_seeded_and_totals(self):
        self.client.force_login(self.alice)
        methods = self.client.get("/api/payment-methods/").json()
        self.assertEqual(methods[0]["name"], "現金")
        card = self.client.post(
            "/api/payment-methods/", {"name": "カードA"}, format="json"
        ).json()

        self.client.post(
            "/api/transactions/",
            {
                "category_id": self.alice_food.id,
                "amount": 1200,
                "date": "2026-08-01",
                "payment_method_id": card["id"],
            },
            format="json",
        )
        self.client.post(
            "/api/transactions/",
            {"category_id": self.alice_food.id, "amount": 800, "date": "2026-08-02"},
            format="json",
        )
        summary = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        totals = {m["name"]: m["total"] for m in summary["payment_methods"]}
        self.assertEqual(totals["カードA"], 1200)
        self.assertEqual(totals["未設定"], 800)

        # 絞り込み
        listed = self.client.get(
            "/api/transactions/", {"month": "2026-08", "payment_method": card["id"]}
        ).json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["amount"], 1200)
