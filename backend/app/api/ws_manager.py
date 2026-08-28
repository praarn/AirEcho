"""WebSocket connection registry + alert evaluation.

The WebSocket is a *push channel on top of a REST source of truth*. On reconnect
the client is expected to GET the current state via REST first, then resume the
socket — the server never assumes the socket carried all state.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import desc, select
from starlette.websockets import WebSocket

from app.database import SessionLocal
from app.ml.predict import WHO_PM25_24H, predict_for_user
from app.models import AqiReading, Station, UserLocation


class ConnectionManager:
    def __init__(self) -> None:
        self._user_conns: dict[int, set[WebSocket]] = defaultdict(set)
        self._admin_conns: set[WebSocket] = set()
        self._last_risk: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def connect_user(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._user_conns[user_id].add(ws)

    async def connect_admin(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._admin_conns.add(ws)

    async def disconnect(self, ws: WebSocket, user_id: int | None = None) -> None:
        async with self._lock:
            self._admin_conns.discard(ws)
            if user_id is not None:
                self._user_conns[user_id].discard(ws)
            else:
                for conns in self._user_conns.values():
                    conns.discard(ws)

    async def push_to_user(self, user_id: int, payload: dict) -> None:
        for ws in list(self._user_conns.get(user_id, ())):
            with contextlib.suppress(Exception):
                await ws.send_json(payload)

    async def broadcast_admin(self, payload: dict) -> None:
        for ws in list(self._admin_conns):
            with contextlib.suppress(Exception):
                await ws.send_json(payload)

    def connected_user_ids(self) -> list[int]:
        return [uid for uid, conns in self._user_conns.items() if conns]


manager = ConnectionManager()


async def evaluate_and_push_alerts() -> dict:
    """Called after each ingestion tick. Pushes:
      * threshold-crossing alerts (latest PM2.5 at the user's station > WHO 24h)
      * meaningful risk-score updates (Δ >= 0.5 since last push)
    Only to users with a live socket.
    """
    sent = {"threshold": 0, "risk": 0}
    db = SessionLocal()
    try:
        for user_id in manager.connected_user_ids():
            loc = (
                db.execute(select(UserLocation).where(UserLocation.user_id == user_id))
                .scalars()
                .first()
            )
            if loc and loc.nearest_station_id:
                latest = (
                    db.execute(
                        select(AqiReading)
                        .where(
                            AqiReading.station_id == loc.nearest_station_id,
                            AqiReading.pollutant == "pm25",
                        )
                        .order_by(desc(AqiReading.recorded_at))
                        .limit(1)
                    )
                    .scalars()
                    .first()
                )
                if latest and latest.value > WHO_PM25_24H:
                    station = db.get(Station, loc.nearest_station_id)
                    await manager.push_to_user(
                        user_id,
                        {
                            "type": "threshold_alert",
                            "pollutant": "pm25",
                            "value": round(latest.value, 1),
                            "who_guideline": WHO_PM25_24H,
                            "station": station.location_name if station else None,
                            "recorded_at": latest.recorded_at.isoformat(),
                            "at": datetime.now(UTC).isoformat(),
                        },
                    )
                    sent["threshold"] += 1

            risk = predict_for_user(db, user_id, persist=False)
            prev = manager._last_risk.get(user_id)
            if prev is None or abs(risk["risk_score"] - prev) >= 0.5:
                manager._last_risk[user_id] = risk["risk_score"]
                await manager.push_to_user(
                    user_id,
                    {
                        "type": "risk_update",
                        "risk_score": risk["risk_score"],
                        "is_personalized": risk["is_personalized"],
                        "model_type": risk["model_type"],
                        "at": datetime.now(UTC).isoformat(),
                    },
                )
                sent["risk"] += 1
    finally:
        db.close()
    return sent
