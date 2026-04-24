from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import JWT_ALGORITHM, JWT_SECRET_KEY
from app.database import get_db
from app.enums import UserTypeEnum
from app.models.shipments import Shipment
from app.models.users import User
from app.realtime.tracking import tracking_hub

router = APIRouter(tags=["ws"])


def _get_user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("typ", "access") != "access":
            return None
        subject = payload.get("sub")
    except JWTError:
        return None
    if not subject:
        return None
    return db.query(User).filter(User.id == subject).first()


def _can_access_shipment(user: User, shipment: Shipment) -> bool:
    if user.user_type in {
        UserTypeEnum.agent,
        UserTypeEnum.hub,
        UserTypeEnum.driver,
        UserTypeEnum.admin,
    }:
        return True
    return (
        shipment.sender_id == user.id
        or shipment.sender_phone == user.phone_e164
        or shipment.receiver_phone == user.phone_e164
    )


@router.websocket("/ws/shipments/{shipment_id}")
async def shipment_tracking_socket(
    websocket: WebSocket,
    shipment_id: UUID,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    user = _get_user_from_token(db, token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Shipment not found")
        return

    if not _can_access_shipment(user, shipment):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
        return

    shipment_key = str(shipment_id)
    await tracking_hub.connect(shipment_key, websocket)
    await websocket.send_json(
        {
            "kind": "shipment_snapshot",
            "shipment_id": shipment_key,
            "status": shipment.status,
            "event_type": "snapshot",
        }
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await tracking_hub.disconnect(shipment_key, websocket)

