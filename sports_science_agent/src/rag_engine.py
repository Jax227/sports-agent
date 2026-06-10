"""RAG engine — retrieval-augmented generation for academic Q&A."""

from typing import Optional

from src.database import search_papers, load_papers
from src.vector_store import semantic_search
from src.utils import logger, extract_pico


def decompose_question(question: str) -> dict:
    """Decompose a research question into PICO/PECO components."""
    pico = extract_pico(question)
    # If abstract-based extraction doesn't work, try simple heuristics
    if not any(pico.values()):
        pico = _simple_pico_parse(question)
    return {
        "question": question,
        "pico": pico,
    }


def _simple_pico_parse(question: str) -> dict:
    """Simple PICO parsing for research questions."""
    pico = {"population": "", "intervention": "", "comparator": "", "outcome": ""}
    q = question.lower()

    # Population patterns
    import re
    pop_patterns = [
        r"(?:in|among|for)\s+([\w\s,;-]+?)(?:\s*(?:,|does|is|can|will|what|how|undergo|receiv|perform|after|during))",
        r"(?:older|young|adult|athlete|patient|subject|participant|male|female|elite|youth|adolescent|elderly)[\w\s]*",
    ]
    for pat in pop_patterns:
        m = re.search(pat, q)
        if m:
            pico["population"] = m.group(0).strip()[:200]
            break

    # Intervention
    interv_patterns = [
        r"(?:effect|efficacy|effectiveness)\s+(?:of\s+)?([\w\s]+?)(?:\s+(?:on|in|for|versus|vs|compared|improve))",
        r"([\w\s]+(?:training|exercise|supplement|intervention|therapy|protocol|program))[\w\s]*(?:on|in|for|improve|enhance|versus|vs)",
    ]
    for pat in interv_patterns:
        m = re.search(pat, q)
        if m:
            pico["intervention"] = m.group(1).strip()[:200]
            break

    # Comparator
    comp_patterns = [
        r"(?:versus|vs\.?|compared\s+(?:to|with))\s+([\w\s,;-]+?)(?:\s*(?:on|in|for|improve|\.))",
        r"(?:than)\s+([\w\s,;-]+?)(?:\s*(?:on|in|for|improve|\.))",
    ]
    for pat in comp_patterns:
        m = re.search(pat, q)
        if m:
            pico["comparator"] = m.group(1).strip()[:200]
            break

    # Outcome
    outcome_patterns = [
        r"(?:improve|enhance|reduce|increase|affect|change|influence)\s+(?:the\s+)?([\w\s,;-]+?)(?:\?|$)",
        r"(?:on)\s+([\w\s,;-]+?)(?:\?|$)",
    ]
    for pat in outcome_patterns:
        m = re.search(pat, q)
        if m:
            pico["outcome"] = m.group(1).strip()[:200]
            break

    return pico


def retrieve_evidence(question: str, top_k: int = 10) -> list[dict]:
    """Retrieve relevant literature for a research question."""
    decomposed = decompose_question(question)
    pico = decomposed["pico"]

    # Try semantic search first
    semantic_results = semantic_search(question, n_results=top_k)

    # Supplement with keyword search
    keyword_results = search_papers(keyword=question[:200])

    # Merge, deduplicate, and sort by quality
    seen = set()
    merged = []
    for r in semantic_results:
        pid = r.get("id")
        if pid and pid not in seen:
            seen.add(pid)
            merged.append(r)

    for r in keyword_results:
        pid = r.get("id")
        if pid and pid not in seen:
            seen.add(pid)
            merged.append(r)

    # Sort: quality_score descending, then relevance
    def sort_key(r):
        try:
            qs = float(r.get("quality_score", 0))
        except (ValueError, TypeError):
            qs = 0
        try:
            rs = float(r.get("relevance_score", 0))
        except (ValueError, TypeError):
            rs = 0
        return (qs, rs)

    merged.sort(key=sort_key, reverse=True)
    return merged[:top_k]


def format_evidence_context(results: list[dict]) -> str:
    """Format retrieved evidence into a structured context string."""
    if not results:
        return "No relevant literature found in the local database."

    context_parts = []
    context_parts.append(f"Retrieved {len(results)} relevant papers from the literature database:\n")

    for i, r in enumerate(results):
        title = r.get("title", "Untitled")
        authors = r.get("authors", "Unknown")
        year = r.get("year", "?")
        journal = r.get("journal", "?")
        study_type = r.get("study_type", "?")
        evidence_level = r.get("evidence_level", "?")
        quality = r.get("quality_score", "?")
        doi = r.get("doi", "")
        snippet = r.get("snippet", r.get("abstract", ""))[:400]

        context_parts.append(
            f"--- Paper #{i+1} ---\n"
            f"Title: {title}\n"
            f"Authors: {authors}\n"
            f"Year: {year} | Journal: {journal}\n"
            f"Type: {study_type} | Evidence Level: {evidence_level} | Quality: {quality}/10\n"
            f"DOI: {doi}\n"
            f"Abstract/Snippet: {snippet}\n"
        )

    return "\n".join(context_parts)


def generate_academic_response(question: str, context: str, model: str = "local") -> str:
    """Generate an academic response using available LLM or fallback template."""
    # If API keys are available, try using an LLM
    import os
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if model == "claude" and anthropic_key:
        return _generate_with_claude(question, context, anthropic_key)
    elif model == "openai" and openai_key:
        return _generate_with_openai(question, context, openai_key)
    else:
        return _generate_with_template(question, context)


