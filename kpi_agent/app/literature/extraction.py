"""
Free rule-based evidence extraction from literature results.

Extracts structured information from title + abstract without using LLM APIs.
Uses regex + domain dictionaries + keyword matching.

Extracted fields:
- sport, population_level, sample_size, sex, age
- performance_variables, interventions, measurement_methods
- outcome_variables, key_sentences, kpi_implications
- evidence metadata (confidence, matched_terms, etc.)
"""

import re
import logging
from typing import Optional

from app.literature.schema import LiteratureResult, ExtractionResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Domain dictionaries
# ═══════════════════════════════════════════════════════════════════

SPORT_TERMS = {
    "running": "running", "sprinting": "sprinting",
    "middle-distance running": "middle-distance running",
    "long-distance running": "long-distance running",
    "800m": "800m", "800 m": "800m",
    "1500m": "1500m", "1500 m": "1500m",
    "athletics": "athletics", "track and field": "athletics",
    "marathon": "marathon",
    "swimming": "swimming", "cycling": "cycling",
    "rowing": "rowing", "triathlon": "triathlon",
    "soccer": "soccer", "football": "football",
    "basketball": "basketball",
    "volleyball": "volleyball",
    "rugby": "rugby", "tennis": "tennis",
    "badminton": "badminton",
    "gymnastics": "gymnastics",
    "figure skating": "figure skating",
    "speed skating": "speed skating",
    "skiing": "skiing", "snowboarding": "snowboarding",
    "cross-country skiing": "cross-country skiing",
    "weightlifting": "weightlifting",
    "powerlifting": "powerlifting",
    "boxing": "boxing",
    "judo": "judo", "wrestling": "wrestling",
    "hockey": "hockey", "ice hockey": "ice hockey",
    "baseball": "baseball", "softball": "softball",
    "cricket": "cricket",
    "handball": "handball",
    "fencing": "fencing",
    "archery": "archery",
    "table tennis": "table tennis",
    "golf": "golf",
    "climbing": "climbing", "sport climbing": "sport climbing",
}

POPULATION_TERMS = {
    "elite": ["elite", "elite-level", "elite level"],
    "trained": ["trained", "well-trained", "well trained"],
    "recreational": ["recreational", "amateur"],
    "professional": ["professional", "pro"],
    "collegiate": ["collegiate", "college", "university", "undergraduate"],
    "youth": ["youth", "adolescent", "junior", "young"],
    "national-level": ["national-level", "national level", "national team"],
    "international-level": ["international-level", "international level", "world-class", "world class", "olympic"],
    "sub-elite": ["sub-elite", "sub elite"],
    "moderately trained": ["moderately trained", "moderately active"],
    "untrained": ["untrained", "sedentary"],
    "master": ["master athletes", "masters athletes", "veteran"],
}

PERFORMANCE_VARIABLES = {
    "VO2max": [r"vo2max", r"vo2 max", r"vo2 peak", r"vo2peak",
               r"maximal oxygen uptake", r"maximum oxygen uptake", r"aerobic capacity",
               r"v̇o2max", r"v̇o2 max"],
    "running economy": [r"running economy", r"run economy", r"economy"],
    "lactate threshold": [r"lactate threshold", r"lactate turnpoint", r"anaerobic threshold",
                          r"onset of blood lactate"],
    "anaerobic capacity": [r"anaerobic capacity", r"anaerobic power", r"sprint ability",
                           r"anaerobic speed reserve", r"maximal sprint"],
    "speed": [r"\bspeed\b", r"\bvelocity\b", r"sprint performance", r"peak speed"],
    "power": [r"\bpower\b", r"power output", r"peak power", r"mean power"],
    "strength": [r"\bstrength\b", r"maximal strength", r"1rm", r"1 rm", r"one rep"],
    "jump performance": [r"jump", r"countermovement", r"cmj", r"squat jump", r"\bsj\b"],
    "heart rate": [r"heart rate", r"\bhr\b", r"hrv", r"heart rate variability",
                   r"maximum heart rate", r"hrmax", r"resting heart rate"],
    "training load": [r"training load", r"\btrimp\b", r"tld", r"s-rpe", r"session rpe",
                      r"internal load", r"external load", r"load monitoring"],
    "fatigue": [r"\bfatigue\b", r"perceived fatigue", r"muscle fatigue", r"neuromuscular fatigue"],
    "injury risk": [r"injury risk", r"risk factor", r"injury prevention", r"injury incidence"],
    "reaction time": [r"reaction time", r"rt\b", r"response time"],
    "agility": [r"\bagility\b", r"change of direction", r"cod ", r"t-test"],
    "flexibility": [r"flexibility", r"range of motion", r"\brom\b", r"mobility"],
    "asymmetry": [r"\basymmetry\b", r"\basymmetries\b", r"limb symmetry", r"bilateral"],
    "body composition": [r"body composition", r"body fat", r"lean mass", r"bmi", r"body mass"],
    "sleep": [r"\bsleep\b", r"sleep quality", r"sleep duration", r"insomnia"],
}

