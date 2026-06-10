"""Academic writer — generate publication-ready text components."""

from src.database import search_papers
from src.evidence_synthesizer import synthesize_by_question
from src.utils import logger


def generate_section(section_type: str, question: str, papers: list[dict] = None) -> str:
    """Generate an academic writing section based on literature."""
    if papers is None:
        papers = search_papers(keyword=question[:200])

    if section_type == "introduction":
        return _write_introduction(question, papers)
    elif section_type == "methods_draft":
        return _write_methods(question, papers)
    elif section_type == "discussion":
        return _write_discussion(question, papers)
    elif section_type == "literature_review":
        return _write_literature_review(question, papers)
    elif section_type == "research_gap":
        return _write_research_gap(question, papers)
    elif section_type == "hypothesis":
        return _write_hypothesis(question, papers)
    elif section_type == "abstract":
        return _write_abstract(question, papers)
    elif section_type == "statistical_plan":
        return _write_statistical_plan(question, papers)
    elif section_type == "cover_letter":
        return _write_cover_letter(question, papers)
    elif section_type == "response_to_reviewers":
        return _write_response_template(question)
    else:
        return f"Section type '{section_type}' not recognized."


def _write_introduction(question: str, papers: list[dict]) -> str:
    """Write an introduction section."""
    synth = synthesize_by_question(question, papers) if papers else {}
    gaps = synth.get("research_gaps", ["The research gap has not been systematically defined."])

    intro = f"""## Introduction

The relationship between exercise interventions and physiological outcomes has been extensively investigated in sports science literature. Among the key areas of inquiry, {question.lower().rstrip('?')} has attracted considerable research attention in recent years.

### Background
"""
    if papers:
        high_quality = [p for p in papers if p.get("evidence_level") == "high"][:3]
        for p in high_quality:
            title = p.get("title", "")
            authors = p.get("authors", "").split(";")[0] if p.get("authors") else ""
            year = p.get("year", "")
            findings = p.get("main_findings", "")[:200]
            intro += f"- {authors} et al. ({year}) reported that {findings}\n"
    else:
        intro += ("Previous research has examined various aspects of this question, though "
                   "the evidence base requires further characterization.\n")

    intro += f"""
### Research Gap
"""
    for gap in gaps[:3]:
        intro += f"- {gap}\n"

    if not gaps:
        intro += "- A systematic synthesis of existing evidence is needed to clarify the current state of knowledge.\n"

    intro += f"""
### Objective
The present review aims to synthesize the available evidence regarding {question.lower().rstrip('?')},
identify key findings and inconsistencies, and propose directions for future research.

*Note: This introduction is generated based on the local literature database. It should be verified
and supplemented with a comprehensive literature search before publication.*
"""
    return intro


def _write_methods(question: str, papers: list[dict]) -> str:
    """Draft a methods section for a systematic review or meta-analysis."""
    return f"""## Methods (Draft)

### Search Strategy
A systematic search will be conducted across the following databases:
- PubMed / MEDLINE
- Web of Science
- SPORTDiscus
- Scopus
- Cochrane Library

Search terms will include combinations of keywords related to:
- Population: [to be specified based on research question]
- Intervention/Exposure: [to be specified]
- Comparator: [to be specified]
- Outcomes: [to be specified]

### Inclusion Criteria
1. Peer-reviewed original research articles
2. Published in English or Chinese
3. Human participants
4. Clear description of intervention/exposure and outcomes
5. [Additional criteria specified by research question: "{question}"]

### Exclusion Criteria
1. Non-peer-reviewed sources (conference abstracts, preprints without peer review)
2. Case studies with n < 5
3. Animal studies
4. Reviews without original data (for meta-analysis)
5. Studies without sufficient statistical information for effect size calculation

### Data Extraction
Two independent reviewers will extract:
- Study characteristics (authors, year, design, sample size)
- Participant characteristics (age, sex, training status)
- Intervention details (type, duration, frequency, intensity)
- Outcome measures and time points
- Main findings and effect sizes

### Quality Assessment
- RCTs: Cochrane Risk of Bias Tool (RoB 2)
- Observational studies: Newcastle-Ottawa Scale (NOS)
- Systematic reviews: AMSTAR 2

### Statistical Analysis
- Random-effects meta-analysis (DerSimonian-Laird method)
- Heterogeneity assessed via I^2 statistic and Q-test
- Subgroup analyses by population, intervention type, and study quality
- Publication bias: funnel plot and Egger's test
- Sensitivity analyses excluding low-quality studies

*This is a draft methods section. Specific parameters should be refined based on the research question and
available literature in the local database.*
"""


