"""
Performance model builder.

Builds a deterministic (hierarchical) performance model for a given sport.
The model links PO → Determinants → Sub-factors → Training interventions → KPIs.
"""

from sqlalchemy.orm import Session
from app import crud

# ── Built-in sport templates ───────────────────────────────────

SPORT_TEMPLATES = {
    "Athletics - 800m": {
        "categories": {
            "生理要求": {
                "importance": "关键",
                "factors": [
                    {"name": "有氧能力", "description": "最大摄氧量和有氧代谢效率，决定运动员的氧气输送和利用能力"},
                    {"name": "无氧能力", "description": "无氧糖酵解能力，决定运动员在冲刺和加速阶段的能量供应"},
                    {"name": "冲刺能力", "description": "最大冲刺速度和短距离爆发力，决定终点冲刺能力"},
                    {"name": "缓冲能力", "description": "乳酸缓冲和清除能力，影响中后程降速幅度"},
                    {"name": "无氧速度储备", "description": "最大速度与VO2max速度之间的差距，反映速度能力储备"},
                    {"name": "肌腱组织弹性", "description": "下肢肌腱的弹性回缩能力，影响跑步经济性"},
                ],
            },
            "健康": {
                "importance": "重要",
                "factors": [
                    {"name": "下肢损伤风险", "description": "腘绳肌、跟腱、足底筋膜等下肢常见损伤风险"},
                    {"name": "腰部损伤风险", "description": "核心稳定性不足导致的腰部损伤风险"},
                    {"name": "上呼吸道健康", "description": "高强度训练对免疫系统的抑制及上呼吸道感染风险"},
                    {"name": "人体测量数据", "description": "身高、体重、体成分等基础数据对运动表现的影响"},
                    {"name": "关节活动度", "description": "髋、膝、踝关节活动范围对跑步效率的影响"},
                    {"name": "不对称性", "description": "左右侧力量、柔韧性、协调性不对称对损伤风险的影响"},
                ],
            },
            "技术要求": {
                "importance": "中等",
                "factors": [
                    {"name": "跑步技术", "description": "步频、步幅、着地方式、摆臂等技术要素"},
                    {"name": "配速策略", "description": "比赛中各分段速度的分配和控制能力"},
                ],
            },
            "战术要求": {
                "importance": "中等",
                "factors": [
                    {"name": "比赛位置选择", "description": "根据对手和自身特点选择内侧/外侧、跟随/领跑的战术"},
                    {"name": "终点冲刺时机", "description": "选择最优冲刺点的决策能力"},
                ],
            },
            "心理技能": {
                "importance": "重要",
                "factors": [
                    {"name": "比赛焦虑管理", "description": "赛前和赛中焦虑水平的调节能力"},
                    {"name": "疼痛耐受", "description": "中距离跑特有的酸性环境疼痛耐受能力"},
                    {"name": "注意力稳定性", "description": "全赛程保持战术专注的能力"},
                ],
            },
            "比赛规则": {
                "importance": "基本",
                "factors": [
                    {"name": "世界田径规则", "description": "起跑规则、赛道规则、犯规判罚、抗议程序等"},
                    {"name": "选拔标准", "description": "全国锦标赛、国际赛事的参赛达标标准"},
                ],
            },
        },
    },
}


def get_template(sport_type: str) -> dict | None:
    """Look up a built-in template for the sport."""
    return SPORT_TEMPLATES.get(sport_type)


def build_determinants_from_template(
    db: Session, project_id: int, sport_type: str
) -> list[dict]:
    """
    Build the performance determinant hierarchy from a built-in template.
    Returns the created determinants as dicts.
    """
    template = get_template(sport_type)
    if not template:
        return []

    created = []
    for cat_name, cat_data in template["categories"].items():
        # Create category root
        root = crud.create_determinant(db, project_id, {
            "category": cat_name,
            "name": cat_name,
            "description": f"{sport_type} 项目的{cat_name}",
            "importance": cat_data["importance"],
            "evidence_level": "中",
            "source_summary": "运动科学文献 + 教练经验",
        })
        created.append(root)

        for factor in cat_data["factors"]:
            child = crud.create_determinant(db, project_id, {
                "parent_id": root.id,
                "category": cat_name,
                "name": factor["name"],
                "description": factor.get("description", ""),
                "importance": "medium",
                "evidence_level": "中",
                "source_summary": "",
            })
            created.append(child)

    return created


def build_interventions_from_template(
    db: Session, project_id: int, sport_type: str
) -> list[dict]:
    """Seed standard interventions for the sport."""
    interventions_map = {
        "Athletics - 800m": [
            {"name": "长距离慢跑 (LSD)", "type": "训练", "desc": "发展有氧基础，每周1-2次，心率控制在Zone 2", "target": "有氧能力"},
            {"name": "节奏跑 (Tempo Run)", "type": "训练", "desc": "提升乳酸阈速度，每周1次，配速约比赛配速+10-15秒/400m", "target": "缓冲能力"},
            {"name": "高强度间歇训练 (HIIT)", "type": "训练", "desc": "提升VO2max和最大速度，如8×400m @ 目标比赛配速，间歇90秒", "target": "无氧能力"},
            {"name": "短距离冲刺训练", "type": "训练", "desc": "提升最大速度和神经肌肉募集，如6×60m 最大冲刺", "target": "冲刺能力"},
            {"name": "高原训练", "type": "训练", "desc": "提高红细胞容量和有氧能力，2-4周高原训练营", "target": "有氧能力"},
            {"name": "力量训练 (下肢)", "type": "训练", "desc": "深蹲、硬拉、弓步蹲等，每周2次，提升力量输出和损伤预防", "target": "下肢损伤风险"},
            {"name": "核心稳定性训练", "type": "训练", "desc": "平板支撑、桥式、旋转抗阻等，每周3次", "target": "腰部损伤风险"},
            {"name": "柔韧性与活动度训练", "type": "训练", "desc": "动态拉伸+静态拉伸+泡沫轴，每日进行", "target": "关节活动度"},
            {"name": "跑步技术训练", "type": "技术", "desc": "步频优化、着地模式改进、视频分析反馈", "target": "跑步技术"},
            {"name": "恢复策略", "type": "恢复", "desc": "冷热交替浴、压缩服装、营养补充、睡眠优化", "target": "恢复"},
        ],
    }

    items = interventions_map.get(sport_type, [])
    created = []
    for item in items:
        obj = crud.create_intervention(db, project_id, {
            "name": item["name"],
            "intervention_type": item["type"],
            "description": item["desc"],
            "status": "planned",
        })
        created.append({"id": obj.id, "name": obj.name})
    return created
