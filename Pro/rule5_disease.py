import math
from datetime import datetime, timezone
from common import *

DEFAULT_CONF = 0.60
DEFAULT_RH_CONFLICT_BELOW = 50


def _valid_prob(x):
    return (
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(x)
        and 0 <= x <= 1
    )


def disease_guidance(
    crop,
    label,
    confidence,
    image_ok=True,
    model_classes=None,
    rh: Reading = None,
    conf_threshold=DEFAULT_CONF,
    rh_conflict_below=DEFAULT_RH_CONFLICT_BELOW,
    now=None,
):
    g = load_json("guidance.json")
    res = Result(
        rule="5_disease",
        status=OK,
        references=[g["ref"].get(crop, "?")],
        data_sources=sources_of(rh),
    )
    key = f"{crop}:{label}"

    if crop not in g["ref"]:
        res.status = INSUFFICIENT
        res.missing = ["crop"]
        res.reasons.append(f"No guidance reference for crop: {crop}")
        return res

    if not image_ok:
        res.status = INSUFFICIENT
        res.reasons.append(
            "Image is not suitable; retake the leaf photo with better "
            "light and closer"
        )
        return res

    if model_classes is not None and label not in model_classes:
        res.status = INSUFFICIENT
        res.reasons.append("Class is not in the model class list")
        return res

    if model_classes is None:
        res.details["model_class_check"] = "skipped: model_classes not supplied"

    if not _valid_prob(conf_threshold) or conf_threshold == 0:
        res.status = INSUFFICIENT
        res.reasons.append("Confidence threshold must be in (0, 1]")
        return res

    if not _valid_prob(confidence) or confidence < conf_threshold:
        res.status = INSUFFICIENT
        res.details["result_type"] = "inconclusive"
        res.reasons.append(
            "Inconclusive result: no specific treatment; retake the photo "
            "or keep monitoring the plant. High confidence alone is not "
            "laboratory confirmation."
        )
        return res

    item = g["classes"].get(key)

    if not item:
        res.status = INSUFFICIENT
        res.details["result_type"] = "no_approved_guidance"
        res.reasons.append(f"Class '{label}' has no approved guidance yet")
        return res

    res.details.update(
        result_type=item["kind"],
        label=label,
        confidence=confidence,
        actions=item["actions"],
        guidance_reviewed=item["reviewed"],
        specialist_confirmation=item["kind"] != "healthy",
    )
    res.reasons.append(
        f"Predicted condition: {label} (confidence {confidence:.2f}); "
        "no lesion location or severity"
    )

    if not item["reviewed"]:
        res.details["caveat"] = (
            "Guidance has not been reviewed by a specialist yet"
        )

    if item.get("humidity_linked"):
        note = {"to_decision_engine": "check_humidity_ventilation"}

        if rh is not None:
            ok, why = check_reading(
                rh,
                now=now or datetime.now(timezone.utc),
                max_age_s=1800,
                units=[RH_UNIT],
                lo=0,
                hi=100,
            )
            if not ok:
                note["rh_unusable"] = why
            elif rh.value < rh_conflict_below:
                note["conflict"] = (
                    "Image suggests a humidity-linked disease while RH is "
                    "low; review the reading and the diagnosis"
                )

        res.details["note"] = note

    if item["kind"] == "deficiency":
        res.reasons.append(
            "Deficiency symptoms: review analysis, nutrition, irrigation "
            "and pH; no dose from the image"
        )

    return res
