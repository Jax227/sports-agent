"""Evidence synthesizer — aggregate and synthesize findings across studies."""

from collections import defaultdict
from src.database import search_papers
from src.utils import logger


def synthesize_by_question(question: str, papers: list[dict]) -> dict:
    """Synthesize evidence across papers for a specific research question."""
    if not papers:
        return {
            "question": question,
            "total_papers": 0,
            "evidence_summary": "No papers available for synthesis.",
            "consistency": "unknown",
            "evidence_strength": "insufficient",
            "research_gaps": ["No literature available for this question"],
            "hypotheses": [],
            "references": [],
        }

    # Group by evidence level
    by_level = defaultdict(list)
    for p in papers:
        level = p.get("evidence_level", "unknown")
        by_level[level].append(p)

    high_quality = by_level.get("high", [])
    moderate_quality = by_level.get("moderate", [])
    low_quality = by_level.get("low", []) + by_level.get("very_low", [])

    # Determine evidence strength
    if len(high_quality) >= 2:
        strength = "strong" if len(high_quality) >= 4 else "moderate_to_strong"
    elif len(high_quality) >= 1 or len(moderate_quality) >= 3:
        strength = "moderate"
    elif len(moderate_quality) >= 1 or len(low_quality) >= 3:
        strength = "limited"
    else:
        strength = "insufficient"

    # Extract main findings by level
    findings_summary = {
        "high_quality_findings": _extract_findings(high_quality),
        "moderate_quality_findings": _extract_findings(moderate_quality),
        "low_quality_findings": _extract_findings(low_quality),
    }

    # Assess consistency
    consistency = _assess_consistency(papers)

    # Identify gaps
    gaps = _identify_gaps(papers, question)

    # Generate hypotheses
    hypotheses = _generate_hypotheses(question, gaps)

    # Build references
    references = _build_reference_list(papers)

    return {
        "question": question,
        "total_papers": len(papers),
        "by_evidence_level": {
            "high": len(high_quality),
            "moderate": len(moderate_quality),
            "low": len(low_quality),
        },
        "evidence_summary": _build_evidence_narrative(findings_summary, strength),
        "findings_by_level": findings_summary,
        "consistency": consistency["level"],
        "consistency_notes": consistency["notes"],
        "evidence_strength": strength,
        "research_gaps": gaps,
        "hypotheses": hypotheses,
        "references": references,
    }


def _extract_findings(papers: list[dict]) -> list[dict]:
    """Extract key findings from papers."""
    findings = []
    for p in papers:
        findings.append({
            "title": p.get("title", ""),
            "authors": p.get("authors", ""),
            "year": p.get("year", ""),
            "main_findings": p.get("main_findings", ""),
            "effect_size": p.get("effect_size", ""),
            "study_type": p.get("study_type", ""),
            "sample_size": p.get("sample_size", ""),
            "quality_score": p.get("quality_score", ""),
        })
    return findings


def _assess_consistency(papers: list[dict]) -> dict:
    """Assess consistency of findings across papers."""
    if len(papers) < 2:
        return {"level": "unknown", "notes": "Single study — cannot assess consistency"}

    # Simple heuristic: check if findings mention consistent directions
    positive_count = 0
    negative_count = 0
    mixed_count = 0

    for p in papers:
        findings = (p.get("main_findings", "") or "").lower()
        if any(w in findings for w in ["increase", "improve", "enhance", "significant", "positive", "benefit"]):
            positive_count += 1
        if any(w in findings for w in ["decrease", "reduce", "no significant", "no effect", "not differ", "negative"]):
            negative_count += 1
        if any(w in findings for w in ["however", "mixed", "inconsistent", "varies"]):
            mixed_count += 1

    if positive_count > len(papers) * 0.75:
        return {"level": "consistent", "notes": "Majority of studies report consistent positive direction of effect"}
    elif negative_count > len(papers) * 0.75:
        return {"level": "consistent", "notes": "Majority of studies report consistent null/negative findings"}
    elif mixed_count >= 2:
        return {"level": "inconsistent", "notes": "Findings are mixed across studies"}
    else:
        return {"level": "partially_consistent", "notes": "Some consistency but heterogeneity present"}


