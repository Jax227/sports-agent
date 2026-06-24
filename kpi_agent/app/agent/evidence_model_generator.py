"""
Evidence-based performance model generator.

Replaces hardcoded templates with literature-driven model generation:
1. Search narrative reviews for sport demands
2. Search fitness testing protocols
3. Search meta-analyses for performance determinants
4. Extract structured determinants, KPIs, and interventions from search results
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Optional

# Add sports_science_agent to path for PubMed client.
# IMPORTANT: use append, NOT insert(0) — sports_science_agent/app.py would
# shadow kpi_agent/app/ if placed at the front of sys.path.
SPORTS_AGENT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "sports_science_agent"
if str(SPORTS_AGENT_PATH) not in sys.path:
    sys.path.append(str(SPORTS_AGENT_PATH))

# ── Chinese → English sport name mapping ─────────────────────
# PubMed is an English database; Chinese sport names return zero relevant results.
# This table maps Chinese sport names to their PubMed-searchable English equivalents.

SPORT_NAME_MAP = {
    # Athletics
    "田径": "athletics OR track and field",
    "短跑": "sprinting OR sprint running",
    "100米": "100m sprint OR 100 meter sprint",
    "200米": "200m sprint OR 200 meter sprint",
    "400米": "400m running OR 400 meter",
    "800米": "800m running OR 800 meter OR middle distance running",
    "800米跑": "800m running OR 800 meter OR middle distance running",
    "1500米": "1500m running OR 1500 meter OR middle distance running",
    "中长跑": "middle distance running OR 1500m",
    "5000米": "5000m running OR 5000 meter OR long distance running",
    "10000米": "10000m running OR 10000 meter OR long distance running",
    "马拉松": "marathon running OR marathon",
    "长跑": "long distance running OR marathon",
    "跨栏": "hurdles OR hurdle running",
    "110米栏": "110m hurdles OR 110 meter hurdles",
    "400米栏": "400m hurdles OR 400 meter hurdles",
    "跳高": "high jump",
    "撑竿跳高": "pole vault",
    "跳远": "long jump",
    "三级跳远": "triple jump",
    "铅球": "shot put",
    "铁饼": "discus throw",
    "标枪": "javelin throw",
    "链球": "hammer throw",
    "十项全能": "decathlon",
    "七项全能": "heptathlon",
    "竞走": "race walking",
    "接力": "relay running OR 4x100m relay",

    # Swimming
    "游泳": "swimming OR competitive swimming",
    "自由泳": "freestyle swimming OR front crawl",
    "100米自由泳": "100m freestyle OR 100 meter freestyle",
    "200米自由泳": "200m freestyle",
    "400米自由泳": "400m freestyle",
    "仰泳": "backstroke swimming",
    "蛙泳": "breaststroke swimming",
    "蝶泳": "butterfly swimming",
    "混合泳": "individual medley OR medley swimming",

    # Diving
    "跳水": "diving OR springboard diving",

    # Water polo
    "水球": "water polo",

    # Synchronized swimming / Artistic swimming
    "花样游泳": "artistic swimming OR synchronized swimming",
    "艺术游泳": "artistic swimming OR synchronized swimming",

    # Gymnastics
    "体操": "gymnastics OR artistic gymnastics",
    "竞技体操": "artistic gymnastics",
    "自由体操": "floor exercise gymnastics",
    "鞍马": "pommel horse",
    "吊环": "still rings OR gymnastics rings",
    "跳马": "vault gymnastics",
    "双杠": "parallel bars",
    "单杠": "horizontal bar OR high bar",
    "平衡木": "balance beam",
    "高低杠": "uneven bars",
    "蹦床": "trampoline",

    # Rhythmic gymnastics
    "艺术体操": "rhythmic gymnastics",

    # Figure skating
    "花样滑冰": "figure skating",
    "花滑": "figure skating",
    "冰舞": "ice dance OR ice dancing",

    # Speed skating
    "速度滑冰": "speed skating OR long track speed skating",
    "速滑": "speed skating",
    "短道速滑": "short track speed skating",

    # Skiing
    "滑雪": "skiing OR alpine skiing",
    "高山滑雪": "alpine skiing",
    "越野滑雪": "cross country skiing",
    "跳台滑雪": "ski jumping",
    "自由式滑雪": "freestyle skiing",
    "单板滑雪": "snowboarding",


    # Curling
    "冰壶": "curling",

    # Cycling
    "自行车": "cycling OR competitive cycling",
    "公路自行车": "road cycling OR road bicycle racing",
    "场地自行车": "track cycling OR velodrome cycling",
    "山地自行车": "mountain biking",
    "小轮车": "BMX racing OR BMX cycling",

    # Rowing / Canoe / Kayak
    "赛艇": "rowing",
    "皮划艇": "kayaking OR canoeing",
    "划艇": "canoeing",
    "皮艇": "kayaking",

    # Sailing
    "帆船": "sailing OR yacht racing",

    # Triathlon
    "铁人三项": "triathlon",
    "铁三": "triathlon",

    # Modern pentathlon
    "现代五项": "modern pentathlon",

    # Shooting / Archery
    "射击": "shooting sport OR Olympic shooting",
    "射箭": "archery",

    # Fencing
    "击剑": "fencing",

    # Equestrian
    "马术": "equestrian OR equestrian sport",

    # Weightlifting / Powerlifting
    "举重": "weightlifting OR Olympic weightlifting",
    "力量举": "powerlifting",

    # Combat sports
    "柔道": "judo",
    "跆拳道": "taekwondo",
    "拳击": "boxing",
    "摔跤": "wrestling OR Olympic wrestling",
    "古典式摔跤": "Greco Roman wrestling",
    "自由式摔跤": "freestyle wrestling",
    "空手道": "karate",
    "武术": "wushu OR Chinese martial arts",
    "散打": "sanda OR Chinese kickboxing",

    # Ball sports
    "足球": "soccer OR football",
    "篮球": "basketball",
    "排球": "volleyball",
    "沙滩排球": "beach volleyball",
    "手球": "handball OR team handball",
    "乒乓球": "table tennis",
    "羽毛球": "badminton",
    "网球": "tennis",
    "棒球": "baseball",
    "垒球": "softball",
    "曲棍球": "field hockey",
    "橄榄球": "rugby OR rugby union OR rugby league",
    "高尔夫": "golf",
    "板球": "cricket",
    "壁球": "squash",

    # Other
    "攀岩": "sport climbing OR rock climbing OR competition climbing",
    "滑板": "skateboarding",
    "冲浪": "surfing",
    "霹雳舞": "breaking OR breakdancing",
    "街舞": "breaking OR breakdancing OR hip hop dance",
    "啦啦队": "cheerleading",
    "健美": "bodybuilding",
    "健美操": "aerobics OR sport aerobics",
    "体育舞蹈": "dancesport OR competitive ballroom dancing",
    "轮滑": "roller skating OR inline skating",
    "滑冰": "ice skating OR speed skating",
    "极限运动": "extreme sports OR action sports",
}


def _contains_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(re.search(r'[一-鿿]', text))


def _resolve_sport_terms(sport_name: str, sport_name_en: str = "") -> list[str]:
    """Resolve sport name into PubMed-searchable English terms.

    Strategy:
    1. If user provides English name, use it directly
    2. If Chinese name matches our mapping table, use the mapped English terms
    3. If Chinese name is a substring match in the mapping keys, use that
    4. Fallback: try LLM translation (handled by caller)
    5. Last resort: return empty list (caller should warn user)
    """
    terms = []

    # User-provided English name is gold
    if sport_name_en and not _contains_chinese(sport_name_en):
        terms.append(sport_name_en.strip())

    # Try mapping table for Chinese input
    if _contains_chinese(sport_name) or not terms:
        # Exact match
        if sport_name in SPORT_NAME_MAP:
            mapped = SPORT_NAME_MAP[sport_name]
            if mapped not in terms:
                terms.append(mapped)
        else:
            # Partial match — check if sport_name contains any key
            for cn_key, en_val in SPORT_NAME_MAP.items():
                if cn_key in sport_name or sport_name in cn_key:
                    if en_val not in terms:
                        terms.append(en_val)
                    break

    # If still no terms and it's English-looking, use as-is
    if not terms and not _contains_chinese(sport_name):
        terms.append(sport_name.strip())

    return terms


def _translate_sport_with_llm(sport_name: str) -> str:
    """Use DeepSeek to translate a Chinese sport name to PubMed search terms."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return ""

    import requests
    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-v4-pro",
                "messages": [
                    {"role": "system", "content": (
                        "You are a sports science search specialist. "
                        "Translate the given Chinese sport name to PubMed-searchable English terms. "
                        "Return ONLY the English search terms, using OR between synonyms when helpful. "
                        "No explanation, no markdown, just the terms. "
                        "Example input: '花样滑冰' → output: 'figure skating'"
                        "Example input: '短道速滑' → output: 'short track speed skating'"
                    )},
                    {"role": "user", "content": sport_name},
                ],
                "temperature": 0.1,
                "max_tokens": 128,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"].strip()
            if result and len(result) < 200:
                return result
    except Exception:
        pass
    return ""


