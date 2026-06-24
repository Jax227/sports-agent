"""
KPI Generator — creates KPIs from performance determinants.

Each KPI must be:
- Clearly defined
- Measurable
- Traceable
- Causally/logically linked to a PO
- Actionable via training/intervention
- With an accessible data source
"""

from sqlalchemy.orm import Session
from app import crud

# ── KPI templates per sport ────────────────────────────────────

KPI_TEMPLATES = {
    "Athletics - 800m": {
        "有氧能力": [
            {"name": "VO2max", "definition": "最大摄氧量，反映有氧能力上限", "calc": "递增负荷跑台测试，直接测量气体交换", "unit": "ml/kg/min", "freq": "每6-8周", "source": "实验室跑台测试", "evidence": "高"},
            {"name": "VO2max速度 (vVO2max)", "definition": "达到VO2max时的最低跑速", "calc": "递增负荷跑台测试中确定的对应速度", "unit": "km/h", "freq": "每6-8周", "source": "实验室跑台测试", "evidence": "高"},
        ],
        "无氧能力": [
            {"name": "最大血乳酸", "definition": "最大强度运动后血乳酸峰值", "calc": "全力400m或600m跑后血乳酸测量", "unit": "mmol/L", "freq": "每4-6周", "source": "血乳酸分析仪", "evidence": "高"},
            {"name": "Wingate无氧功率", "definition": "30秒全力骑行平均功率", "calc": "Wingate测试：0.075kg/kg阻力，30秒最大努力", "unit": "W/kg", "freq": "每8-12周", "source": "自行车功率计", "evidence": "中"},
        ],
        "冲刺能力": [
            {"name": "最大速度 (MSS)", "definition": "最大冲刺速度", "calc": "60m冲刺电子计时，取最高瞬时速度", "unit": "m/s", "freq": "每2-4周", "source": "电子计时系统", "evidence": "高"},
            {"name": "30m冲刺时间", "definition": "静止起跑30m用时", "calc": "电子计时门，3次取最佳", "unit": "s", "freq": "每2-4周", "source": "电子计时门", "evidence": "高"},
        ],
        "缓冲能力": [
            {"name": "乳酸阈跑速", "definition": "血乳酸达到4mmol/L时的跑速", "calc": "递增负荷测试，每级测血乳酸，确定4mmol/L拐点", "unit": "km/h", "freq": "每4-6周", "source": "血乳酸分析仪+跑台/跑道", "evidence": "高"},
        ],
        "无氧速度储备": [
            {"name": "无氧速度储备 (ASR)", "definition": "最大速度与VO2max速度的差值", "calc": "MSS - vVO2max", "unit": "m/s", "freq": "每6-8周", "source": "MSS测试 + vVO2max测试", "evidence": "中"},
        ],
        "肌腱组织弹性": [
            {"name": "反应力量指数 (RSI)", "definition": "跳跃高度/触地时间，反映肌腱弹性利用效率", "calc": "跳深测试：从30cm箱跳下后立即全力跳起，测量跳跃高度/触地时间", "unit": "m/s", "freq": "每4-6周", "source": "测力台/Optojump", "evidence": "中"},
        ],
        "下肢损伤风险": [
            {"name": "腘绳肌偏心力量", "definition": "Nordic Hamstring测试最大力量", "calc": "Nordic Hamstring测力装置，记录最大力量", "unit": "N", "freq": "每4周", "source": "NordBord或手持测力计", "evidence": "高"},
            {"name": "损伤发生率", "definition": "每1000训练小时损伤次数", "calc": "损伤次数/训练总小时数×1000", "unit": "次/1000h", "freq": "持续记录", "source": "训练日志、医疗记录", "evidence": "高"},
            {"name": "训练可用率", "definition": "可正常训练天数占比", "calc": "实际训练天数/计划训练天数×100%", "unit": "%", "freq": "每周", "source": "训练日志", "evidence": "高"},
        ],
        "关节活动度": [
            {"name": "踝关节背屈活动度", "definition": "负重弓步测试膝触墙最大距离", "calc": "脚距墙面距离，弓步推膝触墙", "unit": "cm", "freq": "每4周", "source": "卷尺测量", "evidence": "中"},
            {"name": "髋关节屈曲活动度", "definition": "Thomas测试角度", "calc": "仰卧Thomas测试，测角仪测量", "unit": "度", "freq": "每4周", "source": "测角仪", "evidence": "中"},
        ],
        "不对称性": [
            {"name": "单腿纵跳不对称性", "definition": "左右腿单腿纵跳高度差异", "calc": "(左-右)/(max(左,右))×100%", "unit": "%", "freq": "每4周", "source": "测力台/Optojump", "evidence": "中"},
            {"name": "单腿等长力量不对称性", "definition": "左右腿膝伸展最大等长力量差异", "calc": "(左-右)/(max(左,右))×100%", "unit": "%", "freq": "每6周", "source": "等长测力计", "evidence": "中"},
        ],
        "跑步技术": [
            {"name": "步频", "definition": "每分钟步数", "calc": "视频分析或可穿戴设备计数", "unit": "spm", "freq": "每月", "source": "视频分析/可穿戴设备", "evidence": "中"},
            {"name": "触地时间", "definition": "每步着地时间", "calc": "可穿戴设备或高速摄像测量", "unit": "ms", "freq": "每月", "source": "可穿戴设备/高速摄像", "evidence": "中"},
        ],
        "配速策略": [
            {"name": "分段配速偏差", "definition": "各200m分段与目标配速的平均偏差", "calc": "|实际分段-目标分段|的平均值", "unit": "s", "freq": "每场比赛", "source": "比赛计时数据", "evidence": "中"},
        ],
    },
}


