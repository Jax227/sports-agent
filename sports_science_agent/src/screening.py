"""Literature screening — decide inclusion/exclusion of papers."""

import re
from src.config import (
    SPORT_SCIENCE_DOMAINS,
    STUDY_TYPES,
    QUALITY_THRESHOLD,
    RELEVANCE_THRESHOLD,
    HIGH_PRIORITY_TYPES,
    HIGH_PRIORITY_QUALITY,
    HIGH_PRIORITY_RELEVANCE,
)
from src.utils import logger

# Keywords for domain detection
DOMAIN_KEYWORDS = {
    "exercise_physiology": [
        "vo2max", "maximal oxygen", "lactate threshold", "anaerobic threshold",
        "cardiorespiratory", "aerobic capacity", "anaerobic capacity", "heart rate",
        "muscle adaptation", "neuromuscular", "fatigue", "recovery", "cardiac output",
        "stroke volume", "mitochondrial", "capillarization", "fiber type",
        "ventilatory", "respiratory", "oxygen uptake", "vo2", "ventilatory threshold",
        "exercise physiology", "运动生理",
    ],
    "sports_training": [
        "strength training", "endurance training", "hiit", "high intensity interval",
        "periodization", "resist", "sprint", "agility", "power training",
        "plyometric", "training load", "overtraining", "tapering",
        "concurrent training", "velocity based", "rpe", "repetition",
        "sports training", "训练", "运动训练",
    ],
    "sports_medicine_rehab": [
        "acl", "anterior cruciate", "tendinopathy", "tendon", "low back pain",
        "shoulder injury", "rehabilitation", "return to sport", "return to play",
        "injury prevention", "concussion", "ankle sprain", "muscle strain",
        "sports medicine", "运动损伤", "康复",
    ],
    "sports_nutrition": [
        "protein", "carbohydrate", "creatine", "caffeine", "electrolyte",
        "supplement", "ergogenic", "hydration", "pre-exercise", "post-exercise",
        "nutrition", "dietary", "nutrient", "sports nutrition", "运动营养",
    ],
    "fitness_health_promotion": [
        "youth", "adolescent", "elderly", "older adult", "obesity", "diabetes",
        "hypertension", "cardiovascular disease", "metabolic syndrome",
        "exercise prescription", "physical activity", "health promotion",
        "public health", "fitness", "体能", "健康促进",
    ],
    "sports_psychology_performance": [
        "motivation", "attention", "stress", "mental fatigue", "anxiety",
        "team sport", "cognitive function", "psychological", "mental toughness",
        "self-efficacy", "burnout", "sports psychology", "运动心理",
    ],
}

# Negative keywords for exclusion
EXCLUSION_KEYWORDS = [
    "advertisement", "advertorial", "sponsored content", "press release",
    "product launch", "buy now", "commercial", "patent",
]


def detect_research_domain(title: str = "", abstract: str = "", keywords: str = "") -> str:
    """Detect the sports science research domain of a paper."""
    text = f"{title} {abstract} {keywords}".lower()
    scores = {}
    for domain, kws in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if kw.lower() in text)
        scores[domain] = score
    if max(scores.values()) == 0:
        return "unknown"
    return max(scores, key=scores.get)