def build_search_queries(sport_name: str, sport_name_en: str = "") -> dict:
    """Build 3 targeted PubMed queries for a sport.

    Auto-resolves Chinese sport names to English PubMed terms via:
    1. Built-in mapping table (100+ sports)
    2. User-provided English name
    3. LLM translation fallback
    """
    sport_terms = _resolve_sport_terms(sport_name, sport_name_en)

    # If no terms resolved and it's Chinese, try LLM translation
    if not sport_terms and _contains_chinese(sport_name):
        llm_translation = _translate_sport_with_llm(sport_name)
        if llm_translation:
            sport_terms = [llm_translation]

    # Build the sport term clause
    if sport_terms:
        # Each term may contain OR-separated synonyms, so we wrap each and OR them
        term_clauses = []
        for t in sport_terms:
            # If the term itself contains OR, it's already a disjunction of synonyms
            if " OR " in t.upper():
                # Split and quote each alternative
                alternatives = [alt.strip().strip('"') for alt in re.split(r'\s+OR\s+', t, flags=re.IGNORECASE)]
                term_clauses.append(" OR ".join(f'"{a}"[Title/Abstract]' for a in alternatives if a))
            else:
                term_clauses.append(f'"{t.strip()}"[Title/Abstract]')
        term_query = " OR ".join(f"({c})" for c in term_clauses if c)
    else:
        # Last resort: use the raw sport name (will likely find nothing on PubMed)
        term_query = f'"{sport_name}"[Title/Abstract]'

    return {
        "narrative_review": (
            f'({term_query}) AND '
            f'("narrative review"[Publication Type] OR "review"[Publication Type] OR '
            f'"physiological demands"[Title/Abstract] OR "match demands"[Title/Abstract] OR '
            f'"competition demands"[Title/Abstract] OR "sport demands"[Title/Abstract] OR '
            f'"activity profile"[Title/Abstract] OR "performance analysis"[Title/Abstract])'
        ),
        "fitness_test": (
            f'({term_query}) AND '
            f'("fitness test"[Title/Abstract] OR "fitness testing"[Title/Abstract] OR '
            f'"field test"[Title/Abstract] OR "physical test"[Title/Abstract] OR '
            f'"assessment battery"[Title/Abstract] OR "performance test"[Title/Abstract] OR '
            f'"testing protocol"[Title/Abstract] OR "sport-specific"[Title/Abstract])'
        ),
        "meta_analysis": (
            f'({term_query}) AND '
            f'(meta-analysis[Publication Type] OR systematic review[Publication Type] OR '
            f'"performance determinant"[Title/Abstract] OR "predictor"[Title/Abstract] OR '
            f'"key factor"[Title/Abstract] OR "correlate"[Title/Abstract] OR '
            f'"talent identification"[Title/Abstract])'
        ),
    }


# ── Search ─────────────────────────────────────────────────────

def search_evidence(sport_name: str, sport_name_en: str = "", max_results_per_query: int = 8) -> dict:
    """Execute 3 PubMed searches and return aggregated results.

    Auto-resolves Chinese sport names to English PubMed terms.
    """
    from src.pubmed_client import search_pubmed

    resolved_terms = _resolve_sport_terms(sport_name, sport_name_en)
    queries = build_search_queries(sport_name, sport_name_en)
    results = {}

    for query_type, query in queries.items():
        try:
            papers = search_pubmed(query, max_results=max_results_per_query)
            results[query_type] = papers
        except Exception:
            results[query_type] = []

    return {
        "sport_name": sport_name,
        "sport_name_resolved": resolved_terms if resolved_terms else [sport_name],
        "queries": queries,
        "results": results,
        "summary": {
            "narrative_review_count": len(results.get("narrative_review", [])),
            "fitness_test_count": len(results.get("fitness_test", [])),
            "meta_analysis_count": len(results.get("meta_analysis", [])),
        },
    }


# ── LLM Extraction ─────────────────────────────────────────────

def _get_llm_api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "")


