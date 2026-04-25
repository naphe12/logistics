def _req(client, method: str, path: str, expected: tuple[int, ...] = (200,), json=None):
    res = client["session"].request(
        method,
        f'{client["base_url"]}{path}',
        timeout=client["timeout"],
        json=json,
    )
    assert res.status_code in expected, f"{method} {path} -> {res.status_code}: {res.text}"
    return res


def _create_shipment(client, sender_phone: str, receiver_phone: str, run_id: str) -> dict:
    res = _req(
        client,
        "POST",
        "/shipments",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Provider Receiver {run_id}",
            "receiver_phone": receiver_phone,
        },
    )
    return res.json()


def test_payment_provider_normalization_and_webhook_mapping(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id)
    shipment_id = shipment["id"]

    payment = _req(
        client,
        "POST",
        "/payments",
        expected=(200,),
        json={
            "shipment_id": shipment_id,
            "amount": 5000,
            "payer_phone": sender_phone,
            "payment_stage": "at_send",
            "provider": "Lumi-Cash",
        },
    ).json()
    payment_id = payment["id"]
    assert payment["provider"] == "lumicash"

    initiated = _req(
        client,
        "POST",
        f"/payments/{payment_id}/initiate",
        expected=(200,),
        json={},
    ).json()
    assert initiated["status"] == "processing"
    assert initiated.get("extra")
    provider_init = initiated["extra"].get("provider_initiation")
    assert provider_init
    assert provider_init.get("provider") == "lumicash"

    webhook = _req(
        client,
        "POST",
        "/payments/webhooks/provider/simulate",
        expected=(200,),
        json={
            "event_id": f"pytest-provider-{run_id}",
            "event_type": "payment_update",
            "payment_id": payment_id,
            "external_ref": initiated.get("external_ref"),
            "status": "successful",
            "provider": "lumicash",
            "payload": {"source": "pytest"},
        },
    ).json()
    assert webhook["accepted"] is True
    assert webhook["applied"] is True
    assert webhook["status"] == "paid"


def test_shipment_invalid_transition_and_backoffice_s1_kpis(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id)
    shipment_id = shipment["id"]

    invalid_transition = _req(
        client,
        "PATCH",
        f"/shipments/{shipment_id}/status",
        expected=(422,),
        json={"status": "delivered", "event_type": "pytest_invalid_direct_delivered"},
    ).json()
    assert "detail" in invalid_transition

    kpis = _req(
        client,
        "GET",
        "/backoffice/kpis/s1?window_hours=168",
        expected=(200,),
    ).json()
    assert "on_time_rate" in kpis
    assert "incident_rate" in kpis
    assert "scan_compliance" in kpis
    assert "window_hours" in kpis
