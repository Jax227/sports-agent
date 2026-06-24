"""
Multi-method determinant candidate extractor.

Extraction pipeline per document:
1. Text preprocessing (merge title+abstract, split sentences, clean)
2. Domain dictionary matching (8-category keyword matching)
3. KeyBERT keyphrase extraction (if available, falls back to YAKE)
4. YAKE unsupervised keyword extraction (lightweight fallback)
5. spaCy noun phrase extraction (if available)
6. Regex + dictionary final fallback

All methods are free and local. No commercial LLM API calls.
"""

import logging
import re
import json as _json
from collections import defaultdict
from typing import Optional

from app.performance_model.taxonomy import (
    CATEGORY_KEYWORD_MAP,
    get_canonical_name,
    classify_term,
    get_all_keywords,
)
from app.performance_model.batch_loader import LiteratureDocument

logger = logging.getLogger(__name__)

# ── Known terms from taxonomy (flattened) ──────────────────────────────

ALL_KEYWORDS: dict[str, set[str]] = get_all_keywords()
FLAT_KEYWORDS: set[str] = set()
for _kws in ALL_KEYWORDS.values():
    FLAT_KEYWORDS.update(_kws)


# ═══════════════════════════════════════════════════════════════════════
# Data class
# ═══════════════════════════════════════════════════════════════════════

class DeterminantCandidate:
    """A single determinant candidate extracted from literature."""

    __slots__ = (
        "canonical_name", "display_name_en", "display_name_cn", "category_key",
        "aliases", "evidence_sentences", "source_literature_ids",
        "source_databases", "matched_terms", "extraction_methods",
        "confidence_score", "relevance_score", "evidence_strength_score",
        "context_category_keys",
    )

    def __init__(
        self,
        canonical_name: str = "",
        display_name_en: str = "",
        display_name_cn: str = "",
        category_key: str = "other_uncertain",
    ):
        self.canonical_name = canonical_name
        self.display_name_en = display_name_en or canonical_name.replace("_", " ")
        self.display_name_cn = display_name_cn
        self.category_key = category_key
        self.aliases: set[str] = set()
        self.evidence_sentences: list[dict] = []  # [{text, literature_id, location, doi, year}]
        self.source_literature_ids: set[int] = set()
        self.source_databases: set[str] = set()
        self.matched_terms: set[str] = set()
        self.extraction_methods: set[str] = set()
        self.confidence_score: float = 0.0
        self.relevance_score: float = 0.0
        self.evidence_strength_score: float = 0.0
        self.context_category_keys: dict[str, int] = defaultdict(int)  # cat_key -> count

    def to_dict(self) -> dict:
        return {
            "canonical_name": self.canonical_name,
            "display_name_en": self.display_name_en,
            "display_name_cn": self.display_name_cn,
            "category_key": self.category_key,
            "aliases": sorted(self.aliases),
            "evidence_sentences": self.evidence_sentences,
            "source_literature_ids": sorted(self.source_literature_ids),
            "source_databases": sorted(self.source_databases),
            "matched_terms": sorted(self.matched_terms),
            "extraction_methods": sorted(self.extraction_methods),
            "confidence_score": self.confidence_score,
            "relevance_score": self.relevance_score,
            "evidence_strength_score": self.evidence_strength_score,
        }


# ═══════════════════════════════════════════════════════════════════════
# Text preprocessing
# ═══════════════════════════════════════════════════════════════════════

def _preprocess_text(doc: LiteratureDocument, include_fulltext: bool = True) -> tuple[str, list[dict]]:
    """Combine and clean text from a document. Returns (full_text, sentence_list)."""
    parts = []
    if doc.title:
        parts.append(doc.title)
    if doc.abstract:
        parts.append(doc.abstract)

    text = "\n\n".join(parts)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x00-\x7F一-鿿　-〿＀-￯]+", " ", text)

    # Simple sentence splitting
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sent_list = [
        {"text": s.strip(), "location": _guess_location(s, doc)}
        for s in sentences if len(s.strip()) > 10
    ]

    return text.lower(), sent_list


