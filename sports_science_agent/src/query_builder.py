"""Query builder — decompose research topic into PICO/PECO and generate search queries."""

import re
from typing import Optional
from src.utils import logger


def decompose_topic(topic: str) -> dict:
    """Decompose a natural language research topic into PICO/PECO components.

    Returns a dict with population, intervention/exposure, comparator, outcomes,
    and study_design_preference based on keyword heuristics.
    """
    topic_lower = topic.lower()
    result = {
        "population": "",
        "intervention_or_exposure": "",
        "comparator": "",
        "outcomes": "",
        "study_design_preference": "",
    }

    # ── Population detection ──
    pop_patterns = [
        # Age groups
        (r"(?:in|among|for)\s+(?:the\s+)?(elderly|older\s+adults?|middle[\s-]*aged|adolescents?|youth|children|young\s+adults?|adults?)", "age"),
        (r"(?:elderly|older\s+adults?|middle[\s-]*aged|adolescents?|youth|children|young\s+adults?)", "age"),
        # Athletes/patients
        (r"(?:elite|professional|recreational|competitive|amateur|collegiate|sub[\s-]*elite)\s+(?:athletes?|sportsmen|sportswomen|players?|runners?|cyclists?|swimmers?|football|soccer|basketball)", "athlete"),
        (r"(?:athletes?|players?|runners?|cyclists?|swimmers?|football|soccer|basketball|rugby|tennis)", "athlete"),
        # Clinical populations
        (r"(?:patients?\s+(?:with|after)|subjects?\s+(?:with|after))\s*([\w\s,;-]+?)(?:\s*(?:,|undergo|receiv|\.))", "clinical"),
        (r"(?:obesity|obese|diabet(?:ic|es)|hypertensi(?:on|ve)|overweight|metabolic|cardiovascular|COPD|asthma|cancer|stroke|arthritis|osteoporosis)", "clinical"),
        # Sex
        (r"(?:male|female|men|women)\s+(?:athletes?|participants?|subjects?|patients?)", "sex"),
    ]
    for pattern, ptype in pop_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            groups = match.groups()
            if groups:
                result["population"] = groups[0].strip()
            else:
                result["population"] = match.group(0).strip()
            break

    # ── Intervention/Exposure ──
    interv_patterns = [
        # Training types
        (r"(?:effect|efficacy|effectiveness|impact|role|influence)\s+(?:of\s+)?([\w\s,;-]+?(?:training|exercise|intervention|program|protocol|therapy|supplement|diet|nutrition|rehabilitation))", None),
        (r"([\w\s]+(?:training|exercise|HIIT|high[\s-]*intensity|interval|resistance|strength|endurance|aerobic|anaerobic|plyometric|sprint|power|agility|flexibility|mobility|stretching|concurrent|periodi[sz]ed|crossfit|pilates|yoga)[\w\s]*)", None),
        # Supplements / Nutrition
        (r"(creatine|caffeine|protein|beta[\s-]*alanine|nitrate|bicarbonate|carbohydrate|whey|casein|BCAA|HMB|vitamin\s*D|omega[\s-]*3|electrolyte)", None),
        # Rehabilitation / Medical
        (r"(ACL\s*(?:reconstruction|injury|rehab)|anterior\s+cruciate|tendinopathy|rehabilitation|return[\s-]*to[\s-]*(?:sport|play)|injury\s+prevention)", None),
    ]
    for pattern, _ in interv_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            groups = match.groups()
            if groups:
                result["intervention_or_exposure"] = groups[0].strip()
            else:
                result["intervention_or_exposure"] = match.group(0).strip()
            break

    # ── Comparator ──
    comp_patterns = [
        (r"(?:versus|vs\.?|compared\s+(?:to|with))\s+([\w\s,;-]+?)(?:\s*(?:on|in|for|improve|\.|$))", None),
        (r"(?:than)\s+([\w\s,;-]+?)(?:\s*(?:on|in|for|improve|\.|$))", None),
    ]
    for pattern, _ in comp_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            result["comparator"] = match.group(1).strip()
            break
    # Default comparator if not found
    if not result["comparator"] and result["intervention_or_exposure"]:
        if "training" in result["intervention_or_exposure"].lower() or "exercise" in result["intervention_or_exposure"].lower():
            result["comparator"] = "control / usual care / moderate-intensity continuous training"

    # ── Outcomes ──
    outcome_patterns = [
        (r"(?:improve|enhance|reduce|increase|decrease|affect|change|influence|modif|alter)\s+(?:the\s+)?([\w\s,;-]+?)(?:\?|$|\.)", None),
        (r"(?:on)\s+([\w\s,;-]+?(?:VO2max|strength|power|fatigue|recovery|injury|performance|body\s+composition|blood\s+pressure|HRV|heart\s+rate)[\w\s,;-]*?)(?:\?|$|\.)", None),
        # Specific sports science outcomes
        (r"(VO2max|maximal\s+oxygen\s+uptake|VO2\s*max|aerobic\s+capacity|anaerobic\s+capacity|lactate\s+threshold|muscle\s+strength|power\s+output|sprint|jump|agility|flexibility|body\s+fat|lean\s+mass|injury\s+rate|return\s+to\s+sport|recovery\s+time)", None),
    ]
    for pattern, _ in outcome_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            result["outcomes"] = match.group(1).strip() if match.groups() else match.group(0).strip()
            break

    # ── Study design preference ──
    design_patterns = [
        (r"(?:RCT|randomi[sz]ed\s+(?:controlled\s+)?trial|clinical\s+trial)", "RCT / systematic review / meta-analysis / clinical trial"),
        (r"(?:systematic\s+review|meta[\s-]*analys)", "systematic review / meta-analysis"),
        (r"(?:cohort|prospective|longitudinal|observational)", "observational / cohort study"),
    ]
    for pattern, pref in design_patterns:
        if re.search(pattern, topic, re.IGNORECASE):
            result["study_design_preference"] = pref
            break
    if not result["study_design_preference"]:
        result["study_design_preference"] = "RCT / systematic review / meta-analysis / clinical trial"

    return result


