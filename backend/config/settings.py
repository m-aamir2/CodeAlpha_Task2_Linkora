import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development uses the project-root .env. Vercel variables are already in
# the process environment and therefore take precedence over this file.
for local_env_file in (BASE_DIR.parent / ".env.local", BASE_DIR.parent / ".env"):
    if local_env_file.exists():
        for line in local_env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


IS_VERCEL = env_bool("VERCEL", False)
DEBUG = env_bool("DEBUG", not IS_VERCEL)
SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only-change-me")
if IS_VERCEL and (DEBUG or SECRET_KEY == "local-development-only-change-me"):
    raise RuntimeError("Set DEBUG=false and a private SECRET_KEY in the Vercel project environment.")

VERCEL_HOSTS = [
    os.getenv(name, "").strip().removeprefix("https://").removeprefix("http://").split("/")[0]
    for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL")
    if os.getenv(name, "").strip()
]
ALLOWED_HOSTS = list(dict.fromkeys([
    *env_list("ALLOWED_HOSTS", "localhost,127.0.0.1"),
    *VERCEL_HOSTS,
    *( [".vercel.app"] if IS_VERCEL else [] ),
]))

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt.token_blacklist", "corsheaders",
    "accounts", "social", "messaging", "moderation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "").strip()
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    parsed = urlparse(DATABASE_URL)
    query = parse_qs(parsed.query)
    options = {}
    sslmode = query.get("sslmode", ["require" if IS_VERCEL else ""])[0]
    if sslmode:
        options["sslmode"] = sslmode
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or 5432,
        "OPTIONS": options,
        "CONN_MAX_AGE": 0 if IS_VERCEL else 60,
        "CONN_HEALTH_CHECKS": True,
    }}
elif IS_VERCEL:
    raise RuntimeError("Set DATABASE_URL to a persistent PostgreSQL database in the Vercel project environment.")
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
USE_VERCEL_BLOB = env_bool("USE_VERCEL_BLOB", IS_VERCEL)
if USE_VERCEL_BLOB:
    STORAGES = {
        "default": {"BACKEND": "config.storage.VercelBlobStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MAX_UPLOAD_SIZE = 8 * 1024 * 1024

VERCEL_ORIGINS = [f"https://{host}" for host in VERCEL_HOSTS]
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([
    *env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5180,http://127.0.0.1:5180"),
    *VERCEL_ORIGINS,
]))
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://localhost:\d+$", r"^http://127\.0\.0\.1:\d+$"] if DEBUG else []
if IS_VERCEL:
    CORS_ALLOWED_ORIGIN_REGEXES.append(r"^https://[a-z0-9-]+\.vercel\.app$")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([
    *CORS_ALLOWED_ORIGINS,
    *env_list("CSRF_TRUSTED_ORIGINS"),
    *( ["https://*.vercel.app"] if IS_VERCEL else [] ),
]))
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@linkora.local")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/hour", "user": "1200/hour"},
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30), "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True,
}
