import os


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def parse_csv_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip().strip('"').strip("'") for item in raw.split(",") if item.strip()]


def parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
JWT_REFRESH_EXPIRE_MINUTES = int(os.getenv("JWT_REFRESH_EXPIRE_MINUTES", "43200"))

OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_LOCK_MINUTES = int(os.getenv("OTP_LOCK_MINUTES", "15"))
OTP_REQUEST_WINDOW_SECONDS = int(os.getenv("OTP_REQUEST_WINDOW_SECONDS", "300"))
OTP_REQUEST_MAX_PER_WINDOW = int(os.getenv("OTP_REQUEST_MAX_PER_WINDOW", "3"))
AUTH_ALLOW_DEV_LOGIN = parse_bool_env("AUTH_ALLOW_DEV_LOGIN", default=False)
RATE_LIMIT_ENABLED = parse_bool_env("RATE_LIMIT_ENABLED", default=True)
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "240"))
RATE_LIMIT_SENSITIVE_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_SENSITIVE_MAX_REQUESTS", "30"))
RATE_LIMIT_AUTH_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_AUTH_MAX_REQUESTS", "10"))
RATE_LIMIT_USSD_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_USSD_MAX_REQUESTS", "120"))
AUDIT_REQUEST_LOGGING_ENABLED = parse_bool_env("AUDIT_REQUEST_LOGGING_ENABLED", default=True)
USSD_CREATE_WINDOW_SECONDS = int(os.getenv("USSD_CREATE_WINDOW_SECONDS", "3600"))
USSD_CREATE_MAX_PER_WINDOW = int(os.getenv("USSD_CREATE_MAX_PER_WINDOW", "5"))

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "log")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_USERNAME = os.getenv("SMS_USERNAME", "")
SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "LOGIX")
SMS_MAX_RETRIES = int(os.getenv("SMS_MAX_RETRIES", "3"))
SMS_RETRY_BASE_SECONDS = int(os.getenv("SMS_RETRY_BASE_SECONDS", "30"))
SMS_QUEUE_AUTODISPATCH_ENABLED = parse_bool_env("SMS_QUEUE_AUTODISPATCH_ENABLED", default=True)
SMS_QUEUE_AUTODISPATCH_INTERVAL_SECONDS = int(os.getenv("SMS_QUEUE_AUTODISPATCH_INTERVAL_SECONDS", "30"))
SMS_QUEUE_AUTODISPATCH_BATCH = int(os.getenv("SMS_QUEUE_AUTODISPATCH_BATCH", "100"))
SMS_QUEUE_LEADER_LOCK_ENABLED = parse_bool_env("SMS_QUEUE_LEADER_LOCK_ENABLED", default=True)
SMS_QUEUE_LEADER_LOCK_KEY = int(os.getenv("SMS_QUEUE_LEADER_LOCK_KEY", "91542001"))
AFRICASTALKING_BASE_URL = os.getenv(
    "AFRICASTALKING_BASE_URL",
    "https://api.africastalking.com/version1/messaging",
)
COMMISSION_RELAY_RATE = float(os.getenv("COMMISSION_RELAY_RATE", "0.05"))
COMMISSION_TRANSPORT_RATE = float(os.getenv("COMMISSION_TRANSPORT_RATE", "0.03"))
OPS_DELAY_RISK_HOURS = int(os.getenv("OPS_DELAY_RISK_HOURS", "48"))
OPS_RELAY_UTILIZATION_WARN = float(os.getenv("OPS_RELAY_UTILIZATION_WARN", "0.9"))
OPS_ALERT_SMS_THROTTLE_MINUTES = int(os.getenv("OPS_ALERT_SMS_THROTTLE_MINUTES", "30"))
OPS_ALERT_SMS_MAX_RECIPIENTS = int(os.getenv("OPS_ALERT_SMS_MAX_RECIPIENTS", "20"))
OPS_ALERT_AUTONOTIFY_ENABLED = parse_bool_env("OPS_ALERT_AUTONOTIFY_ENABLED", default=True)
OPS_ALERT_AUTONOTIFY_INTERVAL_SECONDS = int(os.getenv("OPS_ALERT_AUTONOTIFY_INTERVAL_SECONDS", "300"))
OPS_ALERT_SMS_MAX_PER_HOUR = int(os.getenv("OPS_ALERT_SMS_MAX_PER_HOUR", "4"))

CORS_ALLOW_ORIGINS = parse_csv_env(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://react-frontend-staging-a79c.up.railway.app,http://react-frontend-staging-a79c.up.railway.app:5173,https://react-frontend-staging-a79c.up.railway.app:5173",
)
CORS_ALLOW_ALL = parse_bool_env("CORS_ALLOW_ALL", default=False)
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://.+$",
)
