import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
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
