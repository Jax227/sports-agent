"""SRSS (Short Recovery and Stress Scale) — scoring, decision logic, visualization data.

SRSS items (8 total):
  Recovery (4): PPC, MPC, EB, OR
  Stress   (4): MS,  LA,  NES, OS

Scoring: raw 1-6 → mapped 0-100 via (raw-1)/5*100
Red light: any stress item >=5 (raw) OR any recovery item <=2 (raw)
Readiness: recovery_avg > stress_avg AND no red light → good; otherwise → adjust training
"""

RECOVERY_ITEMS = {
    "PPC": {"label": "体能恢复 (Physical Performance Capability)", "desc": "强壮·体力充沛·精力充沛·充满力量"},
    "MPC": {"label": "心理恢复 (Mental Performance Capability)", "desc": "专心的·能接受新鲜事物·注意力集中·精神警觉"},
    "EB":  {"label": "情绪平衡 (Emotional Balance)", "desc": "满足·情绪稳定·心情好·一切在掌握之中"},
    "OR":  {"label": "整体恢复 (Overall Recovery)", "desc": "完全恢复·充分休息·肌肉放松·身体放松"},
}

STRESS_ITEMS = {
    "MS":  {"label": "肌肉压力 (Muscular Stress)", "desc": "肌肉力竭·肌肉疲劳·肌肉酸痛·肌肉僵硬"},
    "LA":  {"label": "缺乏活力 (Lack of Activation)", "desc": "积极性低·慵懒·缺乏训练热情·无精打采"},
    "NES": {"label": "负面情绪 (Negative Emotional State)", "desc": "情绪低落·有压力·烦躁·易怒"},
    "OS":  {"label": "整体压力 (Overall Stress)", "desc": "疲劳·消耗殆尽·训练过量·精疲力竭"},
}

ALL_SRSS_ITEMS = {**RECOVERY_ITEMS, **STRESS_ITEMS}
SRSS_ITEM_ORDER = ["PPC", "MPC", "EB", "OR", "MS", "LA", "NES", "OS"]


def map_raw_to_100(raw: int) -> float:
    """Map SRSS 1-6 scale to 0-100."""
    return round((raw - 1) / 5 * 100, 2)


def label_recovery(score: float) -> str:
    if score >= 60:
        return "良好"
    if score >= 45:
        return "一般"
    return "偏低"


def label_stress(score: float) -> str:
    if score <= 35:
        return "较低"
    if score <= 50:
        return "一般"
    return "偏高"


def score_srss_responses(responses: dict[str, int]) -> dict:
    """Score a full set of 8 SRSS responses.

    Args:
        responses: {item_code: raw_int (1-6), ...} — must have all 8 items.

    Returns:
        dict with items, recovery_avg, stress_avg
    """
    items = {}
    recovery_scores = []
    stress_scores = []

    for code in SRSS_ITEM_ORDER:
        raw = responses.get(code, 3)
        mapped = map_raw_to_100(raw)
        category = "recovery" if code in RECOVERY_ITEMS else "stress"
        item_info = ALL_SRSS_ITEMS[code]

        items[code] = {
            "raw": raw,
            "mapped": mapped,
            "label": item_info["label"],
            "category": category,
        }

        if category == "recovery":
            recovery_scores.append(mapped)
        else:
            stress_scores.append(mapped)

    recovery_avg = round(sum(recovery_scores) / 4, 2)
    stress_avg = round(sum(stress_scores) / 4, 2)

    return {
        "items": items,
        "recovery_avg": recovery_avg,
        "stress_avg": stress_avg,
        "recovery_sum": round(sum(recovery_scores), 2),
        "stress_sum": round(sum(stress_scores), 2),
    }


def detect_red_light(responses: dict[str, int]) -> list[dict]:
    """Detect red-light conditions on raw scores.

    Red light criteria:
      - Any stress item raw score >= 5
      - Any recovery item raw score <= 2

    Returns list of red-light alerts.
    """
    alerts = []

    for code, raw in responses.items():
        if code in STRESS_ITEMS and raw >= 5:
            alerts.append({
                "item": code,
                "label": ALL_SRSS_ITEMS[code]["label"],
                "raw": raw,
                "reason": f"压力条目 '{code}' 得分偏高 (≥5)",
                "level": "red",
            })
        if code in RECOVERY_ITEMS and raw <= 2:
            alerts.append({
                "item": code,
                "label": ALL_SRSS_ITEMS[code]["label"],
                "raw": raw,
                "reason": f"恢复条目 '{code}' 得分偏低 (≤2)",
                "level": "red",
            })

    return alerts


