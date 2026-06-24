"""
Evidence linker: connects determinant candidates to source literature.

Stores evidence links as structured records that can be persisted
to the main database or exported for review.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def create_evidence_links(
    candidates: list,
    literature_docs: list,
) -> list[dict]:
    """Create evidence link records between candidates and literature.

    Each link contains:
    - determinant_candidate_id (or canonical_name for lookup)
    - literature_id
    - evidence_text
    - evidence_location (title/abstract/fulltext/methods/results/discussion)
    - matched_terms
    - source_database
    - doi
    - year
    - ranking_score
    - confidence_score

    Args:
        candidates: List of DeterminantCandidate objects (merged).
        literature_docs: List of LiteratureDocument objects.

    Returns:
        List of evidence link dicts ready for storage.
    """
    links = []

    # Build literature lookup
    lit_map: dict[int, object] = {}
    for doc in literature_docs:
        lit_map[doc.literature_id] = doc

    for candidate in candidates:
        # Get attributes
        canonical = _a(candidate, 'canonical_name', '')
        evidence_sentences = _a(candidate, 'evidence_sentences', [])
        source_lit_ids = _a(candidate, 'source_literature_ids', [])
        source_dbs = _a(candidate, 'source_databases', [])
        matched_terms = _a(candidate, 'matched_terms', [])
        confidence = _a(candidate, 'confidence_score', 0.0)

        # Find the best single evidence sentence per literature
        lit_evidence: dict[int, dict] = {}
        for ev in evidence_sentences:
            lid = ev.get("literature_id")
            if lid and (lid not in lit_evidence or len(ev.get("text", "")) > len(lit_evidence[lid].get("text", ""))):
                lit_evidence[lid] = ev

        for lid in source_lit_ids:
            lit_doc = lit_map.get(lid)
            ev = lit_evidence.get(lid, {})

            link = {
                "canonical_name": canonical,
                "literature_id": lid,
                "evidence_text": ev.get("text", "")[:1000],
                "evidence_location": ev.get("location", "unknown"),
                "matched_terms": list(matched_terms)[:10] if matched_terms else [],
                "source_database": list(source_dbs)[:5] if source_dbs else [],
                "doi": ev.get("doi") or (lit_doc.doi if lit_doc else None),
                "year": ev.get("year") or (lit_doc.year if lit_doc else None),
                "ranking_score": lit_doc.ranking_score if lit_doc else None,
                "confidence_score": confidence,
                "created_at": datetime.utcnow().isoformat(),
            }
            links.append(link)

    logger.info(f"Created {len(links)} evidence links for {len(candidates)} candidates")
    return links


def build_evidence_report(
    candidates: list,
    links: list[dict],
    model_tree: dict,
) -> str:
    """Generate an evidence-linked Markdown report."""
    lines = [
        "# Performance Model Evidence Report",
        f"Generated: {datetime.utcnow().isoformat()}",
        f"Total candidates: {model_tree.get('total_candidates', 0)}",
        f"Total evidence links: {len(links)}",
        "",
        "---",
        "",
    ]

    for cat in model_tree.get("categories", []):
        lines.append(f"## {cat['name_cn']} ({cat['name_en']})")
        lines.append(f"Candidates: {cat['candidate_count']} | Total evidence: {cat['total_evidence_count']}")
        lines.append("")

        for cand in cat.get("candidates", []):
            name = cand.get("display_name_en", cand.get("canonical_name", ""))
            ev_count = len(cand.get("source_literature_ids", []))
            conf = cand.get("confidence_score", 0)
            strength = cand.get("evidence_strength_score", 0)

            lines.append(f"### {name}")
            lines.append(f"- **Canonical**: `{cand.get('canonical_name', '')}`")
            lines.append(f"- **Evidence**: {ev_count} paper(s)")
            lines.append(f"- **Confidence**: {conf:.2f} | **Strength**: {strength:.2f}")
            lines.append(f"- **Extracted by**: {', '.join(cand.get('extraction_methods', []))}")
            lines.append(f"- **Aliases**: {', '.join(cand.get('aliases', [])[:5])}")
            lines.append("")

            # Evidence sentences
            lines.append("**Supporting evidence:**")
            lines.append("")
            for ev in cand.get("evidence_sentences", [])[:5]:
                text = ev.get("text", "")[:200]
                lit_id = ev.get("literature_id", "?")
                doi = ev.get("doi", "")
                year = ev.get("year", "")
                loc = ev.get("location", "")
                lines.append(f"- [Lit#{lit_id}] ({year}, {loc}) {doi}")
                lines.append(f"  > {text}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Orphans
    orphans = model_tree.get("orphans", [])
    if orphans:
        lines.append("## Unclassified Candidates")
        lines.append("")
        for o in orphans:
            lines.append(f"- **{o['canonical_name']}**: {o.get('reason', '')}")
        lines.append("")

    return "\n".join(lines)


def _a(obj, attr: str, default=None):
    """Get attribute from object or dict."""
    if hasattr(obj, attr):
        return getattr(obj, attr, default)
    return obj.get(attr, default) if isinstance(obj, dict) else default
