# AgriSense Rules (Rules 1-5)

Run tests: `python3 tests/test_rules.py` (87 tests, no extra packages needed)

| File | Rule |
|---|---|
| rule1_suitability.py | 1 Land suitability (crop, setting, stage, medium, pH/EC, weather context) |
| rule2_soil_prep.py | 2 Soil preparation and nutrition (NPK branch disabled: `NPK_BRANCH_ENABLED=False`) |
| rule3_greenhouse.py | 3 Greenhouse readiness + DLI + vent/fan commands (commands need the ESP32 safety check) |
| rule4_irrigation.py | 4 Irrigation (pot decision loop + open-field advice) |
| rule5_disease.py | 5 Disease guidance |
| profiles.json / guidance.json | Thresholds and guidance (`verified=false` / `reviewed=false` means needs review) |
| PLAN_CHECK.md | Page-by-page check of the code against the plan (pages 1-6) |

## How the code is used
* Every rule returns a `Result` with `status`, `reasons`, `missing`, `references`, `details`, `data_sources`.
* Missing or invalid data gives `insufficient_data`; it is never replaced by zero.
* A violation plus a missing essential variable gives `needs_adjustment` with `details["conditional"]=True` (rules 1 and 2).
* Rule 4 never switches the pump: `pump_on` is always `False`. The caller keeps this state between calls and passes it back:
  `irrigating` (use `details["irrigating_next"]`), `last_dose_ml`, `last_dose_time` (timezone-aware), `prev_moisture`, `daily_used_ml`, `cycle_used_ml`.
  The caller resets `cycle_used_ml` / `daily_used_ml` at cycle/day boundaries.
* Rule 3 takes `outside_rh` as well as `outside_t`; the humidity vent command needs both.
* Settings live in the JSON files (day hours, outside-warmer margin, irrigation thresholds) or as arguments (`min_response_pct`, `conf_threshold`, `rh_conflict_below`).

## Team must review
1. `profiles.json` values are provisional; match them with CV123/137/268/266/265/296 and record the measurement method. `allowed_media` and `rule3_settings` are provisional too.
2. Pot moisture thresholds must be calibrated on the real medium (`verified` stays false until then).
3. `guidance.json` texts need specialist review against IPM UC.
4. Confidence threshold 0.60 and the RH conflict limit 50 are provisional; tune on validation.
5. Simulations 6 and 7 and the integration spec (pages 7-9) are NOT implemented (postponed by decision).
6. The unit tests check program logic only. They do not prove that a real crop will grow.

## Changes in this revision
* Rule 3: no humidity vent command when it is cold inside, or when outside air is colder than the target and inside is near the lower limit.
* Rule 5: RH age is always checked (`now` defaults to the current UTC time); stale RH can no longer create a conflict note.
* Rule 2: in-range pH/EC now produce positive reasons.
* profiles.json: greenhouse air temperatures set from HS788 (tomato) and HS790 (cucumber); open-field pH 6.0-6.5 from CV296; tomato DLI floor 10 (Purdue HO-238-W Table 2, good 14-20). EC limits, RH ranges and cucumber DLI still have NO source in the references and stay provisional.

## Revision 3 (new references: CV123, CV137, IPM UC Cucurbits/Tomato)
* CV123/CV137 are pest/weed chapters: they contain NO soil pH/EC limits. Open-field pH comes from CV296 only.
* EC limits have no source in any provided reference: every profile now has `ec.source = null`, and rules 1 and 2 say so in the result (`details["ec_limit_source"]`).
* Tomato DLI uses Purdue HO-238-W Table 2 (10-12 minimum acceptable, 14-20 good, 22+ high quality); rule 3 reports `details["dli"]["level"]`. Cucumber DLI has no source (provisional).
* guidance.json: each class now has `ipm_section` / `ipm_matched`. `tomato:leaf_mold` has no section in IPM UC Tomato, so `ipm_matched=false`. `reviewed` stays false until a specialist signs off.

## Revision 4
* Rule 3: `compute_dli(..., expected_s=)` and `assess_greenhouse(..., ppfd_log="24h"|"daylight")`. A daylight-only log is no longer always incomplete. Default stays "24h" (old behaviour).
* Rule 1: references now list CV296 (pH) and FAO 29 (EC); CV123/CV137 are marked "crop context only".
* EC: limit 2.5 mS/cm (ECe, saturated paste, mineral soil) for both crops, source FAO 29 Rev.1 (1985). Soilless media / pour-through now give `insufficient` for EC (rules 1 and 2) until a source exists.
* Cucumber DLI: min 15, good 20-30 (MSU + Cornell via Hort Americas; provisional).
* Tests that expected EC 3.0/3.5 to be suitable must be updated.
