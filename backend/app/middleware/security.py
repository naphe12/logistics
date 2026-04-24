from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import (
    AUDIT_REQUEST_LOGGING_ENABLED,
    RATE_LIMIT_AUTH_MAX_REQUESTS,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_SENSITIVE_MAX_REQUESTS,
    RATE_LIMIT_USSD_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from app.database import SessionLocal
from app.models.users import User
from app.security import decode_token
from app.services.audit_service import log_action


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _entity_from_path(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else "root"


def _extract_actor_user_id(request: Request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("typ") != "access":
            return None
        subject = payload.get("sub")
        if not subject:
            return None
        return UUID(str(subject))
    except Exception:
        return None


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = (request.headers.get("x-request-id") or "").strip()
        if incoming:
            request_id = incoming[:64]
        else:
            request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.enabled = RATE_LIMIT_ENABLED
        self.window_seconds = RATE_LIMIT_WINDOW_SECONDS
        self.default_limit = RATE_LIMIT_MAX_REQUESTS
        self.sensitive_limit = RATE_LIMIT_SENSITIVE_MAX_REQUESTS
        self.auth_limit = RATE_LIMIT_AUTH_MAX_REQUESTS
        self.ussd_limit = RATE_LIMIT_USSD_MAX_REQUESTS
        self._buckets: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _rule_for_path(self, path: str) -> tuple[str, int]:
        if path.startswith("/auth/otp/request") or path.startswith("/auth/otp/verify") or path.startswith("/auth/login"):
            return "auth", self.auth_limit
        if path.startswith("/codes/") or path.startswith("/payments/") or path.startswith("/incidents/"):
            return "sensitive", self.sensitive_limit
        if path.startswith("/ussd"):
            return "ussd", self.ussd_limit
        return "global", self.default_limit

    def _cleanup(self, timestamps: deque, now: float) -> None:
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    def _audit_rate_limit_block(self, request: Request, path: str, bucket_name: str, limit: int) -> None:
        db = SessionLocal()
        try:
            actor_user_id = _extract_actor_user_id(request)
            actor_phone = None
            if actor_user_id:
                user = db.query(User).filter(User.id == actor_user_id).first()
                actor_phone = user.phone_e164 if user else None
            log_action(
                db,
                entity=_entity_from_path(path),
                action="rate_limit_block",
                actor_user_id=actor_user_id,
                actor_phone=actor_phone,
                ip_address=_client_ip(request),
                request_id=_request_id(request),
                endpoint=path,
                method=request.method,
                status_code=429,
            )
            db.commit()
        finally:
            db.close()

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path.startswith("/health"):
            return await call_next(request)

        bucket_name, limit = self._rule_for_path(path)
        ip = _client_ip(request)
        key = f"{bucket_name}:{ip}"
        now = monotonic()

        with self._lock:
            timestamps = self._buckets[key]
            self._cleanup(timestamps, now)
            if len(timestamps) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - timestamps[0])))
                self._audit_rate_limit_block(request, path, bucket_name, limit)
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "detail": {
                            "message": "Too many requests",
                            "error_code": "rate_limited",
                            "bucket": bucket_name,
                            "limit": limit,
                            "window_seconds": self.window_seconds,
                            "retry_after_seconds": retry_after,
                        }
                    },
                )
            timestamps.append(now)

        return await call_next(request)


class RequestAuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.enabled = AUDIT_REQUEST_LOGGING_ENABLED

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if not self.enabled:
            return response
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return response
        path = request.url.path
        if path.startswith("/health"):
            return response

        db = SessionLocal()
        try:
            actor_user_id = _extract_actor_user_id(request)
            actor_phone = None
            if actor_user_id:
                user = db.query(User).filter(User.id == actor_user_id).first()
                actor_phone = user.phone_e164 if user else None
            log_action(
                db,
                entity=_entity_from_path(path),
                action=f"http_{request.method.lower()}",
                actor_user_id=actor_user_id,
                actor_phone=actor_phone,
                ip_address=_client_ip(request),
                request_id=_request_id(request),
                endpoint=path,
                method=request.method,
                status_code=response.status_code,
            )
            db.commit()
        finally:
            db.close()

        return response
