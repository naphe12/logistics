from datetime import UTC, datetime, timedelta
import pytest


def _req(client, method: str, path: str, expected: tuple[int, ...] = (200,), json=None):
    res = client["session"].request(
        method,
        f'{client["base_url"]}{path}',
        timeout=client["timeout"],
        json=json,
    )
    assert res.status_code in expected, f"{method} {path} -> {res.status_code}: {res.text}"
    return res


def _req_with_token(
    client,
    token: str,
    method: str,
    path: str,
    expected: tuple[int, ...] = (200,),
    json=None,
):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    res = client["session"].request(
        method,
        f'{client["base_url"]}{path}',
        timeout=client["timeout"],
        json=json,
        headers=headers,
    )
    assert res.status_code in expected, f"{method} {path} -> {res.status_code}: {res.text}"
    return res


def _try_dev_login_token(client, phone: str) -> str | None:
    res = client["session"].request(
        "POST",
        f'{client["base_url"]}/auth/login',
        timeout=client["timeout"],
        json={"phone_e164": phone},
        headers={"Content-Type": "application/json"},
    )
    if res.status_code == 403:
        return None
    assert res.status_code == 200, f"POST /auth/login -> {res.status_code}: {res.text}"
    payload = res.json()
    return payload.get("access_token")


def _create_shipment(client, sender_phone: str, receiver_phone: str, run_id: str, suffix: str) -> dict:
    res = _req(
        client,
        "POST",
        "/shipments",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Flow Receiver {run_id}-{suffix}",
            "receiver_phone": receiver_phone,
        },
    )
    return res.json()


def _ensure_two_relays(client, run_id: str) -> tuple[str, str]:
    created_ids: list[str] = []
    session = client["session"]
    timeout = client["timeout"]
    base_url = client["base_url"]

    for idx in range(2):
        relay_code = f"PYR{run_id[:4]}{idx}".upper()[:30]
        payload = {
            "relay_code": relay_code,
            "name": f"Py Relay {run_id}-{idx}",
            "type": "relay",
            "opening_hours": "08:00-18:00",
            "storage_capacity": 50,
            "is_active": True,
        }
        res = session.request(
            "POST",
            f"{base_url}/relays",
            timeout=timeout,
            json=payload,
        )
        if res.status_code == 200:
            created_ids.append(res.json()["id"])
        elif res.status_code != 403:
            assert False, f"POST /relays -> {res.status_code}: {res.text}"

    if len(created_ids) >= 2:
        return created_ids[0], created_ids[1]

    relays = _req(client, "GET", "/relays/public", expected=(200,)).json()
    relay_ids = [row["id"] for row in relays if row.get("id")]
    relay_ids = list(dict.fromkeys(relay_ids))
    assert len(relay_ids) >= 2, "Need at least 2 relays (create rights or seeded relays)"
    return relay_ids[0], relay_ids[1]


def test_transport_trip_scan_and_ops_summary(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "transport")
    shipment_id = shipment["id"]

    trip = _req(
        client,
        "POST",
        "/transport/trips",
        expected=(200,),
        json={"status": "planned", "extra": {"source": "pytest_transport_flow"}},
    ).json()
    trip_id = trip["id"]
    assert trip["status"] == "planned"

    add_res = _req(
        client,
        "POST",
        f"/transport/trips/{trip_id}/manifest/shipments",
        expected=(200,),
        json={"shipment_id": shipment_id},
    ).json()
    assert add_res.get("manifest_shipment_id")

    departure = _req(
        client,
        "POST",
        f"/transport/trips/{trip_id}/scan/departure",
        expected=(200,),
        json={"event_type": "pytest_trip_departure"},
    ).json()
    assert departure["trip_id"] == trip_id
    assert departure["status"] == "in_progress"
    assert departure["updated_shipments"] >= 1

    arrival = _req(
        client,
        "POST",
        f"/transport/trips/{trip_id}/scan/arrival",
        expected=(200,),
        json={"event_type": "pytest_trip_arrival"},
    ).json()
    assert arrival["trip_id"] == trip_id
    assert arrival["status"] == "arrived"
    assert arrival["updated_shipments"] >= 1

    ops = _req(
        client,
        "GET",
        f"/transport/trips/{trip_id}/ops-summary",
        expected=(200,),
    ).json()
    assert ops["trip_id"] == trip_id
    assert ops["manifest_count"] >= 1
    assert "status_breakdown" in ops
    assert "blocked_shipment_ids" in ops
    assert isinstance(ops["load_ratio"], float)


