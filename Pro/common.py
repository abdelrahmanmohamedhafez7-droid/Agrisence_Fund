from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List
import json
import os
import math

OK = "suitable_per_available"
ADJUST = "needs_adjustment"
INSUFFICIENT = "insufficient_data"

# Units are written with unicode escapes so a copy/paste can never change them.
TEMP_UNIT = "°C"                      # degree Celsius
RH_UNIT = "%RH"
PPM_UNIT = "ppm"
PPFD_UNIT = "µmol/m²/s"          # micro sign (U+00B5)
PPFD_UNITS = (
    PPFD_UNIT,
    "μmol/m²/s",                 # Greek mu variant (U+03BC)
    "umol/m2/s",
)

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(name):
    path = os.path.join(_HERE, name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Reading:
    value: Optional[float]
    unit: str
    method: Optional[str] = None
    timestamp: Optional[datetime] = None
    quality: str = "ok"
    source: str = "sensor"   # recorded / simulation / sensor


@dataclass
class Result:
    rule: str
    status: str
    reasons: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    data_sources: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# 1 mS/cm == 1 dS/m. Conversion only changes the unit; the analysis method
# (saturated paste, 1:2 extract, solution ...) is checked separately.
_EC = {
    "mS/cm": 1.0,
    "dS/m": 1.0,
    "µS/cm": 0.001,   # micro sign
    "μS/cm": 0.001,   # Greek mu
    "uS/cm": 0.001,
}

_VWC = {
    "%VWC": 1.0,
    "m3/m3": 100.0,
}

EC_UNITS = tuple(_EC)
VWC_UNITS = tuple(_VWC)


def to_ec_ms_cm(v: float, unit: str):
    if unit not in _EC:
        raise ValueError(f"Unknown EC unit: {unit}")
    return v * _EC[unit]


def to_vwc_pct(v: float, unit: str):
    if unit not in _VWC:
        raise ValueError(f"Unknown moisture unit: {unit}")
    return v * _VWC[unit]


def check_reading(
    r: Optional[Reading],
    *,
    now=None,
    max_age_s=None,
    units=None,
    methods=None,
    lo=None,
    hi=None,
):
    if r is None or r.value is None:
        return False, "reading is missing"

    if isinstance(r.value, bool):
        return False, "reading value is not numeric"

    try:
        value = float(r.value)
    except (TypeError, ValueError):
        return False, "reading value is not numeric"

    if not math.isfinite(value):
        return False, "reading value is not finite"

    if r.quality != "ok":
        return False, f"reading quality is {r.quality}"

    if units and r.unit not in units:
        return False, f"unit not accepted: {r.unit}"

    if methods is not None and r.method not in methods:
        return False, (
            f"measurement method '{r.method}' is not compatible "
            "with the reference threshold"
        )

    if max_age_s is not None:
        if r.timestamp is None:
            return False, "reading has no timestamp"

        if r.timestamp.tzinfo is None or r.timestamp.utcoffset() is None:
            return False, "reading timestamp must include a timezone"

        now = now or datetime.now(timezone.utc)

        if now.tzinfo is None or now.utcoffset() is None:
            return False, "current time must include a timezone"

        age = (now - r.timestamp).total_seconds()

        if age < 0:
            return False, "reading timestamp is in the future"

        if age > max_age_s:
            return False, "reading is stale"

    if lo is not None and value < lo:
        return False, "implausible value outside physical range"

    if hi is not None and value > hi:
        return False, "implausible value outside physical range"

    return True, ""


def sources_of(*readings):
    """Distinct data sources (recorded / simulation / sensor) of the readings used."""
    return sorted(
        {
            r.source
            for r in readings
            if r is not None and getattr(r, "source", None)
        }
    )


def provisional_caveat(res, prof, what="thresholds"):
    """Flag provisional (verified=false) profiles in the result."""
    if prof is not None and not prof.get("verified"):
        res.details["caveat"] = (
            f"Provisional {what}, not yet matched against the reference"
        )
