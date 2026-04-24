from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ALLOW_ALL, CORS_ALLOW_ORIGINS, CORS_ALLOW_ORIGIN_REGEX
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.shipments import router as shipments_router
from app.api.ussd import router as ussd_router
from app.api.codes import router as codes_router
from app.api.payments import router as payments_router

app = FastAPI(title="Logix API")

allow_origins = ["*"] if CORS_ALLOW_ALL else CORS_ALLOW_ORIGINS
allow_origin_regex = None if CORS_ALLOW_ALL else (CORS_ALLOW_ORIGIN_REGEX or None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(shipments_router)
app.include_router(ussd_router)
app.include_router(codes_router)
app.include_router(payments_router)
