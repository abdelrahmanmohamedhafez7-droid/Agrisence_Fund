from datetime import datetime, timezone
from common import *
import math

PLAN = {
    "open_field": "FAO-56",
    "greenhouse": "CV264",
}

KNOWN_CROPS = ("cucumber", "tomato")
DEFAULT_MIN_RESPONSE_PCT = 0.5


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def pot_decision(
    moisture: Reading,
    th: dict,
    tank: str,
    dose: dict,
    state: dict,
    now=None,
    max_age_s=600,
):
    """One irrigation decision for a pot in the greenhouse.

    state keys (all optional): irrigating (bool), last_dose_ml, last_dose_time
    (tz-aware datetime), prev_moisture (%VWC before the last dose),
    daily_used_ml, cycle_used_ml.
    dose optional key: min_response_pct (default 0.5).
    th optional key: target (start <= target <= stop), verified.
    The result never switches the pump itself: pump_on is always False and the
    decision must pass the ESP32 safety check first.
    """
    res = Result(
        rule="4_irrigation",
        status=OK,
        references=[PLAN["greenhouse"]],
        data_sources=sources_of(moisture),
    )
    res.details["pump_on"] = False

    def stop(code, reason, alert=False):
        res.status = (
            INSUFFICIENT if code in ("insufficient", "no_response") else ADJUST
        )
        res.details.update(
            decision=code,
            alert=alert,
            pump_on=False,
            irrigating_next=False,
        )
        res.reasons.append(reason)
        return res

    if not isinstance(th, dict) or not isinstance(dose, dict):
        res.missing = ["thresholds_or_dose_settings"]
        return stop(
            "insufficient",
            "Thresholds or dose settings are missing or invalid; no pumping.",
            alert=True,
        )

    if not isinstance(state, dict):
        res.missing = ["state"]
        return stop(
            "insufficient",
            "Irrigation state is missing or invalid; no pumping.",
            alert=True,
        )

    if not all(k in th for k in ("start", "stop", "method")):
        res.missing = ["thresholds_or_dose_settings"]
        return stop(
            "insufficient",
            "Start/stop thresholds or measurement method are missing; no pumping.",
            alert=True,
        )

    if not th.get("verified"):
        res.details["caveat"] = (
            "Provisional moisture thresholds: calibrate on the real medium "
            "and measurement method"
        )

    required_dose = (
        "dose_ml",
        "wait_s",
        "max_cycle_ml",
        "max_daily_ml",
        "max_run_s",
        "flow_ml_per_min",
    )

    if any(not _is_number(dose.get(k)) for k in required_dose):
        res.missing = ["thresholds_or_dose_settings"]
        return stop(
            "insufficient",
            "Dose and flow settings must all be valid finite numbers; no pumping.",
            alert=True,
        )

    if any(
        dose[k] <= 0
        for k in (
            "dose_ml",
            "max_cycle_ml",
            "max_daily_ml",
            "max_run_s",
            "flow_ml_per_min",
        )
    ) or dose["wait_s"] < 0:
        return stop(
            "insufficient",
            "Dose, water limits, run time and flow must be positive; "
            "wait time cannot be negative.",
            alert=True,
        )

    min_response = dose.get("min_response_pct", DEFAULT_MIN_RESPONSE_PCT)
    if not _is_number(min_response) or min_response < 0:
        return stop(
            "insufficient",
            "min_response_pct must be a non-negative number.",
            alert=True,
        )

    if (
        not _is_number(th["start"])
        or not _is_number(th["stop"])
        or not 0 <= th["start"] < th["stop"] <= 100
    ):
        return stop(
            "insufficient",
            "Moisture thresholds must satisfy 0 <= start < stop <= 100.",
            alert=True,
        )

    target = th.get("target")
    if target is not None and (
        not _is_number(target) or not th["start"] <= target <= th["stop"]
    ):
        return stop(
            "insufficient",
            "Target moisture must satisfy start <= target <= stop.",
            alert=True,
        )

    if not th["method"]:
        return stop(
            "insufficient",
            "A valid moisture measurement method is required.",
            alert=True,
        )

    for key in ("daily_used_ml", "cycle_used_ml"):
        used = state.get(key, 0)
        if not _is_number(used) or used < 0:
            return stop(
                "insufficient",
                f"Invalid irrigation state: {key} must be a non-negative number.",
                alert=True,
            )

    ok, why = check_reading(
        moisture,
        now=now,
        max_age_s=max_age_s,
        units=VWC_UNITS,
        methods=[th["method"]],
        lo=0,
        hi=100,
    )

    if not ok:
        res.missing = ["moisture"]
        return stop(
            "insufficient",
            f"Soil moisture: {why}; safe stop and alert.",
            alert=True,
        )

    try:
        vwc = to_vwc_pct(moisture.value, moisture.unit)
    except (ValueError, TypeError) as ex:
        res.missing = ["moisture"]
        return stop(
            "insufficient",
            f"Cannot interpret soil moisture: {ex}",
            alert=True,
        )

    if not _is_number(vwc) or not 0 <= vwc <= 100:
        return stop(
            "insufficient",
            "Implausible moisture reading; safe stop and alert.",
            alert=True,
        )

    res.details["moisture_vwc_pct"] = round(vwc, 2)

    if tank != "ok":
        return stop(
            "blocked_tank",
            "Tank is low or its state is unknown; pumping is blocked "
            "and an alert is raised.",
            alert=True,
        )

    if vwc >= th["stop"]:
        res.details.update(
            decision="stop_target_reached", irrigating_next=False
        )
        res.reasons.append(
            f"Moisture {vwc:.1f}% has reached the stop threshold "
            f"of {th['stop']}%."
        )
        return res

    last_dose = state.get("last_dose_ml", 0)
    prev = state.get("prev_moisture")

    if last_dose:
        if not _is_number(last_dose) or last_dose < 0:
            return stop(
                "insufficient",
                "Previous dose state is invalid; pumping is blocked.",
                alert=True,
            )

        last_time = state.get("last_dose_time")
        if (
            not isinstance(last_time, datetime)
            or last_time.tzinfo is None
            or last_time.utcoffset() is None
        ):
            return stop(
                "insufficient",
                "Time of the previous dose is missing or has no timezone; "
                "the wait time cannot be verified, so pumping is blocked.",
                alert=True,
            )

        now_ = now or datetime.now(timezone.utc)
        elapsed = (now_ - last_time).total_seconds()

        if elapsed < 0:
            return stop(
                "insufficient",
                "Time of the previous dose is in the future; pumping is blocked.",
                alert=True,
            )

        if elapsed < dose["wait_s"]:
            remaining = dose["wait_s"] - elapsed
            res.details.update(
                decision="waiting",
                wait_remaining_s=round(remaining, 1),
                alert=False,
                pump_on=False,
                irrigating_next=bool(state.get("irrigating")),
            )
            res.reasons.append(
                f"Waiting for water to spread: {remaining:.0f} s left "
                "before the next measurement counts."
            )
            return res

        if prev is None or not _is_number(prev):
            return stop(
                "insufficient",
                "Previous moisture reading is missing or invalid after a "
                "dose; recheck before pumping.",
                alert=True,
            )

        if not 0 <= prev <= 100:
            return stop(
                "insufficient",
                "Previous moisture reading is outside the valid range.",
                alert=True,
            )

        if vwc <= prev + min_response:
            return stop(
                "no_response",
                "No plausible moisture increase after the previous dose; "
                "inspect the sensor, water flow and irrigation system "
                "before continuing.",
                alert=True,
            )

    irrigating = bool(state.get("irrigating"))
    end_level = target if target is not None else th["stop"]

    if irrigating and vwc >= end_level:
        res.details.update(
            decision="stop_target_reached", irrigating_next=False
        )
        res.reasons.append(
            f"Moisture {vwc:.1f}% has reached the target of {end_level}%; "
            "stop irrigating."
        )
        return res

    if vwc >= th["start"] and not irrigating:
        res.details.update(decision="no_action", irrigating_next=False)
        res.reasons.append(
            f"Moisture {vwc:.1f}% has not fallen below the start "
            f"threshold of {th['start']}%; no irrigation is recommended."
        )
        return res

    daily_left = dose["max_daily_ml"] - state.get("daily_used_ml", 0)
    cycle_left = dose["max_cycle_ml"] - state.get("cycle_used_ml", 0)

    ml = min(dose["dose_ml"], daily_left, cycle_left)

    if ml <= 0:
        return stop(
            "limit_reached",
            "The daily or cycle water limit has been reached; stop and alert.",
            alert=True,
        )

    run_s = ml / dose["flow_ml_per_min"] * 60

    if run_s > dose["max_run_s"]:
        run_s = dose["max_run_s"]
        ml = run_s / 60 * dose["flow_ml_per_min"]

    if ml <= 0 or run_s <= 0:
        return stop(
            "limit_reached",
            "The permitted irrigation dose or run time is zero; no pumping.",
            alert=True,
        )

    res.status = ADJUST
    res.details.update(
        decision="irrigate",
        dose_ml=round(ml, 1),
        run_s=round(run_s, 1),
        wait_s=dose["wait_s"],
        then="stop_pump_wait_then_remeasure",
        requires_safety_check=True,
        pump_on=False,
        irrigating_next=True,
        continuing=irrigating,
    )
    if irrigating:
        res.reasons.append(
            f"Irrigation in progress: moisture {vwc:.1f}% is still below "
            f"{end_level}%. Next dose: {ml:.1f} ml for about {run_s:.1f} "
            f"seconds. Stop, wait {dose['wait_s']} seconds, then remeasure."
        )
    else:
        res.reasons.append(
            f"Moisture {vwc:.1f}% is below the start threshold "
            f"of {th['start']}%. Suggested dose: {ml:.1f} ml "
            f"for about {run_s:.1f} seconds. Stop, wait "
            f"{dose['wait_s']} seconds, then remeasure."
        )
    return res


