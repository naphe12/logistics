from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.schemas.geo import (
    AddressCreate,
    AddressOut,
    CommuneBulkUpsertRequest,
    CommuneBulkUpsertResult,
    CommuneCreate,
    CommuneOut,
    ProvinceCreate,
    ProvinceOut,
)
from app.services.geo_service import (
    GeoValidationError,
    bulk_upsert_communes,
    create_address,
    create_commune,
    create_province,
    list_communes,
    list_provinces,
)

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/provinces", response_model=list[ProvinceOut])
def list_provinces_endpoint(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(
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
    return list_provinces(db, q=q, limit=limit)


@router.get("/communes", response_model=list[CommuneOut])
def list_communes_endpoint(
    province_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    _user=Depends(
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
    return list_communes(db, province_id=province_id, q=q, limit=limit)


@router.post("/addresses", response_model=AddressOut)
def create_address_endpoint(
    payload: AddressCreate,
    db: Session = Depends(get_db),
    _user=Depends(
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
    try:
        return create_address(db, payload)
    except GeoValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/provinces", response_model=ProvinceOut)
def create_province_endpoint(
    payload: ProvinceCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return create_province(db, payload)


@router.post("/communes", response_model=CommuneOut)
def create_commune_endpoint(
    payload: CommuneCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return create_commune(db, payload)
    except GeoValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/communes/bulk-upsert", response_model=CommuneBulkUpsertResult)
def bulk_upsert_communes_endpoint(
    payload: CommuneBulkUpsertRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return bulk_upsert_communes(db, payload.items)