def build_pubmed_query(pico: dict) -> str:
    """Build a PubMed query string from PICO components."""
    clauses = []

    def _term_list(text: str) -> list[str]:
        """Split text into search terms."""
        if not text:
            return []
        # Remove common stop words and split
        cleaned = re.sub(r'[,;:()\[\]{}"]', ' ', text)
        terms = [t.strip().lower() for t in cleaned.split() if len(t.strip()) > 2]
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)
        return unique_terms[:6]  # Limit to 6 most relevant terms

    # Population
    pop_terms = _term_list(pico.get("population", ""))
    if pop_terms:
        pop_phrase = " OR ".join(f'"{t}"[Title/Abstract]' for t in pop_terms)
        clauses.append(f"({pop_phrase})")

    # Intervention/Exposure
    interv_terms = _term_list(pico.get("intervention_or_exposure", ""))
    if interv_terms:
        interv_phrase = " OR ".join(f'"{t}"[Title/Abstract]' for t in interv_terms)
        clauses.append(f"({interv_phrase})")

    # Outcomes
    outcome_terms = _term_list(pico.get("outcomes", ""))
    if outcome_terms:
        outcome_phrase = " OR ".join(f'"{t}"[Title/Abstract]' for t in outcome_terms)
        clauses.append(f"({outcome_phrase})")

    # Study design filter
    design = pico.get("study_design_preference", "")
    design_filters = {
        "RCT": '("randomized controlled trial"[Publication Type] OR "randomised controlled trial"[Publication Type] OR "clinical trial"[Publication Type])',
        "systematic review": '("systematic review"[Publication Type] OR "meta-analysis"[Publication Type])',
        "meta-analysis": '("meta-analysis"[Publication Type])',
    }
    for key, query in design_filters.items():
        if key in design.lower():
            clauses.append(query)
            break

    if not clauses:
        return topic_to_broad_query(pico)

    return " AND ".join(clauses)


