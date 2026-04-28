import os
from pathlib import Path


def load_local_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env_file()


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
PICKUP_CODE_EXPIRE_HOURS = int(os.getenv("PICKUP_CODE_EXPIRE_HOURS", "6"))
PICKUP_CODE_ATTEMPT_WINDOW_SECONDS = int(os.getenv("PICKUP_CODE_ATTEMPT_WINDOW_SECONDS", "900"))
PICKUP_CODE_MAX_ATTEMPTS_PER_WINDOW = int(os.getenv("PICKUP_CODE_MAX_ATTEMPTS_PER_WINDOW", "5"))
AUTH_ALLOW_DEV_LOGIN = parse_bool_env("AUTH_ALLOW_DEV_LOGIN", default=False)
RATE_LIMIT_ENABLED = parse_bool_env("RATE_LIMIT_ENABLED", default=True)
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "240"))
RATE_LIMIT_SENSITIVE_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_SENSITIVE_MAX_REQUESTS", "30"))
RATE_LIMIT_AUTH_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_AUTH_MAX_REQUESTS", "10"))
RATE_LIMIT_USSD_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_USSD_MAX_REQUESTS", "120"))
RATE_LIMIT_PUBLIC_TRACK_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_PUBLIC_TRACK_MAX_REQUESTS", "6"))
PUBLIC_TRACK_BRUTEFORCE_ENABLED = parse_bool_env("PUBLIC_TRACK_BRUTEFORCE_ENABLED", default=True)
PUBLIC_TRACK_BRUTEFORCE_THRESHOLD = int(os.getenv("PUBLIC_TRACK_BRUTEFORCE_THRESHOLD", "3"))
PUBLIC_TRACK_BRUTEFORCE_BASE_DELAY_SECONDS = int(os.getenv("PUBLIC_TRACK_BRUTEFORCE_BASE_DELAY_SECONDS", "2"))
PUBLIC_TRACK_BRUTEFORCE_MAX_DELAY_SECONDS = int(os.getenv("PUBLIC_TRACK_BRUTEFORCE_MAX_DELAY_SECONDS", "300"))
PUBLIC_TRACK_BRUTEFORCE_RESET_SECONDS = int(os.getenv("PUBLIC_TRACK_BRUTEFORCE_RESET_SECONDS", "1800"))
AUDIT_REQUEST_LOGGING_ENABLED = parse_bool_env("AUDIT_REQUEST_LOGGING_ENABLED", default=True)
USSD_CREATE_WINDOW_SECONDS = int(os.getenv("USSD_CREATE_WINDOW_SECONDS", "3600"))
USSD_CREATE_MAX_PER_WINDOW = int(os.getenv("USSD_CREATE_MAX_PER_WINDOW", "5"))
USSD_INPUT_MAX_LENGTH = int(os.getenv("USSD_INPUT_MAX_LENGTH", "180"))
USSD_MAX_STEPS = int(os.getenv("USSD_MAX_STEPS", "8"))
USSD_ALLOWED_SERVICE_CODES = parse_csv_env("USSD_ALLOWED_SERVICE_CODES", "")

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
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
PAYMENT_RECONCILE_STALE_MINUTES = int(os.getenv("PAYMENT_RECONCILE_STALE_MINUTES", "30"))

INSURANCE_ENABLED = parse_bool_env("INSURANCE_ENABLED", default=True)
INSURANCE_PREMIUM_RATE = float(os.getenv("INSURANCE_PREMIUM_RATE", "0.05"))
INSURANCE_MAX_COVERAGE_BIF = float(os.getenv("INSURANCE_MAX_COVERAGE_BIF", "100000"))
INSURANCE_LOSS_COVERAGE_RATE = float(os.getenv("INSURANCE_LOSS_COVERAGE_RATE", "0.50"))
INSURANCE_DAMAGE_COVERAGE_RATE = float(os.getenv("INSURANCE_DAMAGE_COVERAGE_RATE", "0.30"))
INSURANCE_CLAIM_WINDOW_HOURS = int(os.getenv("INSURANCE_CLAIM_WINDOW_HOURS", "48"))
INSURANCE_CLAIM_REVIEW_SLA_HOURS = int(os.getenv("INSURANCE_CLAIM_REVIEW_SLA_HOURS", "24"))
INSURANCE_REQUIRE_PROOF = parse_bool_env("INSURANCE_REQUIRE_PROOF", default=True)
INSURANCE_PROHIBITED_ITEMS = parse_csv_env(
    "INSURANCE_PROHIBITED_ITEMS",
    "cash,jewelry,weapons,drugs,explosives,flammables,illegal_items",
)
CLAIMS_AUTO_ESCALATE_ENABLED = parse_bool_env("CLAIMS_AUTO_ESCALATE_ENABLED", default=True)
CLAIMS_AUTO_ESCALATE_INTERVAL_SECONDS = int(os.getenv("CLAIMS_AUTO_ESCALATE_INTERVAL_SECONDS", "300"))
CLAIMS_AUTO_ESCALATE_LIMIT = int(os.getenv("CLAIMS_AUTO_ESCALATE_LIMIT", "100"))
CLAIMS_ESCALATION_NOTIFY_ROLES = parse_csv_env("CLAIMS_ESCALATION_NOTIFY_ROLES", "admin,hub")
CLAIMS_ANTIFRAUD_HIGH_RISK_THRESHOLD = int(os.getenv("CLAIMS_ANTIFRAUD_HIGH_RISK_THRESHOLD", "70"))
SHIPMENT_SCHEDULE_AUTORUN_ENABLED = parse_bool_env("SHIPMENT_SCHEDULE_AUTORUN_ENABLED", default=True)
SHIPMENT_SCHEDULE_AUTORUN_INTERVAL_SECONDS = int(os.getenv("SHIPMENT_SCHEDULE_AUTORUN_INTERVAL_SECONDS", "300"))
SHIPMENT_SCHEDULE_AUTORUN_LIMIT = int(os.getenv("SHIPMENT_SCHEDULE_AUTORUN_LIMIT", "100"))
OUTBOX_WORKER_ENABLED = parse_bool_env("OUTBOX_WORKER_ENABLED", default=True)
OUTBOX_WORKER_INTERVAL_SECONDS = int(os.getenv("OUTBOX_WORKER_INTERVAL_SECONDS", "15"))
OUTBOX_WORKER_BATCH = int(os.getenv("OUTBOX_WORKER_BATCH", "100"))
OUTBOX_MAX_ATTEMPTS = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10"))

CORS_ALLOW_ORIGINS = parse_csv_env(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://react-frontend-staging-a79c.up.railway.app,http://react-frontend-staging-a79c.up.railway.app:5173,https://react-frontend-staging-a79c.up.railway.app:5173",
)
CORS_ALLOW_ALL = parse_bool_env("CORS_ALLOW_ALL", default=False)
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://.+$",
)
APP_VERSION = os.getenv("APP_VERSION", "dev")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(Path(__file__).resolve().parents[1] / "media"))
GEO_ACTIVE_PROVINCES = parse_csv_env(
    "GEO_ACTIVE_PROVINCES",
    "Bujumbura,Gitega,Butanyerera,Burunga,Buhumuza",
)


def is_dev_login_allowed() -> bool:
    # Reload local .env to avoid stale behavior during dev when values change.
    load_local_env_file()
    raw = os.getenv("AUTH_ALLOW_DEV_LOGIN")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    # Safe dev fallback: if no explicit flag is set, allow direct login only in dev-like app versions.
    app_version = os.getenv("APP_VERSION", "dev").strip().lower()
    return app_version in {"dev", "development", "local"}
