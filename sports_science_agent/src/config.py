"""Central configuration for the Sports Science Research Agent."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load .env file (no external dependencies)
_env_path = ROOT / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            _key, _val = _key.strip(), _val.strip()
            if _key and _key not in os.environ:
                os.environ[_key] = _val

# ── Paths ──────────────────────────────────────────────────
DATA_DIR = ROOT / "data"
RAW_PDFS = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
CHUNKS_DIR = DATA_DIR / "chunks"
LITERATURE_DB_DIR = ROOT / "literature_db"
VECTOR_STORE_DIR = ROOT / "vector_store"
PAPERS_DIR = ROOT / "papers"
OUTPUTS_DIR = ROOT / "outputs"
LOGS_DIR = ROOT / "logs"
PROMPTS_DIR = ROOT / "prompts"

# DB files
PAPERS_METADATA_JSON = LITERATURE_DB_DIR / "papers_metadata.json"
PAPERS_METADATA_CSV = LITERATURE_DB_DIR / "papers_metadata.csv"
SCREENING_DECISIONS_JSON = LITERATURE_DB_DIR / "screening_decisions.json"
EXTRACTED_FINDINGS_JSON = LITERATURE_DB_DIR / "extracted_findings.json"
RESEARCH_QUESTIONS_JSON = LITERATURE_DB_DIR / "research_questions.json"
EVIDENCE_MAP_JSON = LITERATURE_DB_DIR / "evidence_map.json"

# Literature search & appraisal
SEARCH_RESULTS_DIR = DATA_DIR / "search_results"
SEARCH_LOGS_DIR = DATA_DIR / "search_logs"
APPRAISAL_RESULTS_DIR = DATA_DIR / "appraisal_results"
JOURNAL_CLUB_REPORTS_DIR = OUTPUTS_DIR / "journal_club_reports"
JOURNAL_RANKINGS_CSV = DATA_DIR / "journal_rankings" / "sports_science_journal_rankings.csv"

# Vector store
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(VECTOR_STORE_DIR / "chroma"))

# ── API keys ───────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "")
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

# ── Embedding ──────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── Constants ──────────────────────────────────────────────
SPORT_SCIENCE_DOMAINS = [
    "exercise_physiology",
    "sports_training",
    "sports_medicine_rehab",
    "sports_nutrition",
    "fitness_health_promotion",
    "sports_psychology_performance",
]

STUDY_TYPES = [
    "systematic_review",
    "meta_analysis",
    "systematic_review_with_meta_analysis",
    "randomized_controlled_trial",
    "cluster_randomized_trial",
    "crossover_trial",
    "non_randomized_controlled_trial",
    "single_arm_trial",
    "prospective_cohort",
    "cohort_study",
    "case_control_study",
    "cross_sectional_study",
    "case_series",
    "case_report",
    "diagnostic_accuracy_study",
    "qualitative_study",
    "mixed_methods_study",
    "study_protocol",
    "narrative_review",
    "expert_consensus",
    "guideline",
    "animal_study",
    "in_vitro_study",
    "intervention_study_unspecified",
    "observational_unspecified",
    "preprint",
    "conference_abstract",
    "opinion",
    "case_study",
    "unknown",
    "other",
]

EVIDENCE_LEVELS = ["high", "moderate", "low", "very_low"]
RISK_OF_BIAS_LEVELS = ["low", "some_concerns", "high", "unclear"]

# Screening thresholds
QUALITY_THRESHOLD = 6
RELEVANCE_THRESHOLD = 6
HIGH_PRIORITY_QUALITY = 8
HIGH_PRIORITY_RELEVANCE = 8
HIGH_PRIORITY_TYPES = [
    "systematic_review", "meta_analysis", "systematic_review_with_meta_analysis",
    "randomized_controlled_trial", "cluster_randomized_trial", "guideline",
]

# Port for the Streamlit app
APP_PORT = int(os.getenv("APP_PORT", "8502"))