def _write_discussion(question: str, papers: list[dict]) -> str:
    """Write a discussion section."""
    synth = synthesize_by_question(question, papers) if papers else {}
    strength = synth.get("evidence_strength", "insufficient")
    gaps = synth.get("research_gaps", [])
    consistency = synth.get("consistency", "unknown")

    discussion = f"""## Discussion

### Summary of Main Findings
The present synthesis examined the evidence regarding {question.lower().rstrip('?')}.
Overall, the evidence strength is assessed as **{strength}**.
"""

    if papers:
        by_level = synth.get("by_evidence_level", {})
        discussion += f"""
The literature search identified {len(papers)} relevant studies, including
{by_level.get('high', 0)} high-quality, {by_level.get('moderate', 0)} moderate-quality,
and {by_level.get('low', 0)} low-quality studies.
"""

    discussion += f"""
### Consistency of Evidence
The findings across studies are **{consistency}**.
"""

    if consistency == "inconsistent":
        discussion += """
The observed inconsistency may be attributable to several factors:
- Differences in sample characteristics (age, training status, sex distribution)
- Variations in intervention protocols (duration, intensity, frequency)
- Heterogeneity in outcome measurement methods
- Methodological differences in study design and quality
"""

    discussion += """
### Comparison with Existing Literature
The findings from the current synthesis align with [to be compared with broader literature].
However, direct comparison is limited by differences in study populations and methodologies.

### Limitations
"""
    discussion += f"- Evidence strength is **{strength}** — {'conclusions should be interpreted cautiously' if strength in ('limited', 'insufficient') else 'though supporting a reasonable level of confidence'}.\n"
    discussion += f"- Number of included studies: {len(papers)} studies from the local literature database.\n"
    discussion += "- The local literature database may not be exhaustive; a comprehensive systematic search is recommended.\n"
    discussion += "- Between-study heterogeneity limits the precision of pooled estimates.\n"

    discussion += """
### Implications for Practice
Based on the available evidence:
- [Practical implications should be filled in based on specific findings]
- Recommendations should be individualized based on population characteristics

### Future Research Directions
"""
    for gap in gaps[:4]:
        discussion += f"- {gap}\n"

    discussion += """
### Conclusions
"""
    if strength in ("strong", "moderate_to_strong"):
        discussion += "The current evidence supports [conclusion], though continued research should refine effect estimates across populations."
    elif strength == "moderate":
        discussion += "The available evidence provides some support for [conclusion], but additional high-quality research is warranted."
    else:
        discussion += "The current evidence is insufficient to draw definitive conclusions. Well-designed prospective studies are needed."

    discussion += """

*This discussion is generated based on the local literature database. Replace [bracketed] text with
specific findings and verify all statements against primary sources before publication.*
"""
    return discussion


