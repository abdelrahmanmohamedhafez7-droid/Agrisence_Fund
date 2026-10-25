# Plan check - AgriSense_Rules_and_Simulation_Final.pdf, pages 1-6

Pages 7-9 (simulations 6 and 7, integration spec) were read but intentionally not implemented.
Status: OK = implemented and tested | PARTIAL = implemented, needs data or a decision | OPEN = not done

## General (page 1)
| Plan requirement | Code | Test | Status |
|---|---|---|---|
| Cucumber and tomato, open field and greenhouse | profiles.json, `assess_both` | r1_assess_both | OK |
| Each result gives a reason and a reference | `Result.reasons / references` | all | OK |
| Missing data = "insufficient", never zero | `check_reading`, every rule | r1_missing_not_zero, r4_stale_reading | OK |
| Keep crop, stage, medium, method, unit, threshold source | profile `ref`, `methods`, details.stage/medium | r1_stage_medium_weather_recorded | OK |
| NPK branch stays disabled | `NPK_BRANCH_ENABLED=False` | r2_npk_disabled | OK |
| Parma out of scope | not used anywhere | - | OK |
| Data source written explicitly (recorded / simulation / sensor) | `data_sources` in every rule | r1/r2/r3 sources tests | OK |

## Rule 1 (page 2)
| Plan requirement | Code | Test | Status |
|---|---|---|---|
| Inputs: crops, setting, stage, medium, documented pH/EC, weather | `assess_crop(..., stage, medium, weather)` | r1_stage_medium_weather_recorded | OK (stage and weather are recorded, they do not change the pH/EC limits yet) |
| Output suitable / needs adjustment / insufficient with reasons | status + reasons | r1_suitable, r1_out_of_range | OK |
| Method and unit must fit the reference | `methods`, `units`, EC conversion | r1_unknown_method, r1_wrong_ph_unit, r1_ec_unit_conversion | OK |
| Overall result stays conditional if an essential variable is missing | `details["conditional"]` | r1_violation_plus_missing_is_conditional | OK |
| Hand-off to rule 2, and rule 3 for greenhouse | `details["handoff"]` | - | OK |
| Medium picks the profile | `allowed_media` | r1_medium_not_covered | PARTIAL (one profile per crop/setting, media list is provisional) |
| Thresholds match CV123/137/268/266 | profiles.json `verified=false` | - | OPEN (needs the team to check the PDFs) |

## Rule 2 (page 3)
| Plan requirement | Code | Test | Status |
|---|---|---|---|
| pH, EC with method, manual advice only | `soil_prep` | r2_* | OK |
| Direct soil EC is not solution EC | note in reasons + method check | r2_salinity_high | OK |
| Image symptoms are a description, not a dose | symptoms note | r2_symptoms_no_dose | OK |
| No automatic fertilizer / pH action | `auto_actions="none"` | r2_npk_disabled | OK |
| Analysis incomplete = asks for completion | missing -> insufficient / conditional | r2_missing_only_is_insufficient | OK |
| Stage-specific limits | stage recorded only | r2_stage_recorded_and_caveat | PARTIAL (needs stage-specific values in profiles.json) |
| NPK decisions | disabled by decision | - | OK (disabled) |

## Rule 3 (page 4)
| Plan requirement | Code | Test | Status |
|---|---|---|---|
| Air temp/RH against crop, stage, time of day | `daypart`, profile `air` | r3_night_target_used | OK |
| Forecast = early warning, current reading = state | `forecast` block | - | OK |
| DLI from PPFD (umol/m2/s) x time; no lux conversion | `compute_dli` | r3_dli_math_and_units | OK |
| Incomplete day is flagged | coverage/gaps, `incomplete_day` | r3_incomplete_day_not_ready | OK |
| One-day series only | span check | r3_dli_rejects_multi_day_series | OK |
| CO2 monitoring only, no injection | co2 reasons | - | OK |
| Fan/vent need readable + healthy device | `usable()` | r3_device_down_alerts | OK |
| Outside air that helps vs outside air that makes it worse | temperature check; humidity check needs outside RH and outside temp | r3_outside_hotter_no_command, r3_rh_high_* | OK |
| Ventilation is not independent cooling | no command if outside is warmer | r3_outside_hotter_no_command | OK |
| Commands go through the safety check | `requires_safety_check=True` | r3_commands_need_safety_check | OK |
| Light (lamp) command | not generated | - | OPEN (the plan lists the lamp as a device, but gives no rule for when to switch it) |

