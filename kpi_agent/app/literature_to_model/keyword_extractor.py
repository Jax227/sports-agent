"""
Candidate term extraction from literature chunks.

Multi-method extraction with automatic fallback chain:
  KeyBERT → YAKE → regex + dictionary → noun phrase extraction

Every method is wrapped in try/except. If one fails, the next is tried.
"""

import logging
import re
from typing import Optional

from app.literature_to_model.schemas import LiteratureEvidenceChunk, ExtractedCandidate

logger = logging.getLogger(__name__)

# ── Dependency checks ────────────────────────────────────────────────────

_keybert_available = None
_yake_available = None
_spacy_available = None
_nltk_available = None


def _check_keybert() -> bool:
    global _keybert_available
    if _keybert_available is None:
        try:
            from keybert import KeyBERT  # noqa: F401
            _keybert_available = True
        except ImportError:
            _keybert_available = False
    return _keybert_available


def _check_yake() -> bool:
    global _yake_available
    if _yake_available is None:
        try:
            import yake  # noqa: F401
            _yake_available = True
        except ImportError:
            _yake_available = False
    return _yake_available


def _check_spacy() -> bool:
    global _spacy_available
    if _spacy_available is None:
        try:
            import spacy  # noqa: F401
            _spacy_available = True
        except ImportError:
            _spacy_available = False
    return _spacy_available


def _check_nltk_extractor() -> bool:
    global _nltk_available
    if _nltk_available is None:
        try:
            import nltk  # noqa: F401
            _nltk_available = True
        except ImportError:
            _nltk_available = False
    return _nltk_available


# ── Normalization helpers ─────────────────────────────────────────────────

def _normalize_term(term: str) -> str:
    """Normalize a candidate term to a canonical form."""
    term = term.strip().lower()
    term = re.sub(r'\s+', ' ', term)
    # Strip leading/trailing punctuation
    term = term.strip(".,;:!?()[]{}'\"")
    return term


# ── Dictionary-term matching ──────────────────────────────────────────────

# Common sports-science multi-word patterns for regex extraction
SPORTS_SCIENCE_PATTERNS = [
    # VO2/physiological measures
    r"(?:maximal|maximum|peak)\s+oxygen\s+(?:uptake|consumption)",
    r"(?:aerobic|anaerobic)\s+(?:capacity|power|threshold|fitness|endurance|performance)",
    r"lactate\s+(?:threshold|turnpoint|concentration|accumulation)",
    r"ventilatory\s+(?:threshold|equivalent)",
    r"(?:maximal|maximum|peak)\s+(?:heart\s+rate|hr)",
    r"heart\s+rate\s+(?:variability|recovery|reserve)",
    # Strength/power
    r"(?:maximal|maximum|relative|muscular|muscle)\s+strength",
    r"(?:rate\s+of\s+)?force\s+(?:production|development)",
    r"(?:peak|mean|maximal|muscle|anaerobic)\s+power(?:\s+output)?",
    # Sprint/speed
    r"(?:maximal\s+)?sprint\s+(?:speed|ability|performance|time)",
    r"(?:maximum|peak)\s+speed",
    r"(?:acceleration|speed)\s+(?:capacity|endurance)",
    # Biomechanics
    r"(?:stride|step)\s+(?:length|frequency|rate)",
    r"ground\s+contact\s+time",
    r"(?:running|movement|exercise)\s+(?:economy|mechanics|technique|form|pattern)",
    r"(?:joint|knee|hip|ankle)\s+(?:angle|moment|kinematics|kinetics)",
    # Body composition
    r"body\s+(?:composition|fat|mass|weight)",
    r"(?:lean|fat\s+free)\s+body\s+mass",
    r"bmi|body\s+mass\s+index",
    # Nutrition
    r"(?:energy|carbohydrate|protein|fat)\s+(?:intake|availability|balance)",
    r"(?:hydration|dehydration|fluid\s+intake)",
    r"glycogen\s+(?:stores|depletion|resynthesis)",
    # Psychological
    r"(?:reaction|response)\s+time",
    r"(?:mental|psychological)\s+(?:toughness|resilience|skills|fatigue)",
    r"(?:cognitive|attentional|executive)\s+(?:function|performance|load)",
    r"(?:anxiety|stress|mood)\s+(?:management|control|state)",
    # Health
    r"(?:injury|illness)\s+(?:risk|incidence|rate|prevention|surveillance)",
    r"training\s+load(?:\s+(?:management|monitoring))?",
    r"(?:sleep|recovery)\s+(?:quality|duration|efficiency|strategy|time)",
    r"(?:muscle\s+damage|muscle\s+soreness|doms)",
    r"overtraining(?:\s+syndrome)?",
    # Competition
    r"(?:scoring|ranking|qualification)\s+(?:system|standard|criteria)",
    r"(?:anti-)?doping\s+(?:control|test|violation|regulation)",
    r"(?:competition|race)\s+(?:format|strategy|rules|regulation)",
    # Equipment
    r"(?:carbon\s+(?:fiber|plate)|running\s+shoe|footwear)",
    r"(?:wearable|gps|motion\s+capture|force\s+plate)",
]


