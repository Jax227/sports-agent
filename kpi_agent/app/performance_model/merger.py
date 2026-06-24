"""
Merger for determinant candidates: deduplication, alias standardization,
and cross-candidate consolidation.

Uses rapidfuzz for fuzzy matching and taxonomy canonical names for
standardization. Avoids merging candidates across different categories
unless canonical names are identical.
"""

import logging
from typing import Optional

from app.performance_model.taxonomy import get_canonical_name

logger = logging.getLogger(__name__)

# ── rapidfuzz availability ────────────────────────────────────────────

_fuzz_available = None

def _check_rapidfuzz() -> bool:
    global _fuzz_available
    if _fuzz_available is None:
        try:
            from rapidfuzz import fuzz  # noqa: F401
            _fuzz_available = True
        except ImportError:
            logger.info("rapidfuzz not installed, using simple word overlap for merging")
            _fuzz_available = False
    return _fuzz_available


# ── Semantic similarity (optional) ─────────────────────────────────────

_st_available = None

def _check_sentence_transformers() -> bool:
    global _st_available
    if _st_available is None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            _st_available = True
        except ImportError:
            _st_available = False
    return _st_available


# ── Normalization helpers ──────────────────────────────────────────────

# Manual alias groups for terms known to be synonyms
ALIAS_GROUPS = [
    {
        "canonical": "vo2max",
        "aliases": {"vo2max", "vo2 max", "v̇o2max", "maximal oxygen uptake",
                     "maximum oxygen uptake", "maximal oxygen consumption",
                     "aerobic capacity", "vo2peak", "peak vo2"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "lactate_threshold",
        "aliases": {"lactate threshold", "lactate turnpoint", "obla",
                     "onset of blood lactate accumulation", "blood lactate threshold"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "running_economy",
        "aliases": {"running economy", "movement economy", "exercise economy",
                     "oxygen cost", "energy cost", "metabolic cost"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "maximal_strength",
        "aliases": {"maximal strength", "maximum strength", "relative strength",
                     "force production", "muscle strength", "muscular strength"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "power_output",
        "aliases": {"power output", "peak power", "mean power", "muscle power",
                     "anaerobic power", "maximal power"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "sprint_ability",
        "aliases": {"sprint ability", "sprint performance", "sprint speed",
                     "maximal sprint speed", "maximum speed", "mss"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "heart_rate",
        "aliases": {"heart rate", "hr", "maximal heart rate", "hrmax", "hr max",
                     "resting heart rate", "exercise heart rate"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "heart_rate_variability",
        "aliases": {"heart rate variability", "hrv", "rmssd", "sdnn"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "anaerobic_capacity",
        "aliases": {"anaerobic capacity", "anaerobic performance", "anaerobic fitness",
                     "maximal anaerobic power", "wingate"},
        "category": "physiological_requirements",
    },
    {
        "canonical": "stride_length",
        "aliases": {"stride length", "step length", "stride distance"},
        "category": "technical_requirements",
    },
    {
        "canonical": "stride_frequency",
        "aliases": {"stride frequency", "step frequency", "stride rate", "cadence"},
        "category": "technical_requirements",
    },
    {
        "canonical": "ground_contact_time",
        "aliases": {"ground contact time", "gct", "contact time", "stance time"},
        "category": "technical_requirements",
    },
    {
        "canonical": "running_mechanics",
        "aliases": {"running mechanics", "running technique", "running form",
                     "gait pattern", "gait analysis"},
        "category": "technical_requirements",
    },
    {
        "canonical": "pacing_strategy",
        "aliases": {"pacing strategy", "pacing", "pacing pattern", "race strategy",
                     "pacing profile", "race tactics"},
        "category": "tactical_requirements",
    },
    {
        "canonical": "decision_making",
        "aliases": {"decision making", "decision speed", "game intelligence",
                     "tactical knowledge", "game reading"},
        "category": "tactical_requirements",
    },
    {
        "canonical": "reaction_time",
        "aliases": {"reaction time", "response time", "simple reaction time",
                     "choice reaction time", "processing speed"},
        "category": "psychological_skills",
    },
    {
        "canonical": "injury_risk",
        "aliases": {"injury risk", "injury incidence", "injury rate",
                     "injury burden", "injury epidemiology"},
        "category": "health",
    },
    {
        "canonical": "training_load",
        "aliases": {"training load", "internal load", "external load",
                     "load management", "training stress"},
        "category": "health",
    },
    {
        "canonical": "recovery",
        "aliases": {"recovery", "recovery time", "recovery strategy",
                     "active recovery", "post-exercise recovery"},
        "category": "health",
    },
    {
        "canonical": "sleep_quality",
        "aliases": {"sleep quality", "sleep duration", "sleep efficiency",
                     "sleep deprivation", "sleep disorder"},
        "category": "health",
    },
    {
        "canonical": "body_composition",
        "aliases": {"body composition", "body fat", "body fat percentage",
                     "lean body mass", "fat free mass", "body mass"},
        "category": "nutritional_requirements",
    },
]


def _build_alias_map() -> dict[str, str]:
    """Build a mapping from any alias to its canonical form."""
    alias_map: dict[str, str] = {}
    for group in ALIAS_GROUPS:
        canonical = group["canonical"]
        for alias in group["aliases"]:
            alias_map[alias.lower().strip()] = canonical
    return alias_map


ALIAS_TO_CANONICAL = _build_alias_map()


def normalize_name(name: str) -> str:
    """Normalize a term to its standard canonical form."""
    name_lower = name.strip().lower()
    # Check alias groups first
    if name_lower in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[name_lower]
    # Then taxonomy canonical mapping
    return get_canonical_name(name_lower)


def _similarity(a: str, b: str) -> float:
    """Compute string similarity between two terms (0-1)."""
    if _check_rapidfuzz():
        from rapidfuzz import fuzz
        return fuzz.token_sort_ratio(a, b) / 100.0
    # Fallback: simple word overlap
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))


def _semantic_similarity(texts_a: list[str], texts_b: list[str]) -> Optional[list[float]]:
    """Compute semantic similarity via sentence-transformers. Returns None if unavailable."""
    if not _check_sentence_transformers():
        return None
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb_a = model.encode(texts_a, show_progress_bar=False)
        emb_b = model.encode(texts_b, show_progress_bar=False)
        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(emb_a, emb_b).diagonal().tolist()
    except Exception as e:
        logger.warning(f"Semantic similarity failed: {e}")
        return None


def merge_determinant_candidates(
    candidates: list,
    fuzzy_threshold: float = 0.85,
    semantic_threshold: float = 0.82,
) -> list:
    """Merge duplicate and similar determinant candidates.

    Merging logic:
    1. Exact canonical name match → merge
    2. Alias group match → merge
    3. rapidfuzz similarity > threshold AND same category → merge
    4. Cross-category: only merge if canonical names are identical

    Args:
        candidates: List of DeterminantCandidate objects.
        fuzzy_threshold: rapidfuzz token_sort_ratio threshold (0-1).
        semantic_threshold: cosine similarity threshold (0-1).

    Returns:
        Merged list of DeterminantCandidate objects.
    """
    if len(candidates) <= 1:
        return list(candidates)

    # Build index by canonical name
    by_canonical: dict[str, list] = {}
    for c in candidates:
        name = c.canonical_name if hasattr(c, 'canonical_name') else c.get("canonical_name", "")
        if name not in by_canonical:
            by_canonical[name] = []
        by_canonical[name].append(c)

    # Step 1: Merge exact canonical name matches
    merged: dict[str, object] = {}
    merge_log = []
    for name, group in by_canonical.items():
        base = _copy_candidate(group[0])
        for c in group[1:]:
            base = _merge_two(base, c)
            merge_log.append(f"exact merge: {name}")
        merged[name] = base

    # Step 2: Apply alias groups
    alias_groups_found: dict[str, list] = {}
    for name in list(merged.keys()):
        normalized = normalize_name(name)
        if normalized != name:
            if normalized not in alias_groups_found:
                alias_groups_found[normalized] = []
            alias_groups_found[normalized].append(name)

    for canonical, names in alias_groups_found.items():
        if len(names) >= 2:
            base = merged.pop(names[0])
            for name in names[1:]:
                if name in merged:
                    base = _merge_two(base, merged.pop(name))
                    merge_log.append(f"alias merge: {name} → {canonical}")
            # Update canonical name
            if hasattr(base, 'canonical_name'):
                base.canonical_name = canonical
            else:
                base['canonical_name'] = canonical
            merged[canonical] = base

    # Step 3: Fuzzy merge within same category
    names_list = list(merged.keys())
    values_list = list(merged.values())
    n = len(names_list)

    # Precompute display names
    display_names = []
    for v in values_list:
        if hasattr(v, 'display_name_en'):
            display_names.append(v.display_name_en)
        else:
            display_names.append(v.get('display_name_en', ''))

    # Try semantic batch merge if available
    semantic_results = _semantic_similarity(display_names, display_names)
    if semantic_results:
        import math
        total = len(display_names)
        merged_flags = [False] * total
        for i in range(total):
            if merged_flags[i]:
                continue
            cat_i = _get_category(values_list[i])
            for j in range(i + 1, total):
                if merged_flags[j]:
                    continue
                cat_j = _get_category(values_list[j])
                # Only merge same category or strong semantic match
                sim = semantic_results[i * total + j] if isinstance(semantic_results, list) else semantic_results[i * total + j]
                if sim >= semantic_threshold and (cat_i == cat_j or sim >= 0.90):
                    values_list[i] = _merge_two(values_list[i], values_list[j])
                    merged_flags[j] = True
                    merge_log.append(f"semantic merge: {names_list[j]} → {names_list[i]} (sim={sim:.3f})")

        # Remove merged
        new_merged = {}
        for i, name in enumerate(names_list):
            if not merged_flags[i]:
                new_merged[name] = values_list[i]
        merged = new_merged

    # Step 4: Fuzzy string matching as final pass
    names_list = list(merged.keys())
    values_list = list(merged.values())
    skip = set()
    for i in range(len(names_list)):
        if i in skip:
            continue
        cat_i = _get_category(values_list[i])
        for j in range(i + 1, len(names_list)):
            if j in skip:
                continue
            cat_j = _get_category(values_list[j])
            # Don't merge across categories via fuzzy matching
            if cat_i != cat_j and cat_i != "other_uncertain" and cat_j != "other_uncertain":
                continue
            sim = _similarity(names_list[i], names_list[j])
            if sim >= fuzzy_threshold:
                values_list[i] = _merge_two(values_list[i], values_list[j])
                skip.add(j)
                merge_log.append(f"fuzzy merge: {names_list[j]} → {names_list[i]} (sim={sim:.3f})")

    final = [values_list[i] for i in range(len(names_list)) if i not in skip]

    if merge_log:
        logger.info(f"Merged {len(merge_log)} candidate groups: {'; '.join(merge_log[:10])}")

    # Recompute scores after merge
    for c in final:
        _recompute_scores(c)

    return final


def _copy_candidate(c) -> object:
    """Shallow copy a candidate (dict or object)."""
    if hasattr(c, 'to_dict'):
        new = c.__class__(
            canonical_name=c.canonical_name,
            display_name_en=c.display_name_en,
            display_name_cn=c.display_name_cn,
            category_key=c.category_key,
        )
        new.aliases = set(c.aliases)
        new.evidence_sentences = list(c.evidence_sentences)
        new.source_literature_ids = set(c.source_literature_ids)
        new.source_databases = set(c.source_databases)
        new.matched_terms = set(c.matched_terms)
        new.extraction_methods = set(c.extraction_methods)
        new.confidence_score = c.confidence_score
        new.relevance_score = c.relevance_score
        new.evidence_strength_score = c.evidence_strength_score
        if hasattr(c, 'context_category_keys'):
            new.context_category_keys = dict(c.context_category_keys)
        return new
    else:
        import copy
        return copy.deepcopy(c)


def _merge_two(a, b) -> object:
    """Merge b into a (a is the primary)."""
    if hasattr(a, 'aliases'):
        a.aliases.update(b.aliases if hasattr(b, 'aliases') else set())
        a.matched_terms.update(b.matched_terms if hasattr(b, 'matched_terms') else set())
        a.extraction_methods.update(b.extraction_methods if hasattr(b, 'extraction_methods') else set())
        a.source_literature_ids.update(b.source_literature_ids if hasattr(b, 'source_literature_ids') else set())
        a.source_databases.update(b.source_databases if hasattr(b, 'source_databases') else set())

        existing_ids = {e.get("literature_id") for e in a.evidence_sentences}
        for ev in (b.evidence_sentences if hasattr(b, 'evidence_sentences') else []):
            if ev.get("literature_id") not in existing_ids:
                a.evidence_sentences.append(ev)
                existing_ids.add(ev.get("literature_id"))

        if hasattr(a, 'context_category_keys') and hasattr(b, 'context_category_keys'):
            for k, v in b.context_category_keys.items():
                a.context_category_keys[k] = a.context_category_keys.get(k, 0) + v
    else:
        # dict-based candidate
        a['aliases'] = list(set(a.get('aliases', [])) | set(b.get('aliases', [])))
        a['matched_terms'] = list(set(a.get('matched_terms', [])) | set(b.get('matched_terms', [])))
        a['extraction_methods'] = list(set(a.get('extraction_methods', [])) | set(b.get('extraction_methods', [])))
        a['source_literature_ids'] = list(set(a.get('source_literature_ids', [])) | set(b.get('source_literature_ids', [])))
        a['source_databases'] = list(set(a.get('source_databases', [])) | set(b.get('source_databases', [])))
        existing_ids = {e.get("literature_id") for e in a.get('evidence_sentences', [])}
        for ev in b.get('evidence_sentences', []):
            if ev.get("literature_id") not in existing_ids:
                a.setdefault('evidence_sentences', []).append(ev)

    return a


def _get_category(c) -> str:
    """Get category from candidate (dict or object)."""
    if hasattr(c, 'category_key'):
        return c.category_key
    return c.get('category_key', 'other_uncertain')


def _recompute_scores(c):
    """Recompute scores after merge."""
    if hasattr(c, 'source_literature_ids'):
        source_count = len(c.source_literature_ids)
    else:
        source_count = len(c.get('source_literature_ids', []))

    if hasattr(c, 'source_databases'):
        db_count = len(c.source_databases)
    else:
        db_count = len(c.get('source_databases', []))

    if hasattr(c, 'evidence_sentences'):
        evidence_count = len(c.evidence_sentences)
        methods = c.extraction_methods
    else:
        evidence_count = len(c.get('evidence_sentences', []))
        methods = set(c.get('extraction_methods', []))

    # Confidence: more methods + more evidence = higher
    conf = 0.1
    if "dictionary" in methods:
        conf += 0.3
    if evidence_count >= 3:
        conf += 0.2
    if evidence_count >= 5:
        conf += 0.15
    if len(methods) >= 2:
        conf += 0.15
    if len(methods) >= 3:
        conf += 0.1
    conf = min(conf, 1.0)

    # Evidence strength: more sources = stronger
    strength = min(0.1 + source_count * 0.1 + db_count * 0.05, 1.0)

    if hasattr(c, 'confidence_score'):
        c.confidence_score = conf
        c.evidence_strength_score = strength
        # Relevance is the average, kept as-is from extraction
    else:
        c['confidence_score'] = conf
        c['evidence_strength_score'] = strength


def standardize_all_names(candidates: list) -> list:
    """Apply canonical name normalization to all candidates."""
    for c in candidates:
        if hasattr(c, 'canonical_name'):
            c.canonical_name = normalize_name(c.canonical_name)
            if not c.display_name_cn:
                from app.performance_model.taxonomy import get_category_name_cn
                c.display_name_cn = get_category_name_cn(c.category_key)
        else:
            c['canonical_name'] = normalize_name(c.get('canonical_name', ''))
    return candidates