def _guess_location(sentence: str, doc: LiteratureDocument) -> str:
    """Guess which section a sentence belongs to."""
    if doc.title and sentence[:60].lower() in doc.title.lower():
        return "title"
    if doc.abstract and sentence[:80].lower() in doc.abstract.lower():
        return "abstract"
    return "fulltext"


# ═══════════════════════════════════════════════════════════════════════
# Method 1: Domain dictionary matching (ground truth)
# ═══════════════════════════════════════════════════════════════════════

def _extract_by_dictionary(text: str, sentences: list[dict], doc: LiteratureDocument) -> list[DeterminantCandidate]:
    """Extract terms by matching against the 8-category keyword dictionaries."""
    candidates: dict[str, DeterminantCandidate] = {}

    for cat_key, keywords in CATEGORY_KEYWORD_MAP.items():
        for kw in keywords:
            pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
            matches = pattern.finditer(text)
            for match in matches:
                matched_term = match.group(0).strip().lower()
                canonical = get_canonical_name(matched_term)

                if canonical not in candidates:
                    candidates[canonical] = DeterminantCandidate(
                        canonical_name=canonical,
                        display_name_en=matched_term,
                        category_key=cat_key,
                    )
                c = candidates[canonical]
                c.aliases.add(matched_term)
                c.matched_terms.add(matched_term)
                c.extraction_methods.add("dictionary")
                c.source_literature_ids.add(doc.literature_id)
                if doc.source_databases:
                    c.source_databases.update(doc.source_databases)
                c.context_category_keys[cat_key] += 1

                # Find containing sentence
                span_start = max(0, match.start() - 20)
                span_end = min(len(text), match.end() + 100)
                context = text[span_start:span_end].strip()

                # Find best matching sentence
                evidence_sentence = ""
                evidence_location = "unknown"
                for sent in sentences:
                    if matched_term in sent["text"].lower():
                        evidence_sentence = sent["text"]
                        evidence_location = sent["location"]
                        break
                if not evidence_sentence:
                    evidence_sentence = context
                    evidence_location = _guess_location(context, doc)

                # Only add if unique per doc
                existing_doc_ids = {e.get("literature_id") for e in c.evidence_sentences}
                if doc.literature_id not in existing_doc_ids:
                    c.evidence_sentences.append({
                        "text": evidence_sentence[:500],
                        "literature_id": doc.literature_id,
                        "location": evidence_location,
                        "doi": doc.doi,
                        "year": doc.year,
                        "matched_term": matched_term,
                    })

    return list(candidates.values())


# ═══════════════════════════════════════════════════════════════════════
# Method 2: YAKE keyword extraction (lightweight, no training needed)
# ═══════════════════════════════════════════════════════════════════════

_yake_available = None

def _check_yake() -> bool:
    global _yake_available
    if _yake_available is None:
        try:
            import yake  # noqa: F401
            _yake_available = True
        except ImportError:
            logger.info("yake not installed, skipping YAKE extraction")
            _yake_available = False
    return _yake_available


def _extract_by_yake(text: str, doc: LiteratureDocument, max_ngram: int = 3, top_n: int = 30) -> list[DeterminantCandidate]:
    """Extract keyphrases using YAKE unsupervised algorithm."""
    if not _check_yake():
        return []

    import yake

    candidates: dict[str, DeterminantCandidate] = {}
    try:
        kw_extractor = yake.KeywordExtractor(lan="en", n=max_ngram, top=top_n, features=None)
        keywords = kw_extractor.extract_keywords(text)
    except Exception as e:
        logger.warning(f"YAKE extraction error: {e}")
        return []

    for kw, score in keywords:
        kw_lower = kw.strip().lower()
        if len(kw_lower) < 3:
            continue

        canonical = get_canonical_name(kw_lower)
        category = classify_term(canonical) or classify_term(kw_lower)

        if canonical not in candidates:
            candidates[canonical] = DeterminantCandidate(
                canonical_name=canonical,
                display_name_en=kw_lower,
                category_key=category,
            )
        c = candidates[canonical]
        c.aliases.add(kw_lower)
        c.matched_terms.add(kw_lower)
        c.extraction_methods.add("yake")
        c.source_literature_ids.add(doc.literature_id)
        c.context_category_keys[category] += 1

        if doc.literature_id not in {e.get("literature_id") for e in c.evidence_sentences}:
            c.evidence_sentences.append({
                "text": kw_lower,
                "literature_id": doc.literature_id,
                "location": "auto_extracted",
                "doi": doc.doi,
                "year": doc.year,
                "matched_term": kw_lower,
            })

    return list(candidates.values())