def test_transport_scan_requires_manifest(client, run_id):
    trip = _req(
        client,
        "POST",
        "/transport/trips",
        expected=(200,),
        json={"status": "planned", "extra": {"source": f"pytest_scan_required_{run_id}"}},
    ).json()
    trip_id = trip["id"]

    blocked = _req(
        client,
        "POST",
        f"/transport/trips/{trip_id}/scan/departure",
        expected=(422,),
        json={"event_type": "pytest_scan_without_manifest"},
    ).json()
    assert "detail" in blocked


def test_pickup_code_validate_confirm_error_paths(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "pickup")
    shipment_id = shipment["id"]

    code_row = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup",
        expected=(200,),
        json={},
    ).json()
    code = code_row["code"]
    assert code

    replacement = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup",
        expected=(200,),
        json={},
    ).json()
    assert replacement["code"] != code

    expired_validate = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/validate",
        expected=(200,),
        json={"code": code},
    ).json()
    assert expired_validate["valid"] is False
    assert expired_validate["error_code"] == "code_expired"

    code = replacement["code"]

    invalid_validate = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/validate",
        expected=(200,),
        json={"code": "0000"},
    ).json()
    assert invalid_validate["valid"] is False
    assert invalid_validate["error_code"] in {"code_invalid", "code_missing", "code_expired"}

    valid_validate = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/validate",
        expected=(200,),
        json={"code": code},
    ).json()
    assert valid_validate["valid"] is True
    assert valid_validate["error_code"] is None

    invalid_confirm = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/confirm",
        expected=(200,),
        json={"code": "9999", "event_type": "pytest_pickup_confirm_invalid"},
    ).json()
    assert invalid_confirm["confirmed"] is False
    assert invalid_confirm["error_code"] in {"code_invalid", "code_missing", "code_expired"}

    valid_confirm = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/confirm",
        expected=(200,),
        json={"code": code, "event_type": "pytest_pickup_confirm_valid"},
    ).json()
    assert valid_confirm["confirmed"] is True
    assert valid_confirm["status"] == "delivered"
    assert valid_confirm["error_code"] is None

    replay_confirm = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/confirm",
        expected=(200,),
        json={"code": code, "event_type": "pytest_pickup_confirm_replay"},
    ).json()
    assert replay_confirm["confirmed"] is False
    assert replay_confirm["error_code"] in {"code_missing", "code_expired", "code_invalid"}


def test_pickup_mark_workflow_with_transition_guard(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "pickup-mark")
    shipment_id = shipment["id"]

    picked = _req(
        client,
        "POST",
        f"/shipments/{shipment_id}/pickup/mark",
        expected=(200,),
        json={"event_type": "pytest_pickup_mark"},
    ).json()
    assert picked["id"] == shipment_id
    assert picked["status"] == "picked_up"

    delivered = _req(
        client,
        "PATCH",
        f"/shipments/{shipment_id}/status",
        expected=(200,),
        json={"status": "delivered", "event_type": "pytest_force_delivered"},
    ).json()
    assert delivered["status"] == "delivered"

    guarded = _req(
        client,
        "POST",
        f"/shipments/{shipment_id}/pickup/mark",
        expected=(422,),
        json={"event_type": "pytest_pickup_mark_invalid_transition"},
    ).json()
    assert "detail" in guarded


