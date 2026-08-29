"""Coarse PM2.5 climatology for Indian regions.

AirEcho models locations anywhere in India — from the Indo-Gangetic Plain to
Himalayan valleys, the north-east hills and the Andaman & Lakshadweep islands.
Pollution seasonality differs enormously between them, so the synthetic feed is
region-aware rather than assuming a single Delhi-style winter smog curve.

`region` is a short key carried in a synthetic station's `external_id`
(`syn-<region>-<n>`). Real ingested stations (OpenAQ etc.) fall back to a mild
default.
"""

from __future__ import annotations

# Approximate annual-mean PM2.5 (µg/m³) by region family.
REGION_ANNUAL_PM25: dict[str, float] = {
    "igp": 115.0,  # Indo-Gangetic Plain: Delhi, Kanpur, Lucknow, Patna, Ghaziabad
    "east": 68.0,  # Kolkata / lower Gangetic
    "west": 52.0,  # Mumbai, Ahmedabad, Jaipur, Pune
    "south": 36.0,  # Bengaluru, Chennai, Hyderabad
    "central": 58.0,  # Nagpur, Bhopal, Raipur
    "northeast": 30.0,  # Guwahati plains + hill capitals
    "himalaya": 17.0,  # Leh, Gangtok, Shimla, Spiti — very clean, wood-heat winter
    "coastal": 20.0,  # Port Blair, Kavaratti, Panaji, Vizag — flat, sea-washed
}
_DEFAULT_REGION = "west"

# Monthly multipliers on the annual mean. IGP has a severe Nov–Jan spike;
# coastal/southern regions are almost flat; hill regions bump in winter from
# domestic wood/biomass heating rather than traffic+stubble.
_WINTER_SEVERE = {
    1: 1.95, 2: 1.30, 3: 0.95, 4: 0.85, 5: 0.80, 6: 0.68,
    7: 0.48, 8: 0.44, 9: 0.62, 10: 1.15, 11: 2.15, 12: 1.98,
}  # fmt: skip
_WINTER_MILD = {
    1: 1.35, 2: 1.15, 3: 1.00, 4: 0.95, 5: 0.92, 6: 0.85,
    7: 0.70, 8: 0.70, 9: 0.82, 10: 1.05, 11: 1.28, 12: 1.34,
}  # fmt: skip
_FLAT = {
    1: 1.12, 2: 1.05, 3: 1.00, 4: 1.00, 5: 1.02, 6: 0.92,
    7: 0.85, 8: 0.85, 9: 0.90, 10: 1.00, 11: 1.08, 12: 1.14,
}  # fmt: skip
_HILL_WINTER = {
    1: 1.45, 2: 1.22, 3: 1.00, 4: 0.85, 5: 0.75, 6: 0.68,
    7: 0.62, 8: 0.62, 9: 0.78, 10: 1.00, 11: 1.28, 12: 1.46,
}  # fmt: skip

_REGION_MONTHLY: dict[str, dict[int, float]] = {
    "igp": _WINTER_SEVERE,
    "east": _WINTER_MILD,
    "west": _WINTER_MILD,
    "central": _WINTER_MILD,
    "south": _FLAT,
    "coastal": _FLAT,
    "northeast": _HILL_WINTER,
    "himalaya": _HILL_WINTER,
}

# Regions where paddy-stubble smoke is a real autumn contributor.
STUBBLE_REGIONS = {"igp"}
# Regions covered by the Delhi-NCR Graded Response Action Plan.
GRAP_REGIONS = {"igp"}


def region_for_external_id(external_id: str | None) -> str:
    """`syn-igp-3` → `igp`; anything unrecognised → the mild default."""
    parts = (external_id or "").split("-")
    if len(parts) >= 3 and parts[0] == "syn" and parts[1] in REGION_ANNUAL_PM25:
        return parts[1]
    return _DEFAULT_REGION


def region_pm25_mean(region: str, month: int) -> float:
    base = REGION_ANNUAL_PM25.get(region, REGION_ANNUAL_PM25[_DEFAULT_REGION])
    monthly = _REGION_MONTHLY.get(region, _WINTER_MILD)
    return base * monthly[month]
