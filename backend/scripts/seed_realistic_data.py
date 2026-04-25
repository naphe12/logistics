import argparse
import hashlib
import os
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _password_hash(value: str) -> str:
    return f"sha256${_hash_text(value)}"


def _weighted_choice(rng: random.Random, weighted_values: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in weighted_values)
    point = rng.random() * total
    acc = 0.0
    for value, weight in weighted_values:
        acc += weight
        if point <= acc:
            return value
    return weighted_values[-1][0]


def _random_phone(rng: random.Random, prefix: str = "+2576") -> str:
    return f"{prefix}{rng.randint(1000000, 9999999)}"


def _pick_status(preferred: list[str], existing: set[str], fallback: str | None = None) -> str | None:
    for code in preferred:
        if code in existing:
            return code
    if fallback and fallback in existing:
        return fallback
    return next(iter(existing)) if existing else None


def _build_shipment_timeline(target_status: str | None) -> list[str]:
    path = ["created", "ready_for_pickup", "picked_up", "in_transit", "arrived_at_relay", "delivered"]
    if target_status not in path:
        return ["created"]
    idx = path.index(target_status)
    return path[: idx + 1]


@dataclass
class SeedSummary:
    users_created: int = 0
    relays_created: int = 0
    routes_created: int = 0
    trips_created: int = 0
    shipments_created: int = 0
    events_created: int = 0
    payments_created: int = 0
    incidents_created: int = 0
    claims_created: int = 0
    schedules_created: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed realistic logistics test data")
    parser.add_argument("--tag", default="demo", help="Tag added to metadata and generated identifiers")
    parser.add_argument("--seed", type=int, default=20260425, help="Random seed for reproducible generation")
    parser.add_argument("--users", type=int, default=60, help="Number of customer/business users to create")
    parser.add_argument("--relays", type=int, default=12, help="Number of relay points to create")
    parser.add_argument("--trips", type=int, default=16, help="Number of trips to create")
    parser.add_argument("--shipments", type=int, default=220, help="Number of shipments to create")
    parser.add_argument("--schedules", type=int, default=40, help="Number of shipment schedules to create")
    parser.add_argument(
        "--payments-ratio",
        type=float,
        default=0.62,
        help="Ratio of shipments with payment transactions (0..1)",
    )
    parser.add_argument(
        "--incidents-ratio",
        type=float,
        default=0.14,
        help="Ratio of shipments with incidents (0..1)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build data but rollback at the end")
    args = parser.parse_args()

    load_env_file(ROOT_DIR / ".env")

    from app.database import SessionLocal
    from app.enums import CodePurposeEnum, UserTypeEnum
    from app.models.addresses import Address, Commune, Province
    from app.models.incidents import Claim, Commission, Incident, IncidentUpdate
    from app.models.payments import PaymentTransaction
    from app.models.relays import RelayPoint
    from app.models.shipments import (
        Manifest,
        ManifestShipment,
        RelayInventory,
        Shipment,
        ShipmentEvent,
        ShipmentSchedule,
    )
    from app.models.statuses import IncidentStatus, PaymentStatus, ShipmentStatus
    from app.models.transport import Route, TransportPartner, Trip, Vehicle
    from app.models.ussd import ShipmentCode
    from app.models.users import User

    rng = random.Random(args.seed)
    now = datetime.now(UTC)
    summary = SeedSummary()

    db = SessionLocal()
    try:
        provinces = db.query(Province).order_by(Province.name.asc()).all()
        if not provinces:
            fallback = Province(name="Bujumbura Mairie")
            db.add(fallback)
            db.flush()
            provinces = [fallback]
        communes = db.query(Commune).order_by(Commune.name.asc()).all()
        if not communes:
            fallback_commune = Commune(province_id=provinces[0].id, name="Mukaza")
            db.add(fallback_commune)
            db.flush()
            communes = [fallback_commune]

        addresses = db.query(Address).all()
        target_addresses = max(args.relays * 2, 24)
        if len(addresses) < target_addresses:
            for _ in range(target_addresses - len(addresses)):
                province = rng.choice(provinces)
                commune = rng.choice([c for c in communes if c.province_id == province.id] or communes)
                lat = Decimal("-4.4") + (Decimal(rng.random()) * Decimal("1.4"))
                lng = Decimal("29.0") + (Decimal(rng.random()) * Decimal("1.6"))
                address = Address(
                    province_id=province.id,
                    commune_id=commune.id,
                    province=province.name,
                    commune=commune.name,
                    zone=f"Zone {rng.randint(1, 9)}",
                    colline=f"Colline {rng.randint(1, 30)}",
                    quartier=f"Quartier {rng.randint(1, 20)}",
                    landmark=f"Pres de point repere {rng.randint(1, 200)}",
                    latitude=lat.quantize(Decimal("0.000001")),
                    longitude=lng.quantize(Decimal("0.000001")),
                    raw_input=f"{commune.name}, {province.name}",
                    address_line=f"Avenue {rng.randint(1, 80)}",
                    created_at=now - timedelta(days=rng.randint(0, 360)),
                )
                db.add(address)
            db.flush()
            addresses = db.query(Address).all()

        base_password = _password_hash("Test1234!")
        operators = [
            ("admin", UserTypeEnum.admin, "+25762000003", "Admin", "Logix"),
            ("hub", UserTypeEnum.hub, "+25762000004", "Hub", "Manager"),
            ("agent", UserTypeEnum.agent, "+25762000002", "Agent", "Relay"),
        ]
        for _, role, phone, first, last in operators:
            existing = db.query(User).filter(User.phone_e164 == phone).first()
            if existing:
                continue
            db.add(
                User(
                    phone_e164=phone,
                    password_hash=base_password,
                    first_name=first,
                    last_name=last,
                    user_type=role,
                    extra={"seed_tag": args.tag, "seed_kind": "operator"},
                )
            )
            summary.users_created += 1
        db.flush()

        first_names = [
            "Aline",
            "Patrick",
            "Nadine",
            "Claude",
            "Brenda",
            "Thierry",
            "Sonia",
            "Eric",
            "Linda",
            "Pascal",
        ]
        last_names = [
            "Ndayizeye",
            "Nkurunziza",
            "Hakizimana",
            "Niyonsaba",
            "Irankunda",
            "Bizimana",
            "Nshimirimana",
            "Ndikumana",
        ]
        for idx in range(args.users):
            role = UserTypeEnum.customer if rng.random() < 0.82 else UserTypeEnum.business
            phone = _random_phone(rng, prefix="+2576")
            if db.query(User.id).filter(User.phone_e164 == phone).first():
                continue
            db.add(
                User(
                    phone_e164=phone,
                    password_hash=base_password,
                    first_name=rng.choice(first_names),
                    last_name=rng.choice(last_names),
                    user_type=role,
                    extra={"seed_tag": args.tag, "seed_kind": "customer_pool", "seed_idx": idx},
                )
            )
            summary.users_created += 1
        db.flush()

        all_agents = db.query(User).filter(User.user_type == UserTypeEnum.agent).all()
        user_pool = db.query(User).filter(User.user_type.in_([UserTypeEnum.customer, UserTypeEnum.business])).all()
        if not user_pool:
            print("No customer/business users available to create shipments.")
            return 1

        commune_by_id = {row.id: row for row in communes}
        province_by_id = {row.id: row for row in provinces}
        relay_types = ["relay", "hub", "relay", "relay"]
        for idx in range(args.relays):
            code = f"RL-{args.tag[:3].upper()}-{idx:03d}"
            existing = db.query(RelayPoint).filter(RelayPoint.relay_code == code).first()
            if existing:
                continue
            address = rng.choice(addresses)
            province_id = address.province_id or provinces[0].id
            commune_id = address.commune_id or communes[0].id
            province = province_by_id.get(province_id, provinces[0])
            commune = commune_by_id.get(commune_id, communes[0])
            relay = RelayPoint(
                relay_code=code,
                name=f"Relay {commune.name} {idx + 1}",
                type=rng.choice(relay_types),
                province_id=province.id,
                commune_id=commune.id,
                address_id=address.id,
                opening_hours="07:30-19:00",
                storage_capacity=rng.randint(80, 350),
                is_active=True,
            )
            db.add(relay)
            summary.relays_created += 1
        db.flush()
        relays = db.query(RelayPoint).filter(RelayPoint.is_active.is_(True)).all()
        if len(relays) < 2:
            print("Need at least 2 active relays to seed realistic logistics data.")
            return 1

        if all_agents:
            for agent in all_agents:
                if not agent.relay_id:
                    agent.relay_id = rng.choice(relays).id

        partner_name = f"Transit {args.tag.upper()}"
        partner = db.query(TransportPartner).filter(TransportPartner.name == partner_name).first()
        if not partner:
            partner = TransportPartner(name=partner_name)
            db.add(partner)
            db.flush()

        vehicles: list[Vehicle] = []
        for idx in range(max(4, args.trips // 3)):
            plate = f"TR-{args.tag[:2].upper()}{idx:03d}"
            existing_vehicle = db.query(Vehicle).filter(Vehicle.plate == plate).first()
            if existing_vehicle:
                vehicles.append(existing_vehicle)
                continue
            vehicle = Vehicle(partner_id=partner.id, plate=plate)
            db.add(vehicle)
            db.flush()
            vehicles.append(vehicle)

        routes: list[Route] = []
        for idx in range(max(5, args.trips // 2)):
            origin = rng.choice(relays)
            destination = rng.choice([row for row in relays if row.id != origin.id] or relays)
            route = Route(origin=origin.id, destination=destination.id)
            db.add(route)
            db.flush()
            routes.append(route)
            summary.routes_created += 1

        trips: list[Trip] = []
        trip_statuses = ["planned", "in_progress", "arrived", "completed"]
        for idx in range(args.trips):
            route = rng.choice(routes)
            vehicle = rng.choice(vehicles)
            trip = Trip(
                route_id=route.id,
                vehicle_id=vehicle.id,
                status=rng.choice(trip_statuses),
                extra={
                    "seed_tag": args.tag,
                    "seed_idx": idx,
                    "driver_name": f"Driver {idx + 1}",
                    "planned_departure_at": (now + timedelta(hours=rng.randint(-72, 72))).isoformat(),
                },
            )
            db.add(trip)
            db.flush()
            trips.append(trip)
            summary.trips_created += 1

        shipment_statuses = {row.code for row in db.query(ShipmentStatus).all()}
        payment_statuses = {row.code for row in db.query(PaymentStatus).all()}
        incident_statuses = {row.code for row in db.query(IncidentStatus).all()}

        shipment_status_weights = [
            ("created", 0.10),
            ("ready_for_pickup", 0.16),
            ("picked_up", 0.18),
            ("in_transit", 0.24),
            ("arrived_at_relay", 0.15),
            ("delivered", 0.17),
        ]
        shipment_status_choices = [
            (code, weight) for code, weight in shipment_status_weights if code in shipment_statuses
        ] or [(next(iter(shipment_statuses)) if shipment_statuses else "created", 1.0)]

        incident_type_values = ["delayed", "lost", "damaged"]
        payment_stage_values = ["at_send", "at_delivery"]
        payment_provider_values = ["lumicash", "ecocash", "cash"]

        created_shipments: list[Shipment] = []
        for idx in range(args.shipments):
            sender = rng.choice(user_pool)
            receiver_name = f"{rng.choice(first_names)} {rng.choice(last_names)}"
            receiver_phone = _random_phone(rng, prefix="+2577")
            origin = rng.choice(relays)
            destination = rng.choice([row for row in relays if row.id != origin.id] or relays)
            created_at = now - timedelta(
                days=rng.randint(0, 75),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )
            declared_value = Decimal(rng.randint(5000, 650000)).quantize(Decimal("0.01"))
            insurance_fee = (declared_value * Decimal("0.0075")).quantize(Decimal("0.01"))
            status = _weighted_choice(rng, shipment_status_choices)

            shipment_no = f"PBL-{args.tag[:4].upper()}-{datetime.now(UTC).strftime('%y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            shipment = Shipment(
                shipment_no=shipment_no[:40],
                sender_id=sender.id,
                sender_phone=sender.phone_e164,
                receiver_name=receiver_name,
                receiver_phone=receiver_phone,
                origin_relay_id=origin.id,
                destination_relay_id=destination.id,
                delivery_address_id=rng.choice(addresses).id if addresses else None,
                delivery_note=rng.choice(
                    [
                        "Livrer au comptoir principal",
                        "Appeler avant livraison",
                        "Fragile - manipuler avec soin",
                        "Retrait prioritaire",
                    ]
                ),
                origin=origin.id,
                destination=destination.id,
                status=status,
                declared_value=declared_value,
                insurance_fee=insurance_fee if rng.random() < 0.55 else Decimal("0"),
                coverage_amount=declared_value if rng.random() < 0.55 else Decimal("0"),
                extra={"seed_tag": args.tag, "seed_idx": idx, "channel": rng.choice(["app", "ussd", "agent"])},
                created_at=created_at,
                updated_at=created_at + timedelta(hours=rng.randint(1, 72)),
            )
            db.add(shipment)
            db.flush()
            created_shipments.append(shipment)
            summary.shipments_created += 1

            timeline = _build_shipment_timeline(status)
            event_time = created_at
            for step_idx, step_status in enumerate(timeline):
                relay_for_event = origin.id if step_idx <= 1 else destination.id
                event = ShipmentEvent(
                    shipment_id=shipment.id,
                    relay_id=relay_for_event,
                    event_type=f"shipment_{step_status}",
                    extra={"status": step_status, "seed_tag": args.tag},
                    created_at=event_time,
                )
                db.add(event)
                summary.events_created += 1
                event_time = event_time + timedelta(hours=rng.randint(1, 12))

            if status in {"arrived_at_relay", "ready_for_pickup"}:
                db.add(
                    RelayInventory(
                        relay_id=destination.id,
                        shipment_id=shipment.id,
                        present=True,
                    )
                )
            if status == "delivered":
                db.add(
                    RelayInventory(
                        relay_id=destination.id,
                        shipment_id=shipment.id,
                        present=False,
                    )
                )

            if status in {"arrived_at_relay", "ready_for_pickup"}:
                raw_code = f"{rng.randint(0, 999999):06d}"
                db.add(
                    ShipmentCode(
                        shipment_id=shipment.id,
                        code_hash=_hash_text(raw_code),
                        code_last4=raw_code[-4:],
                        purpose=CodePurposeEnum.pickup,
                        expires_at=now + timedelta(hours=rng.randint(6, 72)),
                    )
                )

            if rng.random() <= max(0.0, min(1.0, args.payments_ratio)):
                payment_status = _pick_status(
                    ["paid", "processing", "pending", "failed", "refunded"],
                    payment_statuses,
                )
                amount = (declared_value * Decimal(rng.uniform(0.7, 1.2))).quantize(Decimal("0.01"))
                payment = PaymentTransaction(
                    shipment_id=shipment.id,
                    amount=amount,
                    payer_phone=shipment.sender_phone,
                    payment_stage=rng.choice(payment_stage_values),
                    provider=rng.choice(payment_provider_values),
                    external_ref=f"SEED-{args.tag.upper()}-{uuid.uuid4().hex[:10]}",
                    status=payment_status,
                    failure_reason="insufficient_funds" if payment_status == "failed" else None,
                    extra={"seed_tag": args.tag},
                    created_at=created_at + timedelta(hours=rng.randint(0, 24)),
                    updated_at=created_at + timedelta(hours=rng.randint(1, 48)),
                )
                db.add(payment)
                db.flush()
                summary.payments_created += 1

                if payment_status in {"paid", "refunded"}:
                    relay_commission = Commission(
                        shipment_id=shipment.id,
                        payment_id=payment.id,
                        commission_type="relay",
                        beneficiary_kind="relay",
                        beneficiary_id=destination.id,
                        rate_pct=Decimal("0.0400"),
                        amount=(amount * Decimal("0.04")).quantize(Decimal("0.01")),
                        status="accrued",
                        created_at=payment.created_at,
                    )
                    transporter_commission = Commission(
                        shipment_id=shipment.id,
                        payment_id=payment.id,
                        commission_type="transport",
                        beneficiary_kind="transport_partner",
                        beneficiary_id=partner.id,
                        rate_pct=Decimal("0.0650"),
                        amount=(amount * Decimal("0.065")).quantize(Decimal("0.01")),
                        status="accrued",
                        created_at=payment.created_at,
                    )
                    db.add(relay_commission)
                    db.add(transporter_commission)

            if rng.random() <= max(0.0, min(1.0, args.incidents_ratio)):
                incident_status = _pick_status(
                    ["open", "investigating", "resolved", "closed"],
                    incident_statuses,
                )
                incident = Incident(
                    shipment_id=shipment.id,
                    incident_type=rng.choice(incident_type_values),
                    description=rng.choice(
                        [
                            "Retard signale sur le corridor inter-province.",
                            "Emballage endommage constate a l arrivee.",
                            "Divergence inventaire relais lors du scan.",
                            "Client indisponible au retrait planifie.",
                        ]
                    ),
                    status=incident_status,
                    extra={"seed_tag": args.tag, "priority": rng.choice(["low", "medium", "high"])},
                    created_at=created_at + timedelta(hours=rng.randint(2, 96)),
                    updated_at=created_at + timedelta(hours=rng.randint(4, 120)),
                )
                db.add(incident)
                db.flush()
                summary.incidents_created += 1

                updates_count = rng.randint(1, 3)
                for update_idx in range(updates_count):
                    db.add(
                        IncidentUpdate(
                            incident_id=incident.id,
                            message=f"Suivi incident {update_idx + 1}: action terrain en cours.",
                            created_at=incident.created_at + timedelta(hours=update_idx + 1),
                        )
                    )

                if rng.random() < 0.45:
                    amount_requested = (declared_value * Decimal(rng.uniform(0.2, 1.0))).quantize(Decimal("0.01"))
                    amount_approved = (amount_requested * Decimal(rng.uniform(0.5, 1.0))).quantize(Decimal("0.01"))
                    claim = Claim(
                        shipment_id=shipment.id,
                        incident_id=incident.id,
                        amount=amount_approved,
                        amount_requested=amount_requested,
                        amount_approved=amount_approved,
                        claim_type=rng.choice(["refund", "damage", "loss"]),
                        proof_urls=["https://example.test/proof/1.jpg", "https://example.test/proof/2.jpg"],
                        risk_score=Decimal(rng.uniform(15, 85)).quantize(Decimal("0.01")),
                        risk_flags=rng.sample(
                            ["high_value", "repeat_claimant", "missing_scan", "route_delay"],
                            k=rng.randint(0, 2),
                        ),
                        escalated_at=incident.created_at + timedelta(hours=rng.randint(12, 72)),
                        status=rng.choice(["submitted", "reviewing", "approved", "rejected", "refunded"]),
                        reason="Demande client suite incident",
                        resolution_note="Resolution seed data",
                        refunded_payment_id=None,
                        updated_at=incident.updated_at,
                        created_at=incident.created_at + timedelta(hours=1),
                    )
                    db.add(claim)
                    summary.claims_created += 1

        shipment_ids_for_manifest = [row.id for row in created_shipments if row.status in {"picked_up", "in_transit"}]
        for trip_idx, trip in enumerate(trips):
            manifest = Manifest(trip_id=trip.id)
            db.add(manifest)
            db.flush()
            picked = rng.sample(shipment_ids_for_manifest, k=min(len(shipment_ids_for_manifest), rng.randint(3, 10)))
            for shipment_id in picked:
                db.add(ManifestShipment(manifest_id=manifest.id, shipment_id=shipment_id))
            if trip_idx < len(routes):
                trip.status = rng.choice(["planned", "in_progress", "arrived", "completed"])

        schedule_frequencies = ["once", "daily", "weekly", "monthly"]
        for idx in range(args.schedules):
            sender = rng.choice(user_pool)
            origin = rng.choice(relays)
            destination = rng.choice([row for row in relays if row.id != origin.id] or relays)
            frequency = rng.choice(schedule_frequencies)
            start_at = now + timedelta(days=rng.randint(-7, 25), hours=rng.randint(0, 23))
            schedule = ShipmentSchedule(
                sender_id=sender.id,
                sender_phone=sender.phone_e164,
                receiver_name=f"{rng.choice(first_names)} {rng.choice(last_names)}",
                receiver_phone=_random_phone(rng, prefix="+2577"),
                origin_relay_id=origin.id,
                destination_relay_id=destination.id,
                delivery_address_id=rng.choice(addresses).id if addresses else None,
                delivery_note=rng.choice(["Passage standard", "Retrait matinal", "Client VIP"]),
                declared_value=Decimal(rng.randint(10000, 450000)).quantize(Decimal("0.01")),
                insurance_opt_in=rng.random() < 0.4,
                frequency=frequency,
                interval_count=rng.randint(1, 4),
                day_of_week=rng.randint(0, 6) if frequency == "weekly" else None,
                day_of_month=rng.randint(1, 28) if frequency == "monthly" else None,
                start_at=start_at,
                next_run_at=start_at,
                last_run_at=None,
                end_at=start_at + timedelta(days=rng.randint(30, 180)) if rng.random() < 0.6 else None,
                remaining_runs=rng.randint(2, 40) if rng.random() < 0.7 else None,
                is_active=rng.random() < 0.9,
                last_error=None,
                extra={"seed_tag": args.tag, "seed_idx": idx},
                created_at=now - timedelta(days=rng.randint(0, 40)),
                updated_at=now - timedelta(days=rng.randint(0, 20)),
            )
            db.add(schedule)
            summary.schedules_created += 1

        if args.dry_run:
            db.rollback()
            print("[dry-run] realistic seed prepared (no write).")
        else:
            db.commit()
            print("realistic seed complete.")

        print(
            "summary:"
            f" users={summary.users_created},"
            f" relays={summary.relays_created},"
            f" routes={summary.routes_created},"
            f" trips={summary.trips_created},"
            f" shipments={summary.shipments_created},"
            f" events={summary.events_created},"
            f" payments={summary.payments_created},"
            f" incidents={summary.incidents_created},"
            f" claims={summary.claims_created},"
            f" schedules={summary.schedules_created}"
        )
        print(f"seed tag: {args.tag}")
        print("default seeded user password: Test1234!")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
