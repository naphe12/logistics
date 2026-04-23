import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "log")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_USERNAME = os.getenv("SMS_USERNAME", "")
SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "LOGIX")
AFRICASTALKING_BASE_URL = os.getenv(
    "AFRICASTALKING_BASE_URL",
    "https://api.africastalking.com/version1/messaging",
)
