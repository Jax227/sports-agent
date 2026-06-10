"""Generate realistic demo data for the Sports Agent app."""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

OUT_DIR = Path(__file__).resolve().parent
np.random.seed(42)


def generate_wellness_data(days=90):
    """Generate daily wellness/HRV data with realistic patterns."""
    dates = [datetime(2026, 2, 1) + timedelta(days=i) for i in range(days)]
    n = len(dates)

    # Base RMSSD ~45ms, HRrest ~55bpm for a moderately trained athlete
    rmssd_base, hr_base = 45.0, 55.0

    # Add weekly periodization (hard week → recovery week)
    week = np.array([(d.day - 1) // 7 for d in dates])
    # 3 loading weeks + 1 recovery week pattern
    load_phase = week % 4
    week_effect = np.where(load_phase < 3, -3.0 + 1.5 * load_phase, 5.0)  # recovery boost

    # Add day-of-week effect (Monday fresh, Friday tired)
    dow = np.array([d.weekday() for d in dates])
    dow_effect = -0.8 * (dow % 5)  # slight decline through training week

    # Random daily variation + some autocorrelation
    noise = np.random.normal(0, 4, n)
    ar_noise = np.zeros(n)
    for i in range(1, n):
        ar_noise[i] = 0.3 * ar_noise[i - 1] + 0.7 * noise[i]

    rmssd = rmssd_base + week_effect + dow_effect + ar_noise
    rmssd = np.clip(rmssd, 20, 80).round(1)

    # HRrest inversely correlated with RMSSD
    hr_noise = np.random.normal(0, 2.5, n)
    hr_rest = hr_base - week_effect * 0.6 + dow_effect * 0.5 + hr_noise
    hr_rest = np.clip(hr_rest, 42, 72).round(1)

    # Sleep quality (1-5), slightly better after recovery
    sleep = np.clip(np.round(3.0 + week_effect * 0.08 + np.random.normal(0, 0.6, n)), 1, 5).astype(int)

    # Fatigue (1-5), inverse of freshness
    fatigue = np.clip(np.round(3.0 - week_effect * 0.08 + dow_effect * 0.15 + np.random.normal(0, 0.5, n)), 1, 5).astype(int)

    # Mood (1-5)
    mood = np.clip(np.round(3.2 + week_effect * 0.05 + np.random.normal(0, 0.5, n)), 1, 5).astype(int)

    df = pd.DataFrame({
        "date": dates,
        "rmssd": rmssd,
        "hr_rest": hr_rest,
        "sleep_quality": sleep,
        "fatigue": fatigue,
        "mood": mood,
    })
    return df


def generate_training_data(days=90):
    """Generate daily training data with realistic periodization."""
    dates = [datetime(2026, 2, 1) + timedelta(days=i) for i in range(days)]
    n = len(dates)

    week = np.array([(d.day - 1) // 7 for d in dates])
    dow = np.array([d.weekday() for d in dates])

    # Periodization: 3-week build + 1 deload
    load_phase = week % 4
    # Base load ramps from 200 to 350 over 3 build weeks, deloads to 150
    base_load = np.where(load_phase == 0, 220, np.where(load_phase == 1, 280, np.where(load_phase == 2, 340, 160)))
    # Add weekly ramp within each macro cycle
    cycle_num = week // 4
    base_load = base_load + cycle_num * 15  # progressive overload across cycles

    # Days: Mon=0 rest, Tue-Sat training, Sun lighter
    day_mult = np.where(dow == 0, 0.3, np.where(dow == 6, 0.5, np.where(dow == 5, 1.15, 1.0)))

    session_rpe = np.clip(np.round(np.where(day_mult > 0.3,
        np.random.normal(6.0, 1.5, n),  # training days have RPE 5-8 typically
        np.random.normal(2.0, 1.0, n)), 0), 1, 10).astype(int)

    # Duration: rest ~15min, light ~45min, normal ~60-90min
    duration_min = np.where(dow == 0, 20, np.where(dow == 6, 50,
        np.random.normal(70, 15, n))).clip(15, 120).round(0).astype(int)

    training_load = (session_rpe * duration_min).astype(int)

    # Add 2-3 random illness/injury days with 0 load
    sick_days = np.random.choice(n, size=3, replace=False)
    training_load[sick_days] = 0
    session_rpe[sick_days] = 0

    df = pd.DataFrame({
        "date": dates,
        "session_rpe": session_rpe,
        "duration_min": duration_min,
        "training_load": training_load,
    })

    # Calculate rolling metrics
    df["acute_load_7d"] = df["training_load"].rolling(7, min_periods=4).mean().round(0)
    df["chronic_load_28d"] = df["training_load"].rolling(28, min_periods=14).mean().round(0)
    df["acwr"] = (df["acute_load_7d"] / df["chronic_load_28d"].replace(0, np.nan)).round(2)

    # Training monotony = mean(daily load over 7d) / std(daily load over 7d)
    rolling_mean = df["training_load"].rolling(7, min_periods=4).mean()
    rolling_std = df["training_load"].rolling(7, min_periods=4).std().replace(0, np.nan)
    df["training_monotony"] = (rolling_mean / rolling_std).round(2)

    # Strain = load × monotony (Foster's metric)
    df["training_strain"] = (df["acute_load_7d"] * df["training_monotony"]).round(0)

    return df


def main():
    wellness = generate_wellness_data(90)
    training = generate_training_data(90)

    wellness.to_csv(OUT_DIR / "wellness_demo.csv", index=False, encoding="utf-8")
    training.to_csv(OUT_DIR / "training_demo.csv", index=False, encoding="utf-8")
    print(f"Generated demo data → {OUT_DIR}")
    print(f"  wellness: {len(wellness)} rows, cols={list(wellness.columns)}")
    print(f"  training: {len(training)} rows, cols={list(training.columns)}")


if __name__ == "__main__":
    main()