def test_relay_transfer_workflow(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "relay-transfer")
    shipment_id = shipment["id"]
    relay_a, relay_b = _ensure_two_relays(client, run_id)

    seeded = _req(
        client,
        "PUT",
        f"/relays/{relay_a}/inventory",
        expected=(200,),
        json={"shipment_id": shipment_id, "present": True},
    ).json()
    assert seeded["present"] is True

    invalid_same = _req(
        client,
        "POST",
        f"/shipments/{shipment_id}/relay-transfer",
        expected=(422,),
        json={
            "from_relay_id": relay_a,
            "to_relay_id": relay_a,
            "event_type": "pytest_relay_transfer_invalid_same",
        },
    ).json()
    assert "detail" in invalid_same

    transferred = _req(
        client,
        "POST",
        f"/shipments/{shipment_id}/relay-transfer",
        expected=(200,),
        json={
            "from_relay_id": relay_a,
            "to_relay_id": relay_b,
            "event_type": "pytest_relay_transfer_ok",
        },
    ).json()
    assert transferred["status"] == "arrived_at_relay"

    replay = _req(
        client,
        "POST",
        f"/shipments/{shipment_id}/relay-transfer",
        expected=(422,),
        json={
            "from_relay_id": relay_a,
            "to_relay_id": relay_b,
            "event_type": "pytest_relay_transfer_replay",
        },
    ).json()
    assert "detail" in replay


def test_relay_transfer_incoherent_without_source_inventory(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "relay-transfer-incoherent")
    shipment_id = shipment["id"]
    relay_a, relay_b = _ensure_two_relays(client, run_id)

    incoherent = _req(
        client,
        "POST",
        f"/shipments/{shipment_id}/relay-transfer",
        expected=(422,),
        json={
            "from_relay_id": relay_a,
            "to_relay_id": relay_b,
            "event_type": "pytest_relay_transfer_no_source_inventory",
        },
    ).json()
    assert "detail" in incoherent


def test_relay_inventory_rejects_same_shipment_present_in_two_relays(
    client, sender_phone, receiver_phone, run_id
):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "relay-dup-present")
    shipment_id = shipment["id"]
    relay_a, relay_b = _ensure_two_relays(client, run_id)

    seeded = _req(
        client,
        "PUT",
        f"/relays/{relay_a}/inventory",
        expected=(200,),
        json={"shipment_id": shipment_id, "present": True},
    ).json()
    assert seeded["present"] is True

    conflict = _req(
        client,
        "PUT",
        f"/relays/{relay_b}/inventory",
        expected=(422,),
        json={"shipment_id": shipment_id, "present": True},
    ).json()
    assert "detail" in conflict

    relay_a_present = _req(
        client,
        "GET",
        f"/relays/{relay_a}/inventory?present_only=true",
        expected=(200,),
    ).json()
    assert any(row["shipment_id"] == shipment_id and row["present"] is True for row in relay_a_present)

    relay_b_present = _req(
        client,
        "GET",
        f"/relays/{relay_b}/inventory?present_only=true",
        expected=(200,),
    ).json()
    assert not any(row["shipment_id"] == shipment_id and row["present"] is True for row in relay_b_present)


def test_pickup_code_attempt_window_limit(client, sender_phone, receiver_phone, run_id):
    shipment = _create_shipment(client, sender_phone, receiver_phone, run_id, "pickup-window")
    shipment_id = shipment["id"]

    _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup",
        expected=(200,),
        json={},
    )

    for _ in range(5):
        invalid = _req(
            client,
            "POST",
            f"/codes/shipments/{shipment_id}/pickup/validate",
            expected=(200,),
            json={"code": "0000"},
        ).json()
        assert invalid["valid"] is False
        assert invalid["error_code"] in {"code_invalid", "code_missing", "code_expired"}

    limited = _req(
        client,
        "POST",
        f"/codes/shipments/{shipment_id}/pickup/validate",
        expected=(200,),
        json={"code": "0000"},
    ).json()
    assert limited["valid"] is False
    assert limited["error_code"] == "code_too_many_attempts"


