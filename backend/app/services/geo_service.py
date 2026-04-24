from sqlalchemy.orm import Session

from app.config import GEO_ACTIVE_PROVINCES
from app.models.addresses import Address, Commune, Province
from app.schemas.geo import AddressCreate, CommuneBulkItem, CommuneCreate, ProvinceCreate


class GeoValidationError(Exception):
    pass


def list_provinces(db: Session, *, q: str | None = None, limit: int = 200) -> list[Province]:
    limit = max(1, min(limit, 1000))
    query = db.query(Province)
    if GEO_ACTIVE_PROVINCES:
        query = query.filter(Province.name.in_(GEO_ACTIVE_PROVINCES))
    if q:
        query = query.filter(Province.name.ilike(f"%{q.strip()}%"))
    return query.order_by(Province.name.asc()).limit(limit).all()


def create_province(db: Session, payload: ProvinceCreate) -> Province:
    name = payload.name.strip()
    existing = db.query(Province).filter(Province.name.ilike(name)).first()
    if existing:
        return existing
    row = Province(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_communes(
    db: Session,
    *,
    province_id=None,
    q: str | None = None,
    limit: int = 500,
) -> list[Commune]:
    limit = max(1, min(limit, 2000))
    query = db.query(Commune)
    if GEO_ACTIVE_PROVINCES:
        query = query.join(Province, Province.id == Commune.province_id).filter(
            Province.name.in_(GEO_ACTIVE_PROVINCES)
        )
    if province_id is not None:
        query = query.filter(Commune.province_id == province_id)
    if q:
        query = query.filter(Commune.name.ilike(f"%{q.strip()}%"))
    return query.order_by(Commune.name.asc()).limit(limit).all()


def create_commune(db: Session, payload: CommuneCreate) -> Commune:
    province = db.query(Province).filter(Province.id == payload.province_id).first()
    if not province:
        raise GeoValidationError("Province not found")

    name = payload.name.strip()
    existing = (
        db.query(Commune)
        .filter(Commune.province_id == province.id, Commune.name.ilike(name))
        .first()
    )
    if existing:
        return existing

    row = Commune(province_id=province.id, name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bulk_upsert_communes(db: Session, items: list[CommuneBulkItem]) -> dict:
    scanned = len(items)
    created = 0
    updated = 0
    skipped_missing_province = 0

    province_by_name = {
        row.name.lower(): row
        for row in db.query(Province).all()
    }
    for item in items:
        province = province_by_name.get(item.province_name.strip().lower())
        if not province:
            skipped_missing_province += 1
            continue

        normalized_commune_name = item.commune_name.strip()
        existing = (
            db.query(Commune)
            .filter(
                Commune.province_id == province.id,
                Commune.name.ilike(normalized_commune_name),
            )
            .first()
        )
        if existing:
            if existing.name != normalized_commune_name:
                existing.name = normalized_commune_name
                updated += 1
            continue

        db.add(Commune(province_id=province.id, name=normalized_commune_name))
        created += 1

    db.commit()
    return {
        "scanned": scanned,
        "created": created,
        "updated": updated,
        "skipped_missing_province": skipped_missing_province,
    }


def create_address(db: Session, payload: AddressCreate) -> Address:
    province = db.query(Province).filter(Province.id == payload.province_id).first()
    if not province:
        raise GeoValidationError("Province not found")

    commune = db.query(Commune).filter(Commune.id == payload.commune_id).first()
    if not commune:
        raise GeoValidationError("Commune not found")
    if commune.province_id != province.id:
        raise GeoValidationError("Commune does not belong to selected province")

    address = Address(
        province_id=province.id,
        commune_id=commune.id,
        province=province.name,
        commune=commune.name,
        zone=payload.zone,
        colline=payload.colline,
        quartier=payload.quartier,
        landmark=payload.landmark,
        latitude=payload.latitude,
        longitude=payload.longitude,
        raw_input=payload.raw_input,
        address_line=payload.address_line,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address
