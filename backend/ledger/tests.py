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


class CardBreakdownTests(BaseTestCase):
    """カード請求の親子取引 (内訳) のテスト"""

    def setUp(self):
        super().setUp()
        self.group = Group.objects.create(name="我が家", invite_code="ABCD1234")
        GroupMember.objects.create(group=self.group, user=self.alice, share_percent=50)
        GroupMember.objects.create(group=self.group, user=self.bob, share_percent=50)
        self.alice_daily = Category.objects.get(user=self.alice, name="日用品")
        self.alice_fun = Category.objects.get(user=self.alice, name="娯楽")

    def _create_parent_with_items(self):
        self.client.force_login(self.alice)
        parent = self.client.post(
            "/api/transactions/",
            {"category_id": self.alice_fun.id, "amount": 10000, "date": "2026-08-05"},
            format="json",
        ).json()
        r1 = self.client.post(
            "/api/transactions/",
            {
                "parent": parent["id"],
                "category_id": self.alice_food.id,
                "amount": 1000,
                "shared": True,
            },
            format="json",
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r1.json()["date"], "2026-08-05")  # 日付は親から複写
        r2 = self.client.post(
            "/api/transactions/",
            {
                "parent": parent["id"],
                "category_id": self.alice_daily.id,
                "amount": 2000,
                "shared": True,
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201)
        return parent, r1.json(), r2.json()

    def test_summary_counts_parent_once_and_splits_categories(self):
        parent, _, _ = self._create_parent_with_items()
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertEqual(data["expense_total"], 10000)  # 二重計上しない
        cats = {c["name"]: c["total"] for c in data["expense_by_category"]}
        self.assertEqual(cats["食費"], 1000)
        self.assertEqual(cats["日用品"], 2000)
        self.assertEqual(cats["娯楽"], 7000)  # 残額は親カテゴリ
        # 共有は内訳の3000だけ (折半 → alice負担1500)
        self.assertEqual(data["shared"]["total"], 3000)
        self.assertEqual(data["shared"]["my_paid"], 3000)
        self.assertEqual(data["shared"]["my_burden"], 1500)

    def test_items_sum_cannot_exceed_parent(self):
        parent, _, _ = self._create_parent_with_items()
        res = self.client.post(
            "/api/transactions/",
            {"parent": parent["id"], "category_id": self.alice_food.id, "amount": 7001},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_no_grandchildren(self):
        parent, item1, _ = self._create_parent_with_items()
        res = self.client.post(
            "/api/transactions/",
            {"parent": item1["id"], "category_id": self.alice_food.id, "amount": 100},
            format="json",
        )
        self.assertEqual(res.status_code, 400)  # 内訳行は親候補に出ない

    def test_parent_with_items_cannot_be_shared(self):
        parent, _, _ = self._create_parent_with_items()
        res = self.client.patch(
            f"/api/transactions/{parent['id']}/", {"shared": True}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_partner_sees_shared_items_but_not_parent(self):
        parent, _, _ = self._create_parent_with_items()
        self.client.force_login(self.bob)
        listed = self.client.get("/api/transactions/", {"month": "2026-08"}).json()
        amounts = sorted(t["amount"] for t in listed)
        self.assertEqual(amounts, [1000, 2000])  # 親(10000)は見えない

    def test_deleting_parent_removes_items(self):
        parent, item1, _ = self._create_parent_with_items()
        self.client.delete(f"/api/transactions/{parent['id']}/")
        self.assertEqual(
            self.client.get(f"/api/transactions/{item1['id']}/").status_code, 404
        )


class ImportTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.group = Group.objects.create(name="我が家", invite_code="ABCD1234")
        GroupMember.objects.create(group=self.group, user=self.alice, share_percent=50)
        GroupMember.objects.create(group=self.group, user=self.bob, share_percent=50)
        self.client.force_login(self.alice)
        self.card = self.client.post(
            "/api/payment-methods/", {"name": "カードA"}, format="json"
        ).json()
        self.alice_other = Category.objects.get(
            user=self.alice, name="その他", type=Category.Type.EXPENSE
        )

    def _payload(self):
        return {
            "payment_method_id": self.card["id"],
            "parent": {
                "date": "2026-08-27",
                "amount": 10000,
                "category_id": self.alice_other.id,
                "memo": "8月請求",
            },
            "rows": [
                {
                    "merchant": "セブンイレブン",
                    "used_date": "2026-08-03",
                    "amount": 1000,
                    "category_id": self.alice_food.id,
                    "shared": True,
                },
                {
                    "merchant": "Amazon",
                    "used_date": "2026-08-10",
                    "amount": 2000,
                    "category_id": self.alice_other.id,
                    "shared": False,
                },
            ],
        }

    def test_import_creates_parent_children_and_learns(self):
        res = self.client.post("/api/import/transactions/", self._payload(), format="json")
        self.assertEqual(res.status_code, 201)
        parent = res.json()
        self.assertEqual(parent["amount"], 10000)
        self.assertEqual(parent["payment_method"]["name"], "カードA")
        self.assertEqual(len(parent["items"]), 2)
        memos = {i["memo"] for i in parent["items"]}
        self.assertIn("8/3 セブンイレブン", memos)
        shared_item = next(i for i in parent["items"] if i["memo"].endswith("セブンイレブン"))
        self.assertTrue(shared_item["is_shared"])
        self.assertEqual(shared_item["payer_share_percent"], 50)

        # 集計: 親を1回だけ + 共有は1000だけ
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertEqual(data["expense_total"], 10000)
        self.assertEqual(data["shared"]["total"], 1000)

        # 学習: suggest が返す + existing_statement
        res = self.client.post(
            "/api/import/suggest/",
            {
                "merchants": ["セブンイレブン", "Amazon", "未知の店"],
                "payment_method_id": self.card["id"],
                "month": "2026-08",
            },
            format="json",
        )
        data = res.json()
        self.assertTrue(data["existing_statement"])
        self.assertEqual(
            data["suggestions"]["セブンイレブン"]["category_id"], self.alice_food.id
        )
        self.assertTrue(data["suggestions"]["セブンイレブン"]["shared"])
        self.assertFalse(data["suggestions"]["Amazon"]["shared"])
        self.assertNotIn("未知の店", data["suggestions"])

    def test_import_rows_exceeding_parent_amount(self):
        payload = self._payload()
        payload["parent"]["amount"] = 2500
        res = self.client.post("/api/import/transactions/", payload, format="json")
        self.assertEqual(res.status_code, 400)

    def test_import_rejects_other_users_category(self):
        payload = self._payload()
        payload["rows"][0]["category_id"] = Category.objects.get(
            user=self.bob, name="食費"
        ).id
        res = self.client.post("/api/import/transactions/", payload, format="json")
        self.assertEqual(res.status_code, 400)

    def test_import_row_linked_to_recurring_marks_paid(self):
        rp = RecurringPayment.objects.create(
            user=self.alice,
            name="携帯代",
            amount=4000,
            category=Category.objects.get(user=self.alice, name="通信"),
            day_of_month=15,
        )
        payload = self._payload()
        payload["rows"][0]["recurring_payment_id"] = rp.id
        res = self.client.post("/api/import/transactions/", payload, format="json")
        self.assertEqual(res.status_code, 201)

        # 固定費が支払済扱いになる
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        item = next(i for i in data["recurring"]["items"] if i["id"] == rp.id)
        self.assertTrue(item["paid"])
        self.assertEqual(data["recurring"]["paid_total"], 1000)  # 明細の実額

        # 学習: 次回 suggest に recurring_payment_id が含まれる
        sug = self.client.post(
            "/api/import/suggest/", {"merchants": ["セブンイレブン"]}, format="json"
        ).json()["suggestions"]
        self.assertEqual(sug["セブンイレブン"]["recurring_payment_id"], rp.id)

    def test_import_shared_requires_group(self):
        carol = User.objects.create_user("carol", password="testpass12345")
        seed_default_categories(carol)
        self.client.force_login(carol)
        card = self.client.post(
            "/api/payment-methods/", {"name": "カードC"}, format="json"
        ).json()
        payload = self._payload()
        payload["payment_method_id"] = card["id"]
        food = Category.objects.get(user=carol, name="食費")
        other = Category.objects.get(user=carol, name="その他", type=Category.Type.EXPENSE)
        payload["parent"]["category_id"] = other.id
        payload["rows"][0]["category_id"] = food.id
        payload["rows"][1]["category_id"] = other.id
        res = self.client.post("/api/import/transactions/", payload, format="json")
        self.assertEqual(res.status_code, 400)


class OcrTests(BaseTestCase):
    def test_parse_tsv_reconstructs_rows_and_cells(self):
        from .ocr import parse_tsv

        header = "level\tpage\tblock\tpar\tline\tword\tleft\ttop\twidth\theight\tconf\ttext"
        lines = [
            header,
            "5\t1\t1\t1\t1\t1\t100\t100\t80\t20\t96\t2026/08/03",
            "5\t1\t1\t1\t1\t2\t300\t102\t60\t20\t95\tSEVEN",
            # 直前との隙間 5px → 同じセルに連結される
            "5\t1\t1\t1\t1\t3\t365\t101\t70\t20\t95\tELEVEN",
            "5\t1\t1\t1\t1\t4\t700\t100\t50\t20\t92\t1,000",
            "5\t1\t1\t1\t2\t1\t100\t160\t80\t20\t96\t2026/08/10",
            "5\t1\t1\t1\t2\t2\t300\t161\t60\t20\t95\tGUSTO",
            "5\t1\t1\t1\t2\t3\t700\t159\t50\t20\t92\t1,200",
            # conf -1 の構造行は無視される
            "4\t1\t1\t1\t3\t0\t0\t200\t500\t20\t-1\t",
        ]
        rows = parse_tsv("\n".join(lines), gap_px=25)
        self.assertEqual(
            rows,
            [
                ["2026/08/03", "SEVENELEVEN", "1,000"],
                ["2026/08/10", "GUSTO", "1,200"],
            ],
        )

    def test_ocr_endpoint_validations(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.alice)
        res = self.client.post("/api/import/ocr/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            "/api/import/ocr/",
            {"file": SimpleUploadedFile("a.pdf", b"not a pdf at all")},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)


class PreferenceTests(BaseTestCase):
    def test_prev_month_income_mode(self):
        Transaction.objects.create(
            user=self.alice, category=self.alice_salary, amount=300000, date="2026-07-25"
        )
        Transaction.objects.create(
            user=self.alice, category=self.alice_salary, amount=310000, date="2026-08-25"
        )
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=50000, date="2026-08-05"
        )
        self.client.force_login(self.alice)

        # デフォルト: 当月収入ベース
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertEqual(data["income_month"], "2026-08")
        self.assertEqual(data["income_total"], 310000)
        self.assertEqual(data["balance"], 260000)

        # オン: 前月収入ベース
        res = self.client.put(
            "/api/preferences/", {"use_prev_month_income": True}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertEqual(data["income_month"], "2026-07")
        self.assertEqual(data["income_total"], 300000)
        self.assertEqual(data["balance"], 250000)  # 7月収入 − 8月支出
        self.assertEqual(data["expense_total"], 50000)
        self.assertEqual(data["income_by_category"][0]["total"], 300000)

        # 1月表示では前年12月が原資になる
        Transaction.objects.create(
            user=self.alice, category=self.alice_salary, amount=999, date="2026-12-25"
        )
        data = self.client.get("/api/summary/monthly/", {"month": "2027-01"}).json()
        self.assertEqual(data["income_month"], "2026-12")
        self.assertEqual(data["income_total"], 999)


class BalanceTests(BaseTestCase):
    def test_balance_forecast(self):
        self.client.force_login(self.alice)
        # 未登録なら anchor: null
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        self.assertIsNone(data["balance_forecast"]["anchor"])

        res = self.client.put(
            "/api/balance/", {"amount": 150000, "as_of_date": "2026-08-01"}, format="json"
        )
        self.assertEqual(res.status_code, 200)

        # 基準日より後: 収入 +5000, 支出 -3000 / 基準日当日は含めない
        Transaction.objects.create(
            user=self.alice, category=self.alice_salary, amount=5000, date="2026-08-02"
        )
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=3000, date="2026-08-03"
        )
        Transaction.objects.create(
            user=self.alice, category=self.alice_food, amount=9999, date="2026-08-01"
        )
        # 未払い固定費 48000
        RecurringPayment.objects.create(
            user=self.alice,
            name="家賃",
            amount=48000,
            category=self.alice_housing,
            day_of_month=27,
        )
        data = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()
        fc = data["balance_forecast"]
        self.assertEqual(fc["projected"], 152000)
        self.assertEqual(fc["unpaid_recurring"], 48000)
        self.assertEqual(fc["after_required"], 104000)

    def test_balance_ignores_breakdown_items(self):
        self.client.force_login(self.alice)
        self.client.put(
            "/api/balance/", {"amount": 100000, "as_of_date": "2026-08-01"}, format="json"
        )
        parent = self.client.post(
            "/api/transactions/",
            {"category_id": self.alice_food.id, "amount": 10000, "date": "2026-08-05"},
            format="json",
        ).json()
        self.client.post(
            "/api/transactions/",
            {"parent": parent["id"], "category_id": self.alice_food.id, "amount": 4000},
            format="json",
        )
        fc = self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()[
            "balance_forecast"
        ]
        self.assertEqual(fc["projected"], 90000)  # 内訳を二重に引かない


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

    def test_recurring_pay_inherits_payment_method(self):
        self.client.force_login(self.alice)
        card = self.client.post(
            "/api/payment-methods/", {"name": "カードB"}, format="json"
        ).json()
        rp = self.client.post(
            "/api/recurring-payments/",
            {
                "name": "インターネット",
                "amount": 5000,
                "category_id": Category.objects.get(user=self.alice, name="通信").id,
                "day_of_month": 10,
                "payment_method_id": card["id"],
            },
            format="json",
        ).json()
        res = self.client.post(
            f"/api/recurring-payments/{rp['id']}/pay/", {"month": "2026-08"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["payment_method"]["name"], "カードB")
        totals = {
            m["name"]: m["total"]
            for m in self.client.get("/api/summary/monthly/", {"month": "2026-08"}).json()[
                "payment_methods"
            ]
        }
        self.assertEqual(totals["カードB"], 5000)
