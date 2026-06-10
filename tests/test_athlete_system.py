"""E2E test for the athlete management system."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.athlete_manager import (
    create_athlete, list_athletes, get_athlete, get_athlete_detail,
    delete_athlete, restore_athlete, update_athlete, get_last_entry_date,
)
from src.baseline_calculator import (
    is_valid_baseline_day, compute_wellness_score, compute_training_load,
    get_valid_baseline_records, get_baseline_status, rebuild_baseline,
)
from src.risk_analyzer import analyze_daily_record
from src import athlete_storage as store


def test_create_athletes():
    print("=" * 60)
    print("TEST 1: Create athletes")
    a1 = create_athlete(name="张三", sex="男", sport="篮球", event_or_position="后卫", training_level="专业", team="A队")
    a2 = create_athlete(name="李四", sex="女", sport="游泳", event_or_position="自由泳", training_level="精英", team="B队")
    a3 = create_athlete(name="张三", sex="男", sport="足球")  # Same name, should get different ID

    print(f"  A1: {a1['name']} -> {a1['athlete_id']}")
    print(f"  A2: {a2['name']} -> {a2['athlete_id']}")
    print(f"  A3: {a3['name']} -> {a3['athlete_id']}")
    assert a1["athlete_id"] != a2["athlete_id"]
    assert a1["athlete_id"] != a3["athlete_id"], "Same name should still get unique IDs"
    assert a1["baseline_status"] == "not_started"
    print("  PASS")
    return a1["athlete_id"], a2["athlete_id"], a3["athlete_id"]


def test_list_athletes(aid1, aid2, aid3):
    print("=" * 60)
    print("TEST 2: List athletes")
    active = list_athletes(include_deleted=False)
    print(f"  Active: {len(active)} athletes")
    assert len(active) >= 3
    ids = {a["athlete_id"] for a in active}
    assert aid1 in ids and aid2 in ids and aid3 in ids
    print("  PASS")


def test_baseline_day_validation():
    print("=" * 60)
    print("TEST 3: Baseline day validation")
    valid_record = {
        "date": "2026-06-01", "sleep_hours": 8, "sleep_quality": 7,
        "fatigue": 3, "muscle_soreness": 2, "mood": 7, "stress": 3,
        "resting_hr": 52, "duration_min": 60, "session_rpe": 6,
    }
    assert is_valid_baseline_day(valid_record), "Should be valid"

    invalid = dict(valid_record)
    invalid["sleep_hours"] = None
    assert not is_valid_baseline_day(invalid), "Missing sleep_hours should be invalid"

    no_physio = dict(valid_record)
    no_physio["resting_hr"] = None
    no_physio["hrv"] = None
    assert not is_valid_baseline_day(no_physio), "Missing both HR and HRV should be invalid"

    # HRV alone should be enough
    hrv_only = dict(valid_record)
    hrv_only["resting_hr"] = None
    hrv_only["hrv"] = 78
    assert is_valid_baseline_day(hrv_only), "HRV alone should satisfy physio requirement"

    print("  PASS")


def test_data_isolation(aid1, aid2):
    print("=" * 60)
    print("TEST 4: Data isolation")

    # Add 3 days for athlete A
    for i in range(1, 4):
        record = {
            "record_id": f"REC_{aid1}_test_{i}",
            "athlete_id": aid1,
            "date": f"2026-06-{i:02d}",
            "sleep_hours": 8.0, "sleep_quality": 7, "fatigue": 3,
            "muscle_soreness": 2, "mood": 7, "stress": 3,
            "resting_hr": 52, "hrv": 78, "body_weight": 75.0,
            "training_type": "力量", "duration_min": 60, "session_rpe": 6,
            "training_load": 360, "wellness_score": 6,
            "notes": "", "created_at": "2026-06-01T10:00:00",
        }
        store.add_daily_record(aid1, record)

    # Add 1 day for athlete B
    record_b = {
        "record_id": f"REC_{aid2}_test_1",
        "athlete_id": aid2,
        "date": "2026-06-01",
        "sleep_hours": 7.0, "sleep_quality": 6, "fatigue": 5,
        "muscle_soreness": 4, "mood": 5, "stress": 5,
        "resting_hr": 58, "hrv": 55, "body_weight": 60.0,
        "training_type": "游泳", "duration_min": 90, "session_rpe": 7,
        "training_load": 630, "wellness_score": -3,
        "notes": "", "created_at": "2026-06-01T10:00:00",
    }
    store.add_daily_record(aid2, record_b)

    a_records = store.load_daily_data(aid1)
    b_records = store.load_daily_data(aid2)
    print(f"  A records: {len(a_records)} (expect 3)")
    print(f"  B records: {len(b_records)} (expect 1)")
    assert len(a_records) == 3, f"Expected 3 for A, got {len(a_records)}"
    assert len(b_records) == 1, f"Expected 1 for B, got {len(b_records)}"

    # Verify A cannot see B's data
    a_dates = {r["date"] for r in a_records}
    assert "2026-06-01" in a_dates
    a_loads = [r.get("training_load") for r in a_records]
    assert all(l == 360 for l in a_loads), f"A's loads should all be 360, got {a_loads}"
    b_loads = [r.get("training_load") for r in b_records]
    assert b_loads[0] == 630, f"B's load should be 630, got {b_loads}"
    print("  PASS")


def test_baseline_progression(aid1):
    print("=" * 60)
    print("TEST 5: Baseline progression (in_progress)")

    rebuild_baseline(aid1)
    status = get_baseline_status(aid1)
    valid = get_valid_baseline_records(aid1)
    print(f"  Status: {status}, Valid days: {len(valid)}")
    assert status == "in_progress", f"Expected in_progress, got {status}"
    assert len(valid) == 3, f"Expected 3 valid days, got {len(valid)}"
    print("  PASS (3/5 days)")

    # Add days 4 and 5
    for i in range(4, 6):
        record = {
            "record_id": f"REC_{aid1}_test_{i}",
            "athlete_id": aid1,
            "date": f"2026-06-{i:02d}",
            "sleep_hours": 7.5 + i * 0.2, "sleep_quality": 6 + i % 3,
            "fatigue": 4 - i % 2, "muscle_soreness": 3, "mood": 7, "stress": 2 + i % 2,
            "resting_hr": 50 + i, "hrv": 75 - i,
            "training_type": "力量", "duration_min": 60 + i * 5, "session_rpe": 5 + i % 2,
            "training_load": (60 + i * 5) * (5 + i % 2),
            "wellness_score": 7 + 7 - 4 - 3 - 2,
            "notes": "", "created_at": f"2026-06-{i:02d}T10:00:00",
        }
        store.add_daily_record(aid1, record)

    rebuild_baseline(aid1)
    status = get_baseline_status(aid1)
    valid = get_valid_baseline_records(aid1)
    print(f"  Status: {status}, Valid days: {len(valid)}")
    assert status == "completed", f"Expected completed, got {status}"
    assert len(valid) >= 5

    baseline = store.load_baseline(aid1)
    metrics = baseline.get("metrics", {})
    print(f"  Baseline metrics: {list(metrics.keys())}")
    assert "sleep_hours" in metrics
    assert "resting_hr" in metrics
    assert "training_load" in metrics
    assert "wellness_score" in metrics
    print(f"  sleep_hours baseline: mean={metrics['sleep_hours']['mean']}, sd={metrics['sleep_hours']['sd']}")
    print("  PASS")


def test_baseline_comparison(aid1):
    print("=" * 60)
    print("TEST 6: Day-to-baseline comparison")

    baseline = store.load_baseline(aid1)
    assert baseline["baseline_status"] == "completed"

    # Day 6 — slightly elevated fatigue
    day6 = {
        "record_id": f"REC_{aid1}_test_6",
        "athlete_id": aid1,
        "date": "2026-06-06",
        "sleep_hours": 7.0, "sleep_quality": 5,
        "fatigue": 7, "muscle_soreness": 5, "mood": 5, "stress": 6,
        "resting_hr": 62, "hrv": 55,
        "training_type": "力量", "duration_min": 90, "session_rpe": 8,
        "training_load": 720, "wellness_score": 5 + 5 - 7 - 5 - 6,
        "notes": "hard day", "created_at": "2026-06-06T10:00:00",
    }

    analysis = analyze_daily_record(day6, baseline)
    print(f"  Summary: {analysis['summary']}")
    print(f"  Red alerts: {analysis['red_count']}, Yellow: {analysis['yellow_count']}")

    for alert in analysis.get("alerts", []):
        print(f"    {alert['level']}: {alert['metric']} z={alert['z_score']} ({alert['direction']})")

    # There should be at least some alerts for this hard day
    assert analysis["status"] == "baseline_ready"
    assert analysis["red_count"] + analysis["yellow_count"] > 0, "Hard day should trigger some alerts"
    print("  PASS")


def test_delete_daily_data(aid1):
    print("=" * 60)
    print("TEST 7: Delete daily data triggers baseline recalculation")

    records = store.load_daily_data(aid1)
    day5 = next((r for r in records if r.get("date") == "2026-06-05"), None)
    assert day5, "Should have day 5 data"

    store.delete_daily_record(aid1, day5["record_id"])
    rebuild_baseline(aid1)
    status = get_baseline_status(aid1)
    valid = get_valid_baseline_records(aid1)
    print(f"  After deleting day 5: status={status}, valid days={len(valid)}")
    assert status == "in_progress", f"Should revert to in_progress, got {status}"

    # Restore day 5
    store.add_daily_record(aid1, day5)
    rebuild_baseline(aid1)
    status = get_baseline_status(aid1)
    print(f"  After restoring day 5: status={status}")
    assert status == "completed"
    print("  PASS")


def test_soft_delete_athlete(aid3):
    print("=" * 60)
    print("TEST 8: Soft delete athlete")

    delete_athlete(aid3, hard=False)
    active = list_athletes(include_deleted=False)
    all_a = list_athletes(include_deleted=True)
    print(f"  Active after soft delete: {len(active)}, All (incl deleted): {len(all_a)}")
    assert aid3 not in {a["athlete_id"] for a in active}, "Should not appear in active list"
    assert aid3 in {a["athlete_id"] for a in all_a}, "Should appear in full list"

    # Restore
    restore_athlete(aid3)
    active = list_athletes(include_deleted=False)
    assert aid3 in {a["athlete_id"] for a in active}, "Should be back in active list"
    print("  PASS")


def test_update_athlete(aid1):
    print("=" * 60)
    print("TEST 9: Update athlete profile")

    update_athlete(aid1, {"name": "张三丰", "sport": "武术", "notes": "改名并换项目"})
    profile = get_athlete(aid1)
    assert profile["name"] == "张三丰"
    assert profile["sport"] == "武术"
    assert profile["sex"] == "男"  # Unchanged
    print(f"  Updated: {profile['name']}, {profile['sport']}")
    print("  PASS")


def test_hard_delete(aid3):
    print("=" * 60)
    print("TEST 10: Hard delete athlete with backup")

    delete_athlete(aid3, hard=True)
    all_a = list_athletes(include_deleted=True)
    print(f"  After hard delete: {len(all_a)} athletes remain")
    assert aid3 not in {a["athlete_id"] for a in all_a}, "Should be gone entirely"

    # Check backup exists
    import glob
    backups = list(Path(store.ATHLETES_DIR).glob(f"_deleted_{aid3}_*"))
    print(f"  Backup found: {len(backups) > 0}")
    assert len(backups) > 0, "Backup should be created on hard delete"
    print("  PASS")


def cleanup():
    """Remove test data."""
    import shutil
    store.ATHLETES_DIR.mkdir(parents=True, exist_ok=True)
    # Remove test athlete dirs but keep the index
    for d in store.ATHLETES_DIR.iterdir():
        if d.is_dir() and d.name.startswith("ATH_"):
            shutil.rmtree(d)
    # Reset index
    if store.INDEX_PATH.exists():
        store.INDEX_PATH.unlink()


if __name__ == "__main__":
    print("\n=== Sports Agent — Athlete System E2E Test ===\n")

    try:
        cleanup()  # Start fresh
        aid1, aid2, aid3 = test_create_athletes()
        test_list_athletes(aid1, aid2, aid3)
        test_baseline_day_validation()
        test_data_isolation(aid1, aid2)
        test_baseline_progression(aid1)
        test_baseline_comparison(aid1)
        test_delete_daily_data(aid1)
        test_soft_delete_athlete(aid3)
        test_update_athlete(aid1)
        test_hard_delete(aid3)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