def _extract_with_llm(search_results: dict, sport_name: str) -> Optional[dict]:
    """Use DeepSeek LLM to extract structured performance model from search results."""
    api_key = _get_llm_api_key()
    if not api_key:
        return None

    # Build paper summaries for LLM
    papers_summary = []
    for query_type, papers in search_results.get("results", {}).items():
        type_label = {"narrative_review": "运动需求分析", "fitness_test": "体能测试", "meta_analysis": "元分析/系统综述"}.get(query_type, query_type)
        for p in papers[:5]:
            papers_summary.append({
                "title": p.get("title", ""),
                "abstract": (p.get("abstract", "") or "")[:600],
                "keywords": p.get("keywords", []),
                "year": p.get("year", ""),
                "query_type": type_label,
            })

    if not papers_summary:
        return None

    papers_text = "\n\n".join(
        f"### Paper {i+1} [{p['query_type']}]\nTitle: {p['title']}\nYear: {p['year']}\nAbstract: {p['abstract']}"
        for i, p in enumerate(papers_summary)
    )

    system_prompt = (
        "You are a sports science expert specializing in performance modeling. "
        "Based on the provided research papers, extract a structured performance model "
        "for the specified sport. Output ONLY valid JSON (no markdown, no explanation).\n\n"
        "The performance model MUST include these categories where evidence exists:\n"
        "- 生理要求 (physiological): energy systems, strength, speed, endurance, power, etc.\n"
        "- 健康 (health): injury risks, body composition, joint health, asymmetries\n"
        "- 技术要求 (technical): sport-specific techniques, biomechanics, movement patterns\n"
        "- 战术要求 (tactical): pacing, strategy, decision-making, positioning\n"
        "- 心理技能 (psychological): anxiety, concentration, mental toughness, confidence\n"
        "- 比赛规则 (rules): competition rules, qualification standards\n\n"
        "For EACH determinant include: name (Chinese), description, importance (关键/重要/中等/基本), "
        "evidence_level (高/中/低/专家经验).\n"
        "Generate specific KPIs with: name, unit, measurement protocol, testing frequency.\n"
        "Generate interventions linked to determinants.\n\n"
        "IMPORTANT: Only include items supported by the papers. If no evidence for a category, "
        "include it with an empty determinants list. For determinants without KPI evidence, "
        "suggest reasonable KPIs based on sports science standards and mark evidence_level as '专家经验'.\n\n"
        "Format:\n"
        '{"categories": {"生理要求": {"importance": "关键", "determinants": ['
        '{"name": "有氧能力", "description": "...", "importance": "关键", "evidence_level": "高"}, ...]}, ...}, '
        '"kpis": [{"name": "VO2max", "determinant": "有氧能力", "unit": "ml/kg/min", '
        '"protocol": "递增负荷跑台测试", "frequency": "每6-8周", "evidence_level": "高"}, ...], '
        '"interventions": [{"name": "高强度间歇训练", "type": "训练", '
        '"target_determinant": "有氧能力", "description": "...", "evidence_level": "高"}, ...], '
        '"model_summary": "brief summary of the model based on literature"}'
    )

    import requests
    try:
        session = requests.Session()
        session.trust_env = False

        resp = session.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-v4-pro",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Sport: {sport_name}\n\nResearch Papers:\n{papers_text}"},
                ],
                "temperature": 0.1,
                "max_tokens": 8192,
            },
            timeout=120,
        )

        if resp.status_code != 200:
            return None

        content = resp.json()["choices"][0]["message"]["content"].strip()

        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                fixed = re.sub(r',\s*(\}|\])', r'\1', json_match.group(0))
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass
        return None
    except Exception:
        return None


# ── Heuristic Extraction (no LLM fallback) ─────────────────────

def _count_matches(text_lower: str, keywords: list[str]) -> int:
    return sum(text_lower.count(kw.lower()) for kw in keywords)


def _scan_physiological(all_text: str, all_lower: str) -> list[dict]:
    patterns = {
        "有氧能力": (["vo2max", "vo2 max", "aerobic capacity", "aerobic power", "maximal oxygen uptake", "cardiorespiratory", "endurance capacity", "aerobic endurance"], "关键"),
        "无氧能力": (["anaerobic capacity", "anaerobic power", "glycolytic", "anaerobic glycolysis", "anaerobic endurance", "maximal anaerobic"], "关键"),
        "速度素质": (["sprint speed", "maximum speed", "acceleration", "velocity", "running speed", "sprint ability", "maximal velocity"], "关键"),
        "力量素质": (["maximal strength", "muscle strength", "force production", "peak force", "strength level", "1rm", "isometric strength"], "重要"),
        "爆发力": (["power output", "explosive power", "rate of force development", "jump height", "peak power", "explosive strength", "vertical jump"], "重要"),
        "速度耐力": (["speed endurance", "repeated sprint ability", "RSA", "repeated sprint", "intermittent"], "重要"),
        "柔韧性与活动度": (["flexibility", "mobility", "range of motion", "joint range", "stretching", "flexibility training"], "中等"),
        "敏捷性": (["agility", "change of direction", "COD", "maneuverability", "agility test"], "中等"),
        "平衡能力": (["balance", "postural control", "stability", "proprioception"], "中等"),
        "协调性": (["coordination", "motor control", "neuromuscular control", "movement quality", "motor skill"], "中等"),
        "乳酸代谢": (["lactate threshold", "anaerobic threshold", "blood lactate", "lactate accumulation", "ventilatory threshold", "onset of blood lactate"], "关键"),
        "跑步经济性": (["running economy", "movement economy", "energy cost", "oxygen cost", "mechanical efficiency", "metabolic cost"], "重要"),
        "无氧速度储备": (["anaerobic speed reserve", "ASR", "speed reserve", "maximal sprinting speed"], "中等"),
        "缓冲能力": (["buffering capacity", "lactate buffering", "ph regulation", "acid-base", "muscle buffer"], "中等"),
        "肌肉耐力": (["muscular endurance", "muscle endurance", "strength endurance", "local endurance"], "中等"),
        "核心稳定性": (["core stability", "core strength", "trunk stability", "core endurance", "core muscle"], "重要"),
        "反应速度": (["reaction time", "response time", "reactivity", "reactive agility", "reactive strength"], "中等"),
    }
    return _match_determinants(all_text, all_lower, patterns)


