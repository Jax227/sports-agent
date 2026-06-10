"""Generate demo CSV files using only stdlib (no pandas/numpy needed)."""
import csv
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).resolve().parent


def gauss(mu=0, sigma=1):
    """Box-Muller normal random."""
    u1 = random.random()
    u2 = random.random()
    return mu + sigma * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)


def generate_wellness(days=90):
    """Generate wellness data with realistic periodization patterns."""
    base_date = datetime(2026, 2, 1)
    rows = []

    # AR(1) noise state for RMSSD
    ar_state = 0
    rmssd_base, hr_base = 45.0, 55.0

    for i in range(days):
        date = base_date + timedelta(days=i)
        week = i // 7
        dow = date.weekday()  # Monday=0

        # Periodization: 3 load + 1 recovery
        load_phase = week % 4
        week_effect = 5.0 if load_phase == 3 else (-3.0 + 1.5 * load_phase)

        # Day-of-week
        dow_effect = -0.8 * (dow % 5)

        # AR noise
        ar_state = 0.3 * ar_state + 0.7 * gauss(0, 4)
        rmssd = rmssd_base + week_effect + dow_effect + ar_state
        rmssd = max(20, min(80, round(rmssd, 1)))

        hr = hr_base - week_effect * 0.6 + dow_effect * 0.5 + gauss(0, 2.5)
        hr = max(42, min(72, round(hr, 1)))

        sleep_q = max(1, min(5, round(3.0 + week_effect * 0.08 + gauss(0, 0.6))))
        fatigue = max(1, min(5, round(3.0 - week_effect * 0.08 + dow_effect * 0.15 + gauss(0, 0.5))))
        mood = max(1, min(5, round(3.2 + week_effect * 0.05 + gauss(0, 0.5))))

        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "rmssd": rmssd,
            "hr_rest": hr,
            "sleep_quality": sleep_q,
            "fatigue": fatigue,
            "mood": mood,
        })

    return rows


def generate_training(days=90):
    """Generate training data with periodization."""
    base_date = datetime(2026, 2, 1)
    rows = []
    load_history = []

    for i in range(days):
        date = base_date + timedelta(days=i)
        week = i // 7
        dow = date.weekday()
        load_phase = week % 4

        # Base load per micro-cycle phase
        base = {0: 220, 1: 280, 2: 340, 3: 160}[load_phase]
        cycle = week // 4
        base += cycle * 15

        # Day multiplier
        if dow == 0:
            day_mult = 0.3
        elif dow == 6:
            day_mult = 0.5
        elif dow == 5:
            day_mult = 1.15
        else:
            day_mult = 1.0

        # RPE
        if day_mult > 0.3:
            rpe = max(1, min(10, round(gauss(6, 1.5))))
        else:
            rpe = max(1, min(10, round(gauss(2, 1.0))))

        # Duration
        if dow == 0:
            dur = 20
        elif dow == 6:
            dur = 50
        else:
            dur = max(15, min(120, round(gauss(70, 15))))

        training_load = rpe * dur
        load_history.append(training_load)

        # Random sick days (3 out of 90)
        if i in {25, 55, 78}:
            rpe, dur, training_load = 0, 0, 0

        # Rolling metrics
        def roll_mean(vals, window, min_per):
            if len(vals) < min_per:
                return None
            w = vals[-window:] if len(vals) >= window else vals
            return round(sum(w) / len(w), 0)

        def roll_std(vals, window, min_per):
            if len(vals) < min_per:
                return None
            w = vals[-window:] if len(vals) >= window else vals
            m = sum(w) / len(w)
            var = sum((x - m) ** 2 for x in w) / len(w)
            return math.sqrt(var)

        acute = roll_mean(load_history, 7, 4)
        chronic = roll_mean(load_history, 28, 14)
        acwr = round(acute / chronic, 2) if acute and chronic and chronic > 0 else None

        mean7 = sum(load_history[-7:]) / min(len(load_history), 7) if len(load_history) >= 4 else None
        std7 = roll_std(load_history, 7, 4)
        mono = round(mean7 / std7, 2) if mean7 and std7 and std7 > 0 else None
        strain = round(acute * mono, 0) if acute and mono else None

        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "session_rpe": rpe,
            "duration_min": dur,
            "training_load": training_load,
            "acute_load_7d": int(acute) if acute else "",
            "chronic_load_28d": int(chronic) if chronic else "",
            "acwr": acwr if acwr else "",
            "training_monotony": mono if mono else "",
            "training_strain": int(strain) if strain else "",
        })

    return rows


def write_csv(filename, rows, fieldnames):
    path = OUT / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows → {path}")


def main():
    w = generate_wellness(90)
    write_csv("wellness_demo.csv", w,
              ["date", "rmssd", "hr_rest", "sleep_quality", "fatigue", "mood"])

    t = generate_training(90)
    write_csv("training_demo.csv", t,
              ["date", "session_rpe", "duration_min", "training_load",
               "acute_load_7d", "chronic_load_28d", "acwr",
               "training_monotony", "training_strain"])


if __name__ == "__main__":
    main()