def detect_study_type(title: str = "", abstract: str = "", keywords: str = "") -> str:
    """Heuristically detect study type."""
    text = f"{title} {abstract} {keywords}".lower()

    if re.search(r"\bmeta[\s-]*analys", text):
        return "meta_analysis"
    if re.search(r"\bsystematic\s+review\b", text):
        return "systematic_review"
    if re.search(r"\brandomi[sz]ed\s+(controlled\s+)?trial\b|\brct\b", text):
        return "randomized_controlled_trial"
    if re.search(r"\bprospective\s+cohort\b|\bcohort\s+study\b", text):
        return "prospective_cohort"
    if re.search(r"\bcross[\s-]*sectional\b", text):
        return "cross_sectional"
    if re.search(r"\bintervention\b|\bpre[\s-]*post\b", text):
        return "intervention_study"
    if re.search(r"\bguideline\b|\bconsensus\b|\bposition\s+stand\b|\bstatement\b", text):
        return "guideline_consensus"
    if re.search(r"\bnarrative\s+review\b|\breview\s+article\b", text):
        return "narrative_review"
    if re.search(r"\bcase\s+(study|report)\b", text):
        return "case_study"
    if re.search(r"\bconference\b|\bproceedings\b|\babstract\b", text):
        return "conference_abstract"
    if re.search(r"\bpre[\s-]*print\b|\barxiv\b|\bbiorxiv\b", text):
        return "preprint"
    if text.strip() and re.search(r"\bexperiment\b|\blaboratory\b", text):
        return "experimental"

    return "other"


def is_predatory_journal(journal: str = "") -> bool:
    """Simple heuristic check for potentially predatory journals."""
    predatory_patterns = [
        r"international\s+journal\s+of\s+(?:advanced|modern|current|recent|innovative)",
        r"(?:american|european|asian)\s+(?:scientific|academic)\s+(?:journal|publisher)",
        r"(?:journal|publisher)\s+of\s+(?:advanced|modern|science)\s+and\s+(?:research|technology)",
    ]
    jlower = journal.lower()
    return any(re.search(p, jlower) for p in predatory_patterns)


def check_basic_validity(paper: dict) -> tuple[bool, str]:
    """Check minimum requirements: has title, authors, year, source."""
    title = paper.get("title", "").strip()
    authors = paper.get("authors", "").strip()
    year = paper.get("year", "")
    journal = paper.get("journal", "").strip()

    if not title or len(title) < 5:
        return False, "No valid title"
    if not authors or len(authors) < 3:
        return False, "No valid authors"
    if not year or not str(year).isdigit():
        return False, "No valid year"
    if not journal or len(journal) < 2:
        return False, "No valid journal/source"

    # Check for commercial/spam content
    lower_text = f"{title} {journal}".lower()
    for kw in EXCLUSION_KEYWORDS:
        if kw.lower() in lower_text:
            return False, f"Appears to be commercial/spam content: {kw}"

    return True, "OK"


def screen_paper(paper: dict) -> dict:
    """Full screening pipeline. Returns a dict with screening result."""
    title = paper.get("title", "")
    abstract = paper.get("abstract", "") or paper.get("full_text", "")[:3000]
    keywords = paper.get("keywords", "")
    if isinstance(keywords, list):
        keywords = "; ".join(keywords)

    # 1. Domain detection
    domain = detect_research_domain(title, abstract, keywords)

    # 2. Basic validity check
    valid, reason = check_basic_validity(paper)
    if not valid:
        return {
            "inclusion_decision": "exclude",
            "reason": f"Basic validity check failed: {reason}",
            "research_domain": domain,
            "study_type": "unknown",
            "relevance_score": 0,
            "quality_score": 0,
        }

    # 3. Check if sport science related
    if domain == "unknown":
        return {
            "inclusion_decision": "exclude",
            "reason": "Not related to sports science research domains",
            "research_domain": domain,
            "study_type": "unknown",
            "relevance_score": 0,
            "quality_score": 0,
        }

    # 4. Study type detection
    study_type = detect_study_type(title, abstract, keywords)

    # 5. Evidence level from study type
    evidence_level_map = {
        "meta_analysis": "high",
        "systematic_review": "high",
        "randomized_controlled_trial": "high",
        "prospective_cohort": "moderate",
        "experimental": "moderate",
        "intervention_study": "moderate",
        "cross_sectional": "low",
        "narrative_review": "low",
        "case_study": "very_low",
        "conference_abstract": "very_low",
        "preprint": "very_low",
        "non_randomized_trial": "moderate",
        "guideline_consensus": "high",
        "opinion": "very_low",
        "other": "low",
    }
    evidence_level = evidence_level_map.get(study_type, "low")

    # 6. Relevance scoring
    relevance = _score_relevance(title, abstract, domain)

    # 7. Quality scoring (coarse pre-screening)
    quality = _score_quality_prelim(paper, study_type)

    # 8. Predatory check
    journal = paper.get("journal", "")
    if is_predatory_journal(journal):
        quality = min(quality, 3)
        evidence_level = "very_low"

    # 9. Decision
    if domain == "unknown":
        decision = "exclude"
        reason = "Not in sports science domain"
    elif study_type in HIGH_PRIORITY_TYPES and quality >= HIGH_PRIORITY_QUALITY and relevance >= HIGH_PRIORITY_RELEVANCE:
        decision = "include"
        reason = "High priority: strong study type with high quality and relevance"
    elif quality >= QUALITY_THRESHOLD and relevance >= RELEVANCE_THRESHOLD:
        decision = "include"
        reason = "Meets quality and relevance thresholds"
    elif quality >= 4 and relevance >= 4:
        decision = "maybe"
        reason = "Borderline quality/relevance — manual review recommended"
    else:
        decision = "exclude"
        reason = f"Below thresholds: quality={quality}, relevance={relevance}"

    return {
        "inclusion_decision": decision,
        "reason": reason,
        "research_domain": domain,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "relevance_score": relevance,
        "quality_score": quality,
    }


