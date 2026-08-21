#!/usr/bin/env bash
# 2回目以降のデプロイスクリプト。/opt/kakei で kakei ユーザーとして実行
# (systemctl のみ sudo が必要)。初回セットアップは README.md 参照。
set -euo pipefail

cd /opt/kakei
git pull

cd backend
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --settings=config.settings.prod
.venv/bin/python manage.py collectstatic --noinput --settings=config.settings.prod

cd ../frontend
npm ci
npm run build

# KABU (株収支アプリ) のフロント
cd ../kabu
npm ci
npm run build

sudo systemctl restart kakei-gunicorn
echo "デプロイ完了"
