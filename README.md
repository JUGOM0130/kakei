# KAKEI — 家計管理アプリ

Vue 3 + Django REST Framework の家計管理 Web アプリ。スマホブラウザでの利用を前提としたモバイルファースト UI。

## 機能

- 収入・支出の記録 (CRUD)、カテゴリ別管理・色分け
- 月次サマリー: 収入・支出・収支、カテゴリ別内訳のドーナツグラフ
- **定期支払 (固定費)**: 家賃・サブスク等をテンプレート登録し、月ごとに「支払済にする」で記帳。毎月/2ヶ月ごと(水道)/4ヶ月ごと(固定資産税)/半年/毎年の間隔に対応
- **今月の最低必要額**: 当月が支払月の固定費合計をダッシュボード最上部に表示 (支払済/残り + プログレスバー)
- **グループ共有・精算 (2人)**: 招待コードで夫婦グループを作成。支出1件ごとに共有(折半または任意の割合)を選択でき、月次で「誰が誰にいくら渡すか」を表示、精算済み記録も可能。デフォルト負担割合はグループ設定で調整
- **支払方法タグ**: 現金・カードA等を登録して支出にタグ付け。ホームにカード別の月間合計(請求予定額)、履歴で絞り込み
- **カード内訳 (親子取引)**: カード請求を合計金額で1件登録し、その中に内訳行を追加。内訳ごとにカテゴリ・共有(折半/割合)を選択でき、内訳化していない残額は親のカテゴリ・自分のみ扱い。支出合計には親の金額を1回だけ計上
- **明細 CSV / PDF の一括取込**: VPASS / 楽天カード e-NAVI からダウンロードした明細 CSV・PDF を選ぶだけで、請求(親)+内訳として一括登録。PDF は日本語 CMap 対応の pdfjs でブラウザ内解析 (真の画像 PDF はサーバー OCR にフォールバック)。返品(マイナス)行は対応する購入明細と自動相殺し、請求合計を実額に補正。明細行を定期支払に紐付けると固定費が支払済扱いになり、紐付けも学習される。共有(折半)は取込後でも内訳行ごとに変更可能。文字コード (Shift_JIS/UTF-8) と列構成は自動判定 (失敗時は手動割り当て)。行ごとに取込対象・カテゴリ・共有を選択でき、**店名→カテゴリ/共有は学習**されて次回から自動プリセット。二重取込の注意表示あり (履歴画面 →「CSV取込」)
- **前月収入でやりくり**: 設定でオンにすると、ホームの収入・収支が「前月の収入 (給料) − 当月の支出」基準になる (給料日ベースの家計管理)
- **口座残高と繰越**: 基準となる残高を一度登録すると、以降の収支から想定残高を自動計算(繰越)。ホームに「想定残高 − 今月の未払い固定費 = 差引後の残り(足りる/不足)」を表示
- 固定費に支払方法を紐付け可能(カード払いのインターネット等)。※カード払い固定費は「支払済にする」だけで記録すればカード別合計に入る。同じ月のカード請求を親子方式でも入力する場合は、二重計上を避けるため内訳・親金額にその固定費分を含めないこと
- マルチユーザー (会員登録制、共有した記録以外はユーザーごとに完全分離)

## KABU — 株収支アプリ (同居)

