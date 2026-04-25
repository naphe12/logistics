from typing import Any

from sqlalchemy.orm import Session

from app.models.users import User

DEFAULT_NOTIFICATION_PREFERENCES: dict[str, Any] = {
    "sms_enabled": True,
    "email_enabled": False,
    "push_enabled": False,
    "whatsapp_enabled": False,
    "language": "fr",
}

DEFAULT_SHIPPING_PREFERENCES: dict[str, Any] = {
    "preferred_relay_id": None,
    "use_preferred_relay": False,
}


def _user_extra(user: User) -> dict[str, Any]:
    return user.extra if isinstance(user.extra, dict) else {}


def get_notification_preferences(user: User) -> dict[str, Any]:
    extra = _user_extra(user)
    prefs = extra.get("notification_preferences")
    if not isinstance(prefs, dict):
        prefs = {}
    merged = {**DEFAULT_NOTIFICATION_PREFERENCES, **prefs}
    return merged


def set_notification_preferences(
    db: Session,
    user: User,
    payload: dict[str, Any],
) -> dict[str, Any]:
    extra = _user_extra(user)
    current = get_notification_preferences(user)
    updates = {k: v for k, v in payload.items() if v is not None}
    merged = {**current, **updates}
    extra["notification_preferences"] = merged
    user.extra = extra
    db.commit()
    db.refresh(user)
    return merged


def is_sms_allowed(user: User | None) -> bool:
    if user is None:
        return True
    prefs = get_notification_preferences(user)
    return bool(prefs.get("sms_enabled", True))


def get_shipping_preferences(user: User) -> dict[str, Any]:
    extra = _user_extra(user)
    prefs = extra.get("shipping_preferences")
    if not isinstance(prefs, dict):
        prefs = {}
    merged = {**DEFAULT_SHIPPING_PREFERENCES, **prefs}
    if merged.get("preferred_relay_id") is not None:
        merged["preferred_relay_id"] = str(merged["preferred_relay_id"])
    return merged


def set_shipping_preferences(
    db: Session,
    user: User,
    payload: dict[str, Any],
) -> dict[str, Any]:
    extra = _user_extra(user)
    current = get_shipping_preferences(user)
    updates = {k: v for k, v in payload.items() if v is not None}
    merged = {**current, **updates}
    preferred_relay_id = merged.get("preferred_relay_id")
    merged["preferred_relay_id"] = str(preferred_relay_id) if preferred_relay_id else None
    extra["shipping_preferences"] = merged
    user.extra = extra
    db.commit()
    db.refresh(user)
    return merged
