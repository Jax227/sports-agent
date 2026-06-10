"""Query understanding — decompose NL research topic into structured PICO/PECO.

Uses LLM (DeepSeek) as primary driver, with regex fallback for English input.
Produces mandatory/optional/exclusion term triage for strict relevance filtering.
"""

import json
import re
import os

import requests

from src.utils import logger

DEEPSEEK_BASE = "https://api.deepseek.com"


def _llm_decompose(topic: str) -> dict:
    """Use DeepSeek V4 to decompose a research topic into structured PICO + term triage.

    Returns a dict with pico, mandatory_terms, optional_terms, exclusion_terms,
    and a PubMed-ready query string.  Falls back to regex on any failure.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.warning("No DEEPSEEK_API_KEY — falling back to regex decomposition")
        return _regex_decompose(topic)

    system_prompt = (
        "You are a sports science search specialist. Decompose topics into structured retrieval plans. "
        "Translate Chinese to English. Output ONLY valid JSON (no markdown, no explanation).\n"
        "Rules:\n"
        "- mandatory_terms: 2-5 core concepts that MUST appear in title/abstract for high relevance\n"
        "- optional_terms: synonyms for broader recall, not required\n"
        "- exclusion_terms: terms indicating irrelevance (animal, rat, mouse, cell, in vitro, etc.)\n"
        "- pubmed_query: use [Title/Abstract] field, AND between concept groups, OR within groups, add study design filter\n"
        "- Only expand standard synonyms, never replace specific concepts with generic ones\n"
        "- Never ignore user-specified outcomes or populations\n"
        "Format:\n"
        '{"pico":{"population":{"english_terms":[],"required":false},'
        '"intervention_or_exposure":{"english_terms":[],"required":true},'
        '"comparator":{"english_terms":[],"required":false},'
        '"outcomes":{"english_terms":[],"required":false},'
        '"context":{"english_terms":["exercise","training","sport"],"required":false}},'
        '"mandatory_terms":[],"optional_terms":[],"exclusion_terms":[],"pubmed_query":""}'
    )

    try:
        session = requests.Session()
        session.trust_env = False

        resp = session.post(
            f"{DEEPSEEK_BASE}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-v4-pro",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": topic},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
            },
            timeout=60,
        )

        if resp.status_code != 200:
            logger.warning(f"Query understanding LLM HTTP {resp.status_code}")
            return _regex_decompose(topic)

        choice = resp.json()["choices"][0]
        finish_reason = choice.get("finish_reason", "")
        content = choice["message"]["content"].strip()

        # If output was truncated, the JSON will be incomplete — fall back to regex
        if finish_reason == "length":
            logger.warning("LLM output truncated (finish_reason=length) — falling back to regex")
            return _regex_decompose(topic)

        # ── Robust JSON extraction ──
        # Remove markdown fences
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)

        # Extract the outermost JSON object
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            raw_json = json_match.group(0)
        else:
            raw_json = content

        # Try parsing; fix common LLM JSON errors on failure
        try:
            result = json.loads(raw_json)
        except json.JSONDecodeError:
            # Common fix: trailing comma before closing brace/bracket
            fixed = re.sub(r',\s*(\}|\])', r'\1', raw_json)
            try:
                result = json.loads(fixed)
            except json.JSONDecodeError as e2:
                logger.error(f"Failed to parse LLM JSON even after fix: {e2}")
                logger.error(f"Raw content (first 500): {content[:500]}")
                return _regex_decompose(topic)

        _validate_and_fix(result, topic)
        logger.info(f"LLM decomposed topic: {topic[:50]}... → {len(result.get('mandatory_terms', []))} mandatory, {len(result.get('optional_terms', []))} optional, {len(result.get('exclusion_terms', []))} exclusion")
        return result

    except Exception as e:
        logger.error(f"LLM query understanding failed: {e}, falling back to regex")
        return _regex_decompose(topic)


def _validate_and_fix(result: dict, topic: str):
    """Ensure the LLM output has all required fields with sensible defaults."""
    # ── Normalize PICO/PECO key format ──
    # LLM may return "PICO" (uppercase) or "pico_peco" or nested "PICO.P/I/C/O"
    if "PICO" in result and "pico" not in result:
        result["pico"] = result.pop("PICO")
    if "PECO" in result and "pico" not in result:
        result["pico"] = result.pop("PECO")
    if "pico_peco" in result and "pico" not in result:
        result["pico"] = result.pop("pico_peco")

    # ── Map P/I/C/O shorthand to full names ──
    pico = result.get("pico", {})
    shorthand_map = {
        "P": "population", "I": "intervention_or_exposure",
        "C": "comparator", "O": "outcomes",
        "E": "intervention_or_exposure",  # PECO variant
    }
    mapped_pico = {}
    for key, val in pico.items():
        full_key = shorthand_map.get(key, key)
        mapped_pico[full_key] = val
    result["pico"] = mapped_pico
    pico = result["pico"]

    # Ensure all 5 PICO components exist
    for key in ["population", "intervention_or_exposure", "comparator", "outcomes", "context"]:
        if key not in pico:
            pico[key] = {"raw": "", "english_terms": [], "required": False}
        comp = pico[key]
        # Normalize string values to dict
        if isinstance(comp, str):
            pico[key] = {"raw": comp, "english_terms": [comp.lower()] if comp else [], "required": key in ["intervention_or_exposure"]}
        elif isinstance(comp, list):
            pico[key] = {"raw": "; ".join(comp), "english_terms": comp, "required": key in ["intervention_or_exposure"]}
        elif isinstance(comp, dict):
            if "english_terms" not in comp:
                comp["english_terms"] = []
            if "required" not in comp:
                comp["required"] = key in ["intervention_or_exposure"]
            if "raw" not in comp:
                comp["raw"] = ""
            # Normalize string english_terms to list
            if isinstance(comp["english_terms"], str):
                comp["english_terms"] = [comp["english_terms"]]
        else:
            pico[key] = {"raw": str(comp), "english_terms": [str(comp).lower()], "required": False}

    # Ensure term lists
    for field in ["mandatory_terms", "optional_terms", "exclusion_terms"]:
        if field not in result:
            result[field] = []

    # Ensure pubmed_query
    if "pubmed_query" not in result or not result["pubmed_query"]:
        result["pubmed_query"] = _build_fallback_pubmed_query(result)

    # Ensure mandatory_terms include the core intervention (keep it tight: max 5)
    interv = result["pico"].get("intervention_or_exposure", {})
    if interv.get("required") and interv.get("english_terms"):
        for t in interv["english_terms"][:1]:  # Only add the primary intervention term
            if t not in result["mandatory_terms"] and len(t.split()) <= 3:
                result["mandatory_terms"].insert(0, t)

    # Trim to max 5 most important terms
    result["mandatory_terms"] = result["mandatory_terms"][:5]

    # Ensure exclusion_terms cover standard exclusions for human exercise studies
    standard_exclusions = ["animal", "rat", "mouse", "mice", "cell line", "in vitro"]
    for ex in standard_exclusions:
        if ex not in result["exclusion_terms"]:
            result["exclusion_terms"].append(ex)


def _build_fallback_pubmed_query(result: dict) -> str:
    """Build a PubMed query from PICO components when LLM doesn't provide one."""
    groups = []

    for pico_key, label in [
        ("intervention_or_exposure", "intervention"),
        ("population", "population"),
        ("outcomes", "outcomes"),
    ]:
        comp = result["pico"].get(pico_key, {})
        terms = comp.get("english_terms", []) if isinstance(comp, dict) else []
        if terms:
            clauses = " OR ".join(
                f'"{t}"[Title/Abstract]' for t in terms[:5]
            )
            groups.append(f"({clauses})")

    if groups:
        query = " AND ".join(groups)
        query += ' AND ("systematic review"[Publication Type] OR "meta-analysis"[Publication Type] OR "randomized controlled trial"[Publication Type])'
        return query

    return ""