def _extract_by_regex_dictionary(text: str) -> list[dict]:
    """Extract terms using regex patterns. Returns list of {term, method, score}."""
    found = []
    seen = set()

    for pattern in SPORTS_SCIENCE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            term = _normalize_term(match.group(0))
            if term not in seen and len(term) >= 3:
                seen.add(term)
                found.append({
                    "term": term,
                    "method": "regex",
                    "score": 0.7,
                })

    return found


# ── Noun phrase extraction (spaCy or nltk fallback) ───────────────────────

def _extract_noun_phrases_spacy(text: str) -> list[dict]:
    """Extract noun phrases using spaCy."""
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.info("spaCy model en_core_web_sm not found, downloading...")
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")

    doc = nlp(text)
    found = []
    seen = set()

    for chunk in doc.noun_chunks:
        term = _normalize_term(chunk.text)
        if term not in seen and len(term) >= 3 and len(term.split()) >= 1:
            seen.add(term)
            found.append({
                "term": term,
                "method": "spacy_np",
                "score": 0.5,
            })

    return found


def _extract_noun_phrases_nltk(text: str) -> list[dict]:
    """Extract noun phrases using NLTK (fallback when spaCy unavailable)."""
    import nltk

    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
    try:
        nltk.data.find("averaged_perceptron_tagger_eng")
    except LookupError:
        nltk.download("averaged_perceptron_tagger_eng", quiet=True)
    try:
        nltk.data.find("maxent_ne_chunker_tab")
    except LookupError:
        nltk.download("maxent_ne_chunker_tab", quiet=True)
    try:
        nltk.data.find("words")
    except LookupError:
        nltk.download("words", quiet=True)

    sentences = nltk.sent_tokenize(text)
    found = []
    seen = set()

    grammar = r"NP: {<JJ.*>*<NN.*>+}"
    chunk_parser = nltk.RegexpParser(grammar)

    for sent in sentences:
        words = nltk.word_tokenize(sent)
        pos_tags = nltk.pos_tag(words)
        tree = chunk_parser.parse(pos_tags)

        for subtree in tree.subtrees():
            if subtree.label() == "NP":
                term = _normalize_term(" ".join(word for word, _ in subtree.leaves()))
                if term not in seen and len(term) >= 3:
                    seen.add(term)
                    found.append({
                        "term": term,
                        "method": "nltk_np",
                        "score": 0.4,
                    })

    return found


def _extract_noun_phrases(text: str) -> list[dict]:
    """Extract noun phrases, trying spaCy first then NLTK."""
    if _check_spacy():
        try:
            return _extract_noun_phrases_spacy(text)
        except Exception as e:
            logger.warning("spaCy noun phrase extraction failed: %s", e)

    if _check_nltk_extractor():
        try:
            return _extract_noun_phrases_nltk(text)
        except Exception as e:
            logger.warning("NLTK noun phrase extraction failed: %s", e)

    return []


# ── KeyBERT extraction ────────────────────────────────────────────────────

# Default sports-science seed keywords for KeyBERT-guided extraction
SEED_KEYWORDS = [
    "vo2max", "lactate", "heart rate", "strength", "power", "speed",
    "endurance", "biomechanics", "technique", "tactics", "nutrition",
    "recovery", "injury", "sleep", "body composition", "psychology",
    "equipment", "competition", "training load", "flexibility",
    "balance", "coordination", "reaction time", "decision making",
    "hydration", "supplement", "running economy", "sprint",
    "aerobic", "anaerobic", "fatigue", "pacing", "motion capture",
]


def _extract_by_keybert(texts: list[str]) -> list[list[dict]]:
    """Extract keywords using KeyBERT for each text. Returns per-text results."""
    if not _check_keybert():
        return [[] for _ in texts]

    try:
        from keybert import KeyBERT
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
        kw_model = KeyBERT(model=model)

        results = []
        for text in texts:
            if not text or len(text.strip()) < 20:
                results.append([])
                continue

            raw = kw_model.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 3),
                stop_words="english",
                top_n=10,
                use_mmr=True,
                diversity=0.5,
                seed_keywords=SEED_KEYWORDS,
            )

            found = []
            seen = set()
            for term, score in raw:
                norm = _normalize_term(term)
                if norm not in seen and len(norm) >= 3:
                    seen.add(norm)
                    found.append({
                        "term": norm,
                        "method": "keybert",
                        "score": float(score),
                    })
            results.append(found)

        return results
    except Exception as e:
        logger.warning("KeyBERT extraction failed: %s", e)
        return [[] for _ in texts]