def _scan_health(all_text: str, all_lower: str) -> list[dict]:
    patterns = {
        "下肢损伤风险": (["lower limb injury", "hamstring injury", "acl injury", "ankle sprain", "groin injury", "knee injury", "lower extremity injury", "injury risk factor", "injury prevention"], "关键"),
        "过度使用损伤": (["overuse injury", "tendinopathy", "stress fracture", "shin splint", "overuse", "chronic injury", "tendon injury"], "重要"),
        "身体成分": (["body composition", "body fat", "lean body mass", "fat mass", "anthropometry", "body mass", "somatotype", "body size"], "重要"),
        "关节活动度": (["range of motion", "joint mobility", "joint flexibility", "hip mobility", "ankle mobility", "shoulder mobility"], "中等"),
        "不对称性": (["asymmetry", "bilateral deficit", "limb asymmetry", "inter-limb", "bilateral difference", "symmetry", "imbalance"], "重要"),
        "骨密度": (["bone density", "bone mineral density", "BMD", "bone health", "bone mass", "osteoporosis"], "中等"),
        "免疫功能": (["immune function", "upper respiratory", "illness", "infection", "immune system", "salivary iga"], "中等"),
        "睡眠与恢复": (["sleep quality", "sleep duration", "recovery", "fatigue", "sleep hygiene", "circadian"], "重要"),
    }
    return _match_determinants(all_text, all_lower, patterns)


def _scan_technical(all_text: str, all_lower: str) -> list[dict]:
    patterns = {
        "运动技术": (["technique", "technical skill", "biomechanics", "movement pattern", "kinematics", "kinetics", "skill execution"], "中等"),
        "步频与步幅": (["stride frequency", "stride length", "cadence", "step rate", "step length", "stride pattern"], "中等"),
        "触地时间": (["ground contact time", "contact time", "GCT", "stance time", "support time"], "中等"),
        "着地模式": (["foot strike", "landing pattern", "foot strike pattern", "rearfoot", "forefoot", "midfoot"], "低"),
        "动作经济性": (["movement economy", "efficiency", "energy cost of locomotion", "biomechanical efficiency"], "重要"),
        "关节角度": (["joint angle", "knee angle", "hip angle", "ankle angle", "joint kinematics"], "低"),
        "力量传递效率": (["force transfer", "kinetic chain", "force transmission", "movement efficiency", "energy transfer"], "中等"),
    }
    return _match_determinants(all_text, all_lower, patterns)


def _scan_tactical(all_text: str, all_lower: str) -> list[dict]:
    patterns = {
        "配速策略": (["pacing strategy", "pacing", "race strategy", "pacing profile", "speed distribution", "pacing pattern"], "中等"),
        "战术决策": (["tactical", "decision making", "strategy", "game plan", "competition strategy", "tactical behavior"], "中等"),
        "位置选择": (["positioning", "position", "track position", "formation", "spatial", "court position"], "低"),
        "时机把握": (["timing", "anticipation", "reaction", "readiness", "preparation"], "中等"),
    }
    return _match_determinants(all_text, all_lower, patterns)


def _scan_psychological(all_text: str, all_lower: str) -> list[dict]:
    patterns = {
        "焦虑管理": (["anxiety", "competitive anxiety", "stress management", "anxiety management", "pre-competition anxiety", "state anxiety"], "重要"),
        "注意力": (["attention", "concentration", "focus", "attentional control", "attentional focus", "concentration skills"], "重要"),
        "自信心": (["self-confidence", "self-efficacy", "confidence", "sport confidence", "self-belief"], "重要"),
        "心理韧性": (["mental toughness", "resilience", "coping", "adversity", "mental resilience", "hardiness", "perseverance"], "关键"),
        "动机": (["motivation", "goal orientation", "achievement motivation", "intrinsic motivation", "self-determination", "motivation climate"], "中等"),
        "心理技能": (["mental skills", "psychological skills", "mental training", "imagery", "self-talk", "goal setting", "relaxation"], "重要"),
    }
    return _match_determinants(all_text, all_lower, patterns)


def _match_determinants(all_text: str, all_lower: str, patterns: dict) -> list[dict]:
    found = []
    for name, (keywords, default_importance) in patterns.items():
        score = _count_matches(all_lower, keywords)
        if score >= 2:
            best_kw = max(keywords, key=lambda k: all_lower.count(k.lower()))
            evidence_level = "高" if score >= 8 else "中" if score >= 4 else "低"
            found.append({
                "name": name,
                "description": f"文献中{score}次提及 {best_kw} 等相关概念",
                "importance": "关键" if score >= 8 else "重要" if score >= 6 else default_importance,
                "evidence_level": evidence_level,
                "mention_count": score,
            })
    found.sort(key=lambda x: x.get("mention_count", 0), reverse=True)
    return found[:10]


# ── KPI generation from determinants ───────────────────────────

