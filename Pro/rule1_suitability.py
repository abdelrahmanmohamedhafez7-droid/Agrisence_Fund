from common import *

REFS = {
    "cucumber": {
        "open_field": "CV123 / Ch.7 (crop context only: no pH/EC limits)",
        "greenhouse": "CV268",
    },
    "tomato": {
        "open_field": "CV137 / Ch.18 (crop context only: no pH/EC limits)",
        "greenhouse": "CV266",
    },
}
# Where the numeric limits come from (added to every result)
LIMIT_REFS = {
    "open_field": ["CV296 (pH limits)", "FAO 29 (EC limit, ECe saturated paste)"],
    "greenhouse": ["CV265 (nutrition/medium)", "FAO 29 (EC limit, mineral soil only)"],
}


def _profile(crop, setting):
    return load_json("profiles.json")["crops"].get(crop, {}).get(setting)


def ec_applies(prof, medium):
    """The EC limit is valid only for the media listed in ec['media']."""
    media = prof["ec"].get("media")
    return medium is None or not media or medium in media


def medium_in_profile(prof, medium):
    """True when no medium was given, or the profile covers it."""
    media = prof.get("allowed_media")
    return medium is None or not media or medium in media


def assess_crop(
    crop,
    setting,
    ph: Reading,
    ec: Reading,
    now=None,
    max_age_s=3600,
    stage=None,
    medium=None,
    weather=None,
):
    res = Result(
        rule="1_suitability",
        status=OK,
        references=[REFS.get(crop, {}).get(setting, "?")]
        + LIMIT_REFS.get(setting, []),
        data_sources=sources_of(ph, ec),
    )

    prof = _profile(crop, setting)

    if prof is None:
        res.status = INSUFFICIENT
        res.reasons.append(
            f"No requirements profile for crop/setting: {crop}/{setting}"
        )
        return res

    provisional_caveat(res, prof)

    res.details["stage"] = stage
    res.details["medium"] = medium

    if weather is not None:
        # Context only: weather does not change the pH/EC thresholds.
        res.details["weather_context"] = weather

    if medium is not None and not medium_in_profile(prof, medium):
        res.status = INSUFFICIENT
        res.missing = ["medium_profile"]
        res.reasons.append(
            f"Medium '{medium}' is not covered by the {crop}/{setting} profile"
        )
        return res

    if medium is None:
        res.details["medium_note"] = (
            "Medium not given; the profile's default medium assumption applies"
        )

    out, missing = [], []

    p = prof["ph"]
    ok, why = check_reading(
        ph,
        now=now,
        max_age_s=max_age_s,
        units=["pH"],
        methods=p["methods"],
        lo=0,
        hi=14,
    )

    if not ok:
        missing.append("ph")
        res.reasons.append(f"pH: {why}")
    elif ph.value < p["min"]:
        out.append("ph")
        res.reasons.append(f"pH {ph.value} is below {p['min']}")
    elif ph.value > p["max"]:
        out.append("ph")
        res.reasons.append(f"pH {ph.value} is above {p['max']}")
    else:
        res.reasons.append(f"pH {ph.value} is within {p['min']}-{p['max']}")

    e = prof["ec"]
    ec_ok_medium = ec_applies(prof, medium)
    ok, why = check_reading(
        ec,
        now=now,
        max_age_s=max_age_s,
        units=EC_UNITS,
        methods=e["methods"],
        lo=0,
    )
    if ok and not ec_ok_medium:
        ok = False
        why = (f"no EC limit for medium '{medium}' (soilless/solution EC "
               "needs its own source)")

    ec_v = None
    if ok:
        try:
            ec_v = to_ec_ms_cm(ec.value, ec.unit)
        except (ValueError, TypeError) as ex:
            ok, why = False, str(ex)

    if not ok:
        missing.append("ec")
        res.reasons.append(f"EC: {why}")
    elif ec_v > e["max"]:
        out.append("ec")
        res.reasons.append(f"EC {ec_v:.2f} mS/cm is above {e['max']}")
    else:
        res.reasons.append(
            f"EC {ec_v:.2f} mS/cm is within the limit of {e['max']}"
        )

    res.missing = missing
    res.details["ec_limit_source"] = e.get("source")
    if e.get("source") is None:
        res.reasons.append(
            "EC limit has no source in the provided references (provisional)"
        )
    res.details["out_of_range"] = out

    if out:
        res.status = ADJUST
        if missing:
            # a violation plus a missing essential variable stays conditional
            res.details["conditional"] = True
    elif missing:
        res.status = INSUFFICIENT

    res.details["handoff"] = {
        "rule2": {
            "ph_ok": "ph" not in out and "ph" not in missing,
            "ec_ok": "ec" not in out and "ec" not in missing,
        },
        "rule3": setting == "greenhouse",
    }

    return res


def assess_both(setting, ph, ec, **kw):
    return {
        c: assess_crop(c, setting, ph, ec, **kw)
        for c in ("cucumber", "tomato")
    }