def assess_readiness(scored: dict, red_lights: list[dict]) -> dict:
    """Assess overall athlete readiness.

    Returns dict with status, rationale, recommendations.
    """
    recovery_avg = scored["recovery_avg"]
    stress_avg = scored["stress_avg"]
    has_red = len(red_lights) > 0

    if recovery_avg > stress_avg and not has_red:
        return {
            "status": "good",
            "title": "运动员准备状态良好",
            "rationale": f"恢复均分 ({recovery_avg}) > 压力均分 ({stress_avg})，且无红灯信号。",
            "recommendation": "按计划训练为主，继续日常跟踪。",
            "recovery_avg": recovery_avg,
            "stress_avg": stress_avg,
            "red_lights": [],
        }

    reasons = []
    if not (recovery_avg > stress_avg):
        reasons.append(f"恢复均分 ({recovery_avg}) ≤ 压力均分 ({stress_avg})")
    if has_red:
        item_names = [a["item"] for a in red_lights]
        reasons.append(f"出现红灯信号: {', '.join(item_names)}")

    return {
        "status": "adjust_training",
        "title": "需要进一步观察，建议调整训练",
        "rationale": "；".join(reasons) + "。",
        "recommendation": "对运动员进行进一步观察，并适当调整训练内容以降低损伤与过度训练风险（例如降低总量/强度、减少高冲击/高变向、增加恢复与技术性训练）。",
        "recovery_avg": recovery_avg,
        "stress_avg": stress_avg,
        "red_lights": red_lights,
    }


def compare_training_load(current: float, previous: float | None) -> dict:
    """Compare current training load vs same day previous week."""
    if previous is None or previous == 0:
        return {
            "current": current,
            "previous": previous,
            "pct_change": None,
            "direction": "no_comparison",
        }

    pct = round((current - previous) / previous * 100, 2)
    if pct > 5:
        direction = "increase"
    elif pct < -5:
        direction = "decrease"
    else:
        direction = "stable"

    return {
        "current": current,
        "previous": previous,
        "pct_change": pct,
        "direction": direction,
    }


def get_previous_srss_record(records: list[dict], current_date: str) -> dict | None:
    """Find the most recent SRSS record before current_date."""
    candidates = [
        r for r in records
        if "srss_scored" in r and r.get("date", "") < current_date
    ]
    candidates.sort(key=lambda r: r.get("date", ""), reverse=True)
    return candidates[0] if candidates else None


def get_same_weekday_load(records: list[dict], current_date: str) -> float | None:
    """Get training_load from 7 days before current_date."""
    from datetime import datetime, timedelta

    try:
        target_date = datetime.strptime(current_date, "%Y-%m-%d")
        prev_date = target_date - timedelta(days=7)
        prev_str = prev_date.strftime("%Y-%m-%d")
    except ValueError:
        return None

    for r in records:
        if r.get("date") == prev_str:
            return r.get("training_load")
    return None


# ═══════════════════════════════════════════════════════════
# Chart data builders (return dicts, plotly-agnostic)
# ═══════════════════════════════════════════════════════════

def build_radar_data(scored: dict) -> dict:
    """Build data dict for a plotly Scatterpolar radar chart."""
    items_in_order = [scored["items"][code] for code in SRSS_ITEM_ORDER]

    recovery_values = []
    stress_values = []
    recovery_labels = []
    stress_labels = []

    for it in items_in_order:
        if it["category"] == "recovery":
            recovery_values.append(it["mapped"])
            recovery_labels.append(it["label"])
        else:
            stress_values.append(it["mapped"])
            stress_labels.append(it["label"])

    all_labels = [it["label"] for it in items_in_order]
    all_values = [it["mapped"] for it in items_in_order]

    return {
        "all_labels": all_labels,
        "all_values": all_values,
        "recovery_labels": recovery_labels,
        "recovery_values": recovery_values,
        "stress_labels": stress_labels,
        "stress_values": stress_values,
    }


def build_summary_rows(scored: dict, readiness: dict, load_cmp: dict) -> list[dict]:
    """Build rows for a summary table."""
    rows = []

    for code in SRSS_ITEM_ORDER:
        it = scored["items"][code]
        cat = "恢复" if code in RECOVERY_ITEMS else "压力"
        mapped = it["mapped"]
        if code in RECOVERY_ITEMS:
            status = label_recovery(mapped)
        else:
            status = label_stress(mapped)
        rows.append({
            "指标": it["label"],
            "类别": cat,
            "原始分(1-6)": it["raw"],
            "得分(0-100)": mapped,
            "状态": status,
        })

    # Appendix rows
    rows.append({"指标": "—", "类别": "—", "原始分(1-6)": "—", "得分(0-100)": "—", "状态": "—"})
    rows.append({
        "指标": "恢复均值",
        "类别": "汇总",
        "原始分(1-6)": "—",
        "得分(0-100)": scored["recovery_avg"],
        "状态": label_recovery(scored["recovery_avg"]),
    })
    rows.append({
        "指标": "压力均值",
        "类别": "汇总",
        "原始分(1-6)": "—",
        "得分(0-100)": scored["stress_avg"],
        "状态": label_stress(scored["stress_avg"]),
    })
    rows.append({
        "指标": "准备状态",
        "类别": "决策",
        "原始分(1-6)": "—",
        "得分(0-100)": readiness["status"],
        "状态": "✅ 良好" if readiness["status"] == "good" else "⚠️ 需调整",
    })

    if load_cmp["pct_change"] is not None:
        direction_text = f"{'+' if load_cmp['pct_change'] > 0 else ''}{load_cmp['pct_change']}%"
        rows.append({
            "指标": "训练负荷同比",
            "类别": "负荷",
            "原始分(1-6)": f"{load_cmp['previous']} AU",
            "得分(0-100)": f"{load_cmp['current']} AU",
            "状态": direction_text,
        })

    return rows