def _score_relevance(title: str, abstract: str, domain: str) -> float:
    """Score relevance to sports science (0-10)."""
    text = f"{title} {abstract}".lower()
    # Count keyword matches
    all_kws = []
    for kws in DOMAIN_KEYWORDS.values():
        all_kws.extend(kws)

    matches = sum(1 for kw in all_kws if kw.lower() in text)
    # Scale: ~2 matches = 5, ~6+ matches = 10
    score = min(10, matches * 1.5 + 2)
    # Bonus if strong methodology keywords
    method_bonus = 0
    if re.search(r"\brandomi[sz]ed\b|\bcontrolled\s+trial\b|\bcohort\b|\bmeta[\s-]*analys", text):
        method_bonus = 2
    return min(10, round(score + method_bonus, 1))


def _score_quality_prelim(paper: dict, study_type: str) -> float:
    """Preliminary quality score (0-10) based on available metadata."""
    score = 5.0  # Start neutral

    # Study type bonus
    type_bonus = {
        "meta_analysis": 2.5,
        "systematic_review": 2.0,
        "randomized_controlled_trial": 2.0,
        "prospective_cohort": 1.5,
        "guideline_consensus": 2.0,
        "experimental": 1.0,
        "intervention_study": 1.0,
        "cross_sectional": 0.5,
        "narrative_review": 0.5,
        "case_study": -1.0,
        "conference_abstract": -2.0,
        "preprint": -1.5,
        "non_randomized_trial": 0.5,
        "opinion": -2.0,
    }
    score += type_bonus.get(study_type, 0)

    # Sample size (if available)
    sample_size = paper.get("sample_size", "")
    if sample_size:
        try:
            n = int(sample_size)
            if n >= 1000:
                score += 1.0
            elif n >= 100:
                score += 0.5
            elif n >= 30:
                score += 0
            else:
                score -= 0.5
        except (ValueError, TypeError):
            pass

    # Year recency
    year = paper.get("year", "")
    try:
        y = int(year)
        if y >= 2023:
            score += 0.5
        elif y >= 2018:
            score += 0
        elif y >= 2010:
            score -= 0.5
        else:
            score -= 1.0
    except (ValueError, TypeError):
        pass

    # Citation count (if available)
    citations = paper.get("citation_count") or paper.get("is_referenced_by_count") or 0
    try:
        c = int(citations)
        if c >= 100:
            score += 1.0
        elif c >= 10:
            score += 0.5
    except (ValueError, TypeError):
        pass

    return max(0, min(10, round(score, 1)))