KPI_TEMPLATES_BY_DETERMINANT = {
    "有氧能力": [
        {"name": "VO2max", "unit": "ml/kg/min", "protocol": "递增负荷跑台测试，直接气体分析", "frequency": "每6-8周", "evidence_level": "高"},
        {"name": "vVO2max", "unit": "km/h", "protocol": "达到VO2max时的最低速度", "frequency": "每6-8周", "evidence_level": "高"},
    ],
    "无氧能力": [
        {"name": "最大血乳酸", "unit": "mmol/L", "protocol": "全力运动后血乳酸峰值测量", "frequency": "每4-6周", "evidence_level": "高"},
        {"name": "Wingate平均功率", "unit": "W/kg", "protocol": "30秒Wingate测试", "frequency": "每8-12周", "evidence_level": "中"},
    ],
    "速度素质": [
        {"name": "最大冲刺速度", "unit": "m/s", "protocol": "电子计时系统测量最大速度", "frequency": "每2-4周", "evidence_level": "高"},
        {"name": "30m冲刺时间", "unit": "s", "protocol": "静止起跑30m，电子计时", "frequency": "每2-4周", "evidence_level": "高"},
    ],
    "力量素质": [
        {"name": "1RM深蹲", "unit": "kg", "protocol": "标准1RM测试流程", "frequency": "每8-12周", "evidence_level": "高"},
        {"name": "等长最大力量", "unit": "N", "protocol": "等长测力计测量", "frequency": "每6周", "evidence_level": "中"},
    ],
    "爆发力": [
        {"name": "CMJ纵跳高度", "unit": "cm", "protocol": "测力台反向纵跳，3次取最佳", "frequency": "每2-4周", "evidence_level": "高"},
        {"name": "反应力量指数(RSI)", "unit": "m/s", "protocol": "30cm跳深测试", "frequency": "每4-6周", "evidence_level": "中"},
    ],
    "速度耐力": [
        {"name": "重复冲刺递减率", "unit": "%", "protocol": "6×35m冲刺，计算递减百分比", "frequency": "每4周", "evidence_level": "高"},
    ],
    "敏捷性": [
        {"name": "505敏捷测试", "unit": "s", "protocol": "15m跑+180°转身", "frequency": "每4周", "evidence_level": "中"},
        {"name": "T测试", "unit": "s", "protocol": "T形路线多方向跑", "frequency": "每4周", "evidence_level": "中"},
    ],
    "身体成分": [
        {"name": "体脂率", "unit": "%", "protocol": "DXA或皮褶厚度法", "frequency": "每8-12周", "evidence_level": "高"},
        {"name": "去脂体重", "unit": "kg", "protocol": "DXA或生物电阻抗法", "frequency": "每8-12周", "evidence_level": "中"},
    ],
    "乳酸代谢": [
        {"name": "乳酸阈跑速", "unit": "km/h", "protocol": "递增负荷测试，确定4mmol/L拐点", "frequency": "每4-6周", "evidence_level": "高"},
        {"name": "乳酸阈心率", "unit": "bpm", "protocol": "对应乳酸阈的心率值", "frequency": "每4-6周", "evidence_level": "中"},
    ],
    "下肢损伤风险": [
        {"name": "腘绳肌偏心力量", "unit": "N", "protocol": "Nordic Hamstring测试", "frequency": "每4周", "evidence_level": "高"},
        {"name": "损伤发生率", "unit": "次/1000h", "protocol": "损伤次数/训练总小时数×1000", "frequency": "持续记录", "evidence_level": "高"},
    ],
    "不对称性": [
        {"name": "单腿纵跳不对称性", "unit": "%", "protocol": "左右腿CMJ差异百分比", "frequency": "每4周", "evidence_level": "中"},
    ],
    "跑步经济性": [
        {"name": "跑步经济性", "unit": "ml/kg/km", "protocol": "次最大速度稳态耗氧量", "frequency": "每8-12周", "evidence_level": "高"},
    ],
    "核心稳定性": [
        {"name": "核心耐力测试", "unit": "s", "protocol": "平板支撑/侧桥/桥式持续时间", "frequency": "每4周", "evidence_level": "中"},
    ],
    "柔韧性与活动度": [
        {"name": "坐位体前屈", "unit": "cm", "protocol": "标准坐位体前屈测试", "frequency": "每4周", "evidence_level": "中"},
        {"name": "踝关节背屈活动度", "unit": "cm", "protocol": "负重弓步测试膝触墙距离", "frequency": "每4周", "evidence_level": "中"},
    ],
    "平衡能力": [
        {"name": "Y平衡测试", "unit": "cm", "protocol": "Y平衡测试套件，三个方向最大伸展", "frequency": "每4周", "evidence_level": "中"},
    ],
    "睡眠与恢复": [
        {"name": "主观恢复评分", "unit": "分", "protocol": "标准恢复问卷(1-10分)", "frequency": "每日", "evidence_level": "中"},
        {"name": "睡眠时长", "unit": "h", "protocol": "可穿戴设备或睡眠日志", "frequency": "每日", "evidence_level": "中"},
    ],
    "焦虑管理": [
        {"name": "比赛焦虑量表(CSAI-2)", "unit": "分", "protocol": "竞技状态焦虑量表-2", "frequency": "赛前/每季度", "evidence_level": "高"},
    ],
    "心理韧性": [
        {"name": "心理韧性问卷(MTQ)", "unit": "分", "protocol": "心理韧性问卷评估", "frequency": "每季度", "evidence_level": "中"},
    ],
    "配速策略": [
        {"name": "分段配速偏差", "unit": "s", "protocol": "各分段与目标配速的平均偏差", "frequency": "每场比赛", "evidence_level": "中"},
    ],
}


def _generate_kpis_from_determinants(categories: dict) -> list[dict]:
    kpis = []
    for cat_name, cat_data in categories.items():
        for det in cat_data.get("determinants", []):
            det_name = det["name"]
            if det_name in KPI_TEMPLATES_BY_DETERMINANT:
                for tmpl in KPI_TEMPLATES_BY_DETERMINANT[det_name]:
                    kpis.append({
                        "name": tmpl["name"],
                        "determinant": det_name,
                        "category": cat_name,
                        "unit": tmpl["unit"],
                        "protocol": tmpl["protocol"],
                        "frequency": tmpl["frequency"],
                        "evidence_level": tmpl["evidence_level"],
                    })
    return kpis


# ── Intervention generation from determinants ──────────────────

INTERVENTION_TEMPLATES = {
    "有氧能力": [
        {"name": "长距离低强度训练(LSD)", "type": "训练", "description": "Zone 2心率区间长时间持续运动，发展有氧基础"},
        {"name": "高强度间歇训练(HIIT)", "type": "训练", "description": "短时间高强度交替低强度，提升VO2max"},
    ],
    "无氧能力": [
        {"name": "重复冲刺训练(RST)", "type": "训练", "description": "短距离多次冲刺，不完全恢复，提升无氧糖酵解能力"},
    ],
    "速度素质": [
        {"name": "最大速度冲刺训练", "type": "训练", "description": "充分恢复的最大速度冲刺，如6×60m"},
        {"name": "抗阻冲刺训练", "type": "训练", "description": "上坡跑、雪橇拖拽等抗阻形式冲刺"},
    ],
    "力量素质": [
        {"name": "周期化力量训练", "type": "训练", "description": "包含最大力量、爆发力、肌肉耐力阶段的周期化方案"},
    ],
    "爆发力": [
        {"name": "增强式训练", "type": "训练", "description": "跳深、跳箱、跨栏跳等快速伸缩复合训练"},
        {"name": "奥林匹克举重训练", "type": "训练", "description": "高翻、抓举等爆发力举重训练"},
    ],
    "速度耐力": [
        {"name": "重复冲刺能力训练", "type": "训练", "description": "模拟比赛节奏的多次冲刺训练，逐渐缩短恢复时间"},
    ],
    "柔韧性与活动度": [
        {"name": "动态柔韧训练", "type": "训练", "description": "训练前动态拉伸，提高关节活动范围"},
        {"name": "筋膜放松", "type": "恢复", "description": "泡沫轴、按摩球等自我筋膜放松"},
    ],
    "下肢损伤风险": [
        {"name": "北欧腘绳肌训练(NHE)", "type": "训练", "description": "Nordic Hamstring Exercise，减少腘绳肌损伤风险"},
        {"name": "FIFA 11+损伤预防计划", "type": "训练", "description": "包含力量、平衡、敏捷的综合损伤预防方案"},
    ],
    "身体成分": [
        {"name": "个体化营养方案", "type": "营养", "description": "基于运动员目标和训练阶段的营养策略"},
    ],
    "核心稳定性": [
        {"name": "核心稳定性训练", "type": "训练", "description": "平板支撑、桥式、抗旋转训练等"},
    ],
    "跑步经济性": [
        {"name": "跑步技术优化训练", "type": "技术", "description": "步频、着地模式优化，视频分析反馈"},
        {"name": "爆发力与增强式训练", "type": "训练", "description": "提升肌腱弹性和力量传递效率"},
    ],
    "心理韧性": [
        {"name": "心理技能训练(PST)", "type": "心理", "description": "目标设定、意象训练、自我对话、放松训练"},
    ],
    "焦虑管理": [
        {"name": "赛前心理准备程序", "type": "心理", "description": "制定个性化赛前routine，包含呼吸控制和正念"},
    ],
    "注意力": [
        {"name": "注意力训练", "type": "心理", "description": "正念训练、注意力网格训练等"},
    ],
    "睡眠与恢复": [
        {"name": "睡眠优化策略", "type": "恢复", "description": "睡眠卫生教育、环境优化、作息管理"},
        {"name": "主动恢复方案", "type": "恢复", "description": "冷热交替浴、压缩服装、营养补充"},
    ],
    "配速策略": [
        {"name": "配速意识训练", "type": "技术", "description": "使用节拍器、视觉反馈进行配速感知训练"},
    ],
}


