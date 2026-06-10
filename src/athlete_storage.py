"""Athlete data storage — JSON file-based persistence.

Directory layout:
    data/athletes/
    ├── athletes_index.json          # all athlete profiles
    ├── ATH_20260601_0001/
    │   ├── profile.json             # copy of this athlete's profile
    │   ├── daily_data.json          # list of daily metric records
    │   └── baseline.json            # computed baseline
    └── ATH_20260601_0002/
        └── ...
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
ATHLETES_DIR = ROOT / "data" / "athletes"
INDEX_PATH = ATHLETES_DIR / "athletes_index.json"


def _ensure_dir() -> None:
    ATHLETES_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# Index operations
# ═══════════════════════════════════════════════════════════

def load_index() -> list[dict]:
    _ensure_dir()
    if INDEX_PATH.exists():
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    return []


def save_index(athletes: list[dict]) -> None:
    _ensure_dir()
    INDEX_PATH.write_text(
        json.dumps(athletes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_athlete_index(athlete_id: str) -> Optional[dict]:
    for a in load_index():
        if a.get("athlete_id") == athlete_id:
            return a
    return None


def upsert_index(profile: dict) -> None:
    athletes = load_index()
    aid = profile["athlete_id"]
    for i, a in enumerate(athletes):
        if a.get("athlete_id") == aid:
            athletes[i] = profile
            break
    else:
        athletes.append(profile)
    save_index(athletes)


def remove_from_index(athlete_id: str) -> None:
    athletes = load_index()
    save_index([a for a in athletes if a.get("athlete_id") != athlete_id])


# ═══════════════════════════════════════════════════════════
# Per-athlete directory helpers
# ═══════════════════════════════════════════════════════════

def athlete_dir(athlete_id: str) -> Path:
    return ATHLETES_DIR / athlete_id


def ensure_athlete_dir(athlete_id: str) -> Path:
    d = athlete_dir(athlete_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ═══════════════════════════════════════════════════════════
# Profile file
# ═══════════════════════════════════════════════════════════

def load_profile(athlete_id: str) -> dict:
    path = athlete_dir(athlete_id) / "profile.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # fallback: load from index
    entry = get_athlete_index(athlete_id)
    if entry:
        return entry
    return {}


def save_profile(profile: dict) -> None:
    d = ensure_athlete_dir(profile["athlete_id"])
    profile["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    (d / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    upsert_index(profile)


# ═══════════════════════════════════════════════════════════
# Daily data file
# ═══════════════════════════════════════════════════════════

def load_daily_data(athlete_id: str) -> list[dict]:
    path = athlete_dir(athlete_id) / "daily_data.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_daily_data(athlete_id: str, records: list[dict]) -> None:
    ensure_athlete_dir(athlete_id)
    path = athlete_dir(athlete_id) / "daily_data.json"
    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def add_daily_record(athlete_id: str, record: dict) -> dict:
    records = load_daily_data(athlete_id)
    record["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    # Upsert by date: replace existing record for same date
    date_str = record.get("date", "")
    for i, r in enumerate(records):
        if r.get("date") == date_str:
            records[i] = record
            save_daily_data(athlete_id, records)
            return record
    records.append(record)
    save_daily_data(athlete_id, records)
    return record


def delete_daily_record(athlete_id: str, record_id: str) -> bool:
    records = load_daily_data(athlete_id)
    new_records = [r for r in records if r.get("record_id") != record_id]
    if len(new_records) < len(records):
        save_daily_data(athlete_id, new_records)
        return True
    return False


# ═══════════════════════════════════════════════════════════
# Baseline file
# ═══════════════════════════════════════════════════════════

def load_baseline(athlete_id: str) -> dict:
    path = athlete_dir(athlete_id) / "baseline.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "athlete_id": athlete_id,
        "baseline_status": "not_started",
        "baseline_days_count": 0,
    }


def save_baseline(athlete_id: str, baseline: dict) -> None:
    ensure_athlete_dir(athlete_id)
    baseline["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    (athlete_dir(athlete_id) / "baseline.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════
# Deletion
# ═══════════════════════════════════════════════════════════

def soft_delete_athlete(athlete_id: str) -> bool:
    profile = get_athlete_index(athlete_id)
    if not profile:
        return False
    profile["is_active"] = False
    profile["deleted_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    profile["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    upsert_index(profile)
    save_profile(profile)
    return True


def hard_delete_athlete(athlete_id: str) -> bool:
    # Backup first
    d = athlete_dir(athlete_id)
    if d.exists():
        backup_dir = ATHLETES_DIR / f"_deleted_{athlete_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.move(str(d), str(backup_dir))
    remove_from_index(athlete_id)
    return True


def export_athlete_backup(athlete_id: str) -> Optional[Path]:
    d = athlete_dir(athlete_id)
    if not d.exists():
        return None
    import zipfile
    backup_path = ATHLETES_DIR / f"backup_{athlete_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in d.rglob("*"):
            zf.write(f, f.relative_to(d))
    return backup_path