def _write_literature_review(question: str, papers: list[dict]) -> str:
    """Write a structured literature review section."""
    if not papers:
        return f"""## Literature Review: {question}

当前本地文献库中尚无足够文献支持系统综述。建议先导入或检索相关文献。
"""

    # Organize by theme/year/quality
    high = [p for p in papers if p.get("evidence_level") == "high"]
    moderate = [p for p in papers if p.get("evidence_level") == "moderate"]
    low = [p for p in papers if p.get("evidence_level") in ("low", "very_low")]

    review = f"""## Literature Review: {question}

### High-Quality Evidence
"""
    if high:
        for p in high[:10]:
            review += _format_paper_paragraph(p)
    else:
        review += "No high-quality studies identified in the current literature database.\n"

    review += "\n### Moderate-Quality Evidence\n"
    if moderate:
        for p in moderate[:10]:
            review += _format_paper_paragraph(p)
    else:
        review += "No moderate-quality studies identified.\n"

    review += "\n### Lower-Quality Evidence\n"
    if low:
        for p in low[:5]:
            review += _format_paper_paragraph(p)
    else:
        review += "No lower-quality studies identified.\n"

    review += f"""

*This literature review is based on {len(papers)} papers from the local database.
A comprehensive search of external databases is recommended for publication-ready reviews.*
"""
    return review


def _format_paper_paragraph(paper: dict) -> str:
    """Format a single paper as a review paragraph element."""
    authors_short = paper.get("authors", "").split(";")[0] if paper.get("authors") else "Unknown"
    year = paper.get("year", "?")
    title = paper.get("title", "Untitled")
    study_type = paper.get("study_type", "").replace("_", " ").title()
    findings = paper.get("main_findings", "No findings extracted")[:300]
    sample = paper.get("sample_size", "N/R")
    quality = paper.get("quality_score", "?")

    return f"""**{authors_short} et al. ({year})** — *{title}*
- Study type: {study_type} | Sample: n={sample} | Quality: {quality}/10
- Key findings: {findings}

"""


def _write_research_gap(question: str, papers: list[dict]) -> str:
    """Identify and describe research gaps."""
    synth = synthesize_by_question(question, papers) if papers else {}
    gaps = synth.get("research_gaps", [])
    hypotheses = synth.get("hypotheses", [])

    text = f"""## Research Gap Analysis: {question}

### Identified Gaps
"""
    for i, gap in enumerate(gaps, 1):
        text += f"{i}. {gap}\n"

    text += "\n### Testable Hypotheses\n"
    for i, hyp in enumerate(hypotheses, 1):
        text += f"{i}. {hyp}\n"

    text += """
### Significance
Addressing these gaps would contribute to:
- Advancing theoretical understanding of the underlying mechanisms
- Informing evidence-based practice in sports science
- Guiding the design of more effective interventions
- Reducing uncertainty in clinical/sporting decision-making

*This analysis is based on the local literature database and should be validated against the full published literature.*
"""
    return text


def _write_hypothesis(question: str, papers: list[dict]) -> str:
    """Generate research hypotheses."""
    synth = synthesize_by_question(question, papers) if papers else {}
    hypotheses = synth.get("hypotheses", [])

    text = f"""## Research Hypotheses

Based on the available evidence regarding "{question}", the following testable hypotheses are proposed:

"""
    for i, h in enumerate(hypotheses, 1):
        text += f"**H{i}:** {h}\n\n"

    text += """
### Operationalization
Each hypothesis should be tested with:
- Clearly defined independent and dependent variables
- Appropriate statistical methods (e.g., mixed-effects models, ANCOVA, meta-regression)
- Adequate sample size determined by a priori power analysis
- Pre-registration of the analysis plan

*These hypotheses are generated from the local literature database. Refine based on full literature review.*
"""
    return text


def _write_abstract(question: str, papers: list[dict]) -> str:
    """Write a structured abstract."""
    synth = synthesize_by_question(question, papers) if papers else {}
    n = len(papers)
    strength = synth.get("evidence_strength", "insufficient")

    return f"""## Abstract

**Background:** {question}

**Objective:** To synthesize the available evidence regarding this research question using
the local sports science literature database.

**Methods:** {n} relevant studies were identified from the literature database. Studies were
categorized by evidence level (high / moderate / low) and quality-scored using a standardized
assessment framework.

**Results:** The evidence base included {n} studies. Overall evidence strength was assessed as
**{strength}**. [Insert key quantitative findings here after comprehensive analysis.]

**Conclusions:** {'The evidence provides preliminary support for [conclusion]. Further research is warranted.' if strength != 'insufficient' else 'The current evidence is insufficient to draw definitive conclusions. Additional high-quality studies are needed.'}

**Keywords:** sports science, evidence synthesis, {question[:100]}

*Replace [bracketed] text with specific findings before submission.*
"""


