"""
Sports Science Research Agent — Streamlit Application
======================================================
独立运行在端口 8502，提供运动科学文献管理、筛选、问答和论文写作功能。
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import os
import json

# Ensure the project root is on sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════
# Page config
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Sports Science Research Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# Styling
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
    .main-header { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.2rem; font-weight: 600; color: #555; margin-bottom: 1rem; }
    .evidence-high { color: #0a7; }
    .evidence-moderate { color: #ea0; }
    .evidence-low { color: #e70; }
    .evidence-very_low { color: #d00; }
    .paper-card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; margin: 0.5rem 0; }
    .score-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600; }
    .score-high { background: #d4edda; color: #155724; }
    .score-mid { background: #fff3cd; color: #856404; }
    .score-low { background: #f8d7da; color: #721c24; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# Import project modules
# ═══════════════════════════════════════════════════════════
from src.config import (
    SPORT_SCIENCE_DOMAINS, STUDY_TYPES, EVIDENCE_LEVELS,
    QUALITY_THRESHOLD, RELEVANCE_THRESHOLD,
)
from src.database import (
    load_papers, add_paper, search_papers, get_statistics,
    delete_paper, update_paper,
)
from src.literature_importer import (
    import_by_doi, import_by_pmid, import_by_pdf,
    import_manually, import_from_text,
)
from src.pdf_parser import parse_pdf
from src.screening import screen_paper
from src.quality_assessment import full_quality_assessment
from src.rag_engine import answer_question
from src.evidence_synthesizer import synthesize_by_question, build_evidence_map
from src.academic_writer import generate_section
from src.citation_manager import format_reference_list
from src.vector_store import get_vector_store_stats
from src.strict_literature_search import run_search_and_appraisal, import_to_library
from src.journal_club_reporter import generate_report as generate_jc_report, save_report

# ═══════════════════════════════════════════════════════════
# Sidebar — Navigation
# ═══════════════════════════════════════════════════════════
st.sidebar.markdown("## 📚 Sports Science Research Agent")
st.sidebar.markdown("运动科学文献智能体")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Dashboard",
        "📥 Import Literature",
        "🔍 Literature Database",
        "🧪 Screening & Quality",
        "📋 严格文献检索与评判",
        "❓ Academic Q&A",
        "✍️ Academic Writing",
        "📈 Evidence Map",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Data directory: `{ROOT / 'literature_db'}`")
st.sidebar.caption(f"Port: `8502` (独立运行)")

# ── Quick stats in sidebar ──
stats = get_statistics()
st.sidebar.markdown("### 📊 Library Stats")
col1, col2 = st.sidebar.columns(2)
col1.metric("Total Papers", stats["total_papers"])
col2.metric("Included", stats["included"])
st.sidebar.progress(
    stats["included"] / max(stats["total_papers"], 1),
    text=f"{stats['included']}/{stats['total_papers']} included"
)

# ═══════════════════════════════════════════════════════════
# Page 1: Dashboard
# ═══════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">📊 Dashboard — Literature Library Overview</p>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Papers", stats["total_papers"])
    col2.metric("✅ Included", stats["included"])
    col3.metric("⚠️ Maybe", stats["maybe"])
    col4.metric("❌ Excluded", stats["excluded"])

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("By Research Domain")
        if stats["by_domain"]:
            df_domain = pd.DataFrame(
                stats["by_domain"].items(),
                columns=["Domain", "Count"]
            ).sort_values("Count", ascending=False)
            st.bar_chart(df_domain.set_index("Domain"))
        else:
            st.info("No papers in library yet. Start by importing literature.")

    with col_right:
        st.subheader("By Evidence Level")
        if stats["by_evidence_level"]:
            df_evidence = pd.DataFrame(
                stats["by_evidence_level"].items(),
                columns=["Evidence Level", "Count"]
            )
            st.bar_chart(df_evidence.set_index("Evidence Level"))
        else:
            st.info("No papers in library yet.")

    st.markdown("---")
    st.subheader("By Study Type")
    if stats["by_study_type"]:
        df_type = pd.DataFrame(
            stats["by_study_type"].items(),
            columns=["Study Type", "Count"]
        ).sort_values("Count", ascending=False)
        st.dataframe(df_type, use_container_width=True)

    # Vector store status
    vs_stats = get_vector_store_stats()
    st.caption(f"Vector Store: {vs_stats.get('status', 'unknown')} | "
               f"Documents: {vs_stats.get('count', 0)} | "
               f"Model: {vs_stats.get('embedding_model', 'N/A')}")

# ═══════════════════════════════════════════════════════════
# Page 2: Import Literature
# ═══════════════════════════════════════════════════════════
elif page == "📥 Import Literature":
    st.markdown('<p class="main-header">📥 Import Literature</p>', unsafe_allow_html=True)

    import_method = st.radio(
        "Import Method",
        ["DOI Lookup", "PMID Lookup", "Upload PDF", "Manual Entry", "BibTeX / RIS / Free Text"],
        horizontal=True,
    )

    if import_method == "DOI Lookup":
        st.subheader("Lookup by DOI")
        doi_input = st.text_input("Enter DOI", placeholder="e.g., 10.1007/s40279-021-01567-3")
        if st.button("🔍 Lookup & Import", type="primary", use_container_width=True):
            if doi_input:
                with st.spinner("Fetching metadata from CrossRef..."):
                    result = import_by_doi(doi_input)
                if result.get("success"):
                    st.success(f"✅ Imported: **{result.get('title', '')}**")
                    st.json(result.get("screening", {}))
                else:
                    st.error(result.get("error", "Import failed"))
            else:
                st.warning("Please enter a DOI.")

    elif import_method == "PMID Lookup":
        st.subheader("Lookup by PMID")
        pmid_input = st.text_input("Enter PMID", placeholder="e.g., 35000001")
        if st.button("🔍 Lookup & Import", type="primary", use_container_width=True):
            if pmid_input:
                with st.spinner("Fetching metadata from PubMed..."):
                    result = import_by_pmid(pmid_input)
                if result.get("success"):
                    st.success(f"✅ Imported: **{result.get('title', '')}**")
                    st.json(result.get("screening", {}))
                else:
                    st.error(result.get("error", "Import failed"))
            else:
                st.warning("Please enter a PMID.")

    elif import_method == "Upload PDF":
        st.subheader("Upload PDF File")
        pdf_file = st.file_uploader("Choose a PDF", type=["pdf"], key="pdf_uploader")
        if pdf_file and st.button("📄 Parse & Import", type="primary", use_container_width=True):
            with st.spinner("Parsing PDF and extracting metadata..."):
                result = import_by_pdf(pdf_file)
            if result.get("success"):
                st.success(f"✅ Imported: **{result.get('title', '')}**")
                st.json(result.get("screening", {}))
            else:
                st.error(result.get("error", "Import failed"))

    elif import_method == "Manual Entry":
        st.subheader("Manual Paper Entry")
        with st.form("manual_entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Title *")
                authors = st.text_input("Authors *", placeholder="Author A; Author B; Author C")
                year = st.text_input("Year *")
                journal = st.text_input("Journal")
                doi = st.text_input("DOI")
                pmid = st.text_input("PMID")
            with col2:
                study_type = st.selectbox("Study Type", [""] + STUDY_TYPES)
                population = st.text_input("Population")
                sample_size = st.text_input("Sample Size")
                research_domain = st.selectbox("Research Domain", [""] + SPORT_SCIENCE_DOMAINS)

            abstract = st.text_area("Abstract")
            keywords = st.text_input("Keywords (semicolon-separated)")
            main_findings = st.text_area("Main Findings")
            effect_size = st.text_input("Effect Size")
            limitations = st.text_area("Limitations")
            notes = st.text_area("Notes")

            submitted = st.form_submit_button("📝 Add Paper", type="primary", use_container_width=True)
            if submitted:
                if title and authors and year:
                    with st.spinner("Processing..."):
                        result = import_manually({
                            "title": title, "authors": authors, "year": year,
                            "journal": journal, "doi": doi, "pmid": pmid,
                            "study_type": study_type, "population": population,
                            "sample_size": sample_size, "abstract": abstract,
                            "keywords": [k.strip() for k in keywords.split(";") if k.strip()],
                            "main_findings": main_findings, "effect_size": effect_size,
                            "limitations": limitations, "notes": notes,
                        })
                    if result.get("success"):
                        st.success(f"✅ Paper added: **{result.get('title', '')}**")
                        st.json(result.get("screening", {}))
                    else:
                        st.error(result.get("error", "Import failed"))
                else:
                    st.warning("Title, Authors, and Year are required.")

    elif import_method == "BibTeX / RIS / Free Text":
        st.subheader("Paste BibTeX, RIS, or Free Text")
        raw_text = st.text_area("Paste content here", height=250,
                                placeholder="@article{...\n  title={...}\n  ...\n}\n\nor RIS format:\nTY  - JOUR\nTI  - ...\n\nor paste text containing a DOI")
        if st.button("📋 Parse & Import", type="primary", use_container_width=True):
            if raw_text:
                with st.spinner("Parsing..."):
                    result = import_from_text(raw_text)
                if result.get("success"):
                    st.success(f"✅ Imported: **{result.get('title', '')}**")
                    st.json(result.get("screening", {}))
                else:
                    st.error(result.get("error", "Import failed"))
            else:
                st.warning("Please paste some content.")

# ═══════════════════════════════════════════════════════════
# Page 3: Literature Database
# ═══════════════════════════════════════════════════════════
elif page == "🔍 Literature Database":
    st.markdown('<p class="main-header">🔍 Literature Database</p>', unsafe_allow_html=True)

    # Filters
    st.markdown("### Search & Filter")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        keyword = st.text_input("Keyword Search", placeholder="Search title, abstract...")
    with col2:
        domain_filter = st.selectbox("Research Domain", ["All"] + SPORT_SCIENCE_DOMAINS)
    with col3:
        study_type_filter = st.selectbox("Study Type", ["All"] + STUDY_TYPES)
    with col4:
        evidence_filter = st.selectbox("Evidence Level", ["All"] + EVIDENCE_LEVELS)

    col5, col6, col7 = st.columns(3)
    with col5:
        year_from = st.number_input("Year From", min_value=1900, max_value=2030, value=1900)
    with col6:
        year_to = st.number_input("Year To", min_value=1900, max_value=2030, value=2030)
    with col7:
        min_quality = st.slider("Min Quality Score", 0.0, 10.0, 0.0, 0.5)

    # Search
    results = search_papers(
        keyword=keyword,
        domain="" if domain_filter == "All" else domain_filter,
        study_type="" if study_type_filter == "All" else study_type_filter,
        evidence_level="" if evidence_filter == "All" else evidence_filter,
        year_from=year_from if year_from > 1900 else None,
        year_to=year_to if year_to < 2030 else None,
        min_quality=min_quality if min_quality > 0 else None,
    )

    st.markdown(f"**Found {len(results)} papers**")

    # Display results
    for paper in results:
        with st.expander(f"{paper.get('title', 'Untitled')[:120]}", expanded=False):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**Authors:** {paper.get('authors', 'N/A')}")
                st.markdown(f"**Year:** {paper.get('year', 'N/A')} | **Journal:** {paper.get('journal', 'N/A')}")
                st.markdown(f"**DOI:** {paper.get('doi', 'N/A')} | **PMID:** {paper.get('pmid', 'N/A')}")
                if paper.get("abstract"):
                    st.markdown(f"**Abstract:** {paper['abstract'][:500]}")
            with col_b:
                qs = paper.get("quality_score", "?")
                rs = paper.get("relevance_score", "?")
                el = paper.get("evidence_level", "?")
                qt_class = "score-high" if float(qs or 0) >= 7 else ("score-mid" if float(qs or 0) >= 4 else "score-low")
                st.markdown(f'<span class="score-badge {qt_class}">Quality: {qs}/10</span>', unsafe_allow_html=True)
                st.markdown(f"**Relevance:** {rs}/10")
                st.markdown(f"**Evidence:** {el}")
                st.markdown(f"**Type:** {paper.get('study_type', '?')}")
                st.markdown(f"**Domain:** {paper.get('research_domain', '?')}")
                decision = paper.get("inclusion_decision", "?")
                dec_icon = {"include": "✅", "exclude": "❌", "maybe": "⚠️"}.get(decision, "❓")
                st.markdown(f"**Decision:** {dec_icon} {decision}")
                if paper.get("reason"):
                    st.caption(paper.get("reason", ""))

            # Actions
            c1, c2, c3 = st.columns(3)
            if c1.button("🗑️ Delete", key=f"del_{paper.get('id')}"):
                delete_paper(paper["id"])
                st.rerun()
            if c2.button("🔄 Re-screen", key=f"rescreen_{paper.get('id')}"):
                screening = screen_paper(paper)
                paper.update(screening)
                full_quality_assessment(paper)
                add_paper(paper)
                st.rerun()

    # Export
    if results:
        st.markdown("---")
        csv = pd.DataFrame(results).to_csv(index=False).encode("utf-8")
        st.download_button("📥 Export Results as CSV", csv, "literature_export.csv", "text/csv")

# ═══════════════════════════════════════════════════════════
# Page 4: Screening & Quality
# ═══════════════════════════════════════════════════════════
elif page == "🧪 Screening & Quality":
    st.markdown('<p class="main-header">🧪 Screening & Quality Assessment</p>', unsafe_allow_html=True)

    st.markdown(f"""
    **Screening thresholds (configurable in `src/config.py`):**
    - Include: quality ≥ {QUALITY_THRESHOLD} AND relevance ≥ {RELEVANCE_THRESHOLD}
    - High priority: quality ≥ 8 AND relevance ≥ 8 AND type ∈ [meta-analysis, systematic review, RCT, guideline]
    """)

    papers = load_papers()

    # Filter for screening view
    decision_filter = st.radio(
        "Filter by decision", ["All", "Pending", "Include", "Maybe", "Exclude"],
        horizontal=True, key="screen_filter"
    )

    filtered = papers
    if decision_filter == "Pending":
        filtered = [p for p in papers if not p.get("inclusion_decision")]
    elif decision_filter != "All":
        filtered = [p for p in papers if p.get("inclusion_decision") == decision_filter.lower()]

    st.markdown(f"**Showing {len(filtered)} papers**")

    for paper in filtered:
        with st.expander(f"{paper.get('title', 'Untitled')[:100]}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Paper Info")
                st.markdown(f"**Title:** {paper.get('title', 'N/A')}")
                st.markdown(f"**Authors:** {paper.get('authors', 'N/A')}")
                st.markdown(f"**Journal:** {paper.get('journal', 'N/A')} ({paper.get('year', '?')})")
                st.markdown(f"**Study Type:** {paper.get('study_type', 'N/A')}")
                st.markdown(f"**Domain:** {paper.get('research_domain', 'N/A')}")
                st.markdown(f"**Evidence Level:** {paper.get('evidence_level', 'N/A')}")
                st.markdown(f"**Sample Size:** {paper.get('sample_size', 'N/A')}")

            with c2:
                st.markdown("### Scores & Decision")
                qs = float(paper.get("quality_score", 0) or 0)
                rs = float(paper.get("relevance_score", 0) or 0)
                st.metric("Quality Score", f"{qs}/10")
                st.metric("Relevance Score", f"{rs}/10")
                st.markdown(f"**Risk of Bias:** {paper.get('risk_of_bias', 'N/A')}")
                if paper.get("risk_of_bias_concerns"):
                    for concern in paper["risk_of_bias_concerns"]:
                        st.caption(f"⚠️ {concern}")
                st.markdown(f"**Decision:** {paper.get('inclusion_decision', 'pending')}")
                st.markdown(f"**Reason:** {paper.get('reason', 'N/A')}")

            # Quality components details
            components = paper.get("quality_components", {})
            if components:
                st.markdown("### Quality Score Breakdown")
                comp_df = pd.DataFrame(
                    list(components.items()),
                    columns=["Component", "Score"]
                )
                st.bar_chart(comp_df.set_index("Component"))

            # Manual override
            c1, c2, c3 = st.columns(3)
            pid = paper.get("id")
            if c1.button("✅ Include", key=f"inc_{pid}"):
                update_paper(pid, {"inclusion_decision": "include",
                                   "reason": "Manually overridden to include"})
                st.rerun()
            if c2.button("⚠️ Maybe", key=f"may_{pid}"):
                update_paper(pid, {"inclusion_decision": "maybe",
                                   "reason": "Manually set to maybe"})
                st.rerun()
            if c3.button("❌ Exclude", key=f"exc_{pid}"):
                update_paper(pid, {"inclusion_decision": "exclude",
                                   "reason": "Manually overridden to exclude"})
                st.rerun()

    # Batch re-screen
    if filtered:
        st.markdown("---")
        if st.button("🔄 Re-screen ALL displayed papers", use_container_width=True):
            with st.spinner(f"Re-screening {len(filtered)} papers..."):
                for paper in filtered:
                    screening = screen_paper(paper)
                    paper.update(screening)
                    full_quality_assessment(paper)
                    add_paper(paper)
            st.success(f"Re-screened {len(filtered)} papers")
            st.rerun()

# ═══════════════════════════════════════════════════════════
# Page 5: Strict Literature Search & Appraisal
# ═══════════════════════════════════════════════════════════
elif page == "📋 严格文献检索与评判":
    st.markdown('<p class="main-header">📋 严格学术标准自动文献检索与评判</p>', unsafe_allow_html=True)

    st.markdown("""
    本模块按照**严格学术标准**，自动检索 PubMed / CrossRef 真实文献，并对每篇文献进行系统评价：
    - **期刊质量**（JCR/CAS 分区，本地 CSV 匹配）
    - **研究设计**（18+ 种研究类型自动识别与严格评分）
    - **统计方法**（效应量、置信区间、样本量估算、运动科学特殊考量）
    - **偏倚风险**（RoB 2 / ROBINS-I / AMSTAR 2 / NOS / AXIS 匹配）
    - **证据等级**（GRADE 初步分级）
    - **PICO 相关性**（与用户研究主题的术语级匹配）

    > 所有评分透明可审计。所有文献信息来自真实检索，**严禁编造数据**。
    """)

    # ── Initialize session state ──
    if "strict_results" not in st.session_state:
        st.session_state.strict_results = None
    if "strict_topic" not in st.session_state:
        st.session_state.strict_topic = ""
    if "strict_search_params" not in st.session_state:
        st.session_state.strict_search_params = {}
    if "strict_abstract_cache" not in st.session_state:
        st.session_state.strict_abstract_cache = {}

    # ── 1. Input form ──
    with st.form("strict_search_form"):
        col_left, col_right = st.columns([3, 1])
        with col_left:
            topic = st.text_area(
                "研究主题（自然语言描述）",
                placeholder=(
                    "例如：HIIT 对中老年人 VO2max 的改善效果是否优于中等强度持续训练？\n"
                    "例如：Does blood flow restriction training improve muscle strength "
                    "in ACL reconstruction patients?\n"
                    "例如：运动干预对青少年抑郁症状影响的系统评价"
                ),
                height=90,
            )
        with col_right:
            databases = st.multiselect(
                "检索数据库", ["pubmed", "crossref"],
                default=["pubmed"],
            )
            max_results = st.slider("每库最大检索数", 5, 50, 10)
            year_from = st.number_input("起始年份（留空不限制）", 1900, 2030, value=None, step=1)
            year_to = st.number_input("截止年份（留空不限制）", 1900, 2030, value=None, step=1)

        submitted = st.form_submit_button(
            "🔬 开始严格检索与评判", type="primary", use_container_width=True
        )

    if submitted:
        if not topic.strip():
            st.warning("请输入研究主题。")
        elif not databases:
            st.warning("请至少选择一个检索数据库。")
        else:
            st.session_state.strict_topic = topic
            st.session_state.strict_search_params = {
                "max_results": max_results,
                "databases": databases,
                "year_from": year_from if year_from else None,
                "year_to": year_to if year_to else None,
            }
            st.rerun()

    # ── Run search (triggered by form submit) ──
    if st.session_state.get("strict_topic") and not st.session_state.get("strict_results"):
        params = st.session_state.strict_search_params
        with st.spinner(f"正在检索「{st.session_state.strict_topic}」并执行严格评价…"):
            with st.status("检索与评价进度", expanded=True) as status:
                st.write("🔍 生成 PICO/PECO 检索式…")
                st.write("📡 检索 PubMed / CrossRef…")
                st.write("📊 执行期刊匹配、研究设计评价、统计评价、偏倚评价…")
                st.write("📝 生成组会报告…")

                try:
                    result = run_search_and_appraisal(
                        topic=st.session_state.strict_topic,
                        max_results=params.get("max_results", 10),
                        databases=params.get("databases", ["pubmed"]),
                        year_from=params.get("year_from"),
                        year_to=params.get("year_to"),
                    )
                    st.session_state.strict_results = result
                    status.update(label="检索与评价完成", state="complete")
                except Exception as e:
                    status.update(label=f"检索失败: {e}", state="error")
                    st.error(f"检索过程中出现错误: {e}")
                    st.session_state.strict_results = None

        st.rerun()

    # ── Display results ──
    result = st.session_state.strict_results
    if result is None:
        st.info("👆 请在上方输入研究主题并点击检索按钮开始。")
    else:
        session = result.get("session", {})
        appraisals = result.get("appraisals", [])
        papers = result.get("papers", [])

        # ── Session summary ──
        st.markdown("---")
        st.markdown("### 📊 检索结果概览")

        # Relevance stats from new evaluator
        relevance_stats = session.get("relevance_stats", {})
        excluded_papers = result.get("excluded_papers", [])

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("检索到文献", session.get("total_retrieved", 0))
        col2.metric("完成评价", session.get("total_appraised", 0))
        col3.metric("高相关", relevance_stats.get("high", 0), delta=None)
        col4.metric("中等相关", relevance_stats.get("moderate", 0), delta=None)
        col5.metric("低相关", relevance_stats.get("low", 0), delta=None)
        col6.metric("已排除", relevance_stats.get("exclude", 0) + len(excluded_papers), delta=None)

        # Legacy recommendation counts (for backward compatibility)
        rec_counts = {"include": 0, "maybe": 0, "manual_review": 0, "exclude": 0, "error": 0}
        for a in appraisals:
            rec = a.get("overall_appraisal", {}).get("recommendation", "error")
            if rec in rec_counts:
                rec_counts[rec] += 1
            else:
                rec_counts["error"] += 1

        # ── Connection errors ──
        search_log = result.get("search_log", {})
        errors = search_log.get("errors", [])
        if errors:
            st.markdown("---")
            st.markdown("### ⚠️ 网络连接问题")
            for err in errors:
                if isinstance(err, dict):
                    db = err.get("database", "unknown")
                    err_type = err.get("type", "unknown")
                    msg = err.get("message", "")
                    detail = err.get("detail", "")

                    if err_type == "connection":
                        st.error(
                            f"**{db.upper()} 连接失败：网络不通**\n\n"
                            f"{msg}\n\n"
                            f"可能原因：\n"
                            f"- 公司/学校网络代理拦截了 HTTPS 请求\n"
                            f"- 防火墙阻断了到学术数据库的出境连接\n"
                            f"- VPN 未开启（如果网络环境需要）\n\n"
                            f"建议：尝试切换网络环境（如手机热点）、开启全局 VPN，或稍后重试。"
                        )
                    else:
                        st.warning(f"**{db.upper()}:** {msg}")
                else:
                    st.warning(str(err))

        # ── PICO display with query context ──
        query_data = result.get("query", {})
        pico = query_data.get("pico_peco", {})
        query_context = query_data.get("query_context", {})

        with st.expander("🔬 PICO/PECO 拆解与检索式", expanded=False):
            col_p, col_i = st.columns(2)
            with col_p:
                st.markdown(f"**P (Population / 人群):** {pico.get('population', '未识别')}")
                st.markdown(f"**I (Intervention / 干预):** {pico.get('intervention_or_exposure', '未识别')}")
                st.markdown(f"**C (Comparator / 对照):** {pico.get('comparator', '未指定')}")
                st.markdown(f"**O (Outcomes / 结局):** {pico.get('outcomes', '未识别')}")
                st.markdown(f"**研究设计偏好:** {pico.get('study_design_preference', '未指定')}")

                # Show structured PICO from LLM if available
                if query_context:
                    structured_pico = query_context.get("pico", {})
                    if structured_pico:
                        st.markdown("---")
                        st.markdown("**📋 LLM 结构化拆解:**")
                        for dim_key, dim_cn in [
                            ("population", "👥 人群"),
                            ("intervention_or_exposure", "💊 干预/暴露"),
                            ("comparator", "⚖️ 对照"),
                            ("outcomes", "📏 结局"),
                            ("context", "🏟️ 上下文"),
                        ]:
                            comp = structured_pico.get(dim_key, {})
                            if isinstance(comp, dict):
                                terms = comp.get("english_terms", [])
                                required = comp.get("required", False)
                                req_tag = " **[必选]**" if required else ""
                                if terms:
                                    st.markdown(f"{dim_cn}{req_tag}: `{'`, `'.join(terms[:6])}`")

                    mandatory = query_context.get("mandatory_terms", [])
                    optional = query_context.get("optional_terms", [])
                    exclusion = query_context.get("exclusion_terms", [])
                    if mandatory:
                        st.markdown(f"🔴 **核心必选词:** `{'`, `'.join(mandatory)}`")
                    if optional:
                        st.markdown(f"🟡 **扩展可选词:** `{'`, `'.join(optional[:8])}`")
                    if exclusion:
                        st.markdown(f"🚫 **排除词:** `{'`, `'.join(exclusion[:8])}`")

            with col_i:
                queries = query_data.get("queries", {})
                st.markdown("**PubMed 检索式:**")
                pubmed_q = queries.get("pubmed", "N/A")
                st.code(pubmed_q, language=None)
                # Allow editing query
                edited_query = st.text_area(
                    "编辑 PubMed 检索式（修改后需重新检索）",
                    value=pubmed_q,
                    key="edited_pubmed_query",
                    height=80,
                    disabled=True,
                )
                if queries.get("crossref"):
                    st.markdown("**CrossRef 检索式:**")
                    st.code(queries.get("crossref", ""), language=None)

        # ── Recommendation distribution ──
        if appraisals:
            st.markdown("### 📋 评价结果分布")
            rec_cols = st.columns(4)
            rec_labels = {
                "include": ("✅ 建议纳入", "#d4edda"),
                "maybe": ("⚠️ 可能纳入", "#fff3cd"),
                "manual_review": ("🔍 需人工复核", "#cce5ff"),
                "exclude": ("❌ 建议排除", "#f8d7da"),
            }
            for (key, (label, color)), col in zip(rec_labels.items(), rec_cols):
                count = rec_counts.get(key, 0)
                col.markdown(
                    f'<div style="background:{color};padding:12px;border-radius:8px;text-align:center;">'
                    f'<span style="font-size:1.5rem;font-weight:700;">{count}</span><br>{label}</div>',
                    unsafe_allow_html=True,
                )

        # ── Results table ──
        st.markdown("---")
        st.markdown("### 📚 检索结果与评价详情")

        # ── Abstract language toggle ──
        lang_col1, lang_col2 = st.columns([1, 5])
        with lang_col1:
            st.radio(
                "摘要语言",
                options=["zh", "en"],
                format_func=lambda x: ("中文" if x == "zh" else "English"),
                key="abstract_lang_radio",
                horizontal=True,
            )

        if not appraisals and not excluded_papers:
            errors = result.get("search_log", {}).get("errors", [])
            has_connection_error = any(
                isinstance(e, dict) and e.get("type") == "connection" for e in errors
            )
            if has_connection_error:
                st.error(
                    "未能检索到任何文献，因为网络无法连接到学术数据库。"
                    "请参考上方 ⚠️ 网络连接问题 中的建议排查网络后重试。"
                )
            elif errors:
                st.warning("未检索到任何文献，检索过程中出现错误。请查看上方错误详情。")
            else:
                st.info(
                    "未检索到任何文献。可能原因：\n"
                    "- 研究主题的关键词未在 PubMed/CrossRef 中匹配到论文\n"
                    "- 中文主题尚未翻译为英文检索词（当前版本查询构建器仅支持英文）\n"
                    "- 年份范围过于狭窄\n\n"
                    "建议：尝试用英文关键词检索（如 'OPL optimal load resistance training intervention'），"
                    "或缩小检索范围。"
                )
        else:
            # ── Relevance filter ──
            filter_col1, filter_col2 = st.columns([1, 5])
            with filter_col1:
                relevance_filter = st.radio(
                    "相关性筛选",
                    options=["high_moderate", "all"],
                    format_func=lambda x: "仅高/中相关" if x == "high_moderate" else "显示全部",
                    key="relevance_filter_radio",
                    horizontal=True,
                )

            # Apply filter
            if relevance_filter == "high_moderate":
                visible_appraisals = [
                    a for a in appraisals
                    if (a.get("relevance_analysis", {}).get("relevance_label") or
                        a.get("relevance_evaluation", {}).get("relevance_label", ""))
                    in ("high", "moderate", "")
                ]
            else:
                visible_appraisals = list(appraisals)

            # Show filter summary
            show_excluded_count = len(excluded_papers)
            low_count = relevance_stats.get("low", 0)
            if relevance_filter == "high_moderate":
                st.caption(f"显示 {len(visible_appraisals)} 篇高/中相关文献（隐藏 {len(appraisals) - len(visible_appraisals)} 篇低相关，{show_excluded_count} 篇已排除）")

            for i, appraisal in enumerate(visible_appraisals):
                paper_id = appraisal.get("paper_id", f"paper_{i}")
                title = appraisal.get("title", "无标题")
                oa = appraisal.get("overall_appraisal", {})
                sde = appraisal.get("study_design_evaluation", {})
                be = appraisal.get("bias_and_evidence", {})
                re = appraisal.get("relevance_evaluation", {})
                je = appraisal.get("journal_evaluation", {})
                ra = appraisal.get("relevance_analysis", {})

                score = oa.get("overall_quality_score", 0) or 0
                rec = oa.get("recommendation", "error")

                # Relevance label and score
                rel_label = ra.get("relevance_label", "") if isinstance(ra, dict) else ""
                rel_score = ra.get("final_relevance_score", "") if isinstance(ra, dict) else ""
                rel_icon_map = {"high": "🟢", "moderate": "🟡", "low": "🟠", "exclude": "🔴"}
                rel_icon = rel_icon_map.get(rel_label, "⚪")
                rel_badge = f"{rel_icon} {rel_label.upper()} [{rel_score}/10]" if rel_label else ""

                score_class = (
                    "score-high" if score >= 7 else "score-mid" if score >= 4 else "score-low"
                )
                rec_icon = {
                    "include": "✅", "maybe": "⚠️", "manual_review": "🔍", "exclude": "❌"
                }.get(rec, "❓")

                with st.expander(
                    f"{rel_badge} | {rec_icon} [{score}/10] {title[:100]}", expanded=(i == 0)
                ):
                    # ── Top metadata row ──
                    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
                    with meta_col1:
                        st.markdown(f"**作者:** {', '.join(appraisal.get('authors', [])[:3]) or 'N/A'}")
                        st.markdown(f"**年份:** {appraisal.get('year', 'N/A')}")
                        st.markdown(f"**期刊:** {appraisal.get('journal', 'N/A')}")
                    with meta_col2:
                        st.markdown(f"**DOI:** {appraisal.get('doi', 'N/A')}")
                        st.markdown(f"**PMID:** {appraisal.get('pmid', 'N/A')}")
                        st.markdown(f"**出版类型:** {', '.join(appraisal.get('publication_type', [])) or 'N/A'}")
                    with meta_col3:
                        st.markdown(f"**证据等级:** {be.get('evidence_level', 'N/A')}")
                        st.markdown(f"**偏倚风险:** {be.get('risk_of_bias', 'N/A')}")
                        st.markdown(f"**研究类型:** {sde.get('study_type', 'N/A')}")
                    with meta_col4:
                        st.markdown(
                            f'<span class="score-badge {score_class}">'
                            f'综合: {score}/10</span>',
                            unsafe_allow_html=True,
                        )
                        # New strict relevance score (primary)
                        if isinstance(ra, dict) and ra:
                            rel_score = ra.get("final_relevance_score", "")
                            rel_label = ra.get("relevance_label", "")
                            if rel_label:
                                st.markdown(f"**🎯 相关性: {rel_label.upper()} [{rel_score}/10]**")
                        st.markdown(f"**设计: {oa.get('design_score', '?')}/10**")
                        st.markdown(f"**统计: {oa.get('statistics_score', '?')}/10**")
                        if oa.get("journal_score") is not None:
                            st.markdown(f"**期刊: {oa.get('journal_score')}/10**")

                    # ── Recommendation ──
                    st.markdown(f"**推荐意见:** {rec_icon} {rec} — {oa.get('recommendation_reason', '')}")

                    # ── Abstract ──
                    abstract = appraisal.get("abstract", "")
                    if abstract:
                        show_zh = st.session_state.get("abstract_lang_radio", "zh") == "zh"
                        cache = st.session_state.strict_abstract_cache
                        paper_id = appraisal.get("paper_id", f"paper_{i}")

                        if show_zh:
                            # Use cached translation or translate on demand
                            if paper_id not in cache:
                                with st.spinner("翻译摘要中…"):
                                    from src.utils import translate_abstract
                                    cache[paper_id] = translate_abstract(abstract)
                                st.session_state.strict_abstract_cache = cache

                            display_text = cache.get(paper_id, abstract)
                            expander_label = "📄 摘要 (简体中文)"
                        else:
                            display_text = abstract
                            expander_label = "📄 摘要 (English)"

                        with st.expander(expander_label, expanded=False):
                            st.markdown(display_text[:3000])

                    # ── Tabs for detailed evaluations ──
                    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                        "📊 综合评分", "🏥 研究设计", "📈 统计方法", "⚖️ 偏倚与证据",
                        "🎯 相关性", "📋 PICO & 缺失信息"
                    ])

                    with tab1:
                        st.markdown("#### 综合质量评分明细")
                        weights = oa.get("weights_used", {})
                        st.markdown(f"**置信度:** {oa.get('confidence_in_appraisal', 'N/A')}")
                        st.caption(" | ".join(oa.get("confidence_reasons", [])))

                        comp_data = {
                            "评分维度": [
                                "期刊质量", "研究设计", "统计方法",
                                "PICO相关性", "偏倚风险", "报告质量"
                            ],
                            "得分": [
                                oa.get("journal_score") or "缺失",
                                oa.get("design_score", 0),
                                oa.get("statistics_score", 0),
                                oa.get("relevance_score", 0),
                                oa.get("risk_of_bias_score", 0),
                                oa.get("reporting_quality_score", 0),
                            ],
                            "权重": [
                                f"{weights.get('journal_score', 0)*100:.0f}%",
                                f"{weights.get('design_score', 0)*100:.0f}%",
                                f"{weights.get('statistics_score', 0)*100:.0f}%",
                                f"{weights.get('relevance_score', 0)*100:.0f}%",
                                f"{weights.get('risk_of_bias_score', 0)*100:.0f}%",
                                f"{weights.get('reporting_quality_score', 0)*100:.0f}%",
                            ],
                        }
                        st.dataframe(
                            pd.DataFrame(comp_data), use_container_width=True, hide_index=True
                        )
                        if oa.get("journal_note"):
                            st.warning(oa["journal_note"])

                    with tab2:
                        st.markdown(f"**研究类型:** {sde.get('study_type', 'N/A')}")
                        st.markdown(f"**识别置信度:** {sde.get('study_type_confidence', 0):.0%}")
                        st.markdown(f"**设计评分:** {sde.get('design_score', '?')}/10")

                        strengths = sde.get("design_strengths", [])
                        if strengths:
                            st.markdown("**优点:**")
                            for s in strengths:
                                st.markdown(f"- ✅ {s}")

                        limitations = sde.get("design_limitations", [])
                        if limitations:
                            st.markdown("**局限:**")
                            for l in limitations:
                                st.markdown(f"- ⚠️ {l}")

                        if sde.get("design_evaluation_notes"):
                            st.caption(sde["design_evaluation_notes"])

                    with tab3:
                        se = appraisal.get("statistics_evaluation", {})
                        st.markdown(f"**统计评分:** {se.get('statistics_score', '?')}/10")
                        st.markdown(f"**评价层级:** {se.get('statistics_review_level', 'N/A')}")

                        st.markdown("**检测到的统计方法:**")
                        tests = se.get("statistical_tests", [])
                        if tests:
                            st.markdown(", ".join(f"`{t}`" for t in tests))
                        else:
                            st.caption("未检测到具体统计检验方法")

                        stats_detail_col1, stats_detail_col2 = st.columns(2)
                        with stats_detail_col1:
                            st.markdown(f"**效应量:** {se.get('effect_size_type', '未报告')}")
                            st.markdown(f"**置信区间:** {se.get('confidence_interval_reported', '未报告')}")
                            st.markdown(f"**模型类型:** {se.get('model_type', '未识别')}")
                        with stats_detail_col2:
                            st.markdown(f"**样本量估算:** {se.get('sample_size_calculation', '未报告')}")
                            st.markdown(f"**多重比较校正:** {se.get('multiple_comparison_correction', '未报告')}")
                            st.markdown(f"**缺失数据处理:** {se.get('missing_data_handling', '未报告')}")

                        strengths = se.get("statistics_strengths", [])
                        if strengths:
                            st.markdown("**统计优点:**")
                            for s in strengths:
                                st.markdown(f"- {s}")

                        limitations = se.get("statistics_limitations", [])
                        if limitations:
                            st.markdown("**统计局限:**")
                            for l in limitations:
                                st.markdown(f"- {l}")

                        if se.get("mbi_warning"):
                            st.warning(f"⚠️ MBI 争议提醒: {se['mbi_warning']}")

                    with tab4:
                        st.markdown(f"**偏倚风险:** {be.get('risk_of_bias', 'N/A')}")
                        st.markdown(f"**评价工具:** {be.get('bias_tool', 'N/A')}")
                        st.markdown(f"**证据等级:** {be.get('evidence_level', 'N/A')}")

                        domains = be.get("risk_of_bias_domains", {})
                        if domains:
                            st.markdown("**偏倚领域评估:**")
                            for domain, judgment in domains.items():
                                j_icon = {"low": "🟢", "some_concerns": "🟡", "high": "🔴"}.get(
                                    judgment, "⚪"
                                )
                                st.markdown(f"- {j_icon} {domain}: {judgment}")

                        reasons = be.get("risk_of_bias_reasons", [])
                        if reasons:
                            st.markdown("**偏倚理由:**")
                            for r in reasons:
                                st.caption(f"• {r}")

                        ev_reasons = be.get("evidence_level_reasons", [])
                        if ev_reasons:
                            st.markdown("**证据等级理由:**")
                            for r in ev_reasons:
                                st.caption(f"• {r}")

                    with tab5:
                        # ── New strict relevance analysis ──
                        if isinstance(ra, dict) and ra:
                            st.markdown("### 🎯 严格标题/摘要相关性分析")
                            st.markdown(f"**最终相关性评分:** {ra.get('final_relevance_score', '?')}/10")
                            st.markdown(f"**相关性标签:** {ra.get('relevance_label', 'N/A').upper()}")
                            decision = ra.get("decision_reason", "")
                            if decision:
                                st.markdown(f"**决策理由:** {decision}")

                            st.markdown("---")
                            st.markdown("#### 分项评分")
                            score_cols = st.columns(5)
                            with score_cols[0]:
                                st.metric("标题相关性", f"{ra.get('title_relevance_score', '?')}/10")
                            with score_cols[1]:
                                st.metric("摘要相关性", f"{ra.get('abstract_relevance_score', '?')}/10")
                            with score_cols[2]:
                                st.metric("PICO覆盖", f"{ra.get('pico_coverage_score', '?')}/10")
                            with score_cols[3]:
                                st.metric("核心词覆盖", f"{ra.get('mandatory_coverage_score', '?.00')}")
                            with score_cols[4]:
                                penalty = ra.get("exclusion_penalty", 0)
                                st.metric("排除罚分", f"-{penalty}")

                            st.markdown("---")
                            st.markdown("#### 术语匹配详情")
                            matched = ra.get("matched_terms", {})
                            match_col1, match_col2 = st.columns(2)
                            with match_col1:
                                for dim_key, dim_cn in [
                                    ("population", "👥 人群"),
                                    ("intervention_or_exposure", "💊 干预/暴露"),
                                    ("comparator", "⚖️ 对照"),
                                ]:
                                    terms = matched.get(dim_key, [])
                                    st.markdown(f"{dim_cn}: {'✅ `' + '`, `'.join(terms) + '`' if terms else '❌ 未匹配'}")

                            with match_col2:
                                for dim_key, dim_cn in [
                                    ("outcomes", "📏 结局"),
                                    ("context", "🏟️ 上下文"),
                                ]:
                                    terms = matched.get(dim_key, [])
                                    st.markdown(f"{dim_cn}: {'✅ `' + '`, `'.join(terms) + '`' if terms else '❌ 未匹配'}")

                                missing = ra.get("missing_required_concepts", [])
                                if missing:
                                    st.markdown(f"🔴 **缺失核心词:** `{'`, `'.join(missing)}`")

                            excluded_found = ra.get("exclusion_terms_found", [])
                            if excluded_found:
                                st.warning(f"🚫 **发现排除词:** `{'`, `'.join(excluded_found)}`")

                        # ── Legacy relevance (compact) ──
                        st.markdown("---")
                        st.markdown("#### 📜 传统PICO相关性（向后兼容）")
                        st.markdown(f"**相关性评分:** {re.get('relevance_score', '?')}/10")
                        pico_match = re.get("pico_match", {})
                        if pico_match:
                            st.caption(f"人群: {pico_match.get('population_match', '')} | "
                                       f"干预: {pico_match.get('intervention_match', '')} | "
                                       f"对照: {pico_match.get('comparator_match', '')} | "
                                       f"结局: {pico_match.get('outcome_match', '')}")
                        if re.get("relevance_reason"):
                            st.caption(re["relevance_reason"])

                    with tab6:
                        pp = appraisal.get("pico_peco", {})
                        st.markdown(f"**P (人群):** {pp.get('population', 'N/A')}")
                        st.markdown(f"**I (干预/暴露):** {pp.get('intervention_or_exposure', 'N/A')}")
                        st.markdown(f"**C (对照):** {pp.get('comparator', 'N/A')}")
                        st.markdown(f"**O (结局):** {pp.get('outcomes', 'N/A')}")
                        st.markdown(f"**研究设计:** {pp.get('study_design', 'N/A')}")

                        missing = oa.get("missing_information", [])
                        if missing:
                            st.markdown("**缺失信息（需人工补充）:**")
                            for m in missing:
                                st.markdown(f"- 🔍 {m}")

                    # ── Bottom action buttons ──
                    st.markdown("---")
                    btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns(5)

                    # Generate journal club report
                    with btn_col1:
                        if st.button("📝 生成组会报告", key=f"jc_{paper_id}", use_container_width=True):
                            with st.spinner("生成组会报告..."):
                                try:
                                    # Find corresponding paper dict by paper_id
                                    paper = next(
                                        (p for p in papers if p.get("paper_id") == paper_id),
                                        papers[i] if i < len(papers) else {}
                                    )
                                    report_md = generate_jc_report(paper, appraisal, st.session_state.strict_topic)
                                    report_path = save_report(report_md, paper)
                                    if report_path:
                                        appraisal["journal_club_report_path"] = report_path
                                        st.success(f"报告已保存: {report_path}")
                                except Exception as e:
                                    st.error(f"报告生成失败: {e}")

                    # Import to library
                    with btn_col2:
                        if st.button("📥 加入文献库", key=f"import_{paper_id}", use_container_width=True):
                            paper = next(
                                (p for p in papers if p.get("paper_id") == paper_id),
                                papers[i] if i < len(papers) else {}
                            )
                            try:
                                import_result = import_to_library(appraisal, paper)
                                if import_result.get("success"):
                                    tag = "更新" if import_result.get("was_existing") else "新增"
                                    st.success(f"✅ 已{tag}纳入文献库: {import_result.get('title', '')[:80]}")
                                else:
                                    st.error("导入文献库失败")
                            except Exception as e:
                                st.error(f"导入失败: {e}")

                    # Export appraisal JSON
                    with btn_col3:
                        appraisal_json = json.dumps(appraisal, ensure_ascii=False, indent=2, default=str)
                        st.download_button(
                            "💾 导出评价JSON",
                            appraisal_json,
                            file_name=f"appraisal_{paper_id}.json",
                            mime="application/json",
                            use_container_width=True,
                        )

                    # Manual review marker
                    with btn_col4:
                        manual_note = st.text_input(
                            "人工复核备注", key=f"note_{paper_id}",
                            placeholder="添加复核备注…",
                            label_visibility="collapsed",
                        )

                    with btn_col5:
                        if st.button("🏷️ 标记人工复核", key=f"mark_{paper_id}", use_container_width=True):
                            st.info("人工复核标记功能 — 备注已记录（功能原型）")

                    # Show journal club report if it exists
                    report_path = appraisal.get("journal_club_report_path", "")
                    if report_path:
                        st.markdown(f"📄 **已有组会报告:** `{report_path}`")
                        if st.button("👁️ 查看报告", key=f"view_{paper_id}"):
                            try:
                                report_content = Path(report_path).read_text(encoding="utf-8")
                                with st.expander("📝 组会报告全文", expanded=True):
                                    st.markdown(report_content)
                            except Exception as e:
                                st.error(f"无法读取报告文件: {e}")

            # ── Excluded papers (collapsed) ──
            if excluded_papers:
                with st.expander(f"🚫 已排除结果 ({len(excluded_papers)} 篇) — 点击展开", expanded=False):
                    st.caption("以下文献因相关性低或含排除词被自动排除。可手动恢复。")
                    for j, excl in enumerate(excluded_papers):
                        excl_title = excl.get("title", "无标题")
                        excl_ra = excl.get("relevance_analysis", {})
                        excl_reason = excl_ra.get("decision_reason", "未知原因") if isinstance(excl_ra, dict) else ""
                        excl_score = excl_ra.get("final_relevance_score", "?") if isinstance(excl_ra, dict) else "?"
                        st.markdown(
                            f"**{j+1}.** *{excl_title[:120]}*  \n"
                            f"🔴 相关性: {excl_score}/10 — {excl_reason}"
                        )

            # ── Bottom: Batch actions ──
            if appraisals:
                st.markdown("---")
                st.markdown("### ⚡ 批量操作")
                batch_col1, batch_col2, batch_col3 = st.columns(3)

                # Batch import all "include" papers
                with batch_col1:
                    if st.button("📥 批量导入「建议纳入」文献", use_container_width=True):
                        imported_count = 0
                        for appr in appraisals:
                            rec = appr.get("overall_appraisal", {}).get("recommendation", "")
                            if rec == "include":
                                try:
                                    pid = appr.get("paper_id", "")
                                    paper = next((p for p in papers if p.get("paper_id") == pid), {})
                                    ir = import_to_library(appr, paper)
                                    if ir.get("success"):
                                        imported_count += 1
                                except Exception:
                                    pass
                        st.success(f"已导入 {imported_count} 篇文献到文献库")

                # Batch export all appraisals
                with batch_col2:
                    all_json = json.dumps(
                        {"session": session, "appraisals": appraisals},
                        ensure_ascii=False, indent=2, default=str,
                    )
                    st.download_button(
                        "💾 批量导出所有评价 (JSON)",
                        all_json,
                        file_name=f"strict_appraisals_{session.get('timestamp', 'export')}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                # Clear results
                with batch_col3:
                    if st.button("🗑️ 清除本次检索结果", use_container_width=True):
                        st.session_state.strict_results = None
                        st.session_state.strict_topic = ""
                        st.rerun()

# ═══════════════════════════════════════════════════════════
# Page 6: Academic Q&A
# ═══════════════════════════════════════════════════════════
elif page == "❓ Academic Q&A":
    st.markdown('<p class="main-header">❓ Academic Q&A — Evidence-Based Answers</p>', unsafe_allow_html=True)

    st.markdown("""
    Ask a research question. The agent will:
    1. Search the local literature database
    2. Retrieve relevant papers by quality level
    3. Generate an evidence-based response with citations
    """)

    question = st.text_area(
        "Your Research Question",
        placeholder="e.g., HIIT 对中老年人的 VO2max 改善是否优于中等强度持续训练？\n\n"
                    "e.g., Does creatine supplementation improve strength gains more in trained vs. untrained individuals?",
        height=100,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        top_k = st.slider("Max papers to retrieve", 3, 20, 10)
    with col2:
        model_choice = st.selectbox("LLM (if API key set)", ["local (template)", "claude", "openai"])
    with col3:
        if st.button("🔬 Answer Question", type="primary", use_container_width=True):
            if not question:
                st.warning("Please enter a research question.")
            else:
                with st.spinner("Retrieving evidence and generating response..."):
                    model = model_choice.split()[0]
                    result = answer_question(question, top_k=top_k, model=model)

                st.markdown("---")
                st.markdown(result["response"])

                # Show PICO decomposition
                with st.expander("🔬 PICO Decomposition", expanded=False):
                    st.json(result["pico"])

                # Show retrieved papers
                with st.expander(f"📚 Retrieved Papers ({result['retrieved_count']})", expanded=False):
                    for i, p in enumerate(result.get("retrieved_papers", [])):
                        st.markdown(f"**{i+1}. {p.get('title', 'Untitled')}**")
                        st.caption(f"Quality: {p.get('quality_score', '?')}/10 | "
                                   f"Evidence: {p.get('evidence_level', '?')} | "
                                   f"Year: {p.get('year', '?')} | "
                                   f"Type: {p.get('study_type', '?')}")

                # Show references
                with st.expander("📖 References", expanded=False):
                    papers = result.get("retrieved_papers", [])
                    if papers:
                        refs = format_reference_list(papers, style="apa")
                        st.markdown(refs)
                    else:
                        st.info("No references available.")

    # Example questions
    st.markdown("---")
    st.caption("Example questions you can ask:")
    examples = [
        "What is the effect of high-intensity interval training on VO2max in older adults?",
        "Does protein supplementation timing affect muscle hypertrophy outcomes?",
        "What are the risk factors for ACL injury recurrence in female athletes?",
        "HIIT 与中等强度持续训练对心肺适能改善的比较研究",
        "肌酸补充对爆发力运动员表现的 Meta 分析证据",
    ]
    for ex in examples:
        st.caption(f"• {ex}")

# ═══════════════════════════════════════════════════════════
# Page 6: Academic Writing
# ═══════════════════════════════════════════════════════════
elif page == "✍️ Academic Writing":
    st.markdown('<p class="main-header">✍️ Academic Writing — Publication-Ready Content</p>', unsafe_allow_html=True)

    st.markdown("Generate academic writing sections based on your research question and the local literature database.")

    writing_question = st.text_area(
        "Research Topic / Question",
        placeholder="e.g., The effect of blood flow restriction training on muscle hypertrophy and strength in...",
        height=80,
    )

    section_type = st.selectbox(
        "Section to Generate",
        [
            "introduction",
            "literature_review",
            "methods_draft",
            "discussion",
            "research_gap",
            "hypothesis",
            "abstract",
            "statistical_plan",
            "cover_letter",
            "response_to_reviewers",
        ],
        format_func=lambda x: {
            "introduction": "Introduction",
            "literature_review": "Literature Review",
            "methods_draft": "Methods (Systematic Review / Meta-Analysis)",
            "discussion": "Discussion",
            "research_gap": "Research Gap Analysis",
            "hypothesis": "Research Hypotheses",
            "abstract": "Abstract",
            "statistical_plan": "Statistical Analysis Plan",
            "cover_letter": "Cover Letter",
            "response_to_reviewers": "Response to Reviewers Template",
        }.get(x, x),
    )

    citation_style = st.selectbox("Citation Style", ["apa", "vancouver", "ama", "gbt7714"])

    if st.button("✍️ Generate", type="primary", use_container_width=True):
        if not writing_question:
            st.warning("Please enter a research topic/question.")
        else:
            with st.spinner("Generating academic content..."):
                # Get relevant papers
                papers = search_papers(keyword=writing_question[:200])
                content = generate_section(section_type, writing_question, papers)

            st.markdown("---")
            st.markdown(content)

            # Copy button
            st.markdown("---")
            st.download_button(
                "📥 Download as Markdown",
                content,
                file_name=f"{section_type}_{writing_question[:30]}.md",
                mime="text/markdown",
            )

            # Show which papers were used
            if papers:
                with st.expander(f"Based on {len(papers)} papers from library", expanded=False):
                    refs = format_reference_list(papers[:20], style=citation_style)
                    st.markdown(refs)

# ═══════════════════════════════════════════════════════════
# Page 7: Evidence Map
# ═══════════════════════════════════════════════════════════
elif page == "📈 Evidence Map":
    st.markdown('<p class="main-header">📈 Evidence Map</p>', unsafe_allow_html=True)

    papers = load_papers()
    if not papers:
        st.info("No papers in the library. Import literature to build an evidence map.")
    else:
        evidence_map = build_evidence_map(papers)

        # Summary table
        rows = []
        for domain, types in evidence_map.items():
            for stype, info in types.items():
                rows.append({
                    "Domain": domain,
                    "Study Type": stype.replace("_", " ").title(),
                    "Count": info["count"],
                    "Avg Quality": round(sum(
                        float(p.get("quality_score", 0) or 0) for p in info["papers"]
                    ) / max(info["count"], 1), 1),
                    "Papers": ", ".join(
                        f"{p.get('authors', '?').split(';')[0] if p.get('authors') else '?'} ({p.get('year', '?')})"
                        for p in info["papers"][:3]
                    ),
                })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Heatmap
            st.subheader("Evidence Density Heatmap")
            pivot = df.pivot_table(
                values="Count", index="Domain", columns="Study Type",
                aggfunc="sum", fill_value=0
            )
            st.dataframe(pivot, use_container_width=True)
        else:
            st.info("No structured evidence map data available yet.")

        # Export
        st.download_button(
            "📥 Download Evidence Map (CSV)",
            pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
            "evidence_map.csv",
            "text/csv",
        )

# ═══════════════════════════════════════════════════════════
# Footer
# ═══════════════════════════════════════════════════════════
st.sidebar.markdown("---")
st.sidebar.caption("Sports Science Research Agent v1.0")
st.sidebar.caption("独立项目 — 不影响 localhost:8501")
st.sidebar.caption("运行端口: 8502")
