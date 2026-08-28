from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep, get_owned_or_404, scoped
from app.models import UserLocation
from app.schemas import LocationIn, LocationOut
from app.services.geo import resolve_nearest_station

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationOut])
def list_locations(user: CurrentUser, db: DbDep):
    return db.execute(scoped(db, UserLocation, user.id)).scalars().all()


@router.post("", response_model=LocationOut, status_code=201)
def create_location(body: LocationIn, user: CurrentUser, db: DbDep):
    loc = UserLocation(user_id=user.id, label=body.label, lat=body.lat, lng=body.lng)
    db.add(loc)
    db.flush()
    station_id, distance = resolve_nearest_station(db, loc)
    loc.nearest_station_id = station_id
    loc.distance_km = distance
    loc.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(loc)
    return loc


@router.post("/{location_id}/resolve", response_model=LocationOut)
def reresolve(location_id: int, user: CurrentUser, db: DbDep):
    """Re-run nearest-station resolution (e.g. a closer station came online)."""
    loc = get_owned_or_404(db, UserLocation, user.id, location_id)
    station_id, distance = resolve_nearest_station(db, loc)
    loc.nearest_station_id = station_id
    loc.distance_km = distance
    loc.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=204)
def delete_location(location_id: int, user: CurrentUser, db: DbDep):
    loc = get_owned_or_404(db, UserLocation, user.id, location_id)
    db.delete(loc)
    db.commit()
