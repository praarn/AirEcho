"""Per-user data isolation — enforced at the query layer, not trusted from
params. User A must never reach User B's data via ANY endpoint.
"""

from __future__ import annotations


def _hdr(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_user_cannot_read_or_mutate_another_users_location(client, user_a, user_b):
    loc = client.post(
        "/locations", json={"label": "home", "lat": 28.6, "lng": 77.2}, headers=_hdr(user_a)
    ).json()
    lid = loc["id"]

    # B does not see A's location in the list
    b_list = client.get("/locations", headers=_hdr(user_b)).json()
    assert all(x["id"] != lid for x in b_list)

    # B cannot re-resolve, delete, or query windows for A's location
    assert client.post(f"/locations/{lid}/resolve", headers=_hdr(user_b)).status_code == 404
    assert client.delete(f"/locations/{lid}", headers=_hdr(user_b)).status_code == 404
    assert (
        client.get(f"/exposure/windows?location_id={lid}", headers=_hdr(user_b)).status_code == 404
    )

    # A still can
    assert client.post(f"/locations/{lid}/resolve", headers=_hdr(user_a)).status_code == 200


def test_user_cannot_touch_another_users_symptom_log(client, user_a, user_b):
    sym = client.post(
        "/symptoms", json={"severity": 5, "notes": "mine"}, headers=_hdr(user_a)
    ).json()
    sid = sym["id"]

    assert all(x["id"] != sid for x in client.get("/symptoms", headers=_hdr(user_b)).json())
    assert (
        client.post(
            f"/symptoms/{sid}/confirm-peak-flow",
            json={"peak_flow_value": 400},
            headers=_hdr(user_b),
        ).status_code
        == 404
    )
    assert client.delete(f"/symptoms/{sid}", headers=_hdr(user_b)).status_code == 404


def test_export_only_returns_callers_own_data(client, user_a, user_b):
    client.post("/symptoms", json={"severity": 7, "notes": "A-only"}, headers=_hdr(user_a))
    client.post("/symptoms", json={"severity": 2, "notes": "B-only"}, headers=_hdr(user_b))

    dump_b = client.get("/privacy/export", headers=_hdr(user_b)).json()
    notes = {s["notes"] for s in dump_b["symptom_logs"]}
    assert notes == {"B-only"}
    assert dump_b["user"]["email"] == "user-b@example.com"


def test_delete_is_scoped_and_leaves_other_user_intact(client, user_a, user_b):
    client.post("/symptoms", json={"severity": 7}, headers=_hdr(user_a))
    client.post("/symptoms", json={"severity": 3}, headers=_hdr(user_b))

    r = client.request("DELETE", "/privacy/delete", headers=_hdr(user_a))
    assert r.status_code == 200

    # A's token is now dead; B is untouched
    assert client.get("/symptoms", headers=_hdr(user_a)).status_code == 401
    assert len(client.get("/symptoms", headers=_hdr(user_b)).json()) == 1