# ── Regex fallback ──────────────────────────────────────────────────

def _regex_decompose(topic: str) -> dict:
    """Regex-based decomposition for English input. Limited but works offline."""
    topic_lower = topic.lower()

    pico = {
        "population": {"raw": "", "english_terms": [], "required": False},
        "intervention_or_exposure": {"raw": "", "english_terms": [], "required": True},
        "comparator": {"raw": "", "english_terms": [], "required": False},
        "outcomes": {"raw": "", "english_terms": [], "required": False},
        "context": {"raw": "运动科学", "english_terms": ["exercise", "training", "sport", "physical activity"], "required": False},
    }

    # Population patterns
    pop_patterns = [
        (r"(?:in|among|for)\s+(?:the\s+)?(elderly|older\s+adults?|middle[\s-]*aged|adolescents?|youth|children|young\s+adults?|adults?)", "age"),
        (r"(?:elite|professional|recreational|competitive|amateur|collegiate)\s+(?:athletes?|sportsmen|players?|runners?|cyclists?|swimmers?|football|soccer|basketball)", "athlete"),
        (r"(?:athletes?|players?|runners?|cyclists?|swimmers?)", "athlete"),
        (r"(?:patients?\s+(?:with|after))\s*([\w\s,;-]+?)(?:\s*(?:,|undergo|receiv|\.))", "clinical"),
        (r"(obesity|obese|diabet(?:ic|es)|hypertensi(?:on|ve)|overweight)", "clinical"),
    ]
    for pattern, _ in pop_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            groups = match.groups()
            raw = groups[0].strip() if groups else match.group(0).strip()
            pico["population"]["raw"] = raw
            pico["population"]["english_terms"] = [t.strip().lower() for t in raw.replace(",", " ").split() if len(t.strip()) > 2][:5]
            pico["population"]["required"] = True
            break

    # Intervention patterns
    interv_patterns = [
        (r"((?:high[\s-]*intensity|HIIT|interval|resistance|strength|endurance|aerobic|anaerobic|plyometric|sprint|power|agility|flexibility|concurrent|periodi[sz]ed|optimal\s+load|OPL|blood\s+flow\s+restriction|BFR)[\w\s-]*(?:training|exercise|intervention|program|protocol)?)", None),
        (r"(creatine|caffeine|protein|beta[\s-]*alanine|nitrate|bicarbonate|carbohydrate|whey|casein|BCAA|HMB|vitamin\s*D|omega[\s-]*3)", None),
        (r"(ACL\s*(?:reconstruction|injury|rehab|prevention)|anterior\s+cruciate|tendinopathy|rehabilitation|return[\s-]*to[\s-]*(?:sport|play)|injury\s+prevention|neuromuscular\s+training)", None),
        (r"(heart\s+rate\s+variability|HRV|training\s+load\s+monitor)", None),
    ]
    for pattern, _ in interv_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            groups = match.groups()
            raw = groups[0].strip() if groups else match.group(0).strip()
            pico["intervention_or_exposure"]["raw"] = raw
            pico["intervention_or_exposure"]["english_terms"] = [t.strip().lower() for t in raw.replace(",", " ").split() if len(t.strip()) > 2][:5]
            pico["intervention_or_exposure"]["required"] = True
            break

    # Outcome patterns
    outcome_patterns = [
        (r"VO2\s*max|maximal\s+oxygen\s+uptake|VO2|aerobic\s+capacity", "vo2"),
        (r"muscle\s+strength|muscular\s+strength|strength\s+gain", "strength"),
        (r"muscle\s+hypertrophy|muscle\s+mass|lean\s+mass|body\s+composition|fat[\s-]*free\s+mass", "hypertrophy"),
        (r"jump\s+performance|sprint\s+performance|power\s+output|athletic\s+performance", "performance"),
        (r"injury\s+risk|injury\s+prevention|injury\s+rate|return\s+to\s+sport", "injury"),
        (r"heart\s+rate\s+variability|HRV|autonomic", "hrv"),
        (r"lactate\s+threshold|blood\s+lactate|anaerobic\s+threshold", "lactate"),
    ]
    for pattern, _ in outcome_patterns:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            raw = match.group(0).strip()
            pico["outcomes"]["raw"] = raw
            pico["outcomes"]["english_terms"] = [t.strip().lower() for t in raw.replace(",", " ").split() if len(t.strip()) > 2][:5]
            pico["outcomes"]["required"] = True
            break

    # Build terms
    mandatory_terms = []
    for key in ["intervention_or_exposure", "population", "outcomes"]:
        comp = pico.get(key, {})
        if comp.get("required") and comp.get("english_terms"):
            mandatory_terms.extend(comp["english_terms"][:3])

    # Build optional terms from context
    optional_terms = []
    context = pico.get("context", {})
    if context.get("english_terms"):
        optional_terms.extend(context["english_terms"])

    # Exclusion terms
    exclusion_terms = ["animal", "rat", "mouse", "mice", "cell line", "in vitro",
                       "molecular docking", "robot", "algorithm"]

    # Build PubMed query
    pubmed_query = _build_fallback_pubmed_query({
        "pico": pico,
        "mandatory_terms": mandatory_terms,
    })

    return {
        "pico": pico,
        "mandatory_terms": mandatory_terms,
        "optional_terms": optional_terms,
        "exclusion_terms": exclusion_terms,
        "pubmed_query": pubmed_query,
    }