# ── YAKE extraction ───────────────────────────────────────────────────────

def _extract_by_yake(texts: list[str]) -> list[list[dict]]:
    """Extract keywords using YAKE for each text."""
    if not _check_yake():
        return [[] for _ in texts]

    try:
        import yake

        yake_kw = yake.KeywordExtractor(
            lan="en",
            n=3,           # ngram size
            dedupLim=0.7,  # deduplication threshold
            top=15,
        )

        results = []
        for text in texts:
            if not text or len(text.strip()) < 20:
                results.append([])
                continue

            raw = yake_kw.extract_keywords(text)
            found = []
            seen = set()
            for term, score in raw:
                norm = _normalize_term(term)
                if norm not in seen and len(norm) >= 3:
                    seen.add(norm)
                    # YAKE scores are 0-1 where lower = better; invert for consistency
                    found.append({
                        "term": norm,
                        "method": "yake",
                        "score": round(1.0 - score, 4),
                    })
            results.append(found)

        return results
    except Exception as e:
        logger.warning("YAKE extraction failed: %s", e)
        return [[] for _ in texts]


# ── Main extraction function ──────────────────────────────────────────────

def extract_candidate_terms(
    chunks: list[LiteratureEvidenceChunk],
    use_keybert: bool = True,
    use_yake: bool = True,
    use_regex: bool = True,
    use_noun_phrases: bool = True,
    min_score: float = 0.0,
) -> list[ExtractedCandidate]:
    """Extract candidate performance terms from literature chunks.

    Extraction chain (each method tried in order; if one fails, the next runs):
      1. KeyBERT (guided by sports-science seed keywords)
      2. YAKE (unsupervised keyword extraction)
      3. Regex dictionary (domain-specific patterns)
      4. Noun phrase extraction (spaCy → NLTK)

    Args:
        chunks: LiteratureEvidenceChunk objects to extract from.
        use_keybert: Enable KeyBERT extraction.
        use_yake: Enable YAKE extraction.
        use_regex: Enable regex+dictionary extraction.
        use_noun_phrases: Enable noun phrase extraction.
        min_score: Minimum raw score threshold (0-1).

    Returns:
        List of ExtractedCandidate objects, deduplicated by normalized_term.
    """
    candidates: dict[str, ExtractedCandidate] = {}
    chunk_map: dict[int, LiteratureEvidenceChunk] = {i: c for i, c in enumerate(chunks)}

    # Prepare texts for batch methods
    texts = [c.chunk_text for c in chunks]

    # ── Layer 1: KeyBERT ──────────────────────────────────────────────
    keybert_results = None
    if use_keybert and _check_keybert():
        logger.info("Running KeyBERT extraction on %d chunks...", len(chunks))
        keybert_results = _extract_by_keybert(texts)

    # ── Layer 2: YAKE ─────────────────────────────────────────────────
    yake_results = None
    if use_yake and _check_yake():
        logger.info("Running YAKE extraction on %d chunks...", len(chunks))
        yake_results = _extract_by_yake(texts)

    # ── Layer 3: Regex + Noun phrases (per-chunk) ──────────────────────
    for i, chunk in enumerate(chunks):
        text = chunk.chunk_text

        chunk_terms: list[dict] = []

        # KeyBERT results for this chunk
        if keybert_results and i < len(keybert_results):
            chunk_terms.extend(keybert_results[i])

        # YAKE results for this chunk
        if yake_results and i < len(yake_results):
            chunk_terms.extend(yake_results[i])

        # Regex dictionary
        if use_regex:
            chunk_terms.extend(_extract_by_regex_dictionary(text))

        # Noun phrase extraction
        if use_noun_phrases and (not chunk_terms or len(chunk_terms) < 3):
            chunk_terms.extend(_extract_noun_phrases(text))

        # Deduplicate and create ExtractedCandidate objects
        for ct in chunk_terms:
            norm = _normalize_term(ct["term"])
            if ct["score"] < min_score:
                continue

            if norm in candidates:
                # Update existing: keep higher score
                existing = candidates[norm]
                if ct["score"] > existing.raw_score:
                    existing.raw_score = ct["score"]
                    existing.extraction_method = ct["method"]
                    existing.evidence_sentence = chunk.chunk_text
                    existing.chunk_index = i
            else:
                candidates[norm] = ExtractedCandidate(
                    candidate_term=ct["term"],
                    normalized_term=norm,
                    source_literature_id=chunk.literature_id,
                    source_title=chunk.title,
                    source_year=chunk.year,
                    evidence_sentence=chunk.chunk_text,
                    extraction_method=ct["method"],
                    raw_score=ct["score"],
                    chunk_index=i,
                )

    logger.info("Extracted %d unique candidate terms from %d chunks", len(candidates), len(chunks))
    return list(candidates.values())