# ═══════════════════════════════════════════════════════════════════════
# Method 3: KeyBERT keyphrase extraction
# ═══════════════════════════════════════════════════════════════════════

_keybert_available = None

def _check_keybert() -> bool:
    global _keybert_available
    if _keybert_available is None:
        try:
            from keybert import KeyBERT  # noqa: F401
            _keybert_available = True
        except ImportError:
            logger.info("keybert not installed, skipping KeyBERT extraction")
            _keybert_available = False
    return _keybert_available


def _extract_by_keybert(text: str, doc: LiteratureDocument, top_n: int = 30) -> list[DeterminantCandidate]:
    """Extract keyphrases using KeyBERT with sentence-transformers."""
    if not _check_keybert():
        return []

    from keybert import KeyBERT

    candidates: dict[str, DeterminantCandidate] = {}
    try:
        kw_model = KeyBERT()
        keywords = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            top_n=top_n,
            use_maxsum=False,
            use_mmr=True,
            diversity=0.5,
        )
    except Exception as e:
        logger.warning(f"KeyBERT extraction error: {e}")
        return []

    for kw, score in keywords:
        kw_lower = kw.strip().lower()
        if len(kw_lower) < 3:
            continue

        canonical = get_canonical_name(kw_lower)
        category = classify_term(canonical) or classify_term(kw_lower)

        if canonical not in candidates:
            candidates[canonical] = DeterminantCandidate(
                canonical_name=canonical,
                display_name_en=kw_lower,
                category_key=category,
            )
        c = candidates[canonical]
        c.aliases.add(kw_lower)
        c.matched_terms.add(kw_lower)
        c.extraction_methods.add("keybert")
        c.source_literature_ids.add(doc.literature_id)

        if doc.literature_id not in {e.get("literature_id") for e in c.evidence_sentences}:
            c.evidence_sentences.append({
                "text": kw_lower,
                "literature_id": doc.literature_id,
                "location": "auto_extracted",
                "doi": doc.doi,
                "year": doc.year,
                "matched_term": kw_lower,
            })

    return list(candidates.values())


# ═══════════════════════════════════════════════════════════════════════
# Method 4: spaCy noun phrase extraction
# ═══════════════════════════════════════════════════════════════════════

_spacy_available = None

def _check_spacy() -> bool:
    global _spacy_available
    if _spacy_available is None:
        try:
            import spacy  # noqa: F401
            _spacy_available = True
        except ImportError:
            logger.info("spaCy not installed, skipping NP extraction")
            _spacy_available = False
    return _spacy_available


