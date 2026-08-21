from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# フォールバック無し — 未設定なら起動時に落とす
SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("SQLITE_PATH", default="/opt/kakei/backend/data/db.sqlite3"),
        "OPTIONS": {
            # WAL: 読み書き並行性の改善。timeout はロック待ち(秒)
            "init_command": "PRAGMA journal_mode=WAL;",
            "timeout": 20,
        },
    }
}

STATIC_ROOT = env("STATIC_ROOT", default="/opt/kakei/backend/staticfiles")

# Nginx が TLS を終端する
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