## Rule 4 (page 5)
| Plan requirement | Code | Test | Status |
|---|---|---|---|
| Reject missing / stale / unknown-method moisture | `check_reading` | r4_stale_reading, r4_wrong_method_refused | OK |
| Check tank and operating limits | tank check, limits | r4_tank_*, r4_daily_limit, r4_cycle_limit | OK |
| Below start threshold -> small dose within limits | `irrigate` | r4_dry_small_dose | OK |
| Run time = dose / flow, capped | `run_s` | r4_run_cap | OK |
| Stop, wait for water to spread, then remeasure | `waiting` decision, `last_dose_time` | r4_waits_before_remeasure | OK |
| Continue or stop on the new reading (gap between start and stop) | `irrigating` state, target | r4_continues_*, r4_target_used_to_stop_irrigating | OK |
| Target moisture, start/stop thresholds | `th["target"]` validated | r4_bad_target_rejected | OK |
| Max dose, time, daily water; no response = stop + alert | limits, `no_response` | r4_no_response_stops | OK |
| Response threshold is configurable | `dose["min_response_pct"]` | r4_min_response_is_a_setting | OK |
| Open field = advice only; missing inputs = conditional advice, no number | `open_field_advice` | r4_open_field* | OK |
| Moisture thresholds calibrated on the real medium | `verified=false` caveat | r4_provisional_caveat | OPEN (needs real calibration) |
| Hardware safety check on the ESP32 before the pump runs | `pump_on` always False | - | OK in software, hardware part comes later |

## Rule 5 (page 6)
| Plan requirement | Code | Test | Status |
|---|---|---|---|
| Class must exist in the model list and match crop | `model_classes`, `crop:label` key | r5_class_*, r5_label_from_other_crop_has_no_guidance | OK (model list is optional; skipped and noted when not supplied) |
| Bad image / inconclusive result is shown, no specific treatment | `image_ok`, threshold | r5_bad_image, r5_low_confidence, r5_nan_confidence_is_inconclusive | OK |
| High confidence is not lab confirmation | reasons + `specialist_confirmation` | r5_known_class | OK |
| Class without approved guidance | `no_approved_guidance` | r5_no_guidance | OK |
| Humidity link goes to the decision engine; conflict with RH | `note` | r5_env_conflict, r5_stale_or_wrong_unit_rh_never_conflicts | OK |
| Deficiency: review analysis, no dose from the image | deficiency reason | r5_deficiency_no_dose | OK |
| Healthy is not a guarantee | action text | r5_healthy_is_not_a_guarantee | OK |
| No pesticide recipes, no automatic spraying | guidance.json | r5_no_pesticides_in_guidance | OK |
| Guidance reviewed against IPM UC | `reviewed=false` | r5_provisional_caveat | OPEN (needs a specialist) |

## Partly checked against the references (revision 2)
Temperatures (HS788, HS790), open-field pH (CV296) and tomato DLI (HO-238-W) were matched. EC limits, RH ranges, CO2 limits and cucumber DLI have no source in the provided PDFs. CV123/137/268/266 and IPM UC were not provided.

## What cannot be confirmed from here
The CV / FAO / IPM UC PDFs were not available, so the numbers in profiles.json and guidance.json
(pH, EC, temperature, RH, DLI, CO2 ranges and the guidance texts) were NOT matched against them.
They stay marked provisional (`verified=false`, `reviewed=false`) until the team does that.

## Revision 3 status
| Item | Status |
|---|---|
| CV123/CV137 matched | DONE: they hold no pH/EC limits (pest/weed chapters) |
| IPM UC matched for 4 classes | DONE (powdery/downy mildew, late/early blight); leaf_mold has no IPM section |
| Tomato DLI vs Purdue | DONE |
| EC limits, RH ranges, CO2 range, cucumber DLI | OPEN: no source in the provided PDFs |
| Lamp rule, simulations 6/7, integration (pages 7-9) | OPEN / postponed by decision |

## Revision 4 status
| Item | Status |
|---|---|
| DLI coverage for daylight-only logs (`ppfd_log="daylight"`) | DONE |
| Rule 1 references (CV296 pH, FAO 29 EC; CV123/137 = context only) | DONE |
| EC limit 2.5 mS/cm, mineral soil, saturated paste (FAO 29); soilless = insufficient | DONE |
| Cucumber DLI min 15 / good 20-30 (MSU, Cornell) | DONE (provisional) |
| Lamp rule, moisture calibration, specialist review, page 9 | OPEN |
| Simulations 6/7 (pages 7-8) | postponed by decision |