# ── Public API ──────────────────────────────────────────────────────

def understand_topic(topic: str, use_llm: bool = True) -> dict:
    """Decompose a natural language research topic into structured query plan.

    Args:
        topic: Natural language research topic (Chinese or English)
        use_llm: Whether to use LLM for decomposition (default True)

    Returns:
        Dict with:
        - pico: structured PICO/PECO with english_terms per component
        - mandatory_terms: terms that MUST appear in title/abstract
        - optional_terms: terms that are nice-to-have
        - exclusion_terms: terms that indicate irrelevance if present
        - pubmed_query: ready-to-use PubMed query string
    """
    if not topic or not topic.strip():
        return _empty_result()

    if use_llm:
        return _llm_decompose(topic.strip())
    else:
        return _regex_decompose(topic.strip())


def _empty_result() -> dict:
    return {
        "pico": {
            "population": {"raw": "", "english_terms": [], "required": False},
            "intervention_or_exposure": {"raw": "", "english_terms": [], "required": True},
            "comparator": {"raw": "", "english_terms": [], "required": False},
            "outcomes": {"raw": "", "english_terms": [], "required": False},
            "context": {"raw": "", "english_terms": [], "required": False},
        },
        "mandatory_terms": [],
        "optional_terms": [],
        "exclusion_terms": [],
        "pubmed_query": "",
    }
