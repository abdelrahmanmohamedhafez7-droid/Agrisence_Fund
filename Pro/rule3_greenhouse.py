from datetime import datetime, timezone
from common import *


def _settings():
    return load_json("profiles.json").get("rule3_settings", {})


def daypart(local_dt: datetime, day_start=None, day_end=None):
    s = _settings()
    day_start = s.get("day_start", 6) if day_start is None else day_start
    day_end = s.get("day_end", 18) if day_end is None else day_end
    return "day" if day_start <= local_dt.hour < day_end else "night"


def compute_dli(
    ppfd_series,
    day_seconds=86400,
    max_gap_s=900,
    min_coverage=0.9,
    expected_s=None,
):
    """DLI (mol/m2/day) = sum(PPFD[umol/m2/s] * dt[s]) / 1e6, PPFD only.

    expected_s: seconds the log should cover. Default = day_seconds (a 24 h
    log with zeros at night). For a daylight-only log pass the photoperiod
    length, so a normal daytime log is not always called incomplete.
    """
    if day_seconds <= 0 or max_gap_s <= 0:
        raise ValueError("day_seconds and max_gap_s must be positive")
    expected_s = day_seconds if expected_s is None else expected_s
    if expected_s <= 0 or expected_s > day_seconds:
        raise ValueError("expected_s must be in (0, day_seconds]")

    series = list(ppfd_series)

    if len(series) < 2:
        raise ValueError("At least two PPFD readings are required")

    for _, r in series:
        if r.unit not in PPFD_UNITS:
            raise ValueError(
                f"PPFD must be in {PPFD_UNIT}, not {r.unit} "
                "(no lux or W/m2 conversion)"
            )

    span = (series[-1][0] - series[0][0]).total_seconds()
    if span > day_seconds:
        raise ValueError(
            "PPFD series spans more than one day; pass one day at a time"
        )

    total, covered, gaps = 0.0, 0.0, 0

    for (t0, r0), (t1, _) in zip(series, series[1:]):
        ok, _ = check_reading(r0, lo=0, hi=3000)
        dt = (t1 - t0).total_seconds()

        if not ok or dt <= 0 or dt > max_gap_s:
            gaps += 1
            continue

        total += r0.value * dt
        covered += dt

    coverage = min(covered / expected_s, 1.0)

    return {
        "dli_mol": total / 1e6,
        "coverage": coverage,
        "gaps": gaps,
        "complete": coverage >= min_coverage and gaps == 0,
    }


def _range_status(v, lo, hi):
    return "low" if v < lo else "high" if v > hi else "ok"