同じリポジトリ・同じバックエンドで動く株式収支の記録アプリ。`kabu/` に独立した Vue アプリとして置き、URL は `/kabu/` で公開する (開発: http://localhost:5175/kabu/)。**アカウントは KAKEI と共通** (認証・API は KAKEI バックエンドの `/kakei/api` を共用するため、nginx にプロキシ追加は不要)。

- **取引記録**: 買付/売却、銘柄コード・銘柄名、株数・単価・手数料、口座区分 (特定/NISA成長/NISAつみたて/一般)、証券会社、メモ
- **銘柄名の自動補完**: 銘柄コードを入力すると JPX 上場銘柄一覧 (約4,400銘柄、ETF・REIT・285A 等の英字入りコード含む) から銘柄名を自動入力。全角入力も正規化。証券会社・口座区分は過去取引から補完。マスタの更新は `kabu/scripts/update-stock-names.mjs` (README 内コメント参照)
- **実現損益の自動計算**: 移動平均法 (買付手数料込み)。売却行に損益を表示し、(銘柄コード, 口座区分) ごとに平均取得単価を管理
- **保有一覧**: 保有株数・平均取得単価・取得額。現在値を手動入力すると評価額・評価損益を表示
- **取引履歴CSV取込 (楽天証券)**: 「取引履歴 (国内株式)」CSV (tradehistory(JP)_～.csv、Shift_JIS) をブラウザ内で解析し一括登録 (履歴画面 →「CSV取込」)。買付・積立・売付の現物取引に対応 (積立はメモに記録)、手数料・税金等・諸費用は合算。**冪等**: 行内容のハッシュを `import_key` として保存し、同じファイルの再取込や手入力済みの同内容取引は自動スキップ
- **配当金記録**: 受取日・銘柄・税引後受取額
- **年間ダッシュボード**: 実現損益+配当の年間トータル、月別推移 (積み上げ棒グラフ)、銘柄別内訳。年送りで過去年も参照可
- データはユーザーごとに分離 (KAKEI のグループ共有とは無関係)

## 技術スタック

| 層 | 技術 |
|---|---|
| フロントエンド | Vue 3 + Vite + Pinia + Vue Router + Chart.js |
| バックエンド | Django 5.2 + Django REST Framework (セッション認証) |
| DB | SQLite |
| 開発環境 | Docker Compose (Windows) |
| 本番 | カゴヤ VPS `/opt/kakei`、Nginx + Gunicorn (systemd)、Let's Encrypt |

## ローカル開発 (Docker Compose)

```powershell
docker compose up -d

# 初回のみ: マイグレーション
docker compose exec backend python manage.py migrate

# (任意) 管理画面用スーパーユーザー
docker compose exec backend python manage.py createsuperuser
```

- アプリ: http://localhost:5174/kakei/ (Vite。`/kakei/api` は backend コンテナへプロキシ)
- KABU: http://localhost:5175/kabu/ (API は同じ backend へプロキシ)
- API 直接 / DRF browsable API: http://localhost:8000/api/
- 管理画面: http://localhost:8000/admin/

※ ホスト側ポートは **5174**(5173 は別プロジェクトが使用中のため)。

テスト実行:

```powershell
docker compose exec backend python manage.py test
```

依存パッケージを変更したら:

```powershell
# backend/requirements.txt 変更時
docker compose build backend
# frontend/package.json 変更時 (ホストで npm install --package-lock-only してから)
docker compose build frontend; docker compose up -d --force-recreate frontend
# kabu/package.json 変更時も同様
docker compose build kabu; docker compose up -d --force-recreate kabu
```

## 本番デプロイ (カゴヤ VPS / AlmaLinux)

公開 URL: **http://v133-18-242-137.vir.kagoya.net/kakei/**(VPS 標準ドメインのサブパス公開。独自ドメイン取得後に HTTPS 化できる)

構成: Nginx が `frontend/dist` を配信し `/kakei/api/`・`/kakei/admin/` を Gunicorn (127.0.0.1:8001) へプロキシ。サブパスのプレフィックスは gunicorn の `SCRIPT_NAME=/kakei` が処理。SQLite は `/opt/kakei/backend/data/db.sqlite3`。専用ユーザー `kakei` で運用し、本番では Docker を使わない。SELinux は有効のまま運用する。

### 初回セットアップ

```bash
# 1. 必要パッケージ (Node 22 は NodeSource から)
sudo dnf install -y python3.12 git nginx policycoreutils-python-utils
curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
sudo dnf install -y nodejs

# 2. 専用ユーザーとコード取得 (git clone は空ディレクトリにしか出来ない点に注意)
sudo useradd -r -d /opt/kakei -s /bin/bash kakei
sudo mkdir -p /opt/kakei
sudo chown kakei:kakei /opt/kakei
sudo chmod 755 /opt/kakei          # nginx が dist を読めるように
sudo -u kakei git clone <リポジトリURL> /opt/kakei

# 3. Python 環境
sudo -u kakei python3.12 -m venv /opt/kakei/backend/.venv
sudo -u kakei /opt/kakei/backend/.venv/bin/pip install -r /opt/kakei/backend/requirements.txt

# 4. 環境変数 (.env.example がそのまま雛形。SECRET_KEY だけ生成して設定)
sudo -u kakei cp /opt/kakei/backend/.env.example /opt/kakei/backend/.env
sudo -u kakei chmod 600 /opt/kakei/backend/.env
# SECRET_KEY を生成して .env に設定:
#   python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS / USE_HTTPS=false は VPS 標準ドメイン用に設定済み

# 5. DB ディレクトリ (SQLite は WAL/journal のためディレクトリ書込権限が必要)
sudo -u kakei mkdir -p /opt/kakei/backend/data
sudo chmod 750 /opt/kakei/backend/data

# 6. マイグレーション・静的ファイル・管理ユーザー
cd /opt/kakei/backend
sudo -u kakei .venv/bin/python manage.py migrate --settings=config.settings.prod
sudo -u kakei .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.prod
sudo -u kakei .venv/bin/python manage.py createsuperuser --settings=config.settings.prod

# 7. フロントエンドビルド (KAKEI と KABU)
cd /opt/kakei/frontend
sudo -u kakei npm ci
sudo -u kakei npm run build
cd /opt/kakei/kabu
sudo -u kakei npm ci
sudo -u kakei npm run build

# 8. systemd (Gunicorn)
sudo cp /opt/kakei/deploy/kakei-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kakei-gunicorn

# 9. SELinux (nginx に静的ファイルの読取とバックエンド接続を許可)
sudo setsebool -P httpd_can_network_connect 1
sudo semanage fcontext -a -t httpd_sys_content_t "/opt/kakei/frontend/dist(/.*)?"
sudo semanage fcontext -a -t httpd_sys_content_t "/opt/kakei/kabu/dist(/.*)?"
sudo semanage fcontext -a -t httpd_sys_content_t "/opt/kakei/backend/staticfiles(/.*)?"
sudo restorecon -R /opt/kakei

# 10. Nginx (AlmaLinux は conf.d 方式)
sudo cp /opt/kakei/deploy/nginx-kakei.conf /etc/nginx/conf.d/kakei.conf
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx

# 11. firewalld で HTTP を開放
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload

# 12. deploy.sh 内の systemctl restart を kakei ユーザーに許可
echo "kakei ALL=(root) NOPASSWD: /usr/bin/systemctl restart kakei-gunicorn" | sudo tee /etc/sudoers.d/kakei
sudo chmod 440 /etc/sudoers.d/kakei
```

カゴヤのコントロールパネル側にセキュリティグループ (パケットフィルタ) がある場合は、そちらでも 80 番ポートを開放すること。

### 独自ドメイン取得後の HTTPS 化 (任意)

1. ドメインの A レコードを VPS の IP に向ける
2. `deploy/nginx-kakei.conf` の `server_name` を新ドメインに変更して再配置
3. `.env` の `ALLOWED_HOSTS`・`CSRF_TRUSTED_ORIGINS` (https://) を更新し `USE_HTTPS=true` に
4. `sudo dnf install -y epel-release && sudo dnf install -y certbot python3-certbot-nginx && sudo certbot --nginx -d <ドメイン>`
5. `sudo firewall-cmd --permanent --add-service=https && sudo firewall-cmd --reload`
6. `sudo systemctl restart kakei-gunicorn && sudo systemctl reload nginx`

### 2回目以降の更新

```bash
sudo -u kakei /opt/kakei/deploy/deploy.sh
```

### 動作確認

```bash
curl -I http://v133-18-242-137.vir.kagoya.net/kakei/            # 200 (index.html)
curl -I http://v133-18-242-137.vir.kagoya.net/kabu/             # 200 (KABU index.html)
curl http://v133-18-242-137.vir.kagoya.net/kakei/api/auth/me/   # 401 JSON
# スマホから会員登録 → 取引追加 → ダッシュボード表示
# 管理画面: http://v133-18-242-137.vir.kagoya.net/kakei/admin/
```

## API 概要

| Method | Path | 説明 |
|---|---|---|
| POST | `/api/auth/register/` | 会員登録 (デフォルトカテゴリ自動作成 + 自動ログイン) |
| POST/POST/GET | `/api/auth/login/` `logout/` `me/` | セッション認証 |
| GET | `/api/auth/csrf/` | CSRF トークン Cookie 配布 |
| CRUD | `/api/categories/` | カテゴリ (`?type=income\|expense`) |
| CRUD | `/api/transactions/` | 取引 (`?month=YYYY-MM&category=&type=`) |
| CRUD | `/api/payment-methods/` | 支払方法 (現金・カード) |
| CRUD | `/api/recurring-payments/` | 定期支払 (`?is_active=`)。間隔は interval_months + anchor_month |
| POST | `/api/recurring-payments/{id}/pay/` | 当月の支払を記帳 (対象外の月は 400、二重払いは 409) |
| GET/POST/PATCH | `/api/group/` | グループ取得/作成/負担割合変更 |
| POST | `/api/group/join/` `leave/` | 招待コードで参加 / 退出 |
| POST/DELETE | `/api/settlements/` `{id}/` | 月次精算の記録 / 取消 |
| GET | `/api/summary/monthly/?month=YYYY-MM` | 月次サマリー + 最低必要額 + 共有精算 + 支払方法別合計 |
| CRUD | `/api/stocks/trades/` | (KABU) 株取引 (`?year=&code=`)。売却行は `realized_pnl` 付き |
| POST | `/api/stocks/import/trades/` | (KABU) 取引の一括取込 (冪等、import_key + 手入力重複スキップ) |
| CRUD | `/api/stocks/dividends/` | (KABU) 配当金 (`?year=`) |
| GET | `/api/stocks/positions/` | (KABU) 保有ポジション (移動平均) + 評価損益 |
| PUT/DELETE | `/api/stocks/prices/{code}/` | (KABU) 銘柄の現在値を手動登録/削除 |
| GET | `/api/stocks/summary/?year=YYYY` | (KABU) 年間サマリー (実現損益・配当・月別・銘柄別) |