def open_field_advice(
    crop=None,
    stage=None,
    area_m2=None,
    eto_mm_day=None,
    kc=None,
    efficiency=None,
    rain_mm=0.0,
):
    """Advisory only. The farmer applies water manually."""
    res = Result(
        rule="4_irrigation_open_field",
        status=OK,
        references=[PLAN["open_field"]],
    )

    res.details["advisory_only"] = True
    res.details["automatic_irrigation"] = False

    values = {
        "crop": crop,
        "stage": stage,
        "area_m2": area_m2,
        "eto_mm_day": eto_mm_day,
        "kc": kc,
        "efficiency": efficiency,
        "rain_mm": rain_mm,
    }

    missing = [k for k, v in values.items() if v is None or v == ""]

    if missing:
        res.status = INSUFFICIENT
        res.missing = missing
        res.reasons.append(
            "Required inputs are missing. No numeric irrigation "
            "recommendation can be calculated."
        )
        res.details["conditional_advice"] = (
            "Conditional guidance only: check the soil moisture by hand "
            "(finger test or a calibrated probe) before irrigating, adjust to "
            "the crop stage and the weather, and provide the missing inputs "
            f"({', '.join(missing)}) to get an indicative volume."
        )
        return res

    if crop not in KNOWN_CROPS or not isinstance(stage, str):
        res.status = INSUFFICIENT
        res.missing = ["crop" if crop not in KNOWN_CROPS else "stage"]
        res.reasons.append(
            "Crop must be cucumber or tomato and stage must be text; "
            "no numeric irrigation recommendation can be calculated."
        )
        res.details["conditional_advice"] = (
            "Conditional guidance only: check the soil moisture by hand "
            "before irrigating."
        )
        return res

    numeric_values = {
        "area_m2": area_m2,
        "eto_mm_day": eto_mm_day,
        "kc": kc,
        "efficiency": efficiency,
        "rain_mm": rain_mm,
    }

    invalid = [k for k, v in numeric_values.items() if not _is_number(v)]

    if invalid:
        res.status = INSUFFICIENT
        res.missing = invalid
        res.reasons.append("Numeric inputs must be finite numbers.")
        return res

    if (
        area_m2 <= 0
        or eto_mm_day < 0
        or kc <= 0
        or not 0 < efficiency <= 1
        or rain_mm < 0
    ):
        res.status = INSUFFICIENT
        res.reasons.append(
            "Invalid irrigation inputs: area and Kc must be positive, "
            "ETo and rainfall cannot be negative, and efficiency "
            "must be greater than 0 and at most 1."
        )
        return res

    etc = max(eto_mm_day * kc - rain_mm, 0.0)
    liters = etc * area_m2 / efficiency

    res.details.update(
        etc_mm_day=round(etc, 2),
        liters_per_day=round(liters, 1),
    )

    res.reasons.append(
        "This is an indicative calculation only. Check soil moisture "
        "and local conditions; the farmer applies water manually."
    )

    return res
