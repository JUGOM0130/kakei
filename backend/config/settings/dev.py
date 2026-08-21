from pathlib import Path

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = True

SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-prod"

ALLOWED_HOSTS = ["*"]

_sqlite_path = Path(env("SQLITE_PATH", default=str(BASE_DIR / "data" / "db.sqlite3")))
_sqlite_path.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _sqlite_path,
    }
}
