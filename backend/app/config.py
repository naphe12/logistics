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
USSD_CREATE_WINDOW_SECONDS = int(os.getenv("USSD_CREATE_WINDOW_SECONDS", "3600"))
USSD_CREATE_MAX_PER_WINDOW = int(os.getenv("USSD_CREATE_MAX_PER_WINDOW", "5"))

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "log")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_USERNAME = os.getenv("SMS_USERNAME", "")
SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "LOGIX")
AFRICASTALKING_BASE_URL = os.getenv(
    "AFRICASTALKING_BASE_URL",
    "https://api.africastalking.com/version1/messaging",
)

CORS_ALLOW_ORIGINS = parse_csv_env(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173","http://react-frontend-staging-a79c.up.railway.app:5173",
)
CORS_ALLOW_ALL = parse_bool_env("CORS_ALLOW_ALL", default=False)