def _extract_by_spacy(text: str, doc: LiteratureDocument) -> list[DeterminantCandidate]:
    """Extract noun phrases using spaCy."""
    if not _check_spacy():
        return []

    import spacy
    candidates: dict[str, DeterminantCandidate] = {}
    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "textcat"])
    except Exception:
        try:
            nlp = spacy.load("en_core_web_sm", disable=["ner", "textcat"])
        except Exception:
            logger.warning("spaCy model 'en_core_web_sm' not found, skipping NP extraction")
            return []

    try:
        doc_nlp = nlp(text[:100000])  # limit to avoid OOM
        for chunk in doc_nlp.noun_chunks:
            phrase = chunk.text.strip().lower()
            if len(phrase) < 3 or len(phrase.split()) > 5:
                continue

            canonical = get_canonical_name(phrase)
            category = classify_term(canonical) or classify_term(phrase)

            if canonical not in candidates:
                candidates[canonical] = DeterminantCandidate(
                    canonical_name=canonical,
                    display_name_en=phrase,
                    category_key=category,
                )
            c = candidates[canonical]
            c.aliases.add(phrase)
            c.matched_terms.add(phrase)
            c.extraction_methods.add("spacy")
            c.source_literature_ids.add(doc.literature_id)
    except Exception as e:
        logger.warning(f"spaCy extraction error: {e}")

    return list(candidates.values())


# ═══════════════════════════════════════════════════════════════════════
# Method 5: Regex pattern matching for common metric patterns
# ═══════════════════════════════════════════════════════════════════════

METRIC_PATTERNS = [
    # VO2 patterns
    (r'(?i)(vo\s*2\s*max|v̇\s*o\s*2\s*max|maximal\s+oxygen\s+uptake)', "vo2max", "physiological_requirements"),
    # Lactate patterns
    (r'(?i)(lactate\s+threshold|blood\s+lactate|peak\s+lactate)', "lactate_threshold", "physiological_requirements"),
    # Running economy
    (r'(?i)(running\s+economy|movement\s+economy|oxygen\s+cost|energy\s+cost)', "running_economy", "physiological_requirements"),
    # Heart rate
    (r'(?i)(heart\s+rate\s+variability|hrv|maximal\s+heart\s+rate)', "heart_rate", "physiological_requirements"),
    # Speed/power
    (r'(?i)(sprint\s+(speed|ability|performance)|maximal\s+sprint\s+speed)', "sprint_ability", "physiological_requirements"),
    (r'(?i)(repeated\s+sprint\s+ability|rsa)', "repeated_sprint_ability", "physiological_requirements"),
    (r'(?i)(peak\s+power|power\s+output|rate\s+of\s+force\s+development)', "power_output", "physiological_requirements"),
    # Strength
    (r'(?i)(maximal\s+strength|relative\s+strength|force\s+production)', "maximal_strength", "physiological_requirements"),
    # Stride
    (r'(?i)(stride\s+length|stride\s+frequency|ground\s+contact\s+time)', "stride_length", "technical_requirements"),
    # Pacing
    (r'(?i)(pacing\s+strategy|race\s+strategy|pacing\s+pattern)', "pacing_strategy", "tactical_requirements"),
    # Injury
    (r'(?i)(injury\s+risk|injury\s+incidence|injury\s+prevention)', "injury_risk", "health"),
    # Training load
    (r'(?i)(training\s+load|acute\s+chronic\s+workload|overtraining)', "training_load", "health"),
    # Reaction time
    (r'(?i)(reaction\s+time|response\s+time|anticipation)', "reaction_time", "psychological_skills"),
    # Nutrition
    (r'(?i)(carbohydrate\s+intake|protein\s+intake|caffeine|creatine)', "carbohydrate_intake", "nutritional_requirements"),
    # Body composition
    (r'(?i)(body\s+composition|body\s+fat|lean\s+body\s+mass)', "body_composition", "nutritional_requirements"),
    # Sleep
    (r'(?i)(sleep\s+quality|sleep\s+duration|sleep\s+deprivation)', "sleep_quality", "health"),
    # Recovery
    (r'(?i)(recovery\s+time|active\s+recovery|post[- ]exercise\s+recovery)', "recovery", "health"),
    # Anaerobic
    (r'(?i)(anaerobic\s+capacity|anaerobic\s+power|anaerobic\s+speed\s+reserve)', "anaerobic_capacity", "physiological_requirements"),
    # Critical power
    (r'(?i)(critical\s+power|critical\s+speed|critical\s+velocity)', "critical_power", "physiological_requirements"),
    # Endurance
    (r'(?i)(endurance\s+capacity|endurance\s+performance|muscular\s+endurance)', "endurance_capacity", "physiological_requirements"),
]


