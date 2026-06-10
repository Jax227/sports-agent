"""Risk analyzer — compare daily data against individual baseline.

Color rules:
  green:  |z_score| < 1  — within normal range
  yellow: 1 <= |z_score| < 2 — mild deviation, monitor
  red:    |z_score| >= 2 — significant deviation, action recommended

Directional metrics:
  Higher = worse: fatigue, muscle_soreness, stress, resting_hr, session_rpe, training_load
  Lower  = worse: sleep_hours, sleep_quality, mood, hrv, wellness_score
"""

RISK_COLORS = {"green": "#4ade80", "yellow": "#fbbf24", "red": "#f87171"}

# Metrics where HIGHER values indicate INCREASED risk
HIGHER_IS_WORSE = {
    "fatigue", "muscle_soreness", "stress", "resting_hr",
    "session_rpe", "training_load",
}

# Metrics where LOWER values indicate INCREASED risk
LOWER_IS_WORSE = {
    "sleep_hours", "sleep_quality", "mood", "hrv", "wellness_score",
}


def compute_z_score(value: float, baseline_mean: float, baseline_sd: float) -> float:
    if baseline_sd == 0 or baseline_sd is None:
        return 0.0
    return (value - baseline_mean) / baseline_sd


def classify_risk(z_score: float, metric: str) -> tuple[str, str]:
    """
    Returns (level, direction_label)
      level: "green" | "yellow" | "red"
      direction_label: "↑偏高" / "↓偏低" / "正常"
    """
    abs_z = abs(z_score)

    if abs_z < 1:
        return "green", "正常"

    # Determine direction
    increasing_is_bad = metric in HIGHER_IS_WORSE

    if z_score > 0:
        direction = "↑偏高" if increasing_is_bad else "↑偏高（好方向）"
    else:
        direction = "↓偏低" if not increasing_is_bad else "↓偏低（好方向）"

    if abs_z < 2:
        return "yellow", direction
    return "red", direction


def analyze_daily_record(record: dict, baseline: dict) -> dict:
    """Compare one daily record against the athlete's baseline. Returns per-metric risks."""
    metrics_baseline = baseline.get("metrics", {})
    if not metrics_baseline:
        return {"status": "no_baseline", "risks": {}, "summary": "基线尚未建立"}

    risks = {}
    alerts = []

    for metric, stats in metrics_baseline.items():
        mean_val = stats.get("mean")
        sd_val = stats.get("sd", 0)
        raw_value = record.get(metric)

        if raw_value is None or mean_val is None:
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        z = compute_z_score(value, mean_val, sd_val)
        level, direction = classify_risk(z, metric)

        risks[metric] = {
            "value": value,
            "baseline_mean": mean_val,
            "baseline_sd": sd_val if sd_val else 0,
            "z_score": round(z, 2),
            "risk_level": level,
            "direction": direction,
        }

        if level in ("yellow", "red"):
            alerts.append({
                "metric": metric,
                "level": level,
                "z_score": round(z, 2),
                "direction": direction,
                "value": value,
                "baseline_mean": mean_val,
            })

    # Sort alerts: red first, then by |z_score|
    alerts.sort(key=lambda a: (0 if a["level"] == "red" else 1, -abs(a["z_score"])))

    red_count = sum(1 for a in alerts if a["level"] == "red")
    yellow_count = sum(1 for a in alerts if a["level"] == "yellow")

    if red_count > 0:
        summary = f"[严重偏离] {red_count} 项指标达红色预警"
    elif yellow_count > 0:
        summary = f"[轻度偏离] {yellow_count} 项指标需关注"
    else:
        summary = "[正常] 所有指标在个人正常范围内"

    return {
        "status": "baseline_ready",
        "risks": risks,
        "alerts": alerts,
        "red_count": red_count,
        "yellow_count": yellow_count,
        "summary": summary,
    }
