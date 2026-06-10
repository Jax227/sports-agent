"""Baseline calculator — 5-day individual baseline logic.

Rules:
  - At least 5 valid daily records to complete baseline.
  - A valid record must have: date, sleep_hours, sleep_quality, fatigue,
    muscle_soreness, mood, stress, AND (resting_hr OR hrv), duration_min, session_rpe.
  - Cumulative days (not necessarily continuous) are counted.
  - After baseline completes, mean/sd/normal_range are computed for each metric.
  - Adding/editing/deleting records triggers automatic recalculation.
"""

from datetime import datetime
from typing import Optional
from . import athlete_storage as store

# Metrics to include in baseline calculation
BASELINE_METRICS = [
    "sleep_hours",
    "sleep_quality",
    "fatigue",
    "muscle_soreness",
    "mood",
    "stress",
    "resting_hr",
    "hrv",
    "body_weight",
    "duration_min",
    "session_rpe",
    "training_load",
    "wellness_score",
]

# Minimum required fields for a valid baseline day
REQUIRED_FIELDS = [
    "date",
    "sleep_hours",
    "sleep_quality",
    "fatigue",
    "muscle_soreness",
    "mood",
    "stress",
    "duration_min",
    "session_rpe",
]

# At least one of these must be present
ONE_OF_FIELDS = ["resting_hr", "hrv"]


def is_valid_baseline_day(record: dict) -> bool:
    """Check if a daily record counts as a valid baseline day."""
    for field in REQUIRED_FIELDS:
        val = record.get(field)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return False

    has_physio = False
    for field in ONE_OF_FIELDS:
        val = record.get(field)
        if val is not None and not (isinstance(val, str) and val.strip() == ""):
            has_physio = True
            break
    return has_physio


def compute_wellness_score(record: dict) -> float:
    """wellness_score = sleep_quality + mood - fatigue - muscle_soreness - stress"""
    def _num(v, default=0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return (
        _num(record.get("sleep_quality", 0))
        + _num(record.get("mood", 0))
        - _num(record.get("fatigue", 0))
        - _num(record.get("muscle_soreness", 0))
        - _num(record.get("stress", 0))
    )


def compute_training_load(record: dict) -> float:
    """training_load = duration_min * session_rpe"""
    try:
        dur = float(record.get("duration_min", 0))
        rpe = float(record.get("session_rpe", 0))
    except (TypeError, ValueError):
        return 0
    return dur * rpe


def get_valid_baseline_records(athlete_id: str) -> list[dict]:
    """Return all valid baseline days sorted by date."""
    records = store.load_daily_data(athlete_id)
    valid = [r for r in records if is_valid_baseline_day(r)]
    valid.sort(key=lambda r: r.get("date", ""))
    return valid


def calculate_baseline_metrics(records: list[dict]) -> dict:
    """Compute mean, sd, min, max, normal_range for each metric."""
    import math

    metrics = {}
    for metric in BASELINE_METRICS:
        vals = []
        for r in records:
            v = r.get(metric)
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue

        if len(vals) < 5:
            continue

        n = len(vals)
        mean = sum(vals) / n
        variance = sum((x - mean) ** 2 for x in vals) / n  # population std on baseline
        sd = math.sqrt(variance) if variance > 0 else 0

        metrics[metric] = {
            "mean": round(mean, 2),
            "sd": round(sd, 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
            "n": n,
            "normal_low": round(mean - sd, 2) if sd > 0 else round(mean, 2),
            "normal_high": round(mean + sd, 2) if sd > 0 else round(mean, 2),
            "caution_low": round(mean - 2 * sd, 2) if sd > 0 else round(mean, 2),
            "caution_high": round(mean + 2 * sd, 2) if sd > 0 else round(mean, 2),
        }

    return metrics


def get_baseline_status(athlete_id: str) -> str:
    """Determine baseline status: not_started | in_progress | completed | needs_review."""
    records = store.load_daily_data(athlete_id)
    valid = get_valid_baseline_records(athlete_id)

    if len(records) == 0:
        return "not_started"
    if len(valid) < 5:
        return "in_progress"
    return "completed"


def rebuild_baseline(athlete_id: str) -> dict:
    """Recalculate and persist baseline for an athlete. Call after any data change."""
    valid = get_valid_baseline_records(athlete_id)
    status = "not_started" if len(valid) == 0 else ("in_progress" if len(valid) < 5 else "completed")

    baseline = {
        "athlete_id": athlete_id,
        "baseline_status": status,
        "baseline_days_count": len(valid),
        "baseline_start_date": valid[0]["date"] if valid else None,
        "baseline_end_date": valid[-1]["date"] if valid else None,
        "total_records": len(store.load_daily_data(athlete_id)),
        "metrics": calculate_baseline_metrics(valid) if status == "completed" else {},
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }

    store.save_baseline(athlete_id, baseline)

    # Also update the index profile's baseline_status
    profile = store.get_athlete_index(athlete_id)
    if profile:
        profile["baseline_status"] = status
        profile["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        store.upsert_index(profile)

    return baseline
