"""API tests against a real PostgreSQL instance.

Covers the two things a reviewer will click first — listing with pagination and
updating a status — plus the failure modes that matter: illegal transitions,
guard rejections and concurrent edits.
"""

from __future__ import annotations

import pytest

API = "/api/v1"


async def _get_shipment(client, reference: str) -> dict:
    response = await client.get(f"{API}/shipments", params={"search": reference})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items, f"{reference} not found"
    return items[0]


# --------------------------------------------------------------------- list


async def test_list_is_paginated_and_never_returns_everything(client, seeded):
    response = await client.get(f"{API}/shipments", params={"page": 1, "page_size": 2})
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"] == {
        "page": 1,
        "page_size": 2,
        "total_items": 5,
        "total_pages": 3,
        "has_previous": False,
        "has_next": True,
    }

    last = await client.get(f"{API}/shipments", params={"page": 3, "page_size": 2})
    last_meta = last.json()["meta"]
    assert last_meta["has_next"] is False and last_meta["has_previous"] is True
    assert len(last.json()["items"]) == 1


async def test_pages_do_not_overlap_or_skip_rows(client, seeded):
    seen: list[str] = []
    for page in (1, 2, 3):
        response = await client.get(f"{API}/shipments", params={"page": page, "page_size": 2})
        seen.extend(item["reference"] for item in response.json()["items"])
    assert seen == sorted(seen)
    assert len(set(seen)) == 5


async def test_page_size_is_capped_server_side(client, seeded):
    response = await client.get(f"{API}/shipments", params={"page_size": 10_000})
    assert response.status_code == 422  # rejected by the Query(le=max_page_size) bound


async def test_filter_by_status_including_multiple_values(client, seeded):
    single = await client.get(f"{API}/shipments", params={"status": "in_transit"})
    assert [item["reference"] for item in single.json()["items"]] == ["TV-9003"]

    multiple = await client.get(
        f"{API}/shipments", params=[("status", "created"), ("status", "delivered")]
    )
    assert multiple.json()["meta"]["total_items"] == 2