INTERVENTION_TERMS = {
    "HIIT": [r"\bhiit\b", r"high intensity interval training", r"high-intensity interval",
             r"interval training", r"sprint interval", r"\bsit\b"],
    "endurance training": [r"endurance training", r"aerobic training", r"continuous training",
                           r"long slow distance", r"\blsd\b"],
    "strength training": [r"strength training", r"resistance training", r"weight training",
                          r"heavy resistance", r"maximal strength training"],
    "plyometric training": [r"plyometric", r"plyometrics", r"jump training", r"ballistic"],
    "altitude training": [r"altitude training", r"hypoxic", r"hypoxia", r"live high", r"train low"],
    "tapering": [r"\btaper\b", r"tapering", r"peaking"],
    "warm-up": [r"warm.up", r"warming up", r"pre.exercise", r"pre activation"],
    "recovery": [r"\brecovery\b", r"active recovery", r"compression", r"cold water immersion",
                 r"cryotherapy"],
    "nutrition": [r"\bnutrition\b", r"carbohydrate", r"\bcaffeine\b", r"protein supplement",
                  r"dietary", r"hydration", r"creatine", r"beta-alanine", r"sodium bicarbonate"],
    "technique training": [r"technique training", r"technique", r"biomechanical", r"skill training"],
    "flexibility training": [r"stretching", r"flexibility training", r"\byoga\b", r"pilates"],
}

MEASUREMENT_METHODS = {
    "treadmill test": [r"treadmill", r"incremental test", r"graded exercise test",
                       r"maximal test", r"gxt\b", r"ramp test"],
    "time trial": [r"time trial", r"time-trial", r"\btt\b", r"race simulation"],
    "blood lactate": [r"blood lactate", r"lactate", r"la-", r"blood sample"],
    "gas analysis": [r"gas analysis", r"gas exchange", r"indirect calorimetry",
                     r"metabolic cart", r"parvomedics", r"cosmed"],
    "GPS": [r"\bgps\b", r"global positioning", r"gnss", r"lps"],
    "accelerometer": [r"accelerometer", r"imu", r"inertial measurement", r"wearable sensor"],
    "force plate": [r"force plate", r"force platform", r"ground reaction"],
    "motion capture": [r"motion capture", r"3d analysis", r"vicon", r"qualisys"],
    "wearable": [r"\bwearable\b", r"wearable device", r"smartwatch", r"fitness tracker"],
    "questionnaire": [r"questionnaire", r"survey", r"self-report", r"likert"],
    "blood test": [r"blood test", r"blood sample", r"serum", r"plasma", r"hematology"],
    "DEXA": [r"\bdexa\b", r"dxa\b", r"dual energy", r"dual-energy"],
}

OUTCOME_VARIABLES = {
    "performance time": [r"performance time", r"race time", r"finish time", r"completion time"],
    "power output": [r"power output", r"\bwatts\b", r"\bw\b", r"mean power", r"peak power"],
    "velocity": [r"\bvelocity\b", r"\bspeed\b", r"pace", r"m/s", r"km/h"],
    "economy": [r"\beconomy\b", r"running economy", r"oxygen cost", r"energy cost"],
    "threshold": [r"\bthreshold\b", r"lactate threshold", r"ventilatory threshold"],
    "injury incidence": [r"injury incidence", r"injury rate", r"injuries per"],
    "ranking": [r"\branking\b", r"position", r"placement"],
}


# ═══════════════════════════════════════════════════════════════════
# Extraction functions
# ═══════════════════════════════════════════════════════════════════

