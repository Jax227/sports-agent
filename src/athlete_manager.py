"""Athlete manager — CRUD operations, ID generation, validation."""

from datetime import datetime
from typing import Optional
from . import athlete_storage as store


def generate_athlete_id() -> str:
    now = datetime.now()
    prefix = now.strftime("%Y%m%d")
    existing = store.load_index()
    today_ids = [
        a["athlete_id"] for a in existing
        if a.get("athlete_id", "").startswith(f"ATH_{prefix}")
    ]
    seq = 1
    for aid in today_ids:
        try:
            n = int(aid.split("_")[-1])
            if n >= seq:
                seq = n + 1
        except (ValueError, IndexError):
            pass
    return f"ATH_{prefix}_{seq:04d}"


def create_athlete(
    name: str,
    sex: str = "",
    date_of_birth: str = "",
    sport: str = "",
    event_or_position: str = "",
    training_level: str = "",
    team: str = "",
    coach: str = "",
    notes: str = "",
) -> dict:
    if not name.strip():
        raise ValueError("姓名不能为空")

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    athlete_id = generate_athlete_id()

    profile = {
        "athlete_id": athlete_id,
        "name": name.strip(),
        "sex": sex,
        "date_of_birth": date_of_birth,
        "sport": sport,
        "event_or_position": event_or_position,
        "training_level": training_level,
        "team": team,
        "coach": coach,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
        "deleted_at": None,
        "baseline_status": "not_started",
        "notes": notes,
    }

    store.save_profile(profile)
    return profile


def update_athlete(athlete_id: str, updates: dict) -> Optional[dict]:
    profile = store.get_athlete_index(athlete_id)
    if not profile:
        return None

    # Fields allowed to update
    allowed = {
        "name", "sex", "date_of_birth", "sport", "event_or_position",
        "training_level", "team", "coach", "notes",
    }
    for k, v in updates.items():
        if k in allowed:
            profile[k] = v

    # Handle restore
    if updates.get("is_active") is True:
        profile["is_active"] = True
        profile["deleted_at"] = None

    profile["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    store.save_profile(profile)
    return profile


def delete_athlete(athlete_id: str, hard: bool = False) -> bool:
    if hard:
        # Auto-backup before hard delete
        store.export_athlete_backup(athlete_id)
        return store.hard_delete_athlete(athlete_id)
    return store.soft_delete_athlete(athlete_id)


def restore_athlete(athlete_id: str) -> Optional[dict]:
    return update_athlete(athlete_id, {"is_active": True})


def list_athletes(include_deleted: bool = False) -> list[dict]:
    all_athletes = store.load_index()
    if include_deleted:
        return all_athletes
    return [a for a in all_athletes if a.get("is_active", True)]


def get_athlete(athlete_id: str) -> Optional[dict]:
    return store.get_athlete_index(athlete_id)


def get_athlete_detail(athlete_id: str) -> Optional[dict]:
    """Get full profile including baseline status from baseline.json."""
    profile = store.load_profile(athlete_id)
    if not profile:
        return None
    baseline = store.load_baseline(athlete_id)
    profile["_baseline"] = baseline
    profile["_daily_count"] = len(store.load_daily_data(athlete_id))
    return profile


def get_last_entry_date(athlete_id: str) -> Optional[str]:
    records = store.load_daily_data(athlete_id)
    if not records:
        return None
    dates = sorted([r.get("date", "") for r in records if r.get("date")], reverse=True)
    return dates[0] if dates else None