def _generate_with_template(question: str, context: str) -> str:
    """Template-based response generator (no external API needed)."""
    has_evidence = "Paper #" in context

    if not has_evidence:
        return (
            f"## Research Question: {question}\n\n"
            "当前本地文献库中尚无足够文献支持该问题的系统回答。\n\n"
            "**建议：**\n"
            "1. 先通过「文献导入」功能导入相关文献（支持 DOI、PMID、PDF 上传等方式）\n"
            "2. 使用 PubMed/CrossRef 检索功能搜索相关研究\n"
            "3. 确认文献库已建立后，再次提问\n\n"
            "当前本地文献库中尚无足够文献支持该结论。建议先导入或检索相关文献。"
        )

    # Count evidence levels
    high_count = context.count("Evidence Level: high")
    moderate_count = context.count("Evidence Level: moderate")
    low_count = context.count("Evidence Level: low")
    very_low_count = context.count("Evidence Level: very_low")

    response_parts = [
        f"## 研究问题：{question}\n",
        "## 证据检索结果\n",
        f"从本地文献库中检索到相关文献。",
    ]

    if high_count > 0:
        response_parts.append(f"其中 **{high_count}** 篇为高质量证据。")
    if moderate_count > 0:
        response_parts.append(f"**{moderate_count}** 篇为中等质量证据。")
    if low_count + very_low_count > 0:
        low_total = low_count + very_low_count
        response_parts.append(f"**{low_total}** 篇证据等级较低，结论需谨慎解释。")

    response_parts.append("\n## 初步综合\n")
    response_parts.append("基于现有文献库的检索结果，提供以下初步综合：\n")
    response_parts.append("**证据概要：** 本地文献库中收录的相关研究提供了对该问题的部分证据。")
    response_parts.append("由于文献库可能尚不完整，以下分析应被视为初步的、有待补充的判断。\n")
    response_parts.append("**局限性：**")
    response_parts.append("- 文献库覆盖范围可能有限")
    response_parts.append("- 部分文献可能未纳入最新研究")
    response_parts.append("- 证据综合需通过系统性文献检索进行验证\n")
    response_parts.append("**研究空白：** 如需对该问题做出确定性结论，建议进行系统性文献检索和 Meta 分析。\n")

    if high_count >= 2:
        response_parts.append("现有较高质量证据提示该问题已有一定研究基础，但结论仍需基于更大范围的文献检索。")
    elif high_count + moderate_count >= 2:
        response_parts.append("现有证据提供了一些初步线索，但高质量证据仍不充分。由于样本量较小或方法学差异，结论仍需谨慎解释。")
    else:
        response_parts.append("目前证据不足以支持确定结论。未来研究应关注该问题的核心变量。")

    response_parts.append("\n---\n")
    response_parts.append("*本回答基于本地文献库中的可用证据生成。如需更全面的分析，请导入更多相关文献。*")

    return "\n".join(response_parts)


def _generate_with_claude(question: str, context: str, api_key: str) -> str:
    """Generate response using Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = """You are a Sports Science Research Agent. Your goal is to help users with academic-level
literature synthesis, evidence evaluation, research design, and paper writing.

You must:
1. Base answers on the provided literature context
2. Do not fabricate citations or findings
3. Distinguish between evidence, inference, and recommendation
4. Organize answers by evidence level
5. Point out study limitations
6. Identify research gaps
7. Propose testable hypotheses
8. Output in academic writing style
9. If evidence is insufficient, state so clearly

Use academic language: "Evidence suggests...", "Higher quality studies indicate...",
"However, some studies have...", "Due to small sample sizes, conclusions should be interpreted cautiously...",
"Current evidence is insufficient to...", "Future research should..."
"""

        user_prompt = f"""Research Question: {question}

Retrieved Literature Context:
{context}

Please analyze the evidence and provide:
1. Summary of available evidence (by quality level)
2. Consistent findings across studies
3. Contradictory results (if any) and possible reasons
4. Evidence strength assessment
5. Research gaps identified
6. Testable hypotheses for future research
7. References cited from the literature context

IMPORTANT: Only cite papers that appear in the provided context. Do not fabricate references."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return _generate_with_template(question, context)


def _generate_with_openai(question: str, context: str, api_key: str) -> str:
    """Generate response using OpenAI API."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        system_prompt = """You are a Sports Science Research Agent, assisting with academic-level literature synthesis,
evidence evaluation, and paper writing. Base answers on provided context. Do not fabricate references.
Distinguish evidence levels, point out limitations, identify gaps. Use academic language."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {question}\n\nLiterature Context:\n{context}"},
            ],
            max_tokens=4000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return _generate_with_template(question, context)


def answer_question(question: str, top_k: int = 10, model: str = "local") -> dict:
    """Full RAG pipeline: retrieve + generate."""
    # Retrieve
    results = retrieve_evidence(question, top_k=top_k)

    # Build context
    context = format_evidence_context(results)

    # Generate
    response = generate_academic_response(question, context, model=model)

    return {
        "question": question,
        "pico": decompose_question(question)["pico"],
        "retrieved_count": len(results),
        "retrieved_papers": results,
        "context": context,
        "response": response,
    }