def get_kpi_template(sport_type: str) -> dict:
    """Return KPI templates for a given sport."""
    return KPI_TEMPLATES.get(sport_type, {})


def generate_kpis_for_determinants(
    db: Session,
    project_id: int,
    sport_type: str,
) -> list[dict]:
    """
    Generate KPIs by matching determinants with built-in KPI templates.
    For each determinant, creates associated KPIs and returns them.
    """
    templates = get_kpi_template(sport_type)
    determinants = crud.get_determinants(db, project_id)

    # Map determinant names to their IDs
    det_map = {d.name: d.id for d in determinants}

    created = []
    for det_name, kpi_list in templates.items():
        det_id = det_map.get(det_name)
        for kpi in kpi_list:
            obj = crud.create_kpi(db, project_id, {
                "name": kpi["name"],
                "determinant_id": det_id,
                "definition": kpi.get("definition", ""),
                "calculation_method": kpi.get("calc", ""),
                "unit": kpi.get("unit", ""),
                "measurement_frequency": kpi.get("freq", ""),
                "data_source": kpi.get("source", ""),
                "evidence_level": kpi.get("evidence", "中"),
                "category": det_name,
            })
            created.append({
                "id": obj.id,
                "name": obj.name,
                "unit": obj.unit,
                "determinant": det_name,
            })

    return created


def generate_kpi_for_category(
    db: Session,
    project_id: int,
    category: str,
    sub_factors: list[str],
) -> list[dict]:
    """
    Generate KPI candidates for a category based on its sub-factors.
    This is the intelligent counterpart — in a real LLM-powered system,
    this would call an LLM to reason about appropriate KPIs.
    For MVP, we use lookup-based logic.
    """
    generated = []
    # Standard KPI patterns per category
    category_patterns = {
        "生理要求": [
            {"name_suffix": "峰值", "unit": "", "calc": "最大努力测试中的最大值"},
            {"name_suffix": "阈值", "unit": "", "calc": "对应代谢拐点的测量值"},
            {"name_suffix": "经济性", "unit": "", "calc": "单位距离/负荷的消耗比"},
        ],
        "技术要求": [
            {"name_suffix": "成功率", "unit": "%", "calc": "成功执行次数/总执行次数×100%"},
            {"name_suffix": "完成速度", "unit": "s", "calc": "完成规定技术动作的时间"},
            {"name_suffix": "质量评分", "unit": "分", "calc": "教练员根据技术标准评分"},
        ],
        "战术要求": [
            {"name_suffix": "执行准确率", "unit": "%", "calc": "正确战术选择/总战术决策×100%"},
            {"name_suffix": "决策速度", "unit": "s", "calc": "从情境触发到决策执行的时间"},
        ],
        "心理技能": [
            {"name_suffix": "评分", "unit": "分", "calc": "标准化心理量表得分"},
            {"name_suffix": "反应时间", "unit": "ms", "calc": "刺激呈现到反应的时间"},
        ],
        "健康": [
            {"name_suffix": "发生率", "unit": "次/1000h", "calc": "事件次数/暴露时间×1000"},
            {"name_suffix": "评分", "unit": "分", "calc": "标准化评估量表得分"},
            {"name_suffix": "不对称性", "unit": "%", "calc": "双侧差异百分比"},
        ],
    }

    patterns = category_patterns.get(category, [
        {"name_suffix": "值", "unit": "", "calc": "直接测量值"},
    ])

    for factor in sub_factors:
        for pat in patterns[:1]:  # One KPI per factor for MVP
            obj = crud.create_kpi(db, project_id, {
                "name": f"{factor}{pat['name_suffix']}",
                "category": category,
                "definition": f"衡量{factor}的{pat['name_suffix']}指标",
                "calculation_method": pat["calc"],
                "unit": pat["unit"],
                "evidence_level": "低",
            })
            generated.append({"id": obj.id, "name": obj.name})

    return generated
