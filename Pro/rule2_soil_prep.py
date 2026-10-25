from common import *
from rule1_suitability import _profile, medium_in_profile, ec_applies

NPK_BRANCH_ENABLED = False

TRUSTED_NUTRIENT_METHODS = {
    "lab_soil_test",
    "lab_solution_analysis",
}


def soil_prep(
    crop,
    setting,
    stage,
    medium,
    ph: Reading,
    ec: Reading,
    nutrients: dict = None,
    symptoms: list = None,
    now=None,
):
    res = Result(
        rule="2_soil_prep",
        status=OK,
        references=[
            "CV296 (open field)"
            if setting == "open_field"
            else "CV265 (greenhouse)"
        ],
        data_sources=sources_of(ph, ec, *(nutrients or {}).values()),
    )

    prof = _profile(crop, setting)

    if prof is None or not stage or not medium:
        res.status = INSUFFICIENT
        res.missing = [
            k
            for k, v in (
                ("profile", prof),
                ("stage", stage),
                ("medium", medium),
            )
            if not v
        ]
        res.reasons.append("Essential inputs missing (crop / stage / medium)")
        return res

    provisional_caveat(res, prof)
    res.details["stage"] = stage
    res.details["medium"] = medium
    res.details["stage_note"] = (
        "Current pH/EC limits are not stage-specific; the stage is recorded "
        "for the report and for future stage-specific limits"
    )

    if not medium_in_profile(prof, medium):
        res.status = INSUFFICIENT
        res.missing = ["medium_profile"]
        res.reasons.append(
            f"Medium '{medium}' is not covered by the {crop}/{setting} profile"
        )
        return res

    notes = []
    needs_adjust = False

    p = prof["ph"]
    e = prof["ec"]

    ok, why = check_reading(
        ph,
        now=now,
        max_age_s=3600,
        units=["pH"],
        methods=p["methods"],
        lo=0,
        hi=14,
    )

    if ok:
        if ph.value < p["min"]:
            needs_adjust = True
            notes.append(
                "pH is low (acidic): review the analysis and consider "
                "raising pH per the reference and medium. Manual adjustment only."
            )
        elif ph.value > p["max"]:
            needs_adjust = True
            notes.append(
                "pH is high: review the irrigation water source and the medium, "
                "and the methods to lower alkalinity per the reference. "
                "Manual adjustment only."
            )
        else:
            notes.append(f"pH {ph.value} is within {p['min']}-{p['max']}")
    else:
        res.missing.append("ph")
        notes.append(f"pH is not valid: {why}")

    ok, why = check_reading(
        ec,
        now=now,
        max_age_s=3600,
        units=EC_UNITS,
        methods=e["methods"],
        lo=0,
    )
    if ok and not ec_applies(prof, medium):
        ok = False
        why = (f"no EC limit for medium '{medium}' (soilless/solution EC "
               "needs its own source)")

    ec_value = None

    if ok:
        try:
            ec_value = to_ec_ms_cm(ec.value, ec.unit)
        except (ValueError, TypeError):
            ok = False
            why = f"Unsupported or invalid EC unit: {ec.unit}"

    if ok:
        if ec_value > e["max"]:
            needs_adjust = True
            notes.append(
                "Salinity is high: review irrigation water quality and "
                "leaching of the medium. Direct soil EC is not a substitute "
                "for nutrient solution EC."
            )
        else:
            notes.append(f"EC {ec_value:.2f} mS/cm is within the limit of {e['max']}")
    else:
        res.missing.append("ec")
        notes.append(f"EC is not valid: {why}")

    res.details["ec_limit_source"] = e.get("source")
    if e.get("source") is None:
        notes.append(
            "EC limit has no source in the provided references (provisional)"
        )

    if not NPK_BRANCH_ENABLED:
        res.details["nutrient_branch"] = "disabled"
        notes.append(
            "NPK deficiency/excess decisions are disabled until a reliable "
            "measurement exists. A number appearing in a sensor or CSV "
            "is not enough."
        )
    elif nutrients:
        for k, r in nutrients.items():
            if (
                r is None
                or getattr(r, "method", None) not in TRUSTED_NUTRIENT_METHODS
            ):
                res.missing.append(f"nutrient:{k}")
                notes.append(f"{k}: untrusted method or unit")

    if symptoms:
        notes.append(
            "Image symptoms: "
            + ", ".join(symptoms)
            + " - a description only, not a concentration or a fertilizer dose; "
            "analysis is required."
        )

    # Same rule as rule 1: violation + missing essential variable = conditional
    if needs_adjust:
        res.status = ADJUST
        if res.missing:
            res.details["conditional"] = True
    elif res.missing:
        res.status = INSUFFICIENT

    res.reasons = notes
    res.details["auto_actions"] = "none"

    return res
