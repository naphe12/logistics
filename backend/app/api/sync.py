from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.sync import ShipmentSyncPullResponse, SyncPushRequest, SyncPushResponse
from app.services.shipment_service import list_shipments_delta
from app.services.sync_service import apply_sync_action

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/shipments/pull", response_model=ShipmentSyncPullResponse)
def sync_pull_shipments_endpoint(
    since: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    rows = list_shipments_delta(
        db,
        current_user,
        since=since,
        limit=limit,
    )
    next_cursor = rows[-1].updated_at if rows else since
    items = [
        {
            "id": row.id,
            "shipment_no": row.shipment_no,
            "status": row.status,
            "sender_phone": row.sender_phone,
            "receiver_name": row.receiver_name,
            "receiver_phone": row.receiver_phone,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "server_version": row.updated_at,
        }
        for row in rows
    ]
    return ShipmentSyncPullResponse(
        server_time=datetime.now(UTC),
        count=len(items),
        next_cursor=next_cursor,
        items=items,
    )


@router.post("/push", response_model=SyncPushResponse)
def sync_push_endpoint(
    payload: SyncPushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    results: list[dict] = []
    succeeded = 0
    failed = 0
    for item in payload.actions[:300]:
        outcome = apply_sync_action(
            db,
            current_user,
            client_action_id=item.client_action_id,
            action_type=item.action_type,
            method=item.method,
            path=item.path,
            payload=item.payload,
            client_version=item.client_version,
            conflict_policy=item.conflict_policy,
        )
        status = str(outcome.get("status") or "failed")
        if status in {"applied", "replayed"}:
            succeeded += 1
        else:
            failed += 1
        results.append(
            {
                "client_action_id": item.client_action_id,
                "status": status,
                "error": outcome.get("error"),
                "data": outcome.get("data"),
            }
        )
    return SyncPushResponse(
        server_time=datetime.now(UTC),
        accepted=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
