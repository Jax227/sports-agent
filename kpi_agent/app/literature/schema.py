"""
Unified LiteratureResult schema for multi-source literature search.

All connectors normalize their output to this structure.
Fields are optional and default to None/unknown when missing.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class LiteratureResult:
    """Unified literature result from any search source."""

    # IDs
    id: Optional[int] = None  # local DB id
    external_id: Optional[str] = None

    # Core metadata
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    abstract: Optional[str] = None
    journal: Optional[str] = None

    # Source tracking
    source_database: str = "unknown"  # openalex, pubmed, europe_pmc, crossref, semantic_scholar
    source_records: list[str] = field(default_factory=list)  # list of source_database names after merge

    # Metrics
    citation_count: Optional[int] = None

    # URLs
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    fulltext_url: Optional[str] = None

    # OA status
    open_access: Optional[bool] = None
    open_access_status: Optional[str] = None  # gold, green, hybrid, bronze, closed

    # Type
    publication_type: Optional[str] = None  # journal-article, review, meta-analysis, etc.
    keywords: list[str] = field(default_factory=list)

    # Fulltext enrichment
    fulltext_available: bool = False
    fulltext_source: Optional[str] = None  # unpaywall, europe_pmc, openalex, etc.
    oa_license: Optional[str] = None

    # Ranking scores
    final_score: Optional[float] = None
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None
    rule_score: Optional[float] = None
    ranking_explanation: str = ""

    # Raw
    raw: Optional[dict] = None
    retrieved_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization and DB storage."""
        d = asdict(self)
        # Convert list fields to JSON strings for DB
        d["authors_json"] = json.dumps(self.authors, ensure_ascii=False) if self.authors else "[]"
        d["keywords_json"] = json.dumps(self.keywords, ensure_ascii=False) if self.keywords else "[]"
        d["source_records_json"] = json.dumps(self.source_records or [self.source_database], ensure_ascii=False)
        d["raw_json"] = json.dumps(self.raw, ensure_ascii=False) if self.raw else "{}"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "LiteratureResult":
        """Create from dict, handling JSON fields."""
        result = cls()
        for key in [
            "id", "external_id", "title", "year", "doi", "pmid", "pmcid",
            "abstract", "journal", "source_database", "citation_count",
            "url", "pdf_url", "fulltext_url", "open_access", "open_access_status",
            "publication_type", "fulltext_available", "fulltext_source", "oa_license",
            "final_score", "bm25_score", "vector_score", "rule_score",
            "ranking_explanation", "retrieved_at",
        ]:
            if key in d:
                setattr(result, key, d[key])

        # Parse JSON list fields
        for json_field, target in [
            ("authors_json", "authors"),
            ("keywords_json", "keywords"),
            ("source_records_json", "source_records"),
        ]:
            val = d.get(json_field, "")
            if isinstance(val, str) and val:
                try:
                    setattr(result, target, json.loads(val))
                except json.JSONDecodeError:
                    pass
            elif isinstance(val, list):
                setattr(result, target, val)

        # Parse raw
        raw_val = d.get("raw_json", "{}")
        if isinstance(raw_val, str):
            try:
                result.raw = json.loads(raw_val)
            except json.JSONDecodeError:
                result.raw = {}
        elif isinstance(raw_val, dict):
            result.raw = raw_val

        return result


@dataclass
class ExtractionResult:
    """Structured evidence extracted from a literature result."""

    literature_id: Optional[int] = None
    title: str = ""

    # Extracted fields
    sport: list[str] = field(default_factory=list)
    population_level: list[str] = field(default_factory=list)
    sample_size: Optional[int] = None
    sex: list[str] = field(default_factory=list)
    age: Optional[str] = None
    performance_variables: list[str] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
    measurement_methods: list[str] = field(default_factory=list)
    outcome_variables: list[str] = field(default_factory=list)
    key_sentences: list[str] = field(default_factory=list)
    kpi_implications: list[dict] = field(default_factory=list)

    # Evidence note
    evidence: str = ""  # human-readable evidence summary

    # Evidence metadata
    extracted_from: str = "title_abstract"  # title_abstract or fulltext
    extraction_method: str = "rule_based"
    confidence: str = "low"  # low / medium / high
    missing_fields: list[str] = field(default_factory=list)
    matched_terms: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidenceMatrix:
    """Evidence matrix built from multiple extracted results."""

    query: str = ""
    generated_at: str = ""
    rows: list[ExtractionResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "query": self.query,
            "generated_at": self.generated_at,
            "rows": [r.to_dict() for r in self.rows],
            "summary": self.summary,
        }, ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        """Generate a compact markdown evidence matrix table."""
        if not self.rows:
            return "*No evidence extracted.*"

        lines = [
            f"# Evidence Matrix",
            f"Query: {self.query}",
            f"Generated: {self.generated_at}",
            f"Rows: {len(self.rows)}",
            "",
        ]

        # Compact table — selected key columns
        headers = ["Title", "Year", "Sport", "Pop.", "N", "Perf. Variables", "Interventions",
                    "OA", "KPI Implications"]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + " --- |" * len(headers))

        for r in self.rows:
            perf = ", ".join(r.performance_variables[:4]) or "—"
            interv = ", ".join(r.interventions[:3]) or "—"
            sport = ", ".join(r.sport[:2]) or "—"
            pop = ", ".join(r.population_level[:2]) or "—"
            kpi = ", ".join([k.get("name", "") for k in r.kpi_implications[:3]]) or "—"
            oa = "+" if r.confidence == "high" else "~"

            row = [
                f"{r.title[:60]}..." if len(r.title) > 60 else r.title,
                str(r.literature_id or "—"),
                sport,
                pop,
                str(r.sample_size or "—"),
                perf,
                interv,
                oa,
                kpi,
            ]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def to_csv(self) -> str:
        """Export as CSV string."""
        import csv, io
        output = io.StringIO()
        if not self.rows:
            return ""
        fieldnames = [
            "title", "sport", "population_level", "sample_size", "sex", "age",
            "performance_variables", "interventions", "measurement_methods",
            "outcome_variables", "kpi_implications", "confidence", "extracted_from",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in self.rows:
            d = r.to_dict()
            for list_field in ["sport", "population_level", "sex", "performance_variables",
                               "interventions", "measurement_methods", "outcome_variables",
                               "kpi_implications"]:
                if isinstance(d.get(list_field), list):
                    d[list_field] = "; ".join(
                        str(x) if isinstance(x, str) else x.get("name", str(x))
                        for x in d[list_field]
                    )
            writer.writerow(d)
        return output.getvalue()