def _extract_by_regex(text: str, doc: LiteratureDocument) -> list[DeterminantCandidate]:
    """Extract terms using regex patterns."""
    candidates: dict[str, DeterminantCandidate] = {}

    for pattern, canonical, category in METRIC_PATTERNS:
        for match in re.finditer(pattern, text):
            matched_text = match.group(0).strip().lower()
            if canonical not in candidates:
                candidates[canonical] = DeterminantCandidate(
                    canonical_name=canonical,
                    display_name_en=matched_text,
                    category_key=category,
                )
            c = candidates[canonical]
            c.aliases.add(matched_text)
            c.matched_terms.add(matched_text)
            c.extraction_methods.add("regex")
            c.source_literature_ids.add(doc.literature_id)
            c.context_category_keys[category] += 1

    return list(candidates.values())


# ═══════════════════════════════════════════════════════════════════════
# Main extraction orchestrator
# ═══════════════════════════════════════════════════════════════════════

def extract_determinant_candidates_from_document(
    doc: LiteratureDocument,
    include_fulltext: bool = True,
    use_keybert: bool = True,
    use_yake: bool = True,
    use_spacy: bool = False,
) -> list[DeterminantCandidate]:
    """Extract determinant candidates from a single document.

    Runs all available extraction methods and merges results by canonical name.
    """
    text, sentences = _preprocess_text(doc, include_fulltext)

    if len(text) < 20:
        logger.warning(f"Document {doc.literature_id}: text too short ({len(text)} chars), skipping")
        return []

    # Always run dictionary matching and regex (guaranteed to work)
    dict_candidates = _extract_by_dictionary(text, sentences, doc)
    regex_candidates = _extract_by_regex(text, doc)

    # Merge dict + regex first
    merged: dict[str, DeterminantCandidate] = {}
    for c in dict_candidates + regex_candidates:
        if c.canonical_name in merged:
            _merge_into(merged[c.canonical_name], c)
        else:
            merged[c.canonical_name] = c

    # YAKE (lightweight, highly recommended)
    if use_yake:
        try:
            yake_candidates = _extract_by_yake(text, doc)
            for c in yake_candidates:
                if c.canonical_name in merged:
                    _merge_into(merged[c.canonical_name], c)
                else:
                    merged[c.canonical_name] = c
        except Exception as e:
            logger.warning(f"YAKE failed for doc {doc.literature_id}: {e}")

    # KeyBERT (semantic, better quality)
    if use_keybert:
        try:
            kb_candidates = _extract_by_keybert(text, doc)
            for c in kb_candidates:
                if c.canonical_name in merged:
                    _merge_into(merged[c.canonical_name], c)
                else:
                    merged[c.canonical_name] = c
        except Exception as e:
            logger.warning(f"KeyBERT failed for doc {doc.literature_id}: {e}")

    # spaCy (optional, heavier)
    if use_spacy:
        try:
            spacy_candidates = _extract_by_spacy(text, doc)
            for c in spacy_candidates:
                if c.canonical_name in merged:
                    _merge_into(merged[c.canonical_name], c)
                else:
                    merged[c.canonical_name] = c
        except Exception as e:
            logger.warning(f"spaCy failed for doc {doc.literature_id}: {e}")

    # Compute initial scores per candidate
    for c in merged.values():
        c.confidence_score = _compute_confidence(c)
        c.relevance_score = _compute_relevance(c, doc)
        c.evidence_strength_score = _compute_evidence_strength(c, doc)

        # Resolve category from all context
        if c.context_category_keys:
            best_cat = max(c.context_category_keys, key=c.context_category_keys.get)
            if c.context_category_keys[best_cat] >= 2:
                c.category_key = best_cat

    return list(merged.values())