def test_shipment_schedule_once_run_due(client, sender_phone, receiver_phone, run_id):
    start_at = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()

    schedule = _req(
        client,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Scheduled Receiver {run_id}",
            "receiver_phone": receiver_phone,
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
            "extra": {"source": "pytest_schedule_once"},
        },
    ).json()
    schedule_id = schedule["id"]
    assert schedule["is_active"] is True

    run_result = _req(
        client,
        "POST",
        "/shipments/schedules/run-due?limit=50",
        expected=(200,),
    ).json()
    assert run_result["examined"] >= 1
    matched = [row for row in run_result["items"] if row["schedule_id"] == schedule_id]
    assert matched
    assert matched[0]["success"] is True
    assert matched[0]["shipment_id"]

    after = _req(
        client,
        "GET",
        f"/shipments/schedules/{schedule_id}",
        expected=(200,),
    ).json()
    assert after["is_active"] is False
    assert after["next_run_at"] is None


def test_shipment_schedule_ownership_scope_for_customers(client, run_id):
    seed = int(run_id[:6], 16)
    phone_a = f"+2577{seed % 10_000_000:07d}"
    phone_b = f"+2577{(seed + 1) % 10_000_000:07d}"

    token_a = _try_dev_login_token(client, phone_a)
    token_b = _try_dev_login_token(client, phone_b)
    if not token_a or not token_b:
        pytest.skip("AUTH_ALLOW_DEV_LOGIN is disabled; cannot provision two customer tokens")

    start_at = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    created = _req_with_token(
        client,
        token_a,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": phone_a,
            "receiver_name": f"Ownership Receiver {run_id}",
            "receiver_phone": "+25762019002",
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
            "extra": {"source": "pytest_schedule_ownership"},
        },
    ).json()
    schedule_id = created["id"]
    assert created["sender_phone"] == phone_a

    visible_to_a = _req_with_token(
        client,
        token_a,
        "GET",
        "/shipments/schedules",
        expected=(200,),
    ).json()
    assert any(row["id"] == schedule_id for row in visible_to_a["items"])

    visible_to_b = _req_with_token(
        client,
        token_b,
        "GET",
        "/shipments/schedules",
        expected=(200,),
    ).json()
    assert not any(row["id"] == schedule_id for row in visible_to_b["items"])

    _req_with_token(
        client,
        token_b,
        "GET",
        f"/shipments/schedules/{schedule_id}",
        expected=(404,),
    )

    _req_with_token(
        client,
        token_b,
        "PATCH",
        f"/shipments/schedules/{schedule_id}",
        expected=(404,),
        json={"delivery_note": "forbidden cross-owner update"},
    )

    mismatch = _req_with_token(
        client,
        token_a,
        "POST",
        "/shipments/schedules",
        expected=(422,),
        json={
            "sender_phone": phone_b,
            "receiver_name": f"Ownership Receiver Mismatch {run_id}",
            "receiver_phone": "+25762019003",
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
        },
    ).json()
    assert "detail" in mismatch


def test_shipment_schedule_mine_filter(client, run_id):
    me = _req(client, "GET", "/auth/me", expected=(200,)).json()
    role = (me.get("user_type") or "").strip()
    my_phone = (me.get("phone_e164") or "").strip()
    if role not in {"customer", "business", "agent", "hub", "admin"}:
        pytest.skip("Current role cannot create shipment schedules")
    if not my_phone:
        pytest.skip("Current user has no phone_e164")

    start_at = (datetime.now(UTC) + timedelta(minutes=3)).isoformat()
    own = _req(
        client,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": my_phone,
            "receiver_name": f"Mine Filter Receiver {run_id}",
            "receiver_phone": "+25762019901",
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
            "extra": {"source": "pytest_schedule_mine_filter", "owner": "primary"},
        },
    ).json()
    own_schedule_id = own["id"]

    mine_rows = _req(
        client,
        "GET",
        "/shipments/schedules?mine=true",
        expected=(200,),
    ).json()
    assert any(row["id"] == own_schedule_id for row in mine_rows["items"])

    mine_active_rows = _req(
        client,
        "GET",
        "/shipments/schedules?mine=true&active_only=true",
        expected=(200,),
    ).json()
    assert any(row["id"] == own_schedule_id for row in mine_active_rows["items"])

    seed = int(run_id[:6], 16)
    other_phone = f"+2578{seed % 10_000_000:07d}"
    other_token = _try_dev_login_token(client, other_phone)
    if not other_token:
        return

    other = _req_with_token(
        client,
        other_token,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": other_phone,
            "receiver_name": f"Mine Filter Receiver Other {run_id}",
            "receiver_phone": "+25762019902",
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
            "extra": {"source": "pytest_schedule_mine_filter", "owner": "secondary"},
        },
    ).json()
    other_schedule_id = other["id"]

    mine_after_other = _req(
        client,
        "GET",
        "/shipments/schedules?mine=true",
        expected=(200,),
    ).json()
    assert any(row["id"] == own_schedule_id for row in mine_after_other["items"])
    assert not any(row["id"] == other_schedule_id for row in mine_after_other["items"])


