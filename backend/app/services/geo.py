"""Nearest-station resolution. The distance is always stored and surfaced — we
never silently assume a station is 'close enough'."""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Station, UserLocation


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def resolve_nearest_station(db: Session, loc: UserLocation) -> tuple[int | None, float | None]:
    stations = db.execute(select(Station)).scalars().all()
    if not stations:
        return None, None
    best: Station | None = None
    best_km = math.inf
    for s in stations:
        d = haversine_km(loc.lat, loc.lng, s.lat, s.lng)
        if d < best_km:
            best, best_km = s, d
    return (best.id if best else None), (round(best_km, 3) if best else None)