def _generate_interventions_from_determinants(categories: dict) -> list[dict]:
    interventions = []
    added = set()
    for cat_data in categories.values():
        for det in cat_data.get("determinants", []):
            det_name = det["name"]
            if det_name in INTERVENTION_TEMPLATES:
                for intv in INTERVENTION_TEMPLATES[det_name]:
                    if intv["name"] not in added:
                        added.add(intv["name"])
                        interventions.append({
                            "name": intv["name"],
                            "type": intv["type"],
                            "target_determinant": det_name,
                            "description": intv["description"],
                            "evidence_level": det.get("evidence_level", "中"),
                        })
    return interventions


# ── Paper dedup ────────────────────────────────────────────────

def _dedup_papers(papers: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in papers:
        key = p.get("pmid") or p.get("title", "")[:100]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _collect_papers(search_results: dict) -> list[dict]:
    """Collect and deduplicate all papers from search results."""
    all_papers = []
    for query_type, papers in search_results.get("results", {}).items():
        for p in papers:
            all_papers.append({
                "title": p.get("title", ""),
                "authors": _normalize_authors(p.get("authors", "")),
                "year": p.get("year", ""),
                "journal": p.get("journal", ""),
                "abstract": (p.get("abstract", "") or "")[:500],
                "pmid": p.get("pmid", ""),
                "doi": p.get("doi", ""),
                "url": p.get("url", ""),
                "keywords": p.get("keywords", []),
                "source_type": query_type,
            })
    return _dedup_papers(all_papers)


def _normalize_authors(authors):
    """Convert authors (list or string) to a semicolon-joined string for DB storage."""
    if isinstance(authors, list):
        return "; ".join(authors)
    return authors or ""


# ── Default model (when nothing found) ─────────────────────────

def _build_default_model(sport_name: str) -> dict:
    return {
        "categories": {
            "生理要求": {
                "importance": "关键",
                "determinants": [
                    {"name": "有氧能力", "description": "基础能量代谢能力", "importance": "关键", "evidence_level": "专家经验"},
                    {"name": "无氧能力", "description": "高强度运动能量供应", "importance": "关键", "evidence_level": "专家经验"},
                    {"name": "速度素质", "description": "最大速度和加速度能力", "importance": "关键", "evidence_level": "专家经验"},
                    {"name": "力量素质", "description": "最大力量输出能力", "importance": "重要", "evidence_level": "专家经验"},
                    {"name": "爆发力", "description": "快速力量输出能力", "importance": "重要", "evidence_level": "专家经验"},
                ],
            },
            "健康": {
                "importance": "重要",
                "determinants": [
                    {"name": "下肢损伤风险", "description": "常见运动损伤风险评估", "importance": "重要", "evidence_level": "专家经验"},
                    {"name": "身体成分", "description": "体脂率和肌肉质量", "importance": "中等", "evidence_level": "专家经验"},
                ],
            },
            "比赛规则": {
                "importance": "基本",
                "determinants": [
                    {"name": "比赛规则理解", "description": f"{sport_name}项目比赛规则", "importance": "基本", "evidence_level": "专家经验"},
                ],
            },
        },
        "kpis": [],
        "interventions": [],
        "evidence_sources": [],
        "model_summary": f"未找到足够的 {sport_name} 相关文献，生成了基础模型框架。建议：1) 尝试英文项目名称检索 2) 手动添加证据资料后重新生成",
    }


# ── Heuristic extraction orchestrator ──────────────────────────

def _extract_heuristic(search_results: dict, sport_name: str) -> dict:
    all_text = ""
    for papers in search_results.get("results", {}).values():
        for p in papers:
            title = p.get("title", "")
            abstract = p.get("abstract", "") or ""
            keywords = " ".join(p.get("keywords", []))
            all_text += f" {title} {abstract} {keywords}"

    if len(all_text.strip()) < 200:
        return _build_default_model(sport_name)

    all_lower = all_text.lower()

    categories = {}
    physio = _scan_physiological(all_text, all_lower)
    if physio:
        categories["生理要求"] = {"importance": "关键", "determinants": physio}

    health = _scan_health(all_text, all_lower)
    if health:
        categories["健康"] = {"importance": "重要", "determinants": health}

    tech = _scan_technical(all_text, all_lower)
    if tech:
        categories["技术要求"] = {"importance": "中等", "determinants": tech}

    tact = _scan_tactical(all_text, all_lower)
    if tact:
        categories["战术要求"] = {"importance": "中等", "determinants": tact}

    psych = _scan_psychological(all_text, all_lower)
    if psych:
        categories["心理技能"] = {"importance": "重要", "determinants": psych}

    categories["比赛规则"] = {
        "importance": "基本",
        "determinants": [
            {"name": "比赛规则理解", "description": f"{sport_name}项目比赛规则和裁判标准", "importance": "基本", "evidence_level": "专家经验"},
            {"name": "选拔标准", "description": "各级赛事参赛资格和选拔标准", "importance": "基本", "evidence_level": "专家经验"},
        ],
    }

    kpis = _generate_kpis_from_determinants(categories)
    interventions = _generate_interventions_from_determinants(categories)
    evidence_sources = _collect_papers(search_results)

    return {
        "categories": categories,
        "kpis": kpis,
        "interventions": interventions,
        "evidence_sources": evidence_sources,
        "model_summary": f"从 {len(evidence_sources)} 篇文献中通过关键词匹配提取 {sport_name} 表现模型",
    }


# ── Public API ─────────────────────────────────────────────────

def generate_model(
    sport_name: str,
    sport_name_en: str = "",
    use_llm: bool = True,
    max_results_per_query: int = 8,
) -> dict:
    """
    Full pipeline: search PubMed → extract structured model.

    Args:
        sport_name: Sport name (Chinese or English)
        sport_name_en: English sport name for better PubMed results
        use_llm: Use DeepSeek LLM for extraction (falls back to heuristic)
        max_results_per_query: Max papers per search query

    Returns:
        Dict with categories, kpis, interventions, evidence_sources, search metadata
    """
    search_results = search_evidence(sport_name, sport_name_en, max_results_per_query)

    # Always collect evidence sources from raw search results
    evidence_sources = _collect_papers(search_results)
    resolved_terms = search_results.get("sport_name_resolved", [sport_name])

    # Detect if the sport name needed translation
    was_translated = _contains_chinese(sport_name) and resolved_terms != [sport_name]
    translation_note = ""
    if was_translated:
        translation_note = f"已将「{sport_name}」转换为 PubMed 检索词: {'; '.join(resolved_terms)}"
    elif _contains_chinese(sport_name) and not sport_name_en:
        translation_note = (
            f"⚠️ 未找到「{sport_name}」的英文对应词，PubMed 检索可能返回不相关结果。"
            f"建议输入英文项目名称（如 'figure skating'）以获得更准确的文献。"
        )

    model = None
    extraction_method = "heuristic"
    if use_llm:
        model = _extract_with_llm(search_results, sport_name)
        if model is not None:
            extraction_method = "llm"

    if model is None:
        model = _extract_heuristic(search_results, sport_name)
        extraction_method = "heuristic"

    # If all searches returned zero papers, build a more useful default model
    total_papers = (
        search_results["summary"]["narrative_review_count"]
        + search_results["summary"]["fitness_test_count"]
        + search_results["summary"]["meta_analysis_count"]
    )
    if total_papers == 0:
        model = _build_default_model(sport_name)

    # Always attach full evidence sources (LLM output may not include them)
    model["evidence_sources"] = evidence_sources
    model["search_queries"] = search_results["queries"]
    model["search_summary"] = search_results["summary"]
    model["sport_name"] = sport_name
    model["sport_name_resolved"] = resolved_terms
    model["translation_note"] = translation_note
    model["extraction_method"] = extraction_method

    # Attach paper-to-determinant mapping for transparency
    model["paper_determinant_map"] = _build_paper_determinant_map(
        search_results, model.get("categories", {})
    )

    # Identify categories with no evidence found
    model["empty_categories"] = _identify_empty_categories(
        search_results, model.get("categories", {})
    )

    return model


def _build_paper_determinant_map(search_results: dict, categories: dict) -> list[dict]:
    """Map each paper to the determinants it mentions."""
    mapping = []
    all_papers = _collect_papers(search_results)

    for paper in all_papers:
        title = (paper.get("title", "") or "").lower()
        abstract = (paper.get("abstract", "") or "").lower()
        text = title + " " + abstract

        matched_dets = []
        for cat_name, cat_data in categories.items():
            for det in cat_data.get("determinants", []):
                det_name = det.get("name", "")
                # Check if paper mentions determinant-related terms
                if _paper_mentions_determinant(text, det_name):
                    matched_dets.append({"determinant": det_name, "category": cat_name})

        mapping.append({
            "title": paper.get("title", ""),
            "year": paper.get("year", ""),
            "pmid": paper.get("pmid", ""),
            "source_type": paper.get("source_type", ""),
            "matched_determinants": matched_dets,
            "match_count": len(matched_dets),
        })

    return mapping


def _paper_mentions_determinant(text: str, det_name: str) -> bool:
    """Check if paper text mentions a determinant's related terms."""
    term_map = {
        "有氧能力": ["aerobic", "vo2max", "vo2 max", "cardiorespiratory", "endurance capacity"],
        "无氧能力": ["anaerobic", "glycolytic", "anaerobic power", "anaerobic capacity"],
        "速度素质": ["speed", "sprint", "acceleration", "velocity", "maximal velocity"],
        "力量素质": ["strength", "force", "1rm", "maximal strength", "isometric"],
        "爆发力": ["power", "explosive", "jump", "vertical jump", "rate of force"],
        "速度耐力": ["repeated sprint", "speed endurance", "RSA", "intermittent"],
        "柔韧性与活动度": ["flexibility", "mobility", "range of motion", "stretch"],
        "敏捷性": ["agility", "change of direction", "COD", "maneuver"],
        "平衡能力": ["balance", "postural", "stability", "proprioception"],
        "协调性": ["coordination", "motor control", "neuromuscular", "movement quality"],
        "乳酸代谢": ["lactate", "threshold", "anaerobic threshold", "blood lactate"],
        "跑步经济性": ["running economy", "economy", "energy cost", "oxygen cost", "efficiency"],
        "无氧速度储备": ["anaerobic speed reserve", "ASR", "speed reserve"],
        "缓冲能力": ["buffering", "buffer", "ph regulation", "acid-base"],
        "肌肉耐力": ["muscular endurance", "muscle endurance", "strength endurance"],
        "核心稳定性": ["core stability", "core strength", "trunk", "core muscle"],
        "反应速度": ["reaction time", "response time", "reactivity", "reactive"],
        "下肢损伤风险": ["injury", "hamstring", "acl", "ankle", "knee", "lower extremity"],
        "过度使用损伤": ["overuse", "tendinopathy", "stress fracture", "shin splint"],
        "身体成分": ["body composition", "body fat", "lean mass", "anthropometry", "body mass"],
        "关节活动度": ["range of motion", "joint mobility", "joint flexibility", "ROM"],
        "不对称性": ["asymmetry", "bilateral", "symmetry", "imbalance", "inter-limb"],
        "骨密度": ["bone density", "bone mineral", "BMD", "osteoporosis"],
        "免疫功能": ["immune", "respiratory infection", "salivary iga", "illness"],
        "睡眠与恢复": ["sleep", "recovery", "fatigue", "circadian"],
        "运动技术": ["technique", "technical", "biomechanics", "kinematics", "kinetics"],
        "步频与步幅": ["stride frequency", "stride length", "cadence", "step rate"],
        "触地时间": ["ground contact", "contact time", "GCT", "stance time"],
        "着地模式": ["foot strike", "landing", "rearfoot", "forefoot", "midfoot"],
        "动作经济性": ["movement economy", "efficiency", "energy cost"],
        "关节角度": ["joint angle", "knee angle", "hip angle", "ankle angle"],
        "力量传递效率": ["force transfer", "kinetic chain", "force transmission"],
        "配速策略": ["pacing", "pacing strategy", "race strategy", "pace", "speed distribution"],
        "战术决策": ["tactical", "decision making", "strategy", "game plan"],
        "位置选择": ["positioning", "position", "formation", "spatial"],
        "时机把握": ["timing", "anticipation", "reaction", "readiness"],
        "焦虑管理": ["anxiety", "stress", "competitive anxiety", "mental preparation"],
        "注意力": ["attention", "concentration", "focus", "attentional"],
        "自信心": ["confidence", "self-efficacy", "self-confidence", "self-belief"],
        "心理韧性": ["mental toughness", "resilience", "coping", "hardiness", "perseverance"],
        "动机": ["motivation", "goal orientation", "achievement", "self-determination"],
        "心理技能": ["mental skills", "psychological", "imagery", "self-talk", "goal setting"],
        "比赛规则理解": ["rule", "regulation", "competition rule", "referee"],
        "选拔标准": ["qualification", "selection", "standard", "entry standard"],
    }
    keywords = term_map.get(det_name, [det_name.lower()])
    return any(kw in text for kw in keywords)


def _identify_empty_categories(search_results: dict, categories: dict) -> list[dict]:
    """Identify categories that have no determinants extracted and explain why."""
    all_text = ""
    for papers in search_results.get("results", {}).values():
        for p in papers:
            all_text += " " + (p.get("title", "") or "")
            all_text += " " + (p.get("abstract", "") or "")

    all_lower = all_text.lower()

    all_possible_categories = {
        "生理要求": ["aerobic", "anaerobic", "vo2max", "strength", "power", "speed", "endurance",
                      "sprint", "heart rate", "lactate", "oxygen"],
        "健康": ["injury", "health", "body composition", "blood", "bone", "immune",
                 "risk factor", "medical", "asymmetry"],
        "技术要求": ["technique", "biomechanics", "kinematics", "movement pattern", "skill",
                     "stride", "cadence", "foot strike", "joint angle", "coordination"],
        "战术要求": ["tactics", "strategy", "pacing", "decision", "positioning", "game plan",
                     "tactical", "formation"],
        "心理技能": ["anxiety", "psychological", "mental", "confidence", "motivation",
                     "concentration", "attention", "coping", "stress"],
    }

    empty = []
    for cat_name, keywords in all_possible_categories.items():
        if cat_name not in categories or not categories[cat_name].get("determinants"):
            found_keywords = [kw for kw in keywords if kw in all_lower]
            empty.append({
                "category": cat_name,
                "reason": (
                    f"文献中未发现足够的{cat_name}相关信息。"
                    if not found_keywords else
                    f"文献中提及了 {', '.join(found_keywords[:5])} 等相关概念，但出现频率不足以提取具体因素。"
                ),
                "found_hints": found_keywords[:5],
            })

    return empty


def save_model_to_db(
    db,
    project_id: int,
    model: dict,
    selected_determinants: list[dict] = None,
    selected_kpis: list[dict] = None,
    selected_interventions: list[dict] = None,
) -> dict:
    """
    Save the generated (and user-reviewed) model to the database.
    Creates determinants, KPIs, interventions, and evidence sources.

    Args:
        db: SQLAlchemy session
        project_id: Target project ID
        model: The generated model dict
        selected_determinants: User-selected determinants (if None, use all)
        selected_kpis: User-selected KPIs (if None, use all)
        selected_interventions: User-selected interventions (if None, use all)

    Returns:
        Summary of what was created
    """
    from app import crud

    determinants = selected_determinants if selected_determinants is not None else []
    if not determinants:
        # Use all from model
        for cat_name, cat_data in model.get("categories", {}).items():
            for det in cat_data.get("determinants", []):
                determinants.append({**det, "category": cat_name})

    kpis = selected_kpis if selected_kpis is not None else model.get("kpis", [])
    interventions = selected_interventions if selected_interventions is not None else model.get("interventions", [])

    # First save evidence sources
    evidence_count = 0
    for src in model.get("evidence_sources", []):
        try:
            crud.create_evidence_source(db, project_id, {
                "title": src.get("title", ""),
                "authors": src.get("authors", ""),
                "year": int(src["year"]) if src.get("year", "").isdigit() else None,
                "source_type": "literature",
                "evidence_level": "中",
                "summary": src.get("abstract", "")[:500],
                "url": src.get("url", ""),
                "doi": src.get("doi", ""),
                "relevance": f"文献检索类型: {src.get('source_type', '')}",
            })
            evidence_count += 1
        except Exception:
            db.rollback()

    # Create determinant hierarchy
    det_id_map = {}
    det_created = 0
    for det in determinants:
        cat_name = det.get("category", "其他")
        try:
            obj = crud.create_determinant(db, project_id, {
                "category": cat_name,
                "name": det["name"],
                "description": det.get("description", ""),
                "importance": det.get("importance", "medium"),
                "evidence_level": det.get("evidence_level", "中"),
                "source_summary": f"从 {model.get('search_summary', {}).get('narrative_review_count', 0) + model.get('search_summary', {}).get('meta_analysis_count', 0)} 篇文献中提取",
            })
            det_id_map[det["name"]] = obj.id
            det_created += 1
        except Exception:
            db.rollback()

    # Create KPIs
    kpi_created = 0
    for kpi in kpis:
        det_name = kpi.get("determinant", "")
        det_id = det_id_map.get(det_name)
        try:
            crud.create_kpi(db, project_id, {
                "name": kpi["name"],
                "determinant_id": det_id,
                "definition": f"衡量{kpi.get('determinant', '')}的指标",
                "calculation_method": kpi.get("protocol", ""),
                "unit": kpi.get("unit", ""),
                "measurement_frequency": kpi.get("frequency", ""),
                "evidence_level": kpi.get("evidence_level", "中"),
                "category": kpi.get("category", ""),
            })
            kpi_created += 1
        except Exception:
            db.rollback()

    # Create interventions
    intv_created = 0
    for intv in interventions:
        try:
            crud.create_intervention(db, project_id, {
                "name": intv["name"],
                "intervention_type": intv.get("type", "训练"),
                "description": intv.get("description", ""),
                "status": "planned",
            })
            intv_created += 1
        except Exception:
            db.rollback()

    return {
        "evidence_sources_created": evidence_count,
        "determinants_created": det_created,
        "kpis_created": kpi_created,
        "interventions_created": intv_created,
    }
