"""
Evidence matrix generation from extracted literature results.

Generates structured output in JSON, Markdown, and CSV formats.
Used for visualization in the Streamlit UI and data export.
"""

import logging
from datetime import datetime
from typing import Optional

from app.literature.schema import LiteratureResult, ExtractionResult, EvidenceMatrix

logger = logging.getLogger(__name__)


def generate_evidence_matrix(
    query: str,
    results: list[LiteratureResult],
    extractions: Optional[list[ExtractionResult]] = None,
) -> EvidenceMatrix:
    """Generate an evidence matrix from literature results and extractions.

    Args:
        query: The original search query
        results: List of LiteratureResult objects (ranked)
        extractions: Optional list of ExtractionResult objects.
                     If not provided, results without extractions are
                     included with empty extraction data.

    Returns:
        EvidenceMatrix with all rows and summary statistics
    """
    # Build extraction map
    ext_map: dict[int, ExtractionResult] = {}
    if extractions:
        for ext in extractions:
            if ext.literature_id is not None:
                ext_map[ext.literature_id] = ext

    rows = []
    for i, r in enumerate(results):
        if r.id and r.id in ext_map:
            rows.append(ext_map[r.id])
        else:
            # Create minimal extraction from literature result
            rows.append(ExtractionResult(
                literature_id=r.id,
                title=r.title,
                evidence=f"Ranked #{i+1}, score={r.final_score:.4f}" if r.final_score else "",
            ))

    # Compute summary
    summary = _compute_summary(rows, results)

    return EvidenceMatrix(
        query=query,
        generated_at=datetime.utcnow().isoformat(),
        rows=rows,
        summary=summary,
    )


def _compute_summary(
    extractions: list[ExtractionResult],
    results: list[LiteratureResult],
) -> dict:
    """Compute summary statistics for the evidence matrix."""
    total = len(extractions)
    if total == 0:
        return {"total": 0}

    # Count extracted fields
    has_sport = sum(1 for e in extractions if e.sport)
    has_population = sum(1 for e in extractions if e.population_level)
    has_sample_size = sum(1 for e in extractions if e.sample_size)
    has_perf_vars = sum(1 for e in extractions if e.performance_variables)
    has_interventions = sum(1 for e in extractions if e.interventions)
    has_methods = sum(1 for e in extractions if e.measurement_methods)
    has_kpi = sum(1 for e in extractions if e.kpi_implications)

    # Count OA
    oa_count = sum(1 for r in results if r.open_access)
    pdf_count = sum(1 for r in results if r.pdf_url)

    # Most common variables
    var_counts: dict[str, int] = {}
    for e in extractions:
        for v in e.performance_variables:
            var_counts[v] = var_counts.get(v, 0) + 1

    top_vars = sorted(var_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Most common interventions
    intv_counts: dict[str, int] = {}
    for e in extractions:
        for v in e.interventions:
            intv_counts[v] = intv_counts.get(v, 0) + 1

    top_interventions = sorted(intv_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Most common sports
    sport_counts: dict[str, int] = {}
    for e in extractions:
        for v in e.sport:
            sport_counts[v] = sport_counts.get(v, 0) + 1

    top_sports = sorted(sport_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Confidence distribution
    confidence_dist = {"high": 0, "medium": 0, "low": 0}
    for e in extractions:
        conf = e.confidence or "low"
        if conf in confidence_dist:
            confidence_dist[conf] += 1

    return {
        "total_papers": total,
        "open_access_count": oa_count,
        "pdf_available_count": pdf_count,
        "extraction_coverage": {
            "sport": {"count": has_sport, "pct": round(has_sport / total * 100, 1)},
            "population_level": {"count": has_population, "pct": round(has_population / total * 100, 1)},
            "sample_size": {"count": has_sample_size, "pct": round(has_sample_size / total * 100, 1)},
            "performance_variables": {"count": has_perf_vars, "pct": round(has_perf_vars / total * 100, 1)},
            "interventions": {"count": has_interventions, "pct": round(has_interventions / total * 100, 1)},
            "measurement_methods": {"count": has_methods, "pct": round(has_methods / total * 100, 1)},
            "kpi_implications": {"count": has_kpi, "pct": round(has_kpi / total * 100, 1)},
        },
        "top_performance_variables": [{"variable": v, "count": c} for v, c in top_vars],
        "top_interventions": [{"intervention": v, "count": c} for v, c in top_interventions],
        "top_sports": [{"sport": v, "count": c} for v, c in top_sports],
        "confidence_distribution": confidence_dist,
    }
