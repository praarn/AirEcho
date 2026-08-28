"""WebSocket live-alerts tests: connect, threshold-triggered push, and the
reconnect-then-REST contract.
"""

from __future__ import annotations

from datetime import UTC, datetime


def _seed_station_and_location(user_email: str) -> None:
    from app.database import SessionLocal
    from app.models import AqiReading, Station, User, UserLocation

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).one()
        st = Station(
            source="synthetic",
            external_id="ws",
            location_name="WS Station",
            lat=1.0,
            lng=1.0,
            nominal_cadence_minutes=60,
        )
        db.add(st)
        db.flush()
        db.add(
            UserLocation(
                user_id=user.id,
                label="home",
                lat=1.0,
                lng=1.0,
                nearest_station_id=st.id,
                distance_km=0.1,
            )
        )
        db.add(
            AqiReading(
                station_id=st.id, pollutant="pm25", value=140.0, recorded_at=datetime.now(UTC)
            )
        )
        db.commit()
    finally:
        db.close()


def test_connect_receives_hello(client, auth):
    with client.websocket_connect(f"/ws/alerts?token={auth['access_token']}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"


def test_bad_token_rejected(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/alerts?token=garbage") as ws:
            ws.receive_json()


def test_threshold_crossing_pushes_alert(client, auth):
    _seed_station_and_location("a@example.com")
    with client.websocket_connect(f"/ws/alerts?token={auth['access_token']}") as ws:
        assert ws.receive_json()["type"] == "connected"

        # trigger an ingestion/eval tick over REST
        r = client.post("/ingestion/run")
        assert r.status_code == 200

        seen = set()
        for _ in range(4):
            msg = ws.receive_json()
            seen.add(msg["type"])
            if msg["type"] == "threshold_alert":
                assert msg["pollutant"] == "pm25"
                assert msg["value"] > msg["who_guideline"]
            if {"threshold_alert", "risk_update"} & seen:
                break
        assert {"threshold_alert", "risk_update"} & seen


def test_reconnect_then_rest_then_resume(client, auth):
    _seed_station_and_location("a@example.com")
    token = auth["access_token"]

    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        ws.receive_json()
    # socket dropped — client falls back to REST for current state
    state = client.get("/risk/score")
    assert state.status_code == 200
    assert 0 <= state.json()["risk_score"] <= 10
    # ...then resumes the socket
    with client.websocket_connect(f"/ws/alerts?token={token}") as ws2:
        assert ws2.receive_json()["type"] == "connected"
        ws2.send_text("ping")
        assert ws2.receive_json()["type"] == "pong"
