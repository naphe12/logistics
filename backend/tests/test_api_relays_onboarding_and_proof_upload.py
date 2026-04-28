def _req(client, method: str, path: str, expected: tuple[int, ...] = (200,), json=None):
    res = client["session"].request(
        method,
        f'{client["base_url"]}{path}',
        timeout=client["timeout"],
        json=json,
    )
    assert res.status_code in expected, f"{method} {path} -> {res.status_code}: {res.text}"
    return res


def _req_multipart(
    client,
    method: str,
    path: str,
    expected: tuple[int, ...] = (200,),
    data=None,
    files=None,
):
    headers = {"Authorization": client["session"].headers.get("Authorization", "")}
    res = client["session"].request(
        method,
        f'{client["base_url"]}{path}',
        timeout=client["timeout"],
        data=data,
        files=files,
        headers=headers,
    )
    assert res.status_code in expected, f"{method} {path} -> {res.status_code}: {res.text}"
    return res


def _create_shipment(client, sender_phone: str, receiver_phone: str, run_id: str, suffix: str) -> dict:
    res = _req(
        client,
        "POST",
        "/shipments",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Proof Receiver {run_id}-{suffix}",
            "receiver_phone": receiver_phone,
        },
    )
    return res.json()


def _first_relay_id_or_skip(client):
    relays = _req(client, "GET", "/relays/public", expected=(200,)).json()
    if not relays:
        return None
    return relays[0].get("id")


def test_delivery_proof_upload_multipart(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "upload")
    shipment_id = shipment["id"]

    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    res = _req_multipart(
        client,
        "POST",
        f"/shipments/{shipment_id}/delivery-proof/upload",
        expected=(200,),
        data={
            "receiver_name": "Receiver Upload Test",
            "signature": "signed-by-manager",
            "geo_lat": "-3.38",
            "geo_lng": "29.36",
        },
        files={"photo": ("proof.png", png_bytes, "image/png")},
    ).json()

    assert res["id"] == shipment_id
    assert res["status"] == "delivered"
    proof = (res.get("extra") or {}).get("delivery_proof") or {}
    assert proof.get("photo_url")
    assert str(proof.get("photo_url")).startswith("/media/delivery-proofs/")


def test_relay_manager_application_lifecycle(client, run_id):
    relay_id = _first_relay_id_or_skip(client)
    if not relay_id:
        return

    created = _req(
        client,
        "POST",
        "/relays/manager-applications",
        expected=(200,),
        json={
            "relay_id": relay_id,
            "manager_name": f"Gerant {run_id}",
            "manager_phone": f"+25779{run_id[:6]}",
            "manager_email": f"gerant-{run_id}@logix.test",
            "notes": "Candidature terrain",
        },
    ).json()
    assert created["relay_id"] == relay_id
    assert created["status"] == "pending"
    app_id = created["id"]

    listing = _req(
        client,
        "GET",
        "/relays/manager-applications?status=pending&limit=200",
        expected=(200,),
    ).json()
    assert any(row["id"] == app_id for row in listing)

    reviewed = _req(
        client,
        "PATCH",
        f"/relays/manager-applications/{app_id}",
        expected=(200,),
        json={
            "status": "trained",
            "training_completed": True,
            "notes": "Formation terminee",
        },
    ).json()
    assert reviewed["id"] == app_id
    assert reviewed["status"] == "trained"
    assert reviewed["training_completed"] is True
