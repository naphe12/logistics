import argparse
import json
import sys
import uuid
from dataclasses import dataclass

import requests


@dataclass
class SmokeContext:
    base_url: str
    token: str
    timeout_seconds: float


class SmokeError(Exception):
    pass


def _request(
    ctx: SmokeContext,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    expected_statuses: tuple[int, ...] = (200,),
) -> requests.Response:
    url = f"{ctx.base_url}{path}"
    headers = {"Authorization": f"Bearer {ctx.token}", "Content-Type": "application/json"}
    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=ctx.timeout_seconds,
    )
    if response.status_code not in expected_statuses:
        body = response.text
        raise SmokeError(f"{method} {path} -> {response.status_code}: {body}")
    return response


def _pretty(data: dict) -> str:
    return json.dumps(data, ensure_ascii=True, indent=2)


def run_smoke(ctx: SmokeContext, sender_phone: str, receiver_phone: str) -> None:
    print("[1/10] GET /health")
    health = requests.get(f"{ctx.base_url}/health", timeout=ctx.timeout_seconds)
    if health.status_code != 200:
        raise SmokeError(f"GET /health -> {health.status_code}: {health.text}")

    print("[2/10] GET /auth/me")
    me = _request(ctx, "GET", "/auth/me").json()
    print(_pretty({"user_id": me.get("id"), "user_type": me.get("user_type"), "phone": me.get("phone_e164")}))

    print("[3/10] POST /shipments")
    shipment = _request(
        ctx,
        "POST",
        "/shipments",
        json_body={
            "sender_phone": sender_phone,
            "receiver_name": "Smoke Receiver",
            "receiver_phone": receiver_phone,
        },
    ).json()
    shipment_id = shipment["id"]
    print(_pretty({"shipment_id": shipment_id, "shipment_no": shipment.get("shipment_no"), "status": shipment.get("status")}))

    print("[4/10] PATCH /shipments/{id}/status")
    updated = _request(
        ctx,
        "PATCH",
        f"/shipments/{shipment_id}/status",
        json_body={"status": "in_transit", "event_type": "smoke_status_update"},
    ).json()
    print(_pretty({"shipment_id": shipment_id, "status": updated.get("status")}))

    print("[5/10] POST /payments")
    payment = _request(
        ctx,
        "POST",
        "/payments",
        json_body={
            "shipment_id": shipment_id,
            "amount": 15000,
            "payer_phone": sender_phone,
            "payment_stage": "at_send",
            "provider": "lumicash",
        },
    ).json()
    payment_id = payment["id"]
    print(_pretty({"payment_id": payment_id, "status": payment.get("status")}))

    print("[6/10] POST /payments/{id}/initiate")
    initiated = _request(
        ctx,
        "POST",
        f"/payments/{payment_id}/initiate",
        json_body={"external_ref": f"SMOKE-{uuid.uuid4().hex[:8]}"},
    ).json()
    print(_pretty({"payment_id": payment_id, "status": initiated.get("status")}))

    print("[7/10] POST /payments/{id}/confirm")
    confirmed = _request(
        ctx,
        "POST",
        f"/payments/{payment_id}/confirm",
        json_body={"external_ref": f"SMOKE-C-{uuid.uuid4().hex[:8]}"},
    ).json()
    print(_pretty({"payment_id": payment_id, "status": confirmed.get("status")}))

    print("[8/10] POST /incidents")
    incident = _request(
        ctx,
        "POST",
        "/incidents",
        json_body={
            "shipment_id": shipment_id,
            "incident_type": "delayed",
            "description": "Smoke incident",
        },
    ).json()
    print(_pretty({"incident_id": incident.get("id"), "status": incident.get("status")}))

    print("[9/10] GET /backoffice/alerts")
    alerts = _request(ctx, "GET", "/backoffice/alerts?delayed_hours=1&relay_utilization_warn=0.8&limit=20").json()
    print(_pretty({"alerts_count": len(alerts)}))

    print("[10/10] POST /backoffice/incidents/auto-detect")
    autodetect = _request(
        ctx,
        "POST",
        "/backoffice/incidents/auto-detect?delayed_hours=1&limit=100",
    ).json()
    print(_pretty(autodetect))

    print("SMOKE OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API smoke checks against a deployed Logix backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL without trailing slash")
    parser.add_argument("--token", required=True, help="Bearer access token (admin/hub recommended)")
    parser.add_argument("--sender-phone", default="+25762009001", help="Sender phone for smoke shipment")
    parser.add_argument("--receiver-phone", default="+25762009002", help="Receiver phone for smoke shipment")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    ctx = SmokeContext(base_url=base, token=args.token, timeout_seconds=max(1.0, args.timeout))
    try:
        run_smoke(ctx, sender_phone=args.sender_phone, receiver_phone=args.receiver_phone)
        return 0
    except SmokeError as exc:
        print(f"SMOKE FAILED: {exc}")
        return 2
    except requests.RequestException as exc:
        print(f"SMOKE NETWORK ERROR: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

