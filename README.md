# KAKEI — 家計管理アプリ

Vue 3 + Django REST Framework の家計管理 Web アプリ。スマホブラウザでの利用を前提としたモバイルファースト UI。

## 機能

- 収入・支出の記録 (CRUD)、カテゴリ別管理・色分け
- 月次サマリー: 収入・支出・収支、カテゴリ別内訳のドーナツグラフ
- **定期支払 (固定費)**: 家賃・サブスク等をテンプレート登録し、月ごとに「支払済にする」で記帳
- **今月の最低必要額**: 有効な固定費の合計をダッシュボード最上部に表示 (支払済/残り + プログレスバー)
- マルチユーザー (会員登録制、データはユーザーごとに完全分離)

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
```

## 本番デプロイ (カゴヤ VPS / Ubuntu)

公開 URL: **http://v133-18-242-137.vir.kagoya.net/kakei/**(VPS 標準ドメインのサブパス公開。独自ドメイン取得後に HTTPS 化できる)

構成: Nginx が `frontend/dist` を配信し `/kakei/api/`・`/kakei/admin/` を Gunicorn (unix ソケット) へプロキシ。サブパスのプレフィックスは gunicorn の `SCRIPT_NAME=/kakei` が処理。SQLite は `/opt/kakei/backend/data/db.sqlite3`。専用ユーザー `kakei` で運用し、本番では Docker を使わない。

### 初回セットアップ

```bash
# 1. 必要パッケージ (Node 22 は NodeSource から)
sudo apt update
sudo apt install -y python3.12-venv git nginx
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# 2. 専用ユーザーとコード取得
sudo adduser --system --group --home /opt/kakei --shell /bin/bash kakei
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

# 7. フロントエンドビルド
cd /opt/kakei/frontend
sudo -u kakei npm ci
sudo -u kakei npm run build

# 8. systemd + Nginx (設定ファイルは VPS 標準ドメイン向けに設定済み)
sudo cp /opt/kakei/deploy/kakei-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kakei-gunicorn
sudo cp /opt/kakei/deploy/nginx-kakei.conf /etc/nginx/sites-available/kakei
sudo ln -s /etc/nginx/sites-available/kakei /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 9. deploy.sh 内の systemctl restart を kakei ユーザーに許可
echo "kakei ALL=(root) NOPASSWD: /usr/bin/systemctl restart kakei-gunicorn" | sudo tee /etc/sudoers.d/kakei
sudo chmod 440 /etc/sudoers.d/kakei
```

### 独自ドメイン取得後の HTTPS 化 (任意)

1. ドメインの A レコードを VPS の IP に向ける
2. `deploy/nginx-kakei.conf` の `server_name` を新ドメインに変更して再配置
3. `.env` の `ALLOWED_HOSTS`・`CSRF_TRUSTED_ORIGINS` (https://) を更新し `USE_HTTPS=true` に
4. `sudo apt install -y certbot python3-certbot-nginx && sudo certbot --nginx -d <ドメイン>`
5. `sudo systemctl restart kakei-gunicorn && sudo systemctl reload nginx`

### 2回目以降の更新

```bash
sudo -u kakei /opt/kakei/deploy/deploy.sh
```

### 動作確認

```bash
curl -I http://v133-18-242-137.vir.kagoya.net/kakei/            # 200 (index.html)
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
| CRUD | `/api/recurring-payments/` | 定期支払 (`?is_active=`) |
| POST | `/api/recurring-payments/{id}/pay/` | 当月の支払を記帳 (二重払いは 409) |
| GET | `/api/summary/monthly/?month=YYYY-MM` | 月次サマリー + 最低必要額 |