async def test_unknown_status_filter_is_a_clear_error(client, seeded):
    response = await client.get(f"{API}/shipments", params={"status": "teleported"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_state"


async def test_search_matches_reference_or_customer(client, seeded):
    by_customer = await client.get(f"{API}/shipments", params={"search": "eastlink"})
    assert [item["reference"] for item in by_customer.json()["items"]] == ["TV-9002"]


async def test_list_rows_carry_their_legal_next_steps(client, seeded):
    created = await _get_shipment(client, "TV-9001")
    assert {t["target"] for t in created["allowed_transitions"]} == {"picked_up", "failed"}
    assert created["is_terminal"] is False

    delivered = await _get_shipment(client, "TV-9004")
    assert delivered["allowed_transitions"] == []
    assert delivered["is_terminal"] is True


async def test_summary_counts_every_configured_status(client, seeded):
    body = (await client.get(f"{API}/shipments/summary")).json()
    assert body["total"] == 5
    assert {row["status"]: row["count"] for row in body["by_status"]} == {
        "created": 1,
        "picked_up": 1,
        "in_transit": 1,
        "delivered": 1,
        "failed": 1,
    }


# ------------------------------------------------------------------- update


async def test_valid_transition_updates_status_and_writes_history(client, seeded):
    shipment = await _get_shipment(client, "TV-9001")

    response = await client.post(
        f"{API}/shipments/{shipment['id']}/status",
        json={"status": "picked_up", "actor": "driver-7"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["shipment"]["status"] == "picked_up"
    assert body["shipment"]["version"] == shipment["version"] + 1
    assert body["event"]["source_status"] == "created"
    assert body["event"]["event"] == "pick_up"
    assert body["event"]["actor"] == "driver-7"

    # The change is durable, not just echoed back.
    assert (await _get_shipment(client, "TV-9001"))["status"] == "picked_up"


async def test_invalid_transition_is_rejected_with_409_and_guidance(client, seeded):
    shipment = await _get_shipment(client, "TV-9001")

    response = await client.post(
        f"{API}/shipments/{shipment['id']}/status", json={"status": "delivered"}
    )
    assert response.status_code == 409

    error = response.json()["error"]
    assert error["code"] == "invalid_transition"
    assert "created" in error["message"] and "delivered" in error["message"]
    assert set(error["details"]["allowed_targets"]) == {"picked_up", "failed"}

    # And nothing was written.
    assert (await _get_shipment(client, "TV-9001"))["status"] == "created"
    history = await client.get(f"{API}/shipments/{shipment['id']}/events")
    assert history.json()["meta"]["total_items"] == 1


async def test_terminal_shipments_cannot_be_moved(client, seeded):
    delivered = await _get_shipment(client, "TV-9004")
    response = await client.post(
        f"{API}/shipments/{delivered['id']}/status",
        json={"status": "failed", "reason": "too late"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["terminal"] is True


async def test_failing_requires_a_reason(client, seeded):
    shipment = await _get_shipment(client, "TV-9003")

    without = await client.post(
        f"{API}/shipments/{shipment['id']}/status", json={"status": "failed"}
    )
    assert without.status_code == 422
    assert without.json()["error"]["code"] == "transition_guard_rejected"

    with_reason = await client.post(
        f"{API}/shipments/{shipment['id']}/status",
        json={"status": "failed", "reason": "Recipient refused delivery"},
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["event"]["reason"] == "Recipient refused delivery"


async def test_unknown_target_status_is_422(client, seeded):
    shipment = await _get_shipment(client, "TV-9001")
    response = await client.post(
        f"{API}/shipments/{shipment['id']}/status", json={"status": "warp_speed"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_state"


async def test_stale_version_is_rejected_instead_of_overwriting(client, seeded):
    shipment = await _get_shipment(client, "TV-9001")
    stale_version = shipment["version"]

    first = await client.post(
        f"{API}/shipments/{shipment['id']}/status",
        json={"status": "picked_up", "expected_version": stale_version},
    )
    assert first.status_code == 200

    second = await client.post(
        f"{API}/shipments/{shipment['id']}/status",
        json={"status": "in_transit", "expected_version": stale_version},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "concurrent_update"


async def test_missing_shipment_is_404(client, seeded):
    response = await client.post(
        f"{API}/shipments/00000000-0000-0000-0000-000000000000/status",
        json={"status": "picked_up"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shipment_not_found"


# ------------------------------------------------------------------ history


async def test_history_is_paginated_and_newest_first(client, seeded):
    shipment = await _get_shipment(client, "TV-9001")
    for target, reason in (("picked_up", None), ("in_transit", None), ("failed", "Van broke down")):
        response = await client.post(
            f"{API}/shipments/{shipment['id']}/status",
            json={"status": target, "reason": reason},
        )
        assert response.status_code == 200

    page = await client.get(
        f"{API}/shipments/{shipment['id']}/events", params={"page_size": 2}
    )
    body = page.json()
    assert body["meta"]["total_items"] == 4  # 1 import + 3 transitions
    assert [event["target_status"] for event in body["items"]] == ["failed", "in_transit"]

    second = await client.get(
        f"{API}/shipments/{shipment['id']}/events", params={"page": 2, "page_size": 2}
    )
    assert [event["target_status"] for event in second.json()["items"]] == [
        "picked_up",
        "created",
    ]


# ----------------------------------------------------------------- lifecycle


async def test_lifecycle_endpoint_describes_the_graph(client):
    body = (await client.get(f"{API}/lifecycle")).json()
    assert body["initial_state"] == "created"
    assert len(body["transitions"]) == 6
    failed = next(state for state in body["states"] if state["code"] == "failed")
    assert failed["terminal"] is True


@pytest.mark.parametrize("path", ["/health", "/ready"])
async def test_probes(client, path):
    assert (await client.get(f"{API}{path}")).status_code == 200
