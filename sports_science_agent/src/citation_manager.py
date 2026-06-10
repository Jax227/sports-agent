"""Citation manager — format references in multiple citation styles."""

from typing import Optional


CITATION_STYLES = ["apa", "vancouver", "ama", "gbt7714"]


def format_citation(paper: dict, style: str = "apa") -> str:
    """Format a single paper as a citation in the given style."""
    if style == "apa":
        return _format_apa(paper)
    elif style == "vancouver":
        return _format_vancouver(paper)
    elif style == "ama":
        return _format_ama(paper)
    elif style == "gbt7714":
        return _format_gbt7714(paper)
    else:
        return _format_apa(paper)


def format_reference_list(papers: list[dict], style: str = "apa", numbered: bool = False) -> str:
    """Format a list of papers as a reference list."""
    refs = []
    for i, p in enumerate(papers):
        citation = format_citation(p, style)
        if numbered or style in ("vancouver", "ama"):
            refs.append(f"{i+1}. {citation}")
        else:
            refs.append(f"{citation}")
    return "\n\n".join(refs)


def _get_authors_apa(authors_str: str) -> str:
    """Format authors in APA style."""
    if not authors_str:
        return "Unknown"
    authors = [a.strip() for a in authors_str.split(";") if a.strip()]
    if not authors:
        return "Unknown"
    if len(authors) == 1:
        return authors[0]
    elif len(authors) == 2:
        return f"{authors[0]} & {authors[1]}"
    elif len(authors) <= 7:
        return ", ".join(authors[:-1]) + f", & {authors[-1]}"
    else:
        return ", ".join(authors[:6]) + f", ... {authors[-1]}"


def _format_apa(paper: dict) -> str:
    """APA 7th edition format."""
    authors = _get_authors_apa(paper.get("authors", ""))
    year = paper.get("year", "n.d.")
    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")

    # Italicize journal name and volume
    ref = f"{authors} ({year}). {title}."
    if journal:
        ref += f" *{journal}*"
        if volume:
            ref += f", *{volume}*"
            if issue:
                ref += f"({issue})"
        if pages:
            ref += f", {pages}"
        ref += "."
    if doi:
        ref += f" https://doi.org/{doi}"

    return ref


def _format_vancouver(paper: dict) -> str:
    """Vancouver (ICMJE) format."""
    authors_str = paper.get("authors", "")
    if authors_str:
        authors = [a.strip() for a in authors_str.split(";") if a.strip()]
        if len(authors) > 6:
            authors = authors[:6]
            authors_str = ", ".join(authors) + ", et al."
        else:
            authors_str = ", ".join(authors)
    else:
        authors_str = "Anonymous"

    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "")
    year = paper.get("year", "")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")

    ref = f"{authors_str}. {title}. {journal}."
    if year:
        ref += f" {year}"
    if volume:
        ref += f";{volume}"
        if issue:
            ref += f"({issue})"
    if pages:
        ref += f":{pages}"
    ref += "."
    if doi:
        ref += f" doi: {doi}"

    return ref


def _format_ama(paper: dict) -> str:
    """AMA (American Medical Association) format."""
    # AMA is similar to Vancouver
    authors_str = paper.get("authors", "")
    if authors_str:
        authors = [a.strip() for a in authors_str.split(";") if a.strip()]
        if len(authors) > 6:
            authors = authors[:3]
            authors_str = ", ".join(authors) + ", et al."
        else:
            authors_str = ", ".join(authors)
    else:
        authors_str = "Anonymous"

    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "")
    year = paper.get("year", "")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")

    ref = f"{authors_str}. {title}. {journal}."
    if year:
        ref += f" {year}"
    if volume:
        ref += f";{volume}"
        if issue:
            ref += f"({issue})"
    if pages:
        ref += f":{pages}"
    ref += "."
    if doi:
        ref += f" doi:{doi}"

    return ref


def _format_gbt7714(paper: dict) -> str:
    """GB/T 7714-2015 (Chinese national standard) format."""
    authors = paper.get("authors", "")
    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "")
    year = paper.get("year", "")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")

    ref = f"{authors}. {title}[J]. {journal}"
    if year:
        ref += f", {year}"
    if volume:
        ref += f", {volume}"
        if issue:
            ref += f"({issue})"
    if pages:
        ref += f": {pages}"
    ref += "."
    if doi:
        ref += f" DOI: {doi}."

    return ref


def extract_citations_from_text(text: str, papers: list[dict], style: str = "apa") -> dict:
    """Identify which papers are cited in a text and return their formatted citations."""
    cited = []
    for p in papers:
        title = p.get("title", "")
        doi = p.get("doi", "")
        pmid = p.get("pmid", "")
        authors = p.get("authors", "")

        # Check if any key identifier appears in the text
        title_words = set(title.lower().split()[:5])
        text_lower = text.lower()

        if (len(title_words) >= 3 and all(w in text_lower for w in list(title_words)[:3])) or \
           (doi and doi in text) or \
           (pmid and pmid in text):
            cited.append(p)

    return {
        "cited_papers": cited,
        "formatted_references": format_reference_list(cited, style=style),
        "in_text_citations": _generate_in_text_citations(cited, style=style),
    }


def _generate_in_text_citations(papers: list[dict], style: str = "apa") -> list[str]:
    """Generate in-text citation strings."""
    citations = []
    for p in papers:
        authors_str = p.get("authors", "")
        year = p.get("year", "")
        if not authors_str:
            continue
        first_author = authors_str.split(";")[0].strip().split()[-1] if ";" in authors_str else authors_str.split()[-1] if " " in authors_str else authors_str

        if style == "apa":
            author_count = len([a for a in authors_str.split(";") if a.strip()])
            if author_count == 1:
                citations.append(f"({first_author}, {year})")
            elif author_count == 2:
                second = authors_str.split(";")[1].strip().split()[-1]
                citations.append(f"({first_author} & {second}, {year})")
            else:
                citations.append(f"({first_author} et al., {year})")
        elif style in ("vancouver", "ama"):
            citations.append(f"[{i+1}]")
        else:
            citations.append(f"({first_author}, {year})")

    return citations