def assess_greenhouse(
    crop,
    stage,
    local_dt,
    air_t: Reading,
    air_rh: Reading,
    ppfd_series=None,
    co2: Reading = None,
    soil_result: Result = None,
    outside_t: Reading = None,
    forecast: dict = None,
    devices: dict = None,
    now=None,
    outside_rh: Reading = None,
    ppfd_log="24h",
):
    """ppfd_log: '24h' (log covers the whole day, zeros at night) or
    'daylight' (log covers only the day hours from rule3_settings)."""
    prof = load_json("profiles.json")["crops"].get(crop, {}).get("greenhouse")
    settings = _settings()

    ref = {"cucumber": "CV268", "tomato": "CV266"}.get(crop, "?")

    res = Result(
        rule="3_greenhouse",
        status=OK,
        references=[ref, "Purdue HO-238-W (DLI)"],
    )

    if not prof or stage not in prof.get("air", {}):
        res.status = INSUFFICIENT
        res.missing.append("crop_stage_profile")
        res.reasons.append("No requirements profile for this crop/stage")
        return res

    provisional_caveat(res, prof)

    series_readings = [r for _, r in (ppfd_series or [])]
    res.data_sources = sources_of(
        air_t, air_rh, co2, outside_t, outside_rh, *series_readings
    )

    target = prof["air"][stage][daypart(local_dt)]
    factors = {}
    commands = []

    for name, reading, limits, unit in (
        ("temp", air_t, target["t"], TEMP_UNIT),
        ("rh", air_rh, target["rh"], RH_UNIT),
    ):
        ok, why = check_reading(
            reading,
            now=now,
            max_age_s=600,
            units=[unit],
        )

        if not ok:
            factors[name] = "insufficient"
            res.missing.append(name)
            res.reasons.append(f"{name}: {why}")
        else:
            factors[name] = _range_status(reading.value, limits[0], limits[1])

            if factors[name] != "ok":
                res.reasons.append(
                    f"{name} {reading.value} is {factors[name]} "
                    f"(target {limits[0]}-{limits[1]})"
                )

    if forecast:
        for name, key, limits in (
            ("temp", "temp_15m", target["t"]),
            ("rh", "rh_15m", target["rh"]),
        ):
            value = forecast.get(key)

            if (
                value is not None
                and factors.get(name) == "ok"
                and _range_status(value, limits[0], limits[1]) != "ok"
            ):
                res.reasons.append(
                    f"Early warning: {name} is forecast at {value} "
                    "within 15 minutes, outside the target"
                )

    if ppfd_series:
        try:
            if ppfd_log == "daylight":
                expected = (
                    settings.get("day_end", 18) - settings.get("day_start", 6)
                ) * 3600
            elif ppfd_log == "24h":
                expected = None
            else:
                raise ValueError("ppfd_log must be '24h' or 'daylight'")
            dli = compute_dli(ppfd_series, expected_s=expected)
            dli["log_mode"] = ppfd_log
            res.details["dli"] = dli
            limits = prof["dli_mol"]

            if not dli["complete"]:
                factors["light"] = "incomplete_day"
                res.reasons.append(
                    "DLI is for an incomplete day or has gaps; "
                    "not a final judgement"
                )
            else:
                factors["light"] = _range_status(
                    dli["dli_mol"], limits["min"], limits["max"]
                )
                v = dli["dli_mol"]
                if "good_min" in limits:
                    good_max = limits.get("good_max", limits["max"])
                    hq = limits.get("high_quality_min")
                    dli["level"] = (
                        "below_minimum" if v < limits["min"]
                        else "minimum_acceptable" if v < limits["good_min"]
                        else "good" if v <= good_max
                        else "above_good_range" if hq is None
                        else "between_good_and_high_quality" if v < hq
                        else "high_quality"
                    )
                dli["limit_source"] = limits.get("source")

                if factors["light"] != "ok":
                    res.reasons.append(
                        f"DLI {dli['dli_mol']:.2f} mol/m²/day "
                        f"is {factors['light']} "
                        f"(target {limits['min']}-{limits['max']})"
                    )

        except (ValueError, TypeError, AttributeError) as ex:
            factors["light"] = "insufficient"
            res.missing.append("light")
            res.reasons.append(f"DLI could not be calculated: {ex}")
    else:
        factors["light"] = "insufficient"
        res.missing.append("light")

    ok, why = check_reading(
        co2,
        now=now,
        max_age_s=900,
        units=[PPM_UNIT],
        lo=0,
        hi=10000,
    )

    if ok:
        factors["co2"] = _range_status(
            co2.value, prof["co2_ppm"]["min"], prof["co2_ppm"]["max"]
        )

        if factors["co2"] == "low":
            res.reasons.append(
                "CO2 is low: review ventilation and CO2 readings; "
                "there is no CO2 injection device"
            )
        elif factors["co2"] == "high":
            res.reasons.append(
                "CO2 is above the target range; verify the reading "
                "and review greenhouse conditions"
            )
    else:
        factors["co2"] = "insufficient"
        res.missing.append("co2")
        res.reasons.append(f"CO2: {why}")

    if soil_result is not None:
        factors["soil"] = soil_result.status

        if soil_result.status == INSUFFICIENT:
            res.missing.append("soil")

    def usable(device_name):
        device = (devices or {}).get(device_name)
        return bool(
            device and device.get("readable") and device.get("healthy")
        )

    ok_out, outside_why = check_reading(
        outside_t, now=now, max_age_s=1800, units=[TEMP_UNIT]
    )
    ok_rh_out, outside_rh_why = check_reading(
        outside_rh, now=now, max_age_s=1800, units=[RH_UNIT], lo=0, hi=100
    )

    if factors.get("temp") == "high":
        if not (usable("fan") or usable("vent")):
            res.reasons.append(
                "Temperature is high but the fan/vent is unavailable "
                "or its state is unknown: alert only, no command"
            )
            commands.append(
                {
                    "device": "alert",
                    "action": "notify_user",
                    "reason": "device_unavailable",
                }
            )

        elif not ok_out:
            res.reasons.append(
                f"Outside temperature is unknown ({outside_why}); "
                "no ventilation command"
            )

        elif outside_t.value >= air_t.value:
            res.reasons.append(
                "Outside air is warmer than inside: ventilation will not cool"
            )

        else:
            device_name = "vent" if usable("vent") else "fan"
            commands.append(
                {
                    "device": device_name,
                    "action": "on_or_open",
                    "reason": "temp_high_outside_cooler",
                }
            )

    if (
        factors.get("rh") == "high"
        and factors.get("temp") != "insufficient"
        and usable("vent")
    ):
        margin = settings.get("rh_vent_max_outside_warmer_c", 5)
        already_open = any(
            c.get("device") == "vent"
            and c.get("action") in ("open", "on_or_open")
            for c in commands
        )

        if not ok_out:
            res.reasons.append(
                f"Humidity is high but outside temperature is unknown "
                f"({outside_why}); no vent command"
            )
        elif not ok_rh_out:
            res.reasons.append(
                f"Humidity is high but outside humidity is unknown "
                f"({outside_rh_why}); no vent command"
            )
        elif factors.get("temp") == "low" or (
            outside_t.value < target["t"][0]
            and air_t.value <= target["t"][0] + 2
        ):
            res.reasons.append(
                "Humidity is high but it is cold inside or outside air is "
                "colder than the temperature target: venting would "
                "over-cool; no vent command"
            )
        elif outside_t.value > air_t.value + margin:
            res.reasons.append(
                "Humidity is high but outside air is much warmer: "
                "venting would raise the temperature; no vent command"
            )
        elif outside_rh.value >= air_rh.value:
            res.reasons.append(
                "Humidity is high but outside air is not drier than inside: "
                "ventilation will not dehumidify; no vent command"
            )
        elif not already_open:
            commands.append(
                {"device": "vent", "action": "open", "reason": "rh_high"}
            )

    res.details.update(
        factors=factors,
        targets=target,
        commands=commands,
        requires_safety_check=True,
    )

    bad = [
        name
        for name, value in factors.items()
        if value in ("low", "high", "needs_adjustment")
    ]

    if bad:
        res.status = ADJUST
        res.details["adjust"] = bad
    elif res.missing or "incomplete_day" in factors.values():
        res.status = INSUFFICIENT

    res.details["readiness"] = "ready" if res.status == OK else "conditional"

    return res