def extract_determinant_candidates_from_batch(
    documents: list[LiteratureDocument],
    include_fulltext: bool = True,
    use_keybert: bool = True,
    use_yake: bool = True,
    use_spacy: bool = False,
) -> list[DeterminantCandidate]:
    """Extract candidates from a batch of documents and merge across documents."""
    all_candidates: dict[str, DeterminantCandidate] = {}

    for doc in documents:
        try:
            doc_candidates = extract_determinant_candidates_from_document(
                doc, include_fulltext, use_keybert, use_yake, use_spacy
            )
            for c in doc_candidates:
                if c.canonical_name in all_candidates:
                    _merge_into(all_candidates[c.canonical_name], c)
                else:
                    all_candidates[c.canonical_name] = c
        except Exception as e:
            logger.warning(f"Extraction failed for doc {doc.literature_id}: {e}")

    return list(all_candidates.values())


def _merge_into(target: DeterminantCandidate, source: DeterminantCandidate):
    """Merge source candidate into target candidate."""
    target.aliases.update(source.aliases)
    target.matched_terms.update(source.matched_terms)
    target.extraction_methods.update(source.extraction_methods)
    target.source_literature_ids.update(source.source_literature_ids)
    target.source_databases.update(source.source_databases)
    for k, v in source.context_category_keys.items():
        target.context_category_keys[k] += v

    # Merge evidence sentences (deduplicate by literature_id)
    existing_lit_ids = {e.get("literature_id") for e in target.evidence_sentences}
    for ev in source.evidence_sentences:
        if ev.get("literature_id") not in existing_lit_ids:
            target.evidence_sentences.append(ev)
            existing_lit_ids.add(ev.get("literature_id"))


def _compute_confidence(c: DeterminantCandidate) -> float:
    """Compute confidence score based on extraction methods used."""
    score = 0.0
    methods = c.extraction_methods
    if "dictionary" in methods:
        score += 0.4
    if "regex" in methods:
        score += 0.2
    if "yake" in methods:
        score += 0.15
    if "keybert" in methods:
        score += 0.15
    if "spacy" in methods:
        score += 0.1
    # Boost if multiple methods agree
    if len(methods) >= 2:
        score += 0.15
    if len(methods) >= 3:
        score += 0.1
    return min(score, 1.0)


def _compute_relevance(c: DeterminantCandidate, doc: LiteratureDocument) -> float:
    """Compute relevance score: how relevant this candidate is to the document."""
    score = 0.0
    text_lower = (doc.title + " " + (doc.abstract or "")).lower()

    if c.canonical_name.replace("_", " ") in text_lower:
        score += 0.3
    if doc.title and any(alias in doc.title.lower() for alias in c.aliases):
        score += 0.2
    if doc.abstract and any(alias in doc.abstract.lower() for alias in c.aliases):
        score += 0.2
    # More appearances = more relevant
    evidence_count = len(c.evidence_sentences)
    if evidence_count >= 3:
        score += 0.1
    if evidence_count >= 5:
        score += 0.1
    # Higher ranked literature = higher relevance
    if doc.ranking_score and doc.ranking_score > 0.02:
        score += 0.1
    return min(score, 1.0)


def _compute_evidence_strength(c: DeterminantCandidate, doc: LiteratureDocument) -> float:
    """Compute evidence strength score."""
    score = 0.1  # baseline for existing
    # DOI availability
    if doc.doi:
        score += 0.1
    # Year recency
    if doc.year and doc.year >= 2020:
        score += 0.1
    if doc.year and doc.year >= 2023:
        score += 0.05
    # Citation count
    if doc.citation_count and doc.citation_count > 10:
        score += 0.1
    if doc.citation_count and doc.citation_count > 50:
        score += 0.1
    # Publication type
    pub_type = (doc.publication_type or "").lower()
    if any(t in pub_type for t in ["review", "meta-analysis", "systematic"]):
        score += 0.15
    # Fulltext available
    if doc.fulltext_available:
        score += 0.1
    # Multiple source databases
    if len(c.source_databases) >= 2:
        score += 0.1
    return min(score, 1.0)
