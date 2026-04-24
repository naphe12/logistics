import uuid


def _req(client, method: str, path: str, expected: tuple[int, ...] = (200,), json=None):
    res = client["session"].request(
        method,
        f'{client["base_url"]}{path}',
        timeout=client["timeout"],
        json=json,
    )
    assert res.status_code in expected, f"{method} {path} -> {res.status_code}: {res.text}"
    return res


def test_health(client):
    _req(client, "GET", "/health", expected=(200,))


def test_auth_me(client):
    res = _req(client, "GET", "/auth/me", expected=(200,))
    data = res.json()
    assert data.get("id")
    assert data.get("user_type")
    assert data.get("phone_e164")


def test_shipment_to_payment_to_incident_flow(client, sender_phone, receiver_phone, run_id):
    shipment_res = _req(
        client,
        "POST",
        "/shipments",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Smoke Receiver {run_id}",
            "receiver_phone": receiver_phone,
        },
    )
    shipment = shipment_res.json()
    shipment_id = shipment["id"]
    assert shipment.get("shipment_no")

    updated_res = _req(
        client,
        "PATCH",
        f"/shipments/{shipment_id}/status",
        expected=(200,),
        json={"status": "in_transit", "event_type": "pytest_status_update"},
    )
    updated = updated_res.json()
    assert updated.get("status") == "in_transit"

    payment_res = _req(
        client,
        "POST",
        "/payments",
        expected=(200,),
        json={
            "shipment_id": shipment_id,
            "amount": 12000,
            "payer_phone": sender_phone,
            "payment_stage": "at_send",
            "provider": "lumicash",
        },
    )
    payment = payment_res.json()
    payment_id = payment["id"]
    assert payment.get("status") == "pending"

    initiated_res = _req(
        client,
        "POST",
        f"/payments/{payment_id}/initiate",
        expected=(200,),
        json={"external_ref": f"PYTEST-I-{uuid.uuid4().hex[:8]}"},
    )
    assert initiated_res.json().get("status") == "processing"

    confirmed_res = _req(
        client,
        "POST",
        f"/payments/{payment_id}/confirm",
        expected=(200,),
        json={"external_ref": f"PYTEST-C-{uuid.uuid4().hex[:8]}"},
    )
    assert confirmed_res.json().get("status") == "paid"

    incident_res = _req(
        client,
        "POST",
        "/incidents",
        expected=(200,),
        json={
            "shipment_id": shipment_id,
            "incident_type": "delayed",
            "description": f"Pytest incident {run_id}",
        },
    )
    incident = incident_res.json()
    assert incident.get("id")
    assert incident.get("status") == "open"


def test_backoffice_endpoints(client):
    alerts_res = _req(
        client,
        "GET",
        "/backoffice/alerts?delayed_hours=1&relay_utilization_warn=0.8&limit=20",
        expected=(200,),
    )
    assert isinstance(alerts_res.json(), list)

    auto_detect_res = _req(
        client,
        "POST",
        "/backoffice/incidents/auto-detect?delayed_hours=1&limit=100",
        expected=(200,),
    )
    payload = auto_detect_res.json()
    assert "examined" in payload
    assert "created" in payload

    notify_res = _req(
        client,
        "POST",
        "/backoffice/alerts/notify-critical?delayed_hours=1&relay_utilization_warn=0.8&throttle_minutes=30&max_recipients=20&max_per_hour=4",
        expected=(200,),
    )
    notify = notify_res.json()
    assert "critical_count" in notify
    assert "sent_count" in notify