def _identify_gaps(papers: list[dict], question: str) -> list[str]:
    """Identify research gaps from the existing literature."""
    gaps = []

    # Check population gaps
    populations = [p.get("population", "") for p in papers if p.get("population")]
    if all("elite" in pop.lower() for pop in populations):
        gaps.append("Limited evidence in non-elite/sub-elite populations")
    if all("male" in pop.lower() or "men" in pop.lower() for pop in populations) and \
       not any("female" in pop.lower() or "women" in pop.lower() for pop in populations):
        gaps.append("Evidence predominantly from male populations — female data lacking")
    if all("young" in pop.lower() or "adult" in pop.lower() for pop in populations):
        gaps.append("Limited evidence in youth or elderly populations")

    # Check sample size
    sample_sizes = [int(p.get("sample_size", 0)) for p in papers
                    if p.get("sample_size") and str(p.get("sample_size", "")).isdigit()]
    if sample_sizes and all(n < 50 for n in sample_sizes):
        gaps.append("All studies have small sample sizes (n < 50) — larger trials needed")

    # Check study type gaps
    study_types = [p.get("study_type") for p in papers]
    if "meta_analysis" not in study_types and "systematic_review" not in study_types:
        gaps.append("No meta-analysis or systematic review available for this question")
    if "randomized_controlled_trial" not in study_types:
        gaps.append("No RCT evidence available — causal inference limited")

    # Check recency
    years = [int(p.get("year", 0)) for p in papers if str(p.get("year", "")).isdigit()]
    if years and max(years) < 2022:
        gaps.append("Most recent study is older than 2022 — updated research needed")

    if not gaps:
        gaps.append("Need for prospective, large-scale studies with standardized outcome measures")

    return gaps


def _generate_hypotheses(question: str, gaps: list[str]) -> list[str]:
    """Generate testable hypotheses based on identified gaps."""
    hypotheses = []
    for gap in gaps:
        if "female" in gap.lower():
            hypotheses.append("H: The effect differs significantly between male and female populations, warranting sex-specific analysis")
        if "elite" in gap.lower():
            hypotheses.append("H: The effect size differs between elite and sub-elite populations due to training status")
        if "small sample" in gap.lower():
            hypotheses.append("H: A large-scale (n > 200) trial would confirm/reject the preliminary findings from small-sample studies")
        if "meta-analysis" in gap.lower():
            hypotheses.append("H: A meta-analysis would reveal significant between-study heterogeneity (I^2 > 50%)")
        if "RCT" in gap.upper():
            hypotheses.append("H: A well-controlled RCT would show more conservative effect sizes than observational studies")
        if "youth" in gap.lower() or "elderly" in gap.lower():
            hypotheses.append("H: Age significantly moderates the intervention effect")
    if not hypotheses:
        hypotheses.append("H: Standardization of outcome measures across studies would reduce between-study heterogeneity")
    return hypotheses


def _build_reference_list(papers: list[dict]) -> list[str]:
    """Build formatted reference list."""
    refs = []
    for p in papers:
        authors = p.get("authors", "Unknown")
        title = p.get("title", "Untitled")
        journal = p.get("journal", "")
        year = p.get("year", "")
        volume = p.get("volume", "")
        issue = p.get("issue", "")
        pages = p.get("pages", "")
        doi = p.get("doi", "")

        # APA-style reference
        ref = f"{authors} ({year}). {title}. *{journal}*"
        if volume:
            ref += f", {volume}"
            if issue:
                ref += f"({issue})"
        if pages:
            ref += f", {pages}"
        if doi:
            ref += f". doi:{doi}"
        refs.append(ref)
    return refs


def _build_evidence_narrative(findings_summary: dict, strength: str) -> str:
    """Build a narrative summary of evidence."""
    high = findings_summary.get("high_quality_findings", [])
    moderate = findings_summary.get("moderate_quality_findings", [])
    low = findings_summary.get("low_quality_findings", [])

    parts = []

    if high:
        parts.append(f"{len(high)} high-quality studies provide the strongest evidence.")
        # Extract common themes from titles
        titles = [h.get("title", "")[:100] for h in high[:3]]
        parts.append(f"Key studies include: {'; '.join(titles)}.")

    if moderate:
        parts.append(f"{len(moderate)} moderate-quality studies provide supporting evidence.")

    if low:
        parts.append(f"{len(low)} lower-quality studies offer additional context but should be interpreted cautiously.")

    parts.append(f"Overall evidence strength: **{strength.upper()}**.")

    if strength in ("insufficient", "limited"):
        parts.append("The current evidence base is not sufficient to draw definitive conclusions. Future research is needed.")

    return " ".join(parts)


def build_evidence_map(papers: list[dict]) -> dict:
    """Build an evidence map: topics × study types × quality."""
    emap = defaultdict(lambda: defaultdict(list))
    for p in papers:
        domain = p.get("research_domain", "unknown")
        study_type = p.get("study_type", "unknown")
        emap[domain][study_type].append({
            "id": p.get("id"),
            "title": p.get("title", ""),
            "quality_score": p.get("quality_score", ""),
            "evidence_level": p.get("evidence_level", ""),
            "year": p.get("year", ""),
        })

    result = {}
    for domain, types in emap.items():
        result[domain] = {}
        for stype, papers_list in types.items():
            result[domain][stype] = {
                "count": len(papers_list),
                "papers": sorted(papers_list, key=lambda x: float(x.get("quality_score", 0) or 0), reverse=True),
            }
    return result