def test_shipment_schedule_list_offset_limit(client, sender_phone, receiver_phone, run_id):
    start_at = (datetime.now(UTC) + timedelta(minutes=4)).isoformat()

    first = _req(
        client,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Page Receiver A {run_id}",
            "receiver_phone": receiver_phone,
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
            "extra": {"source": "pytest_schedule_pagination", "rank": "a"},
        },
    ).json()
    second = _req(
        client,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Page Receiver B {run_id}",
            "receiver_phone": receiver_phone,
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_at,
            "extra": {"source": "pytest_schedule_pagination", "rank": "b"},
        },
    ).json()

    first_page = _req(
        client,
        "GET",
        "/shipments/schedules?limit=1&offset=0",
        expected=(200,),
    ).json()
    second_page = _req(
        client,
        "GET",
        "/shipments/schedules?limit=1&offset=1",
        expected=(200,),
    ).json()

    assert isinstance(first_page, dict)
    assert isinstance(second_page, dict)
    assert first_page["limit"] == 1
    assert first_page["offset"] == 0
    assert second_page["limit"] == 1
    assert second_page["offset"] == 1
    assert first_page["total"] >= 2
    assert second_page["total"] >= 2
    assert isinstance(first_page["items"], list) and len(first_page["items"]) == 1
    assert isinstance(second_page["items"], list) and len(second_page["items"]) == 1
    assert first_page["items"][0]["id"] != second_page["items"][0]["id"]
    assert first_page["items"][0]["id"] in {first["id"], second["id"]}
    assert second_page["items"][0]["id"] in {first["id"], second["id"]}


def test_shipment_schedule_sort_next_run(client, sender_phone, receiver_phone, run_id):
    start_earlier = (datetime.now(UTC) + timedelta(minutes=6)).isoformat()
    start_later = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()

    earlier = _req(
        client,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Sort Receiver Early {run_id}",
            "receiver_phone": receiver_phone,
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_earlier,
            "extra": {"source": "pytest_schedule_sort", "rank": "early"},
        },
    ).json()
    later = _req(
        client,
        "POST",
        "/shipments/schedules",
        expected=(200,),
        json={
            "sender_phone": sender_phone,
            "receiver_name": f"Sort Receiver Late {run_id}",
            "receiver_phone": receiver_phone,
            "frequency": "once",
            "interval_count": 1,
            "start_at": start_later,
            "extra": {"source": "pytest_schedule_sort", "rank": "late"},
        },
    ).json()

    asc_page = _req(
        client,
        "GET",
        "/shipments/schedules?sort=next_run_asc&limit=2&offset=0",
        expected=(200,),
    ).json()
    desc_page = _req(
        client,
        "GET",
        "/shipments/schedules?sort=next_run_desc&limit=2&offset=0",
        expected=(200,),
    ).json()

    asc_items = asc_page.get("items") or []
    desc_items = desc_page.get("items") or []
    target_ids = {earlier["id"], later["id"]}

    asc_targets = [row for row in asc_items if row.get("id") in target_ids]
    desc_targets = [row for row in desc_items if row.get("id") in target_ids]
    assert len(asc_targets) == 2
    assert len(desc_targets) == 2

    assert asc_targets[0]["id"] == earlier["id"]
    assert asc_targets[1]["id"] == later["id"]
    assert desc_targets[0]["id"] == later["id"]
    assert desc_targets[1]["id"] == earlier["id"]
