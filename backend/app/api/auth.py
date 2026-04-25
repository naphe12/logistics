from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.config import is_dev_login_allowed
from app.dependencies import get_current_user, require_roles
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.auth import (
    LoginRequest,
    NotificationPreferencesUpdateRequest,
    OTPRequest,
    OTPVerifyRequest,
    RefreshTokenRequest,
    ShippingPreferencesOut,
    ShippingPreferencesUpdateRequest,
    TokenResponse,
    UserOut,
    UserRoleUpdateRequest,
)
from app.services.auth_service import (
    OTPError,
    OTPExpiredError,
    OTPRequestLimitedError,
    OTPLockedError,
    login_or_create,
    refresh_access_token,
    request_login_otp,
    verify_login_otp,
)
from app.services.user_preferences_service import (
    get_notification_preferences,
    get_shipping_preferences,
    set_notification_preferences,
    set_shipping_preferences,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    if not is_dev_login_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct login disabled. Use OTP flow or enable AUTH_ALLOW_DEV_LOGIN in environment.",
        )
    token = login_or_create(db, payload.phone_e164)
    return TokenResponse(access_token=token)


@router.post("/otp/request")
def request_otp(
    payload: OTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        request_login_otp(db=db, phone_e164=payload.phone_e164, background_tasks=background_tasks)
    except OTPRequestLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": str(exc),
                "error_code": "otp_request_limited",
                "retry_after_seconds": exc.retry_after_seconds,
            },
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return {"detail": "OTP sent"}


@router.post("/otp/verify", response_model=TokenResponse)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    try:
        access_token, refresh_token = verify_login_otp(db, payload.phone_e164, payload.code)
    except OTPExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except OTPLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": str(exc),
                "error_code": "otp_locked",
                "retry_after_seconds": exc.retry_after_seconds,
            },
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except OTPError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        access_token, refresh_token = refresh_access_token(db, payload.refresh_token)
    except (OTPError, JWTError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    payload = UserOut.model_validate(current_user)
    payload.notification_preferences = get_notification_preferences(current_user)
    return payload


@router.get("/me/notification-preferences")
def me_notification_preferences(current_user: User = Depends(get_current_user)):
    return get_notification_preferences(current_user)


@router.patch("/me/notification-preferences")
def update_me_notification_preferences(
    payload: NotificationPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return set_notification_preferences(db, current_user, payload.model_dump())


@router.get("/me/shipping-preferences", response_model=ShippingPreferencesOut)
def me_shipping_preferences(current_user: User = Depends(get_current_user)):
    return get_shipping_preferences(current_user)


@router.patch("/me/shipping-preferences", response_model=ShippingPreferencesOut)
def update_me_shipping_preferences(
    payload: ShippingPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return set_shipping_preferences(db, current_user, payload.model_dump())


@router.get("/users", response_model=list[UserOut])
def list_users(
    role: UserTypeEnum | None = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserTypeEnum.admin)),
):
    query = db.query(User)
    if role is not None:
        query = query.filter(User.user_type == role)
    return query.order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserTypeEnum.admin)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.user_type = payload.user_type
    db.commit()
    db.refresh(user)
    return user