def build_crossref_query(pico: dict) -> str:
    """Build a CrossRef search query string."""
    terms = []
    for key in ["intervention_or_exposure", "population", "outcomes"]:
        val = pico.get(key, "")
        if val:
            # Take first 2-3 significant words
            words = [w for w in val.split() if len(w) > 2][:3]
            terms.extend(words)
    return " ".join(terms[:8])


def build_semantic_scholar_query(pico: dict) -> str:
    """Build a Semantic Scholar search query."""
    # Semantic Scholar works better with natural language queries
    parts = []
    if pico.get("intervention_or_exposure"):
        parts.append(pico["intervention_or_exposure"])
    if pico.get("population"):
        parts.append(f"in {pico['population']}")
    if pico.get("outcomes"):
        parts.append(f"for {pico['outcomes']}")
    return " ".join(parts)


def topic_to_broad_query(pico: dict) -> str:
    """Fallback: broad PubMed query from all PICO terms."""
    all_text = " ".join(v for v in pico.values() if v)
    terms = [t.strip().lower() for t in re.split(r'[,;:()\[\]{}"]', all_text) if len(t.strip()) > 2]
    unique_terms = list(dict.fromkeys(terms))[:8]
    if unique_terms:
        return " AND ".join(f'"{t}"[Title/Abstract]' for t in unique_terms)
    return ""


def generate_search_queries(topic: str, use_llm: bool = True) -> dict:
    """Full query generation pipeline.

    Uses LLM-driven query_understanding as primary (when available),
    with regex fallback for offline/error scenarios.

    Returns:
        dict with pico_peco, query_understanding context, and search queries.
    """
    # ── Primary: LLM-driven query understanding ──
    query_context = None
    pubmed_query = ""
    crossref_query = ""
    sem_scholar_query = ""

    if use_llm:
        try:
            from src.query_understanding import understand_topic
            query_context = understand_topic(topic, use_llm=True)
            pubmed_query = query_context.get("pubmed_query", "")
            crossref_query = query_context.get("crossref_query", "")
            sem_scholar_query = query_context.get("semantic_scholar_query", "")
        except Exception as e:
            logger.warning(f"LLM query understanding failed, falling back to regex: {e}")
            query_context = None

    # ── Fallback: regex-based decomposition ──
    if query_context is None:
        from src.query_understanding import understand_topic
        query_context = understand_topic(topic, use_llm=False)

    # Extract pico_peco in legacy format for compatibility
    legacy_pico = _to_legacy_pico(query_context)

    # Use generated query or build from pico
    if not pubmed_query:
        pubmed_query = build_pubmed_query(legacy_pico)
    if not crossref_query:
        crossref_query = build_crossref_query(legacy_pico)
    if not sem_scholar_query:
        sem_scholar_query = build_semantic_scholar_query(legacy_pico)

    return {
        "topic": topic,
        "pico_peco": legacy_pico,  # legacy flat format for backward compatibility
        "query_context": query_context,  # full structured context for relevance evaluator
        "queries": {
            "pubmed": pubmed_query,
            "crossref": crossref_query,
            "semantic_scholar": sem_scholar_query,
        },
        "generated_at": None,  # filled by orchestrator
    }


def _to_legacy_pico(query_context: dict) -> dict:
    """Convert query_context PICO to legacy flat format for compatibility."""
    pico = query_context.get("pico", {})
    legacy = {}
    for key in ["population", "intervention_or_exposure", "comparator", "outcomes"]:
        comp = pico.get(key, {})
        if isinstance(comp, dict):
            legacy[key] = " ".join(comp.get("english_terms", [])) if comp.get("english_terms") else ""
        elif isinstance(comp, str):
            legacy[key] = comp
        else:
            legacy[key] = ""
    legacy["study_design_preference"] = "RCT / systematic review / meta-analysis / clinical trial"
    return legacy