def _write_statistical_plan(question: str, papers: list[dict]) -> str:
    """Draft a statistical analysis plan."""
    return f"""## Statistical Analysis Plan

### Study Design Considerations
For the research question: "{question}"

### Recommended Design
- **Primary design:** Randomized controlled trial (if feasible) or prospective cohort study
- **Sample size determination:** A priori power analysis based on expected effect sizes
  - α = 0.05, β = 0.20 (80% power)
  - Effect size estimates from pilot data or literature meta-analysis

### Statistical Methods

#### Primary Analysis
1. **Between-group comparisons:**
   - ANCOVA with baseline values as covariates (preferred)
   - Mixed-effects linear models for repeated measures
   - Report adjusted mean differences with 95% CI

2. **Within-group changes:**
   - Paired t-tests or Wilcoxon signed-rank tests
   - Report Cohen's d or Hedges' g with 95% CI

#### Secondary Analyses
1. **Subgroup analyses:**
   - Sex (male vs. female)
   - Age groups (youth, adult, elderly)
   - Training status (untrained, recreational, elite)
   - Intervention characteristics (dose, duration, type)

2. **Moderator analyses:**
   - Meta-regression for continuous moderators
   - Subgroup analysis for categorical moderators

#### Sensitivity Analyses
- Leave-one-out analysis
- Exclusion of low-quality studies
- Influence diagnostics (Cook's distance)

### Software
- R (metafor, lme4 packages) or Python (statsmodels, pingouin)
- G*Power for sample size calculation

### Reporting Standards
- CONSORT for RCTs
- STROBE for observational studies
- PRISMA for systematic reviews/meta-analyses

*Customize this plan based on specific study design and outcome measures.*
"""


def _write_cover_letter(question: str, papers: list[dict]) -> str:
    """Draft a cover letter template."""
    return f"""## Cover Letter

Dear Editor,

We are pleased to submit our manuscript entitled "[Title]" for consideration
for publication in [Journal Name].

### Relevance to Journal Scope
This manuscript addresses the research question: {question}

The findings contribute to the existing literature by:
1. Synthesizing evidence from relevant studies
2. Identifying critical research gaps
3. Proposing testable hypotheses for future investigation

### Key Findings
[Summarize 2-3 key findings]

### Novelty and Significance
- [Novelty point 1]
- [Novelty point 2]
- [Practical/clinical significance]

### Declarations
- This work has not been published elsewhere
- All authors have approved the manuscript
- No conflicts of interest to declare
- [Funding acknowledgment if applicable]

Thank you for considering our manuscript.

Sincerely,
[Corresponding Author]

*Fill in bracketed information before submission.*
"""


def _write_response_template(question: str) -> str:
    """Template for response to reviewers."""
    return """## Response to Reviewers

We thank the reviewers for their thoughtful comments and suggestions, which have
substantially improved the manuscript. Below, we address each comment point by point.

---

**Reviewer 1**

*Comment 1:* [Reviewer comment]

**Response:** We appreciate this observation. [Detailed response with specific changes made.]

*Comment 2:* [Reviewer comment]

**Response:** [Detailed response.]

---

**Reviewer 2**

*Comment 1:* [Reviewer comment]

**Response:** [Detailed response.]

---

All changes in the revised manuscript are highlighted in tracked changes / red text
for the reviewers' convenience.

*Replace all [bracketed] text with actual reviewer comments and responses.*
"""