def _find_terms(text: str, term_dict: dict) -> list[str]:
    """Find which terms from a dictionary appear in text."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for canonical, patterns in term_dict.items():
        if isinstance(patterns, list):
            for pat in patterns:
                if re.search(pat, text_lower, re.IGNORECASE):
                    found.append(canonical)
                    break
        elif isinstance(patterns, str):
            if patterns.lower() in text_lower:
                found.append(canonical)
    return found


def _find_sample_size(text: str) -> Optional[int]:
    """Extract sample size from text patterns like 'n=12', '12 athletes', '20 participants'."""
    if not text:
        return None

    patterns = [
        r"\bn\s*[=：:]\s*(\d{1,6})\b",
        r"\b(\d{1,4})\s*(?:elite|trained|male|female|healthy|young|adult|college|university)\s*(?:athletes?|participants?|subjects?|runners?|swimmers?|cyclists?|players?|individuals?)",
        r"\b(\d{1,4})\s*(?:athletes?|participants?|subjects?|runners?|swimmers?|cyclists?)\s*(?:were|was|completed|participated|volunteered|recruited|enrolled)",
        r"(?:sample|cohort|total)\s*(?:of|size|was|comprised)?\s*[=：:]?\s*(\d{1,4})\b",
        r"(?:included|recruited|enrolled|studied)\s*(\d{1,4})\s*(?:athletes?|participants?|subjects?)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                n = int(m.group(1))
                if 1 <= n <= 100000:
                    return n
            except (ValueError, IndexError):
                continue
    return None


def _find_sex(text: str) -> list[str]:
    """Identify participant sex from text."""
    found = []
    text_lower = text.lower()

    if any(w in text_lower for w in ["male", "men", "man", "boys"]):
        found.append("male")
    if any(w in text_lower for w in ["female", "women", "woman", "girls"]):
        found.append("female")
    if "mixed" in text_lower or ("both" in text_lower and "sex" in text_lower):
        if not found:
            found.append("mixed")

    return found


def _find_age(text: str) -> Optional[str]:
    """Extract age information from text."""
    patterns = [
        r"age[:\s]*(\d{1,2}[\.\d]*)\s*[±+/-]?\s*(\d{1,2}[\.\d]*)?\s*(?:years?|yrs?|y\.?o\.?)",
        r"mean age[:\s]*(\d{1,2}[\.\d]*)",
        r"(\d{1,2}[\.\d]*)\s*[±]\s*(\d{1,2}[\.\d]*)\s*(?:years?|yrs?)",
        r"aged?\s*(\d{1,2})\s*[–-]\s*(\d{1,2})\s*(?:years?|yrs?)",
        r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s*(?:year|yr)[\s-]old",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                return f"{m.group(1)} ± {m.group(2)} years"
            return f"{m.group(1)} years"
    return None


def _extract_key_sentences(text: str, max_sentences: int = 5) -> list[str]:
    """Extract sentences containing key variables or findings."""
    if not text:
        return []

    sentences = re.split(r'(?<=[.!?])\s+', text)
    key_indicators = [
        r"\bvo2max\b", r"running economy", r"lactate", r"threshold",
        r"significant", r"improved", r"increased", r"decreased",
        r"correlated", r"predicted", r"determined", r"associated",
        r"performance", r"training", r"intervention",
    ]

    key_sents = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 30:
            continue
        for indicator in key_indicators:
            if re.search(indicator, sent, re.IGNORECASE):
                key_sents.append(sent[:300])
                break
        if len(key_sents) >= max_sentences:
            break

    return key_sents


def _generate_kpi_implications(extraction: ExtractionResult) -> list[dict]:
    """Generate KPI candidate suggestions based on extracted variables."""
    implications = []

    var_to_kpi = {
        "VO2max": {"name": "VO2max", "unit": "ml/kg/min", "category": "生理", "candidate": True},
        "running economy": {"name": "跑步经济性", "unit": "ml/kg/km", "category": "生理", "candidate": True},
        "lactate threshold": {"name": "乳酸阈", "unit": "km/h or %VO2max", "category": "生理", "candidate": True},
        "anaerobic capacity": {"name": "无氧能力", "unit": "W or m/s", "category": "生理", "candidate": True},
        "speed": {"name": "速度", "unit": "m/s", "category": "体能", "candidate": True},
        "power": {"name": "功率输出", "unit": "W", "category": "体能", "candidate": True},
        "strength": {"name": "最大力量", "unit": "kg or N", "category": "体能", "candidate": True},
        "jump performance": {"name": "跳跃表现", "unit": "cm", "category": "体能", "candidate": True},
        "heart rate": {"name": "心率", "unit": "bpm", "category": "生理", "candidate": True},
        "training load": {"name": "训练负荷", "unit": "AU", "category": "训练监控", "candidate": True},
        "fatigue": {"name": "疲劳水平", "unit": "AU or scale", "category": "恢复", "candidate": True},
        "injury risk": {"name": "损伤风险", "unit": "score", "category": "健康", "candidate": True},
        "sleep": {"name": "睡眠质量", "unit": "hours or score", "category": "恢复", "candidate": True},
    }

    for var in extraction.performance_variables:
        if var in var_to_kpi:
            implications.append(var_to_kpi[var])

    # Also check outcome variables
    for var in extraction.outcome_variables:
        matched = _find_terms(var, {
            "performance time": "performance time",
            "power output": "power output",
        })
        if matched and var_to_kpi.get(matched[0]):
            implications.append(var_to_kpi[matched[0]])

    return implications


def _assess_confidence(extraction: ExtractionResult) -> str:
    """Assess extraction confidence based on completeness."""
    filled = 0
    total = 0

    checks = [
        (extraction.sport, "sport"),
        (extraction.population_level, "population_level"),
        (extraction.sample_size, "sample_size"),
        (extraction.sex, "sex"),
        (extraction.performance_variables, "performance_variables"),
        (extraction.interventions, "interventions"),
    ]

    missing = []
    for val, name in checks:
        total += 1
        if val:
            filled += 1
        else:
            missing.append(name)

    extraction.missing_fields = missing

    if filled >= total * 0.7:
        return "medium"
    elif filled >= total * 0.4:
        return "low"
    return "low"


# ═══════════════════════════════════════════════════════════════════
# Main extraction function
# ═══════════════════════════════════════════════════════════════════

def free_extract_evidence(
    result: LiteratureResult,
    fulltext: Optional[str] = None,
) -> ExtractionResult:
    """Extract structured evidence from a single LiteratureResult.

    Only uses title + abstract by default. Pass fulltext parameter
    for full-text extraction (currently same regex-based approach).

    Args:
        result: LiteratureResult to extract from
        fulltext: Optional fulltext string (not yet downloaded)

    Returns:
        ExtractionResult with all extracted fields
    """
    text = (result.title or "") + " " + (result.abstract or "")
    if fulltext:
        text = fulltext
        extracted_from = "fulltext"
    else:
        extracted_from = "title_abstract"

    extraction = ExtractionResult(
        literature_id=result.id,
        title=result.title,
        extracted_from=extracted_from,
        extraction_method="rule_based",
    )

    # 1. Sport
    extraction.sport = _find_terms(text, SPORT_TERMS)

    # 2. Population level
    extraction.population_level = _find_terms(text, POPULATION_TERMS)

    # 3. Sample size
    extraction.sample_size = _find_sample_size(text)

    # 4. Sex
    extraction.sex = _find_sex(text)

    # 5. Age
    extraction.age = _find_age(text)

    # 6. Performance variables
    extraction.performance_variables = _find_terms(text, PERFORMANCE_VARIABLES)

    # 7. Interventions
    extraction.interventions = _find_terms(text, INTERVENTION_TERMS)

    # 8. Measurement methods
    extraction.measurement_methods = _find_terms(text, MEASUREMENT_METHODS)

    # 9. Outcome variables
    extraction.outcome_variables = _find_terms(text, OUTCOME_VARIABLES)

    # 10. Key sentences
    extraction.key_sentences = _extract_key_sentences(text)

    # 11. KPI implications
    extraction.kpi_implications = _generate_kpi_implications(extraction)

    # 12. Confidence assessment
    extraction.confidence = _assess_confidence(extraction)

    # 13. Matched terms (for debugging)
    extraction.matched_terms = {
        "sport_terms": {t: True for t in extraction.sport},
        "perf_var_terms": {t: True for t in extraction.performance_variables},
    }

    return extraction


def batch_extract(
    results: list[LiteratureResult],
) -> list[ExtractionResult]:
    """Extract evidence from multiple results.

    Args:
        results: List of LiteratureResult objects

    Returns:
        List of ExtractionResult objects
    """
    extractions = []
    for r in results:
        try:
            extraction = free_extract_evidence(r)
            extractions.append(extraction)
        except Exception as e:
            logger.warning(f"Extraction failed for '{r.title[:60]}': {e}")
            # Create empty extraction with error note
            extractions.append(ExtractionResult(
                literature_id=r.id,
                title=r.title,
                evidence_note=f"extraction_error: {str(e)[:100]}",
            ))
    return extractions
