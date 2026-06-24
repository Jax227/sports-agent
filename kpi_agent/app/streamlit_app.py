"""
KPI Agent — 交互式前端
======================
基于 Streamlit 的全功能 UI，连接 FastAPI 后端数据库。
不显示任何原始 JSON，所有操作通过表单、表格和图表完成。
"""

import sys
from pathlib import Path

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime

from app.database import SessionLocal, Base, engine
from app import crud
from app import models

# ── Page config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="KPI Intelligence Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB session ──────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        return None

# Ensure tables exist
Base.metadata.create_all(bind=engine)


# ═══════════════════════════════════════════════════════════════════
#  Sidebar
# ═══════════════════════════════════════════════════════════════════

st.sidebar.title("🎯 KPI Intelligence Agent")
st.sidebar.caption("竞技体育表现智能系统")

# Pick project
db = get_db()
projects = crud.get_projects(db) if db else []
project_names = {p.name: p.id for p in projects}
project_names["➕ 创建新项目"] = -1

selected_name = st.sidebar.selectbox(
    "选择项目",
    list(project_names.keys()),
    index=0 if project_names else 0,
)
project_id = project_names.get(selected_name, -1)

st.sidebar.divider()

# Navigation
page = st.sidebar.radio(
    "导航",
    [
        "📊 项目总览",
        "🎯 表现目标 PO",
        "🌳 表现模型",
        "📈 KPI 管理",
        "🏃 运动员评估",
        "📋 干预计划",
        "📚 证据资料库",
        "📝 报告中心",
        "🤖 Agent 工作流",
        "🔬 免费文献检索增强版",
        "🧬 文献→表现模型",
    ],
)

st.sidebar.divider()
if project_id > 0:
    project = crud.get_project(db, project_id)
    if project:
        st.sidebar.markdown(f"**当前项目**: {project.name}")
        st.sidebar.markdown(f"运动: {project.sport_type}")
        st.sidebar.markdown(f"类型: {project.project_type} | 水平: {project.level}")
else:
    st.sidebar.warning("请先创建或选择一个项目")

st.sidebar.caption("v0.1.0 | MVP Phase 1")

# ── Database backup/restore (critical for Streamlit Cloud ephemeral storage) ──
with st.sidebar.expander("💾 数据库备份/恢复", expanded=False):
    from app.database import DATABASE_URL, IS_SQLITE
    if IS_SQLITE:
        # Parse the SQLite path from the URL
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if not Path(db_path).is_absolute():
            db_path = str(Path(__file__).resolve().parent.parent / db_path)
        if Path(db_path).exists():
            st.caption(f"SQLite: {Path(db_path).name} ({Path(db_path).stat().st_size / 1024:.0f} KB)")
            with open(db_path, "rb") as f:
                st.download_button("⬇ 下载数据库备份", f.read(),
                                   f"kpi_agent_backup_{Path(db_path).stat().st_mtime:.0f}.db",
                                   "application/octet-stream")
        # Literature cache backup
        lit_cache = Path(__file__).resolve().parent.parent / "literature_cache.db"
        if lit_cache.exists():
            st.caption(f"文献缓存: {lit_cache.name} ({lit_cache.stat().st_size / 1024:.0f} KB)")
        # Restore
        uploaded = st.file_uploader("⬆ 恢复数据库", type=["db"], key="db_restore",
                                     help="上传之前下载的 .db 备份文件以恢复数据",
                                     label_visibility="collapsed")
        if uploaded:
            restore_path = Path(db_path)
            restore_path.write_bytes(uploaded.read())
            st.success("数据库已恢复！请刷新页面。")
            st.button("🔄 刷新", on_click=lambda: st.rerun())
    else:
        st.caption("PostgreSQL 模式 — 数据自动持久化")

db.close()


# ═══════════════════════════════════════════════════════════════════
#  Utility functions
# ═══════════════════════════════════════════════════════════════════

def get_fresh_db():
    return SessionLocal()


def metric_card(label, value, delta=None, help_text=None):
    """Render a styled metric card."""
    st.metric(label=label, value=value, delta=delta, help=help_text)


def evidence_badge(level):
    """Colored badge for evidence level."""
    colors = {"高": "green", "中": "blue", "低": "orange", "专家经验": "violet", "未知": "gray"}
    return f":{colors.get(level, 'gray')}[{level}]"


def importance_icon(imp):
    icons = {"关键": "🔴", "重要": "🟡", "中等": "🟢", "基本": "⚪"}
    return icons.get(imp, "⚪") + " " + imp


# ═══════════════════════════════════════════════════════════════════
#  Page: 项目总览
# ═══════════════════════════════════════════════════════════════════

def page_dashboard():
    st.title("📊 项目总览")

    if project_id <= 0:
        st.info("👈 请先在左侧选择一个项目，或创建新项目。")
        return

    db2 = get_fresh_db()
    try:
        project = crud.get_project(db2, project_id)
        outcomes = crud.get_outcomes(db2, project_id)
        kpis = crud.get_kpis(db2, project_id)
        athletes = crud.get_athletes(db2, project_id)
        determinants = crud.get_determinants(db2, project_id)
        interventions = crud.get_interventions(db2, project_id)
        sources = crud.get_evidence_sources(db2, project_id)
        reports = crud.get_reports(db2, project_id)

        # Top metrics row
        cols = st.columns(6)
        with cols[0]:
            metric_card("表现目标", len(outcomes))
        with cols[1]:
            metric_card("KPI 指标", len(kpis))
        with cols[2]:
            metric_card("运动员", len(athletes))
        with cols[3]:
            metric_card("决定因素", len(determinants))
        with cols[4]:
            metric_card("干预措施", len(interventions))
        with cols[5]:
            metric_card("证据来源", len(sources))

        st.divider()

        # Two-column layout
        left, right = st.columns(2)

        with left:
            st.subheader("🎯 表现目标")
            if outcomes:
                for o in outcomes:
                    status_icon = "✅" if o.status == "active" else "🔒"
                    with st.expander(f"{status_icon} {o.name}", expanded=False):
                        st.write(f"**类型**: {o.outcome_type}")
                        st.write(f"**目标值**: {o.target_value} {o.unit}" if o.target_value else "目标值未设定")
                        st.write(f"**基线值**: {o.baseline_value} {o.unit}" if o.baseline_value else "基线值未设定")
                        if o.target_date:
                            st.write(f"**目标日期**: {o.target_date.strftime('%Y-%m-%d')}")
            else:
                st.warning("暂无表现目标")

            st.subheader("🏃 运动员")
            if athletes:
                for a in athletes:
                    with st.expander(f"{a.name} — {a.level}", expanded=False):
                        st.write(f"年龄: {a.age} | 训练年限: {a.training_age}年")
                        st.write(f"身高: {a.height}cm | 体重: {a.weight}kg")
                        if a.injury_history:
                            st.write(f"伤病: {a.injury_history}")
            else:
                st.warning("暂无运动员")

        with right:
            st.subheader("📈 数据完整度")
            completeness_items = {
                "表现目标": len(outcomes) > 0,
                "KPI 指标": len(kpis) > 0,
                "运动员": len(athletes) > 0,
                "表现决定因素": len(determinants) > 0,
                "干预措施": len(interventions) > 0,
                "证据来源": len(sources) > 0,
                "比赛数据": False,
                "报告": len(reports) > 0,
            }
            complete_count = sum(completeness_items.values())
            total = len(completeness_items)

            fig = go.Figure(go.Bar(
                x=list(completeness_items.values()),
                y=list(completeness_items.keys()),
                orientation='h',
                marker_color=['#2ecc71' if v else '#e74c3c' for v in completeness_items.values()],
                text=['✅' if v else '❌' for v in completeness_items.values()],
                textposition='outside',
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(showticklabels=False, showgrid=False, range=[0, 1.5]),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"整体完成度: {complete_count}/{total}")

            st.subheader("🔔 风险提示")
            # Check for missing critical items
            if not outcomes:
                st.warning("⚠️ 未定义表现目标 — 这是所有 KPI 的基础")
            if not kpis:
                st.warning("⚠️ 未定义 KPI — 无法追踪表现")
            if not sources:
                st.info("💡 建议添加证据来源以提高 KPI 可信度")
            if not determinants:
                st.info("💡 建议建立表现模型以系统化 KPI")
            if len(kpis) > 0:
                low_evidence = [k for k in kpis if k.evidence_level in ("低", "未知")]
                if low_evidence:
                    st.warning(f"⚠️ {len(low_evidence)} 个 KPI 证据等级较低")

    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: 表现目标 PO
# ═══════════════════════════════════════════════════════════════════

def page_outcomes():
    st.title("🎯 表现目标 (Performance Outcomes)")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        outcomes = crud.get_outcomes(db2, project_id)

        # ── Create new PO ───────────────────────────────────────
        with st.expander("➕ 创建新表现目标", expanded=len(outcomes) == 0):
            col1, col2 = st.columns(2)
            with col1:
                po_name = st.text_input("目标名称", placeholder="例如：800m 成绩达到 1:48.00", key="po_c_name")
                po_type = st.selectbox("目标类型", ["成绩", "排名", "奖牌", "胜率", "选拔资格", "技术得分", "团队角色", "其他"], key="po_c_type")
            with col2:
                po_target = st.number_input("目标值", value=0.0, step=0.1, key="po_c_target")
                po_unit = st.text_input("单位", placeholder="s / m / 排名 / %", key="po_c_unit")
                po_baseline = st.number_input("当前基线值", value=0.0, step=0.1, key="po_c_base")
            po_desc = st.text_area("详细描述", key="po_c_desc")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                po_date = st.date_input("目标日期", value=None, key="po_c_date")
            with col_d2:
                po_priority = st.slider("优先级", 1, 5, 3, key="po_c_pri")

            if st.button("保存表现目标", type="primary", key="po_c_save"):
                if po_name:
                    from datetime import datetime as dt
                    target_dt = dt.combine(po_date, dt.min.time()) if po_date else None
                    crud.create_outcome(db2, project_id, {
                        "name": po_name,
                        "description": po_desc,
                        "outcome_type": po_type,
                        "target_value": po_target if po_target > 0 else None,
                        "unit": po_unit,
                        "baseline_value": po_baseline if po_baseline > 0 else None,
                        "current_value": po_baseline if po_baseline > 0 else None,
                        "target_date": target_dt,
                        "priority": po_priority,
                    })
                    st.rerun()
                else:
                    st.error("请输入目标名称")

        st.divider()

        # ── Existing POs ────────────────────────────────────────
        if not outcomes:
            st.info("还没有定义表现目标。点击上方展开表单创建第一个 PO。")
            return

        st.subheader(f"已有目标 ({len(outcomes)} 个)")

        for o in outcomes:
            gap = None
            if o.current_value and o.target_value:
                gap_pct = round((o.target_value - o.current_value) / o.current_value * 100, 1)
                gap = f"差距 {gap_pct}%"

            # ── Read mode (default) ─────────────────────────────
            edit_key = f"po_edit_{o.id}"
            if st.session_state.get(edit_key) != o.id:
                cols = st.columns([3, 1, 1, 1, 1, 0.5])
                with cols[0]:
                    st.markdown(f"### {o.name}")
                    st.caption(o.description if o.description else "无详细描述")
                with cols[1]:
                    st.metric("目标值", f"{o.target_value} {o.unit}" if o.target_value else "未设定")
                with cols[2]:
                    st.metric("当前值", f"{o.current_value} {o.unit}" if o.current_value else "未设定", delta=gap)
                with cols[3]:
                    st.write(f"**类型**: {o.outcome_type}")
                    st.write(f"**优先级**: {'⭐' * o.priority}")
                with cols[4]:
                    if o.target_date:
                        st.write(f"**日期**: {o.target_date.strftime('%Y-%m-%d')}")
                    st.write(f"**状态**: {'✅ 进行中' if o.status == 'active' else '🔒 ' + o.status}")
                with cols[5]:
                    if st.button("✏️", key=f"po_ebtn_{o.id}", help="编辑"):
                        st.session_state[edit_key] = o.id
                        st.rerun()

                # Quick update current value
                quick_cols = st.columns([2, 1, 1, 6])
                with quick_cols[0]:
                    new_val = st.number_input(
                        "更新当前值", value=o.current_value or 0.0, step=0.1,
                        key=f"po_qv_{o.id}", label_visibility="collapsed",
                    )
                with quick_cols[1]:
                    if st.button("📝 更新", key=f"po_qu_{o.id}"):
                        crud.update_outcome(db2, o.id, {"current_value": new_val if new_val > 0 else None})
                        st.rerun()
                with quick_cols[2]:
                    new_status = st.selectbox(
                        "状态", ["active", "completed", "on_hold", "cancelled"],
                        index=["active", "completed", "on_hold", "cancelled"].index(o.status) if o.status in ["active", "completed", "on_hold", "cancelled"] else 0,
                        key=f"po_qs_{o.id}", label_visibility="collapsed",
                    )
                    if st.button("🔄 改状态", key=f"po_qst_{o.id}"):
                        crud.update_outcome(db2, o.id, {"status": new_status})
                        st.rerun()

            # ── Edit mode ───────────────────────────────────────
            else:
                st.markdown(f"### ✏️ 编辑: {o.name}")
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_name = st.text_input("目标名称", value=o.name, key=f"po_e_name_{o.id}")
                    e_type = st.selectbox("目标类型", ["成绩", "排名", "奖牌", "胜率", "选拔资格", "技术得分", "团队角色", "其他"],
                                          index=["成绩", "排名", "奖牌", "胜率", "选拔资格", "技术得分", "团队角色", "其他"].index(o.outcome_type) if o.outcome_type in ["成绩", "排名", "奖牌", "胜率", "选拔资格", "技术得分", "团队角色", "其他"] else 0,
                                          key=f"po_e_type_{o.id}")
                    e_priority = st.slider("优先级", 1, 5, o.priority or 3, key=f"po_e_pri_{o.id}")
                with ec2:
                    e_target = st.number_input("目标值", value=o.target_value or 0.0, step=0.1, key=f"po_e_target_{o.id}")
                    e_unit = st.text_input("单位", value=o.unit or "", key=f"po_e_unit_{o.id}")
                    e_current = st.number_input("当前值", value=o.current_value or 0.0, step=0.1, key=f"po_e_current_{o.id}")
                e_desc = st.text_area("详细描述", value=o.description or "", key=f"po_e_desc_{o.id}")
                ed1, ed2, ed3 = st.columns(3)
                with ed1:
                    e_date = st.date_input("目标日期", value=o.target_date, key=f"po_e_date_{o.id}")
                with ed2:
                    e_status = st.selectbox("状态", ["active", "completed", "on_hold", "cancelled"],
                                            index=["active", "completed", "on_hold", "cancelled"].index(o.status) if o.status in ["active", "completed", "on_hold", "cancelled"] else 0,
                                            key=f"po_e_status_{o.id}")
                with ed3:
                    e_evidence = st.text_input("证据说明", value=o.evidence_notes or "", key=f"po_e_ev_{o.id}")

                btn_cols = st.columns([1, 1, 4])
                with btn_cols[0]:
                    if st.button("💾 保存修改", type="primary", key=f"po_e_save_{o.id}"):
                        from datetime import datetime as dt
                        target_dt = dt.combine(e_date, dt.min.time()) if e_date else None
                        crud.update_outcome(db2, o.id, {
                            "name": e_name,
                            "description": e_desc,
                            "outcome_type": e_type,
                            "target_value": e_target if e_target > 0 else None,
                            "unit": e_unit,
                            "current_value": e_current if e_current > 0 else None,
                            "target_date": target_dt,
                            "priority": e_priority,
                            "status": e_status,
                            "evidence_notes": e_evidence,
                        })
                        st.session_state[edit_key] = None
                        st.rerun()
                with btn_cols[1]:
                    if st.button("❌ 取消", key=f"po_e_cancel_{o.id}"):
                        st.session_state[edit_key] = None
                        st.rerun()
                with btn_cols[2]:
                    if st.button("🗑️ 删除此目标", key=f"po_e_del_{o.id}", type="secondary"):
                        crud.delete_outcome(db2, o.id)
                        st.session_state[edit_key] = None
                        st.rerun()

            # ── Associated KPIs ─────────────────────────────────
            related_kpis = [k for k in crud.get_kpis(db2, project_id) if k.performance_outcome_id == o.id]
            if related_kpis:
                with st.expander(f"关联 KPI ({len(related_kpis)})"):
                    kpi_df = pd.DataFrame([{
                        "KPI": k.name, "单位": k.unit, "目标值": k.target_value,
                        "当前值": k.current_value, "证据等级": k.evidence_level,
                    } for k in related_kpis])
                    st.dataframe(kpi_df, use_container_width=True, hide_index=True)

            st.divider()

    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: 表现模型
# ═══════════════════════════════════════════════════════════════════

def page_model():
    st.title("🌳 表现模型")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        project = crud.get_project(db2, project_id)
        determinants = crud.get_determinants(db2, project_id)
        tree = crud.get_determinant_tree(db2, project_id)

        st.caption(f"项目: {project.sport_type} | {len(determinants)} 个决定因素")

        # Evidence search — always available
        if not determinants:
            tab_tpl, ev_container = st.tabs(["📋 内置模板", "🔬 文献检索生成"])

            with tab_tpl:
                st.caption("使用内置的运动项目模板快速建立表现模型。")
                from app.agent.performance_model import build_determinants_from_template, build_interventions_from_template
                if st.button("📥 从内置模板生成表现模型", type="primary", key="pm_btn_tpl"):
                    build_determinants_from_template(db2, project_id, project.sport_type)
                    build_interventions_from_template(db2, project_id, project.sport_type)
                    db2.commit()
                    st.rerun()
        else:
            ev_container = st.expander(
                "🔬 文献检索（重新检索/补充）",
                expanded=st.session_state.get("evidence_model_ready", False),
            )

        with ev_container:
            st.caption("通过 PubMed 文献检索自动提取表现决定因素、KPI 和干预措施。")
            col_ev1, col_ev2 = st.columns(2)
            with col_ev1:
                sport_ev = st.text_input("运动项目", value=project.sport_type,
                                        help="运动项目名称，中英文均可", key="pm_ev_sport")
            with col_ev2:
                sport_ev_en = st.text_input("英文名称 (可选)", placeholder="如：800m / basketball",
                                           key="pm_ev_sport_en")
            col_ev3, col_ev4 = st.columns(2)
            with col_ev3:
                ev_llm = st.checkbox("使用 LLM 提取", value=True, key="pm_ev_llm")
            with col_ev4:
                ev_max = st.slider("检索论文数", 3, 15, 8, key="pm_ev_max")

            if st.button("🔬 从文献检索生成", type="primary", key="pm_btn_evidence"):
                with st.spinner("正在检索文献并提取表现模型..."):
                    from app.agent.evidence_model_generator import generate_model
                    model = generate_model(
                        sport_name=sport_ev,
                        sport_name_en=sport_ev_en,
                        use_llm=ev_llm,
                        max_results_per_query=ev_max,
                    )
                    st.session_state["evidence_model"] = model
                    st.session_state["evidence_model_ready"] = True
                    st.rerun()

            # Show generated model for review
            if st.session_state.get("evidence_model_ready") and st.session_state.get("evidence_model"):
                model = st.session_state["evidence_model"]
                st.divider()
                st.subheader("📋 文献检索结果 — 请审核后保存")
                ss = model.get("search_summary", {})
                st.caption(f"提取方式: {'LLM 智能提取' if model.get('extraction_method') == 'llm' else '关键词匹配'} | "
                           f"综述: {ss.get('narrative_review_count', 0)} 篇 | 体能测试: {ss.get('fitness_test_count', 0)} 篇 | "
                           f"元分析: {ss.get('meta_analysis_count', 0)} 篇")

                # Translation note
                translation_note = model.get("translation_note", "")
                if translation_note:
                    if translation_note.startswith("⚠️"):
                        st.warning(translation_note)
                    else:
                        st.success(translation_note)
                resolved = model.get("sport_name_resolved", [])
                if resolved:
                    st.caption(f"PubMed 检索词: {'; '.join(resolved)}")

                st.info(model.get("model_summary", ""))

                # ── Evidence sources with contribution tracking ──
                all_evidence = model.get("evidence_sources", [])
                paper_map = model.get("paper_determinant_map", [])
                total_papers = len(all_evidence)
                contributed_papers = [p for p in paper_map if p.get("match_count", 0) > 0]
                no_match_papers = [p for p in paper_map if p.get("match_count", 0) == 0]

                with st.expander(f"📚 检索文献 ({total_papers} 篇，{len(contributed_papers)} 篇匹配到决定因素)"):
                    if contributed_papers:
                        st.markdown("**✅ 匹配到的文献:**")
                        for i, p in enumerate(contributed_papers):
                            matched = p.get("matched_determinants", [])
                            det_labels = ", ".join(d["determinant"] for d in matched)
                            st.markdown(f"**{i+1}.** [{p.get('year', '')}] {p.get('title', '')}")
                            st.caption(f"   匹配因素: {det_labels}")
                    if no_match_papers:
                        st.markdown("**⚠️ 未匹配的文献:**")
                        st.caption("以下文献的研究主题与决定因素关键词匹配度不足，可能涉及特定测试方法或人群。")
                        for i, p in enumerate(no_match_papers):
                            st.markdown(f"**{i+1}.** [{p.get('year', '')}] {p.get('title', '')}")

                # ── Empty categories explanation ──
                empty_cats = model.get("empty_categories", [])
                if empty_cats:
                    with st.expander("🔍 未提取到因素的类别及原因"):
                        for ec in empty_cats:
                            st.markdown(f"**{ec['category']}**: {ec['reason']}")
                            if ec.get("found_hints"):
                                st.caption(f"文献相关概念: {', '.join(ec['found_hints'])}")

                # ── Review categories ──
                selected_dets = []
                selected_kpis = []
                selected_intvs = []

                for cat_name, cat_data in model.get("categories", {}).items():
                    dets = cat_data.get("determinants", [])
                    if not dets:
                        continue
                    with st.expander(f"**{cat_name}** — {cat_data.get('importance', '')} ({len(dets)} 个因素)"):
                        for det in dets:
                            mentioning_papers = []
                            for p in paper_map:
                                for md in p.get("matched_determinants", []):
                                    if md.get("determinant") == det.get("name"):
                                        mentioning_papers.append(f"[{p.get('year', '')}] {p.get('title', '')[:60]}")
                                        break
                            det_key = f"pm_det_{cat_name}_{det['name']}"
                            if st.checkbox(f"{det['name']} — {det.get('description', '')[:80]}",
                                           value=True, key=det_key):
                                selected_dets.append({**det, "category": cat_name})
                            st.caption(f"  证据: {det.get('evidence_level', '')} | 重要性: {det.get('importance', '')}")
                            if mentioning_papers:
                                st.caption(f"  来源: {mentioning_papers[0]}")

                kpis = model.get("kpis", [])
                if kpis:
                    with st.expander(f"📈 建议 KPI ({len(kpis)} 个)"):
                        for kpi in kpis:
                            kpi_key = f"pm_kpi_{kpi['name']}_{kpi.get('determinant', '')}"
                            if st.checkbox(f"**{kpi['name']}** ({kpi.get('unit', '')}) — {kpi.get('determinant', '')}",
                                           value=True, key=kpi_key):
                                selected_kpis.append(kpi)
                            st.caption(f"  测试: {kpi.get('protocol', '')} | 频率: {kpi.get('frequency', '')}")

                interventions = model.get("interventions", [])
                if interventions:
                    with st.expander(f"📋 建议干预 ({len(interventions)} 个)"):
                        for intv in interventions:
                            intv_key = f"pm_intv_{intv['name']}"
                            if st.checkbox(f"**{intv['name']}** [{intv.get('type', '')}] → {intv.get('target_determinant', '')}",
                                           value=True, key=intv_key):
                                selected_intvs.append(intv)
                            st.caption(f"  {intv.get('description', '')[:120]}")

                st.divider()
                col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
                with col_s1:
                    st.markdown(f"已选: {len(selected_dets)} 因素, {len(selected_kpis)} KPI, {len(selected_intvs)} 干预")
                with col_s2:
                    if st.button("💾 保存到项目", type="primary", key="pm_btn_save"):
                        from app.agent.evidence_model_generator import save_model_to_db
                        result = save_model_to_db(db2, project_id, model,
                                                  selected_determinants=selected_dets,
                                                  selected_kpis=selected_kpis,
                                                  selected_interventions=selected_intvs)
                        db2.commit()
                        st.success(f"已保存！因素: {result['determinants_created']}, KPI: {result['kpis_created']}, "
                                   f"干预: {result['interventions_created']}, 证据: {result['evidence_sources_created']}")
                        st.rerun()
                with col_s3:
                    if st.button("🗑️ 清除检索", key="pm_btn_clear_evidence"):
                        st.session_state["evidence_model_ready"] = False
                        st.session_state.pop("evidence_model", None)
                        st.rerun()

        # Add manual determinant
        with st.expander("➕ 手动添加决定因素"):
            c1, c2 = st.columns(2)
            with c1:
                det_name = st.text_input("因素名称", key="det_name")
                det_cat = st.selectbox("分类", ["生理要求", "技术要求", "战术要求", "营养要求", "心理技能", "器材特点", "健康", "比赛规则", "其他"], key="det_cat")
            with c2:
                det_parent = st.selectbox("上级因素（可选）", ["(无)"] + [d.name for d in determinants], key="det_parent")
                det_importance = st.selectbox("重要性", ["关键", "重要", "中等", "基本"], key="det_imp")
            det_desc = st.text_area("描述", key="det_desc")
            det_evidence = st.selectbox("证据等级", ["高", "中", "低", "专家经验", "未知"], key="det_ev")

            if st.button("保存决定因素"):
                if det_name:
                    parent_id = None
                    if det_parent != "(无)":
                        for d in determinants:
                            if d.name == det_parent:
                                parent_id = d.id
                                break
                    crud.create_determinant(db2, project_id, {
                        "name": det_name,
                        "category": det_cat,
                        "parent_id": parent_id,
                        "description": det_desc,
                        "importance": det_importance,
                        "evidence_level": det_evidence,
                    })
                    st.rerun()

        st.divider()

        # Tree visualization
        if tree:
            st.subheader("决定因素层级结构")

            # Flatten tree for display
            def render_tree(nodes, depth=0):
                for node in nodes:
                    prefix = " " * depth + ("├─ " if depth > 0 else "")
                    icon = {"生理要求": "🫀", "技术要求": "⚡", "战术要求": "🧠", "营养要求": "🍎",
                            "心理技能": "💪", "器材特点": "🔧", "健康": "🏥", "比赛规则": "📋"}.get(node.get("category", ""), "📌")
                    with st.expander(f"{prefix}{icon} {node['name']}  |  {node.get('kpi_count', 0)} KPI  |  {node.get('intervention_count', 0)} 干预", expanded=depth < 2):
                        st.caption(f"分类: {node.get('category', '')}")
                        if node.get("children"):
                            render_tree(node["children"], depth + 1)
                    if depth == 0 and not node.get("children"):
                        st.write("")

            render_tree(tree)

            # Category summary
            st.divider()
            st.subheader("分类汇总")
            cat_counts = {}
            for d in determinants:
                cat_counts[d.category] = cat_counts.get(d.category, 0) + 1
            cat_df = pd.DataFrame([{"分类": k, "因素数量": v} for k, v in cat_counts.items()])
            st.dataframe(cat_df, use_container_width=True, hide_index=True)
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: KPI 管理
# ═══════════════════════════════════════════════════════════════════

def page_kpis():
    st.title("📈 KPI 管理")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        kpis = crud.get_kpis(db2, project_id)
        determinants = crud.get_determinants(db2, project_id)
        det_map = {d.id: d.name for d in determinants}

        # Filter bar
        col1, col2, col3 = st.columns(3)
        with col1:
            cat_filter = st.selectbox("分类筛选", ["全部"] + sorted(list(set(k.category for k in kpis))))
        with col2:
            ev_filter = st.selectbox("证据等级", ["全部", "高", "中", "低", "专家经验", "未知"])
        with col3:
            quality_filter = st.selectbox("数据质量", ["全部", "high", "medium", "low"])

        # Generate KPIs from template
        if not kpis:
            from app.agent.kpi_generator import generate_kpis_for_determinants
            if st.button("📥 从内置模板生成 KPI", type="primary"):
                if determinants:
                    generate_kpis_for_determinants(db2, project_id, crud.get_project(db2, project_id).sport_type)
                    db2.commit()
                    st.rerun()
                else:
                    st.warning("请先生成表现模型")

        # Add KPI manually
        with st.expander("➕ 手动添加 KPI"):
            cc1, cc2 = st.columns(2)
            with cc1:
                kpi_name = st.text_input("KPI 名称", key="kpi_name")
                kpi_cat = st.text_input("分类", key="kpi_cat")
                kpi_unit = st.text_input("单位", key="kpi_unit")
                kpi_target = st.number_input("目标值", value=0.0, step=0.1, key="kpi_target")
            with cc2:
                kpi_det = st.selectbox("关联决定因素", ["(无)"] + [d.name for d in determinants], key="kpi_det")
                kpi_freq = st.text_input("测量频率", placeholder="每周 / 每月", key="kpi_freq")
                kpi_source = st.text_input("数据来源", placeholder="实验室测试 / 可穿戴设备", key="kpi_src")
                kpi_evidence = st.selectbox("证据等级", ["高", "中", "低", "专家经验", "未知"], key="kpi_ev")
            kpi_def = st.text_area("定义和计算方法", key="kpi_def")

            if st.button("保存 KPI"):
                if kpi_name:
                    det_id = None
                    if kpi_det != "(无)":
                        for d in determinants:
                            if d.name == kpi_det:
                                det_id = d.id
                                break
                    crud.create_kpi(db2, project_id, {
                        "name": kpi_name, "category": kpi_cat, "unit": kpi_unit,
                        "target_value": kpi_target if kpi_target > 0 else None,
                        "determinant_id": det_id,
                        "measurement_frequency": kpi_freq, "data_source": kpi_source,
                        "definition": kpi_def, "evidence_level": kpi_evidence,
                    })
                    st.rerun()

        st.divider()

        # Filter KPIs
        filtered = kpis
        if cat_filter != "全部":
            filtered = [k for k in filtered if k.category == cat_filter]
        if ev_filter != "全部":
            filtered = [k for k in filtered if k.evidence_level == ev_filter]
        if quality_filter != "全部":
            filtered = [k for k in filtered if k.data_quality == quality_filter]

        if filtered:
            st.subheader(f"KPI 列表 ({len(filtered)} 个)")

            for k in filtered:
                det_name = det_map.get(k.determinant_id, "—")
                col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])

                with col_a:
                    st.markdown(f"**{k.name}**  {evidence_badge(k.evidence_level)}")
                    st.caption(f"关联: {det_name} | 频率: {k.measurement_frequency or '未设定'}")
                with col_b:
                    st.metric("目标", f"{k.target_value} {k.unit}" if k.target_value else "未设定")
                with col_c:
                    st.metric("当前", f"{k.current_value} {k.unit}" if k.current_value else "无数据")
                with col_d:
                    if st.button("📊 趋势", key=f"trend_{k.id}"):
                        st.session_state.selected_kpi = k.id
                        st.rerun()

                # Trend chart for selected KPI
                if st.session_state.get("selected_kpi") == k.id:
                    trend = crud.get_kpi_trend(db2, k.id)
                    measurements = trend.get("measurements", [])
                    if measurements:
                        st.caption(f"趋势: {trend.get('trend_summary', '')}")

                        df = pd.DataFrame([{
                            "日期": m.measured_at, "值": m.value, "情境": m.context,
                        } for m in reversed(measurements)])

                        fig = px.line(df, x="日期", y="值", markers=True,
                                      title=f"{k.name} 趋势 ({k.unit})")
                        if k.target_value:
                            fig.add_hline(y=k.target_value, line_dash="dash",
                                          line_color="green", annotation_text="目标值")
                        if k.threshold_low:
                            fig.add_hline(y=k.threshold_low, line_dash="dot",
                                          line_color="red", annotation_text="下限")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("暂无测量数据，请在下方添加")

                    # Add measurement (always visible when KPI is selected)
                    with st.expander("➕ 添加测量记录", expanded=len(measurements) == 0):
                        mc1, mc2, mc3 = st.columns(3)
                        with mc1:
                            m_val = st.number_input("测量值", value=0.0, step=0.01, key=f"mv_{k.id}")
                        with mc2:
                            m_ctx = st.selectbox("测量情境", ["测试", "训练", "比赛", "恢复", "医疗"], key=f"mc_{k.id}")
                        with mc3:
                            m_quality = st.selectbox("数据质量", ["high", "medium", "low"], key=f"mq_{k.id}")
                        if st.button("保存测量", key=f"ms_{k.id}"):
                            crud.create_measurement(db2, {
                                "kpi_id": k.id,
                                "value": m_val,
                                "unit": k.unit,
                                "context": m_ctx,
                                "data_quality": m_quality,
                            })
                            st.rerun()

                    if st.button("关闭趋势图", key=f"close_{k.id}"):
                        st.session_state.selected_kpi = None
                        st.rerun()

                st.divider()

            # Export
            kpi_df = pd.DataFrame([{
                "KPI": k.name, "分类": k.category, "单位": k.unit,
                "目标值": k.target_value, "当前值": k.current_value,
                "关联因素": det_map.get(k.determinant_id, ""),
                "频率": k.measurement_frequency, "证据": k.evidence_level,
            } for k in filtered])
            st.download_button("📥 导出 KPI 列表 (CSV)", kpi_df.to_csv(index=False).encode("utf-8-sig"),
                               "kpi_list.csv", "text/csv")
        else:
            st.info("没有匹配的 KPI")
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: 运动员评估
# ═══════════════════════════════════════════════════════════════════

def page_athletes():
    st.title("🏃 运动员评估")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        athletes = crud.get_athletes(db2, project_id)
        kpis = crud.get_kpis(db2, project_id)

        # Create athlete
        with st.expander("➕ 添加运动员"):
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                a_name = st.text_input("姓名", key="a_name")
                a_gender = st.selectbox("性别", ["男", "女"], key="a_gender")
                a_age = st.number_input("年龄", 10, 80, 20, key="a_age")
            with ac2:
                a_height = st.number_input("身高 (cm)", 100, 250, 175, key="a_height")
                a_weight = st.number_input("体重 (kg)", 30, 200, 68, key="a_weight")
                a_train_age = st.number_input("训练年限", 0, 50, 5, key="a_train")
            with ac3:
                a_level = st.selectbox("水平", ["青少年", "大学", "职业", "国家级", "国际级", "精英级", "其他"], key="a_level")
                a_role = st.text_input("角色/位置", key="a_role")
                a_injury = st.text_area("伤病历史", key="a_injury")

            if st.button("保存运动员", type="primary"):
                if a_name:
                    crud.create_athlete(db2, project_id, {
                        "name": a_name, "gender": a_gender, "age": a_age,
                        "height": a_height, "weight": a_weight, "training_age": a_train_age,
                        "level": a_level, "role": a_role, "injury_history": a_injury,
                    })
                    st.rerun()

        st.divider()

        if not athletes:
            st.info("还没有添加运动员")
            return

        # Athlete selector
        athlete_names = [a.name for a in athletes]
        selected_athlete_name = st.selectbox("选择运动员", athlete_names)
        athlete = next((a for a in athletes if a.name == selected_athlete_name), None)

        if not athlete:
            return

        # Athlete profile + dashboard
        dashboard = crud.get_athlete_dashboard(db2, athlete.id)

        # Profile row
        cols = st.columns(5)
        with cols[0]:
            st.metric("年龄", athlete.age or "—")
        with cols[1]:
            st.metric("身高", f"{athlete.height} cm" if athlete.height else "—")
        with cols[2]:
            st.metric("体重", f"{athlete.weight} kg" if athlete.weight else "—")
        with cols[3]:
            st.metric("训练年限", f"{athlete.training_age}年" if athlete.training_age else "—")
        with cols[4]:
            st.metric("水平", athlete.level)

        if athlete.injury_history:
            st.warning(f"伤病历史: {athlete.injury_history}")

        st.divider()

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 KPI 雷达图", "📋 优点与短板", "📈 趋势对比"])

        with tab1:
            # Radar chart
            radar_data = []
            for s in dashboard.get("kpi_summary", []):
                if s["latest_value"] is not None and s["target_value"] is not None and s["target_value"] > 0:
                    radar_data.append({
                        "KPI": s["kpi_name"],
                        "当前值 (%)": min(100, s["latest_value"] / s["target_value"] * 100),
                        "目标值 (%)": 100,
                    })

            if radar_data:
                df_radar = pd.DataFrame(radar_data)
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=df_radar["当前值 (%)"].tolist(),
                    theta=df_radar["KPI"].tolist(),
                    fill='toself',
                    name='当前值',
                    line_color='#3498db',
                ))
                fig.add_trace(go.Scatterpolar(
                    r=df_radar["目标值 (%)"].tolist(),
                    theta=df_radar["KPI"].tolist(),
                    fill='toself',
                    name='目标值',
                    line_color='#2ecc71',
                    opacity=0.3,
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(range=[0, 120], ticksuffix='%')),
                    height=500,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂无足够 KPI 数据生成雷达图")

        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("✅ 优势")
                for s in dashboard.get("strengths", []):
                    st.success(s)
                if not dashboard.get("strengths"):
                    st.info("暂无足够数据")
            with c2:
                st.subheader("⚠️ 短板")
                for w in dashboard.get("weaknesses", []):
                    st.error(w)
                if not dashboard.get("weaknesses"):
                    st.info("暂无足够数据")

            st.subheader("🔴 风险提示")
            for r in dashboard.get("risk_alerts", []):
                st.warning(r)
            if not dashboard.get("risk_alerts"):
                st.success("当前无风险警报")

        with tab3:
            # Multi-KPI trend
            if dashboard.get("kpi_summary"):
                selected_kpis_for_chart = st.multiselect(
                    "选择 KPI 进行对比",
                    [s["kpi_name"] for s in dashboard["kpi_summary"]],
                )
                if selected_kpis_for_chart:
                    fig = go.Figure()
                    for kpi_name in selected_kpis_for_chart:
                        kpi_obj = next((k for k in kpis if k.name == kpi_name), None)
                        if kpi_obj:
                            measurements = crud.get_measurements(db2, kpi_obj.id, athlete.id)
                            if measurements:
                                dates = [m.measured_at for m in measurements]
                                values = [m.value for m in measurements]
                                fig.add_trace(go.Scatter(x=dates, y=values, mode='lines+markers', name=kpi_name))
                    if fig.data:
                        fig.update_layout(height=400, hovermode='x unified')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("所选 KPI 暂无测量数据")
            else:
                st.info("暂无 KPI 数据")

        # Agent evaluation
        st.divider()
        if st.button("🤖 自动生成运动员评估", type="primary"):
            from app.agent.workflows import workflow_evaluate_athlete
            result = workflow_evaluate_athlete(db2, athlete.id)
            st.subheader("优先提升领域")
            for area in result.get("priority_areas", []):
                st.markdown(f"- 🔥 **{area}**")
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: 干预计划
# ═══════════════════════════════════════════════════════════════════

def page_interventions():
    st.title("📋 干预计划")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        interventions = crud.get_interventions(db2, project_id)
        kpis = crud.get_kpis(db2, project_id)
        kpi_map = {k.id: k.name for k in kpis}

        # Create intervention
        with st.expander("➕ 添加干预措施"):
            ic1, ic2 = st.columns(2)
            with ic1:
                i_name = st.text_input("干预名称", key="i_name")
                i_type = st.selectbox("干预类型", ["训练", "营养", "热身", "恢复", "技术", "战术", "心理", "器材", "健康", "其他"], key="i_type")
                i_freq = st.text_input("频率", placeholder="每周2次", key="i_freq")
            with ic2:
                i_intensity = st.text_input("强度", placeholder="中等 / Zone 3 / 85% 1RM", key="i_intensity")
                i_duration = st.text_input("周期", placeholder="12周 / 4周一个模块", key="i_duration")
                i_status = st.selectbox("状态", ["planned", "active", "completed", "on_hold"], key="i_status")
            i_desc = st.text_area("描述和方案", key="i_desc")
            i_effect = st.text_input("预期效果", key="i_effect")
            i_risk = st.text_input("风险提示", key="i_risk")

            if st.button("保存干预措施"):
                if i_name:
                    crud.create_intervention(db2, project_id, {
                        "name": i_name, "intervention_type": i_type,
                        "description": i_desc, "protocol": i_desc,
                        "frequency": i_freq, "intensity": i_intensity,
                        "duration": i_duration, "expected_effect": i_effect,
                        "risk_notes": i_risk, "status": i_status,
                    })
                    st.rerun()

        st.divider()

        if interventions:
            # Group by type
            types = sorted(set(i.intervention_type for i in interventions))
            type_filter = st.selectbox("筛选类型", ["全部"] + types)
            filtered = interventions if type_filter == "全部" else [i for i in interventions if i.intervention_type == type_filter]

            for i in filtered:
                status_icon = {"planned": "📅", "active": "▶️", "completed": "✅", "on_hold": "⏸️"}.get(i.status, "❓")
                with st.expander(f"{status_icon} {i.name} — {i.intervention_type} | {i.status}"):
                    st.write(f"**类型**: {i.intervention_type}")
                    st.write(f"**频率**: {i.frequency or '未设定'}")
                    st.write(f"**强度**: {i.intensity or '未设定'}")
                    st.write(f"**周期**: {i.duration or '未设定'}")
                    if i.description:
                        st.write(f"**描述**: {i.description}")
                    if i.expected_effect:
                        st.write(f"**预期效果**: {i.expected_effect}")
                    if i.risk_notes:
                        st.warning(f"**风险**: {i.risk_notes}")

                    if st.button("更新状态", key=f"status_{i.id}"):
                        next_status = {"planned": "active", "active": "completed", "completed": "on_hold", "on_hold": "planned"}
                        from app import crud as c
                        c.update_intervention(db2, i.id, {"status": next_status.get(i.status, "planned")})
                        st.rerun()

            # Generate plan button
            st.divider()
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                weeks = st.number_input("训练周期 (周)", 4, 52, 12)
            with col_btn2:
                if st.button("🤖 生成干预计划", type="primary"):
                    from app.agent.workflows import workflow_intervention_plan
                    result = workflow_intervention_plan(db2, project_id, cycle_length_weeks=weeks)
                    st.success(result["schedule_summary"])
                    for item in result.get("interventions", []):
                        st.markdown(f"- **{item['name']}** — {item['frequency']} | {item['intensity']} | {item['duration']}")
        else:
            st.info("还没有干预措施。使用上方表单添加，或通过 Agent 工作流自动生成。")
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: 证据资料库
# ═══════════════════════════════════════════════════════════════════

def page_evidence():
    st.title("📚 证据资料库")
    st.caption("管理文献、规则、教练经验等证据来源。支持中英文关键词搜索和语义搜索。")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        # ── Search Section ──────────────────────────────────────
        st.subheader("🔍 搜索资料")

        search_col1, search_col2, search_col3 = st.columns([3, 1, 1])
        with search_col1:
            search_query = st.text_input(
                "搜索关键词",
                placeholder="输入中文或英文关键词搜索... 例如：800米 有氧能力 / VO2max lactate threshold",
                key="ev_search_q",
            )
        with search_col2:
            search_mode = st.selectbox(
                "搜索模式",
                ["hybrid", "keyword", "vector"],
                format_func=lambda x: {"hybrid": "🔀 混合搜索", "keyword": "📝 关键词", "vector": "🧠 语义搜索"}[x],
                key="ev_search_mode",
            )
        with search_col3:
            search_btn = st.button("🔍 搜索", type="primary", use_container_width=True, key="ev_search_btn")

        # Advanced filters
        with st.expander("筛选条件"):
            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                filter_type = st.selectbox("来源类型", ["全部"] + [
                    "科学文献", "教练员手册", "官方规则", "官方数据库",
                    "教练经验", "运动员数据", "医疗记录", "视频分析", "其他",
                ], key="ev_f_type")
            with fc2:
                filter_ev = st.selectbox("证据等级", ["全部", "高", "中", "低", "专家经验", "未知"], key="ev_f_ev")
            with fc3:
                filter_year_from = st.number_input("起始年份", 1900, 2030, 1900, key="ev_f_yf")
            with fc4:
                filter_year_to = st.number_input("截止年份", 1900, 2030, 2030, key="ev_f_yt")

        # ── Execute Search ──────────────────────────────────────
        if search_btn and search_query.strip():
            from app.agent.search_engine import keyword_search, vector_search, hybrid_search

            st.divider()
            st.subheader(f"搜索结果: 「{search_query}」")

            with st.spinner("搜索中..."):
                if search_mode == "keyword":
                    results = keyword_search(
                        db2, search_query, project_id,
                        filter_type if filter_type != "全部" else None,
                        filter_ev if filter_ev != "全部" else None,
                        filter_year_from if filter_year_from > 1900 else None,
                        filter_year_to if filter_year_to < 2030 else None,
                    )
                    st.caption(f"关键词匹配 — 找到 {len(results)} 条结果")
                    _render_search_results(results, "关键词匹配")

                elif search_mode == "vector":
                    results = vector_search(search_query, project_id, n_results=15)
                    st.caption(f"语义搜索 — 找到 {len(results)} 条结果")
                    _render_vector_results(results)

                else:  # hybrid
                    result = hybrid_search(db2, search_query, project_id)
                    st.caption(f"混合搜索 — 关键词 {result['keyword_count']} 条 + 语义 {result['semantic_count']} 条，共 {result['total']} 条")
                    for r in result["results"]:
                        match_badge = {"关键词匹配": "📝", "语义匹配": "🧠"}.get(r["match_type"], "")
                        ev_badge_text = r.get("evidence_level", "未知")
                        with st.expander(f"{match_badge} {evidence_badge(ev_badge_text)} {r['title'][:80]}"):
                            st.write(f"**匹配方式**: {r['match_type']}")
                            if r.get("similarity"):
                                st.write(f"**语义相似度**: {r['similarity']}%")
                            _render_source_detail(r)

            st.divider()

        # Show all sources when not searching
        elif not search_query.strip():
            sources = crud.get_evidence_sources(db2, project_id)
            if sources:
                st.caption(f"共 {len(sources)} 条证据来源")
            else:
                st.info("还没有证据来源。添加文献、官方规则或教练经验来支撑 KPI 设计。")

        # ── Add Source ──────────────────────────────────────────
        with st.expander("➕ 添加证据来源", expanded=False):
            ec1, ec2 = st.columns(2)
            with ec1:
                e_title = st.text_input("标题", key="e_title")
                e_type = st.selectbox("来源类型", ["科学文献", "教练员手册", "官方规则", "官方数据库", "教练经验", "运动员数据", "医疗记录", "视频分析", "用户上传", "其他"], key="e_type")
                e_authors = st.text_input("作者", key="e_authors")
                e_year = st.number_input("年份", 1900, 2030, 2024, key="e_year")
            with ec2:
                e_url = st.text_input("URL", key="e_url")
                e_doi = st.text_input("DOI", key="e_doi")
                e_evidence = st.selectbox("证据等级", ["高", "中", "低", "专家经验", "未知"], key="e_evidence")
                e_relevance = st.text_input("相关领域 / 标签", key="e_rel", placeholder="例如：有氧能力 / 800米 / 乳酸阈")
            e_summary = st.text_area("摘要/关键发现", key="e_summary")
            e_limitations = st.text_input("局限性", key="e_lim")

            if st.button("保存证据来源", key="ev_save_btn"):
                if e_title:
                    crud.create_evidence_source(db2, project_id, {
                        "title": e_title, "source_type": e_type, "authors": e_authors,
                        "year": e_year, "url": e_url, "doi": e_doi,
                        "summary": e_summary, "relevance": e_relevance,
                        "evidence_level": e_evidence, "limitations": e_limitations,
                    })
                    st.success(f"已保存并索引: {e_title}")
                    st.rerun()

        # ── Management tools ────────────────────────────────────
        st.divider()
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if st.button("🔄 重建向量索引", help="将所有证据重新索引到向量数据库"):
                from app.agent.search_engine import index_all_sources
                count = index_all_sources(db2, project_id)
                st.success(f"已索引 {count} 条证据")
        with col_m2:
            from app.agent.search_engine import _get_collection
            coll = _get_collection()
            if coll:
                st.metric("向量库文档数", coll.count())

        # ── Evidence summary chart ──────────────────────────────
        sources = crud.get_evidence_sources(db2, project_id)
        if sources:
            ev_counts = {}
            for s in sources:
                ev_counts[s.evidence_level] = ev_counts.get(s.evidence_level, 0) + 1
            ev_df = pd.DataFrame([{"等级": k, "数量": v} for k, v in ev_counts.items()])
            fig = px.pie(ev_df, values="数量", names="等级",
                         color="等级",
                         color_discrete_map={"高": "#2ecc71", "中": "#3498db", "低": "#f39c12", "专家经验": "#9b59b6", "未知": "#95a5a6"},
                         title="证据等级分布")
            st.plotly_chart(fig, use_container_width=True)

    finally:
        db2.close()


def _render_source_detail(r: dict):
    """Render a single evidence source detail."""
    if r.get("authors"):
        st.write(f"**作者**: {r['authors']} | **年份**: {r.get('year', '—')}")
    if r.get("source_type"):
        st.caption(f"来源类型: {r['source_type']}")
    if r.get("summary"):
        st.write(r["summary"][:500])
    if r.get("url"):
        st.write(f"🔗 {r['url']}")
    if r.get("doi"):
        st.write(f"📄 DOI: {r['doi']}")
    if r.get("relevance"):
        st.caption(f"标签: {r['relevance']}")
    if r.get("limitations"):
        st.caption(f"⚠️ 局限性: {r['limitations']}")


def _render_search_results(results: list, match_type: str):
    """Render keyword search results."""
    if not results:
        st.info("未找到匹配结果。尝试使用不同的关键词或切换到语义搜索。")
        return
    for s in results:
        with st.expander(f"{evidence_badge(s.evidence_level)} {s.title[:80]}"):
            _render_source_detail({
                "authors": s.authors, "year": s.year, "source_type": s.source_type,
                "summary": s.summary, "url": s.url, "doi": s.doi,
                "relevance": s.relevance, "limitations": s.limitations,
                "evidence_level": s.evidence_level,
            })


def _render_vector_results(results: list):
    """Render vector search results."""
    if not results:
        st.info("未找到语义相似的结果。尝试更具体的查询或切换到关键词搜索。")
        return
    for r in results:
        sim = r.get("similarity", 0)
        ev = r.get("evidence_level", "未知")
        with st.expander(f"🧠 相似度 {sim}% | {evidence_badge(ev)} {r.get('title', '')[:80]}"):
            st.write(f"**语义相似度**: {sim}%")
            _render_source_detail(r)


# ═══════════════════════════════════════════════════════════════════
#  Page: 报告中心
# ═══════════════════════════════════════════════════════════════════

def page_reports():
    st.title("📝 报告中心")

    if project_id <= 0:
        st.info("👈 请先选择项目")
        return

    db2 = get_fresh_db()
    try:
        reports = crud.get_reports(db2, project_id)
        athletes = crud.get_athletes(db2, project_id)

        # Generate new report
        with st.expander("📄 生成新报告"):
            r1, r2 = st.columns(2)
            with r1:
                report_type = st.selectbox("报告类型", [
                    "项目需求分析报告", "PO与KPI设计报告", "运动员评估报告",
                    "KPI趋势报告", "干预建议报告", "数据质量报告", "比赛复盘报告",
                ])
            with r2:
                athlete_choice = st.selectbox("运动员 (可选)", ["(全部)"] + [a.name for a in athletes])
            extra = st.text_area("补充说明 (可选)")

            if st.button("📝 生成报告", type="primary"):
                from app.agent.report_generator import generate_report
                aid = None
                if athlete_choice != "(全部)":
                    for a in athletes:
                        if a.name == athlete_choice:
                            aid = a.id
                            break
                report = generate_report(db2, project_id, report_type, aid, extra)
                if report:
                    st.success(f"报告已生成: {report.title}")
                    st.rerun()

        st.divider()

        if reports:
            st.subheader(f"历史报告 ({len(reports)} 份)")

            for r in reversed(reports):
                with st.expander(f"📄 {r.title} — {r.generated_at.strftime('%Y-%m-%d %H:%M') if r.generated_at else ''}"):
                    st.markdown(r.content_markdown)
                    st.download_button(
                        "📥 下载 Markdown",
                        r.content_markdown.encode("utf-8"),
                        f"{r.report_type}_{r.generated_at.strftime('%Y%m%d') if r.generated_at else 'report'}.md",
                        key=f"dl_{r.id}",
                    )
        else:
            st.info("还没有生成报告。点击上方生成第一份报告。")
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: Agent 工作流
# ═══════════════════════════════════════════════════════════════════

def page_agent():
    st.title("🤖 Agent 智能工作流")
    st.caption("按顺序执行以下步骤，系统化构建完整的 KPI 体系。")

    if project_id <= 0:
        st.info("👈 请先选择或创建一个项目")
        return

    db2 = get_fresh_db()
    try:
        project = crud.get_project(db2, project_id)

        # Workflow progress tracker
        outcomes = crud.get_outcomes(db2, project_id)
        determinants = crud.get_determinants(db2, project_id)
        kpis = crud.get_kpis(db2, project_id)
        athletes = crud.get_athletes(db2, project_id)
        interventions = crud.get_interventions(db2, project_id)

        milestones = [
            ("项目创建", True),
            ("PO 定义", len(outcomes) > 0),
            ("需求分析", len(determinants) > 0),
            ("表现模型", len(determinants) > 0),
            ("KPI 生成", len(kpis) > 0),
            ("干预计划", len(interventions) > 0),
            ("运动员评估", len(athletes) > 0),
            ("报告生成", False),
        ]

        progress_html = ""
        for name, done in milestones:
            icon = "✅" if done else "⏳"
            progress_html += f"{icon} {name}  "
        st.markdown(f"**进度**: {progress_html}")

        # Calculate progress
        done_count = sum(1 for _, d in milestones if d)
        st.progress(done_count / len(milestones), f"{done_count}/{len(milestones)}")

        st.divider()

        # Step 1: Define PO
        with st.expander("**步骤 1: 定义表现目标 (PO)**", expanded=len(outcomes) == 0):
            st.markdown("表现目标是所有 KPI 的出发点。目标必须具体、可测量、有时间边界。")

            col_po1, col_po2 = st.columns(2)
            with col_po1:
                po_name = st.text_input("你想改善什么表现结果？", placeholder="例如：800米成绩达到1:48", key="wf_po_name")
                po_type = st.selectbox("目标类型", ["成绩", "排名", "奖牌", "胜率", "选拔资格", "技术得分", "团队角色", "其他"], key="wf_po_type")
            with col_po2:
                po_value = st.number_input("目标值", value=0.0, step=0.1, key="wf_po_val")
                po_unit = st.text_input("单位", placeholder="s / m / %", key="wf_po_unit")
                po_baseline = st.number_input("当前基线", value=0.0, step=0.1, key="wf_po_base")

            if st.button("定义 PO", type="primary", key="wf_btn_po"):
                if po_name:
                    from app.agent.workflows import workflow_define_po
                    result = workflow_define_po(db2, project_id, po_name, "", po_value if po_value > 0 else None, po_unit, po_baseline if po_baseline > 0 else None, None, "")
                    qc = result["quality_check"]
                    qc_text = f"评分: {qc['overall_score']}/5 ({qc['overall_rating']})"
                    if qc["overall_rating"] == "优秀":
                        st.success(f"PO 已创建 — {qc_text}")
                    else:
                        st.warning(f"PO 已创建 — {qc_text}")
                        for s in result["suggestions"]:
                            st.info(s)
                    st.rerun()

        # Step 2: Analyze demands
        with st.expander("**步骤 2: 项目需求分析**", expanded=len(determinants) == 0 and len(outcomes) > 0):
            st.markdown("从生理、技术、战术、心理、器材、健康和规则维度分析项目需求。")
            if st.button("📊 需求分析", key="wf_btn_demands"):
                from app.agent.workflows import workflow_analyze_demands
                result = workflow_analyze_demands(db2, project_id)
                for cat in result["categories"]:
                    with st.expander(cat["category"]):
                        st.write(f"**为什么重要**: {cat['why_important']}")
                        st.write(f"**可能来源**: {cat['possible_sources']}")
                st.info(f"整体完整度: {result['overall_completeness']}")
                st.rerun()

        # Step 3: Build performance model
        with st.expander("**步骤 3: 建立表现模型**", expanded=len(kpis) == 0 and len(outcomes) > 0):
            st.markdown("建立确定性表现模型，将 PO 拆解为可训练的决定因素。")

            tab_template, tab_evidence = st.tabs(["📋 内置模板", "🔬 文献检索生成"])

            with tab_template:
                st.caption("使用内置的运动项目模板快速建立表现模型。")
                if st.button("🏗️ 使用模板建立表现模型", key="wf_btn_model"):
                    from app.agent.workflows import workflow_build_performance_model
                    result = workflow_build_performance_model(db2, project_id)
                    st.success(f"已创建 {len(result['determinants_tree'])} 个决定因素类别")
                    st.rerun()

            with tab_evidence:
                st.caption("通过 PubMed 文献检索自动提取表现决定因素、KPI 和干预措施。")
                col_ev1, col_ev2 = st.columns(2)
                with col_ev1:
                    sport_name_ev = st.text_input("运动项目名称", value=project.sport_type,
                                                  help="中文名称，如：800米跑、篮球、足球、游泳",
                                                  key="wf_ev_sport")
                with col_ev2:
                    sport_name_en_ev = st.text_input("英文名称 (可选)", placeholder="如：800m running / basketball / soccer",
                                                     help="英文名称可获得更好的 PubMed 检索结果",
                                                     key="wf_ev_sport_en")

                col_ev3, col_ev4 = st.columns(2)
                with col_ev3:
                    use_llm_ev = st.checkbox("使用 LLM 提取 (DeepSeek)", value=True,
                                             help="启用后使用 AI 从文献中智能提取模型，质量更高；关闭则使用关键词匹配",
                                             key="wf_ev_llm")
                with col_ev4:
                    max_papers_ev = st.slider("每类检索论文数", 3, 15, 8,
                                              help="每类检索返回的最大论文数，更多论文可能获得更全面的模型但耗时更长",
                                              key="wf_ev_max")

                if st.button("🔬 从文献检索生成表现模型", type="primary", key="wf_btn_evidence_model"):
                    with st.spinner("正在检索文献并提取表现模型..."):
                        from app.agent.workflows import workflow_generate_model_from_evidence
                        result = workflow_generate_model_from_evidence(
                            db2, project_id,
                            sport_name=sport_name_ev,
                            sport_name_en=sport_name_en_ev,
                            use_llm=use_llm_ev,
                            max_results_per_query=max_papers_ev,
                        )
                        if result.get("error"):
                            st.error(result["error"])
                        else:
                            model = result["model"]
                            st.session_state["evidence_model"] = model
                            st.session_state["evidence_model_sport"] = sport_name_ev
                            st.session_state["evidence_model_ready"] = True
                            st.rerun()

                # Show generated model for review
                if st.session_state.get("evidence_model_ready") and st.session_state.get("evidence_model"):
                    model = st.session_state["evidence_model"]
                    st.divider()
                    st.subheader("📋 文献检索结果 — 请审核")
                    st.caption(f"运动项目: {model.get('sport_name', '')} | "
                               f"提取方式: {'LLM 智能提取' if model.get('extraction_method') == 'llm' else '关键词匹配'} | "
                               f"综述: {ss['narrative_review_count']} 篇 | 体能测试: {ss['fitness_test_count']} 篇 | 元分析: {ss['meta_analysis_count']} 篇"
                               if (ss := model.get('search_summary', {})) else "")

                    # Translation note
                    translation_note = model.get("translation_note", "")
                    if translation_note:
                        if translation_note.startswith("⚠️"):
                            st.warning(translation_note)
                        else:
                            st.success(translation_note)
                    resolved = model.get("sport_name_resolved", [])
                    if resolved:
                        st.caption(f"PubMed 检索词: {'; '.join(resolved)}")

                    # Model summary
                    st.info(model.get("model_summary", ""))

                    # ── Evidence sources with contribution tracking ──
                    all_evidence = model.get("evidence_sources", [])
                    paper_map = model.get("paper_determinant_map", [])
                    total_papers = len(all_evidence)

                    # Papers that contributed to at least one determinant
                    contributed_papers = [p for p in paper_map if p.get("match_count", 0) > 0]
                    no_match_papers = [p for p in paper_map if p.get("match_count", 0) == 0]

                    with st.expander(f"📚 检索到的文献 ({total_papers} 篇，其中 {len(contributed_papers)} 篇有贡献)"):
                        st.caption("每篇文献匹配到的决定因素数量。未匹配的文献可能是因为其研究方向与决定因素关键词不直接对应。")

                        # Contributed papers first
                        if contributed_papers:
                            st.markdown("**✅ 匹配到决定因素的文献:**")
                            for i, p in enumerate(contributed_papers):
                                matched = p.get("matched_determinants", [])
                                det_labels = ", ".join(f"{d['determinant']}({d['category']})" for d in matched)
                                st.markdown(f"**{i+1}.** [{p.get('year', '')}] {p.get('title', '')}")
                                st.caption(f"   匹配: {det_labels}")

                        # Non-matching papers with explanation
                        if no_match_papers:
                            st.markdown("**⚠️ 未匹配到决定因素的文献:**")
                            st.caption("这些文献可能涉及特定测试方法、特定人群或其他研究方向，与模型中的决定因素关键词不完全匹配。建议查看摘要确认是否包含有效信息。")
                            for i, p in enumerate(no_match_papers):
                                st.markdown(f"**{i+1}.** [{p.get('year', '')}] {p.get('title', '')}")
                                st.caption(f"   来源: {p.get('source_type', '')}")

                    # ── Empty categories explanation ──
                    empty_cats = model.get("empty_categories", [])
                    if empty_cats:
                        with st.expander("🔍 未生成因素的类别 (原因说明)"):
                            for ec in empty_cats:
                                st.markdown(f"**{ec['category']}**")
                                st.caption(f"   {ec['reason']}")
                                if ec.get("found_hints"):
                                    st.caption(f"   文献中出现的相关概念: {', '.join(ec['found_hints'])}")

                    # ── Category by category review with paper trace ──
                    selected_dets = []
                    selected_kpis = []
                    selected_intvs = []

                    categories = model.get("categories", {})
                    for cat_name, cat_data in categories.items():
                        dets = cat_data.get("determinants", [])
                        if not dets:
                            continue
                        with st.expander(f"**{cat_name}** — {cat_data.get('importance', '')} ({len(dets)} 个因素)"):
                            for det in dets:
                                # Find papers that mention this determinant
                                mentioning_papers = []
                                for p in paper_map:
                                    for md in p.get("matched_determinants", []):
                                        if md.get("determinant") == det.get("name"):
                                            mentioning_papers.append(f"[{p.get('year', '')}] {p.get('title', '')[:60]}")
                                            break

                                det_key = f"ev_det_{cat_name}_{det['name']}"
                                checked = st.checkbox(
                                    f"{det['name']} — {det.get('description', '')[:80]}",
                                    value=True,
                                    key=det_key,
                                )
                                if checked:
                                    selected_dets.append({**det, "category": cat_name})
                                st.caption(f"  证据等级: {det.get('evidence_level', '未知')} | 重要性: {det.get('importance', '')}")
                                if mentioning_papers:
                                    st.caption(f"  来源: {mentioning_papers[0]}")

                    # KPIs
                    kpis = model.get("kpis", [])
                    if kpis:
                        with st.expander(f"📈 建议的 KPI ({len(kpis)} 个)"):
                            for kpi in kpis:
                                kpi_key = f"ev_kpi_{kpi['name']}_{kpi.get('determinant', '')}"
                                checked = st.checkbox(
                                    f"**{kpi['name']}** ({kpi.get('unit', '')}) — {kpi.get('determinant', '')}",
                                    value=True, key=kpi_key,
                                )
                                if checked:
                                    selected_kpis.append(kpi)
                                st.caption(f"  测试: {kpi.get('protocol', '')} | 频率: {kpi.get('frequency', '')} | 证据: {kpi.get('evidence_level', '')}")

                    # Interventions
                    interventions = model.get("interventions", [])
                    if interventions:
                        with st.expander(f"📋 建议的干预措施 ({len(interventions)} 个)"):
                            for intv in interventions:
                                intv_key = f"ev_intv_{intv['name']}"
                                checked = st.checkbox(
                                    f"**{intv['name']}** [{intv.get('type', '')}] → {intv.get('target_determinant', '')}",
                                    value=True, key=intv_key,
                                )
                                if checked:
                                    selected_intvs.append(intv)
                                st.caption(f"  {intv.get('description', '')[:120]}")

                    # Save button
                    st.divider()
                    col_save1, col_save2, col_save3 = st.columns([2, 1, 1])
                    with col_save1:
                        st.markdown(f"已选择: {len(selected_dets)} 个决定因素, {len(selected_kpis)} 个 KPI, {len(selected_intvs)} 个干预措施")
                    with col_save2:
                        if st.button("💾 保存到项目", type="primary", key="wf_btn_save_evidence"):
                            from app.agent.workflows import workflow_confirm_evidence_model
                            result = workflow_confirm_evidence_model(
                                db2, project_id, model,
                                selected_determinants=selected_dets,
                                selected_kpis=selected_kpis,
                                selected_interventions=selected_intvs,
                            )
                            s = result["summary"]
                            st.success(f"已保存！决定因素: {s['determinants_created']}, KPI: {s['kpis_created']}, "
                                       f"干预: {s['interventions_created']}, 证据: {s['evidence_sources_created']}")
                            st.rerun()
                    with col_save3:
                        if st.button("🗑️ 清除检索", key="wf_btn_clear_evidence"):
                            st.session_state["evidence_model_ready"] = False
                            st.session_state.pop("evidence_model", None)
                            st.rerun()

        # Step 4: Generate KPIs
        with st.expander("**步骤 4: 生成 KPI**", expanded=len(determinants) > 0 and len(kpis) == 0):
            st.markdown("基于表现模型，为每个关键因素生成可测量、可追踪的 KPI。")
            if st.button("🎯 生成 KPI", key="wf_btn_kpi"):
                from app.agent.workflows import workflow_generate_kpis
                result = workflow_generate_kpis(db2, project_id)
                st.success(f"已生成 {result['kpi_count']} 个 KPI")
                st.rerun()

        # Step 5 & 6: Evaluate + Plan
        with st.expander("**步骤 5-6: 评估运动员 & 制定干预计划**", expanded=len(kpis) > 0 and len(athletes) > 0):
            if athletes:
                selected = st.selectbox("选择运动员", [a.name for a in athletes], key="wf_ath")
                athlete = next((a for a in athletes if a.name == selected), None)
                if athlete:
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        if st.button("📊 评估运动员", key="wf_btn_eval"):
                            from app.agent.workflows import workflow_evaluate_athlete
                            result = workflow_evaluate_athlete(db2, athlete.id)
                            st.subheader("优势")
                            for s in result.get("strengths", []):
                                st.success(s)
                            st.subheader("短板")
                            for w in result.get("weaknesses", []):
                                st.error(w)
                            st.subheader("优先提升")
                            for p in result.get("priority_areas", []):
                                st.markdown(f"- 🔥 {p}")
                    with col_e2:
                        if st.button("📋 生成干预计划", key="wf_btn_plan"):
                            from app.agent.workflows import workflow_intervention_plan
                            result = workflow_intervention_plan(db2, project_id, athlete.id, cycle_length_weeks=12)
                            for item in result.get("interventions", []):
                                st.markdown(f"- **{item['name']}** — {item['type']} | {item['frequency']} | {item['intensity']}")

        # Step 7: Generate Report
        with st.expander("**步骤 7: 生成报告**", expanded=False):
            rt = st.selectbox("报告类型", [
                "项目需求分析报告", "PO与KPI设计报告", "运动员评估报告",
                "KPI趋势报告", "干预建议报告", "数据质量报告", "比赛复盘报告",
            ], key="wf_rt")
            if st.button("📝 生成报告", key="wf_btn_report"):
                from app.agent.report_generator import generate_report
                report = generate_report(db2, project_id, rt)
                if report:
                    st.markdown(report.content_markdown)
                    st.download_button("📥 下载", report.content_markdown.encode("utf-8"),
                                       f"{rt}.md", key="wf_dl_report")

    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
#  Page: 创建新项目
# ═══════════════════════════════════════════════════════════════════

def page_create_project():
    st.title("➕ 创建新项目")
    st.caption("创建一个新的竞技体育 KPI 建模项目")

    col_a, col_b = st.columns(2)

    with col_a:
        p_name = st.text_input("项目名称 *", placeholder="例如：Elite 800m Performance Project")
        p_sport = st.text_input("运动项目 *", placeholder="例如：Athletics - 800m / 足球 / 游泳 - 100m自由泳")
        p_type = st.selectbox("项目类型", ["计量类", "非计量类", "团队类", "混合类", "其他"],
                              help="计量类：田径/游泳/举重；非计量类：体操/花滑；团队类：足球/篮球/排球")
        p_level = st.selectbox("运动员水平", ["青少年", "大学", "职业", "国家级", "国际级", "精英级", "其他"])

    with col_b:
        p_competition = st.text_input("目标赛事", placeholder="例如：2026 全国田径锦标赛")
        p_start = st.date_input("开始日期")
        p_end = st.date_input("结束日期 (可选)", value=None)

    p_desc = st.text_area("项目描述", placeholder="训练阶段、主要目标、团队背景等...")

    st.divider()

    # Quick template selector
    st.subheader("🚀 快速开始")
    st.caption("如果运动项目匹配以下模板，可以一键生成完整项目结构（PO + 决定因素 + KPI + 干预措施）")

    template_cols = st.columns(4)
    templates_available = {
        "Athletics - 800m": "🏃 800米跑",
        "Athletics - 100m": "💨 100米短跑",
        "Athletics - Marathon": "🏅 马拉松",
        "Swimming - 100m Freestyle": "🏊 100米自由泳",
        "Football": "⚽ 足球",
        "Basketball": "🏀 篮球",
        "Volleyball": "🏐 排球",
        "Weightlifting": "🏋️ 举重",
        "Gymnastics": "🤸 体操",
        "Rowing": "🚣 赛艇",
        "Cycling - Track": "🚴 场地自行车",
        "Other / Custom": "✏️ 自定义",
    }

    selected_template = None
    for i, (key, label) in enumerate(templates_available.items()):
        col_idx = template_cols[i % 4]
        with col_idx:
            if st.button(label, key=f"tpl_{key}", use_container_width=True):
                selected_template = key

    if selected_template:
        # Pre-fill the sport type from template
        if selected_template != "Other / Custom":
            p_sport = selected_template
            st.info(f"已选择模板: {selected_template}")

    st.divider()

    if st.button("✅ 创建项目", type="primary", use_container_width=True):
        if not p_name:
            st.error("项目名称不能为空")
        elif not p_sport:
            st.error("运动项目不能为空")
        else:
            db3 = get_fresh_db()
            try:
                from datetime import datetime as dt
                project = crud.create_project(db3, {
                    "name": p_name,
                    "sport_type": p_sport,
                    "project_type": p_type,
                    "description": p_desc,
                    "level": p_level,
                    "target_competition": p_competition,
                    "start_date": dt.combine(p_start, dt.min.time()) if p_start else None,
                    "end_date": dt.combine(p_end, dt.min.time()) if p_end else None,
                })
                pid = project.id

                # If matching template, auto-generate everything
                from app.agent.performance_model import (
                    build_determinants_from_template,
                    build_interventions_from_template,
                    get_template,
                )
                from app.agent.kpi_generator import generate_kpis_for_determinants

                template = get_template(p_sport)
                if template:
                    build_determinants_from_template(db3, pid, p_sport)
                    build_interventions_from_template(db3, pid, p_sport)
                    generate_kpis_for_determinants(db3, pid, p_sport)
                    db3.commit()

                st.success(f"项目 '{p_name}' 创建成功！")
                if template:
                    st.info("已自动生成表现模型、KPI 和干预措施。")
                # Auto-select the new project
                st.session_state.force_project = p_name
                st.rerun()
            finally:
                db3.close()

    # Show existing projects
    st.divider()
    st.subheader("📋 已有项目")

    db2 = get_fresh_db()
    try:
        all_projects = crud.get_projects(db2)
        if all_projects:
            for p in all_projects:
                col_p1, col_p2, col_p3 = st.columns([3.5, 0.7, 0.8])
                with col_p1:
                    st.markdown(f"**{p.name}** — {p.sport_type} | {p.project_type} | {p.level}")
                with col_p2:
                    if st.button("📋 选择", key=f"sel_{p.id}"):
                        st.session_state.force_project = p.name
                        st.rerun()
                with col_p3:
                    if st.button("🗑️ 删除", key=f"del_{p.id}"):
                        st.session_state.confirm_delete = p.id
                        st.session_state.confirm_delete_name = p.name
                        st.rerun()

            # Confirm delete dialog
            if st.session_state.get("confirm_delete"):
                st.warning(f"⚠️ 确认删除项目「{st.session_state.confirm_delete_name}」？此操作不可恢复，将同时删除所有关联数据。")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if st.button("✅ 确认删除", type="primary", key="confirm_del_btn"):
                        db4 = get_fresh_db()
                        try:
                            crud.delete_project(db4, st.session_state.confirm_delete)
                        finally:
                            db4.close()
                        st.session_state.confirm_delete = None
                        st.session_state.confirm_delete_name = None
                        st.rerun()
                with col_d2:
                    if st.button("❌ 取消", key="cancel_del_btn"):
                        st.session_state.confirm_delete = None
                        st.session_state.confirm_delete_name = None
                        st.rerun()
        else:
            st.info("暂无项目。创建第一个吧。")
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
#  Page: 文献 → 表现模型
# ═══════════════════════════════════════════════════════════════════

def page_literature_to_performance_model():
    st.title("🧬 文献 → 表现模型")
    st.caption("从已检索文献中批量提取表现决定因素 · 自动归类八大层级 · 构建证据链接模型")

    # ── Initialize session state ──
    if "pm_pipeline_result" not in st.session_state:
        st.session_state.pm_pipeline_result = None
    if "pm_candidates" not in st.session_state:
        st.session_state.pm_candidates = []
    if "pm_candidate_status" not in st.session_state:
        st.session_state.pm_candidate_status = {}
    if "pm_selected_query" not in st.session_state:
        st.session_state.pm_selected_query = None

    # ── Step 1: Select literature source ──
    st.subheader("1. 选择文献来源")

    col_a, col_b, col_c = st.columns([2, 1, 1])

    with col_a:
        from app.performance_model.batch_loader import get_cached_queries as _get_queries
        try:
            queries = _get_queries()
        except Exception:
            queries = []

        query_options = ["(使用全部缓存文献)"] + [
            f"Query #{q['id']}: {q['query_text'][:80]} ({q['result_count']} results, {q['created_at'][:10]})"
            for q in queries
        ]
        selected_query_label = st.selectbox("选择已缓存的检索查询", query_options, key="pm_query_select")

        if selected_query_label and selected_query_label != "(使用全部缓存文献)":
            for q in queries:
                label = f"Query #{q['id']}: {q['query_text'][:80]} ({q['result_count']} results, {q['created_at'][:10]})"
                if label == selected_query_label:
                    st.session_state.pm_selected_query = q['id']
                    break
        else:
            st.session_state.pm_selected_query = None

    with col_b:
        limit = st.number_input("读取文献上限", min_value=5, max_value=200, value=50, step=5)
        min_conf = st.slider("最低置信度", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

    with col_c:
        use_yake = st.checkbox("使用 YAKE", value=True, help="轻量级无监督关键词提取")
        use_keybert = st.checkbox("使用 KeyBERT", value=False, help="需要 sentence-transformers")
        include_fulltext = st.checkbox("包含全文", value=False, help="如果有 fulltext 链接则尝试获取")

    # ── Step 2: Extract button ──
    st.subheader("2. 批量提取表现决定因素")

    if st.button("🚀 从文献批量提取表现决定因素", type="primary", use_container_width=True):
        with st.spinner("正在提取... 读取文献 → 词典匹配 → 关键词提取 → 分类 → 合并 → 评分"):
            try:
                from app.performance_model.pipeline import run_full_pipeline
                result = run_full_pipeline(
                    query_id=st.session_state.pm_selected_query,
                    limit=limit,
                    include_fulltext=include_fulltext,
                    use_keybert=use_keybert,
                    use_yake=use_yake,
                    use_spacy=False,
                    min_confidence=min_conf,
                )
                st.session_state.pm_pipeline_result = result
                st.session_state.pm_candidates = result.get("candidates", [])
                # Reset status tracking
                st.session_state.pm_candidate_status = {
                    c.get("canonical_name", ""): "candidate"
                    for c in result.get("candidates", [])
                }
                st.success(f"提取完成！{result['documents_loaded']} 篇文献 → {result['candidates_extracted']} 原始候选 → {result['candidates_merged']} 合并后 → {result['candidates_filtered']} 最终候选")
            except Exception as e:
                st.error(f"提取失败: {e}")

    # ── Results display ──
    result = st.session_state.pm_pipeline_result
    if not result:
        st.info("请先点击「从文献批量提取表现决定因素」按钮开始分析。")
        return

    # ── Step 3: Processing stats ──
    st.subheader("3. 处理状态")
    cols = st.columns(6)
    cols[0].metric("已读取文献", result.get("documents_loaded", 0))
    cols[1].metric("有摘要", result.get("documents_with_abstract", 0))
    cols[2].metric("有全文", result.get("documents_with_fulltext", 0))
    cols[3].metric("原始候选", result.get("candidates_extracted", 0))
    cols[4].metric("合并后", result.get("candidates_merged", 0))
    cols[5].metric("最终候选", result.get("candidates_filtered", 0))

    candidates = st.session_state.pm_candidates
    if not candidates:
        st.warning("没有提取到满足最低置信度的候选指标。")

    # ── Step 4: Candidate table ──
    st.subheader("4. 候选指标列表")
    import pandas as pd

    # Build table data
    table_data = []
    for i, c in enumerate(candidates):
        canon = c.get("canonical_name", "")
        status = st.session_state.pm_candidate_status.get(canon, "candidate")
        table_data.append({
            "序号": i + 1,
            "canonical_name": canon,
            "display_name_en": c.get("display_name_en", ""),
            "category": c.get("category_key", "other").replace("_", " "),
            "evidence_count": len(c.get("source_literature_ids", [])),
            "source_count": len(c.get("source_databases", [])),
            "confidence": f"{c.get('confidence_score', 0):.2f}",
            "relevance": f"{c.get('relevance_score', 0):.2f}",
            "strength": f"{c.get('evidence_strength_score', 0):.2f}",
            "methods": ", ".join(c.get("extraction_methods", [])),
            "status": status,
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, height=300,
                 column_config={
                     "canonical_name": "标准名称",
                     "display_name_en": "显示名称",
                     "category": "分类",
                     "evidence_count": "证据数",
                     "confidence": "置信度",
                     "status": "状态",
                 })

    # ── Step 5: Expandable evidence ──
    st.subheader("5. 证据详情（点击展开）")

    for i, c in enumerate(candidates[:30]):  # limit to 30 for performance
        canon = c.get("canonical_name", "")
        cat = c.get("category_key", "other")
        status = st.session_state.pm_candidate_status.get(canon, "candidate")
        status_icon = {"accepted": "✅", "rejected": "❌", "candidate": "🔍"}.get(status, "🔍")

        with st.expander(f"{status_icon} {canon} — {cat} — {len(c.get('source_literature_ids', []))} evidence(s)"):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.markdown(f"**Standard name**: `{canon}`")
                st.markdown(f"**Display name**: {c.get('display_name_en', '')}")
                st.markdown(f"**Category**: {cat}")
                st.markdown(f"**Aliases**: {', '.join(c.get('aliases', [])[:10])}")
                st.markdown(f"**Extraction methods**: {', '.join(c.get('extraction_methods', []))}")
                st.markdown(f"**Confidence**: {c.get('confidence_score', 0):.2f} | **Relevance**: {c.get('relevance_score', 0):.2f} | **Strength**: {c.get('evidence_strength_score', 0):.2f}")

                # Evidence sentences
                st.markdown("**Supporting evidence:**")
                for ev in c.get("evidence_sentences", [])[:10]:
                    lit_id = ev.get("literature_id", "?")
                    text = ev.get("text", "")[:300]
                    doi = ev.get("doi", "")
                    year = ev.get("year", "")
                    loc = ev.get("location", "")
                    matched = ev.get("matched_term", "")
                    st.markdown(f"- **[Lit#{lit_id}]** ({year}, {loc}) `{matched}`")
                    st.markdown(f"  DOI: {doi}")
                    st.text(f"  \"{text}...\"")

            with col_action:
                new_status = st.selectbox(
                    "状态", ["candidate", "accepted", "rejected"],
                    index=["candidate", "accepted", "rejected"].index(status),
                    key=f"status_{canon}_{i}"
                )
                if new_status != st.session_state.pm_candidate_status.get(canon, "candidate"):
                    st.session_state.pm_candidate_status[canon] = new_status
                    st.rerun()

    # ── Step 6: Category tree ──
    st.subheader("6. 层级结构展示")
    model_tree = result.get("model_tree", {})

    if model_tree.get("categories"):
        for cat_node in model_tree["categories"]:
            cat_key = cat_node.get("category_key", "")
            name_cn = cat_node.get("name_cn", cat_key)
            name_en = cat_node.get("name_en", "")
            count = cat_node.get("candidate_count", 0)
            total_ev = cat_node.get("total_evidence_count", 0)

            # Check how many are accepted
            accepted_count = sum(
                1 for c in cat_node.get("candidates", [])
                if st.session_state.pm_candidate_status.get(c.get("canonical_name", "")) == "accepted"
            )

            bar = "█" * min(count, 20)
            st.markdown(f"### 📁 {name_cn} ({name_en})")
            st.progress(min(count / max(1, len(candidates)), 1.0),
                        text=f"{count} candidates, {accepted_count} accepted, {total_ev} total evidence")

            # Show top candidates in this category
            for cand in cat_node.get("candidates", [])[:8]:
                canon = cand.get("canonical_name", "")
                display = cand.get("display_name_en", canon)
                ev_count = len(cand.get("source_literature_ids", []))
                conf = cand.get("confidence_score", 0)
                status = st.session_state.pm_candidate_status.get(canon, "candidate")
                icon = {"accepted": "✅", "rejected": "❌", "candidate": "🔍"}.get(status, "🔍")
                st.markdown(f"  {icon} **{display}** `{canon}` — {ev_count} evidence, conf={conf:.2f}")

    # ── Step 7: Export ──
    st.subheader("7. 导出")

    col_x1, col_x2, col_x3, col_x4 = st.columns(4)

    with col_x1:
        # CSV export
        import csv as _csv, io as _io
        csv_buf = _io.StringIO()
        writer = _csv.writer(csv_buf)
        writer.writerow(["canonical_name", "display_name_en", "category_key", "evidence_count",
                          "confidence_score", "relevance_score", "evidence_strength_score", "status"])
        for c in candidates:
            canon = c.get("canonical_name", "")
            writer.writerow([
                canon, c.get("display_name_en", ""), c.get("category_key", ""),
                len(c.get("source_literature_ids", [])),
                c.get("confidence_score", 0), c.get("relevance_score", 0),
                c.get("evidence_strength_score", 0),
                st.session_state.pm_candidate_status.get(canon, "candidate"),
            ])
        st.download_button("📊 CSV", csv_buf.getvalue().encode("utf-8"),
                           "determinant_candidates.csv", "text/csv")

    with col_x2:
        # JSON export
        import json as _json
        json_data = _json.dumps({
            "model_tree": model_tree,
            "candidates": candidates,
            "evidence_links": result.get("evidence_links_data", []),
        }, ensure_ascii=False, indent=2)
        st.download_button("📦 JSON (完整模型)", json_data.encode("utf-8"),
                           "performance_model.json", "application/json")

    with col_x3:
        # Markdown report
        md_content = result.get("evidence_report", "")
        st.download_button("📝 Markdown 报告", md_content.encode("utf-8"),
                           "evidence_report.md", "text/markdown")

    with col_x4:
        # Save to project
        if st.button("💾 保存到当前项目", help=f"保存到项目 #{project_id}", disabled=(project_id <= 0)):
            if project_id > 0:
                with st.spinner("保存中..."):
                    try:
                        accepted = [
                            c for c in candidates
                            if st.session_state.pm_candidate_status.get(c.get("canonical_name", "")) == "accepted"
                        ]
                        if not accepted:
                            st.warning("没有已接受的候选指标。请先在上方展开证据详情，将需要保存的候选标记为「accepted」。")
                        else:
                            from app.performance_model.pipeline import save_model_to_db as _save
                            pipeline_data = {
                                "candidates": accepted,
                                "evidence_links_data": result.get("evidence_links_data", []),
                            }
                            created = _save(pipeline_data, project_id)
                            st.success(f"已保存到项目 #{project_id}: {created['categories']} 个类别节点, {created['determinants']} 个决定因素, {created['evidence_sources']} 个证据来源")
                    except Exception as e:
                        st.error(f"保存失败: {e}")


# ═══════════════════════════════════════════════════════════════════
#  Page: 免费文献检索增强版
# ═══════════════════════════════════════════════════════════════════

def page_literature_search():
    import pandas as pd

    st.title("🔬 免费文献检索增强版")
    st.caption("多源并行检索 · 去重 · 全文发现 · 混合重排 · 规则证据抽取")

    # ── Search controls ──
    with st.form("lit_search_form"):
        col_q1, col_q2 = st.columns([3, 1])
        with col_q1:
            query = st.text_input(
                "检索关键词",
                value="middle distance running performance determinants VO2max running economy lactate threshold elite athletes",
                help="支持英文关键词，用空格分隔。PubMed/Europe PMC/OpenAlex 均使用英文检索。",
            )
        with col_q2:
            sport_ctx = st.text_input("运动项目（可选）", placeholder="如：800m, figure skating")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            sources = st.multiselect(
                "数据源",
                ["openalex", "pubmed", "europe_pmc", "crossref", "semantic_scholar"],
                default=["openalex", "pubmed", "europe_pmc", "crossref", "semantic_scholar"],
            )
        with col_s2:
            limit_per = st.slider("每源结果数", 5, 50, 15)

        col_opts1, col_opts2, col_opts3 = st.columns(3)
        with col_opts1:
            use_cache = not st.checkbox("强制刷新", value=False, help="跳过缓存重新检索")
            enrich_ft = st.checkbox("开放全文发现", value=True)
        with col_opts2:
            do_rerank = st.checkbox("混合重排", value=True)
        with col_opts3:
            do_extract = st.checkbox("免费内容抽取", value=True)

        submitted = st.form_submit_button("🔍 检索文献", type="primary")

    # ── Search execution ──
    if submitted:
        if not query.strip():
            st.warning("请输入检索关键词")
            return

        from app.literature.connectors.registry import search_all_sources
        from app.literature.dedup import deduplicate_results
        from app.literature.cache import LiteratureCache
        from app.literature.fulltext import enrich_fulltext_links
        from app.literature.ranking import hybrid_rerank
        from app.literature.extraction import batch_extract
        from app.literature.matrix import generate_evidence_matrix

        cache = LiteratureCache()
        cache_key = LiteratureCache.make_cache_key(query, sources)

        # Check cache
        results = []
        cached = False
        if use_cache and not st.session_state.get("lit_force_refresh"):
            cached_q = cache.get_cached_query(cache_key)
            if cached_q:
                cached_rows = cache.get_cached_results(cached_q["id"])
                results = []
                from app.literature.schema import LiteratureResult as LR
                for r in cached_rows:
                    results.append(LR.from_dict(dict(r)))
                cached = True

        if not results:
            with st.spinner("正在检索多个数据源..."):
                search_result = search_all_sources(
                    query=query.strip(),
                    sources=[s for s in sources if s],
                    limit_per_source=limit_per,
                )

            raw_results = search_result["results"]

            with st.spinner("正在去重..."):
                dedup_report = deduplicate_results(raw_results)
                results = dedup_report["results"]

            if enrich_ft:
                with st.spinner("正在发现开放全文链接..."):
                    results = enrich_fulltext_links(results)

            if do_rerank:
                with st.spinner("正在混合重排..."):
                    results = hybrid_rerank(query, results, sport_context=sport_ctx.strip() or None)

            # Cache
            qid = cache.save_query(query.strip(), sources, None, cache_key, len(results))
            cache.save_results(qid, results)
            for src_name, count in search_result.get("source_counts", {}).items():
                cache.log_retrieval(qid, src_name, result_count=count)
        else:
            dedup_report = {"before_count": len(results), "after_count": len(results), "duplicates_removed": 0}
            search_result = {"source_counts": {}, "source_status": [], "errors": []}

        # Store in session
        st.session_state["lit_results"] = results
        st.session_state["lit_query"] = query
        st.session_state["lit_cached"] = cached
        st.session_state["lit_sources"] = sources
        st.session_state["lit_dedup"] = dedup_report
        st.session_state["lit_search_result"] = search_result
        st.session_state["lit_show_extraction"] = do_extract

    # ── Display results ──
    results = st.session_state.get("lit_results", [])
    if not results:
        st.info("请输入关键词并点击「检索文献」开始搜索。默认示例查询：middle distance running performance determinants")
        return

    query = st.session_state.get("lit_query", "")
    cached = st.session_state.get("lit_cached", False)
    dedup_report = st.session_state.get("lit_dedup", {})
    search_result = st.session_state.get("lit_search_result", {})

    st.divider()

    # Summary metrics
    oa_count = sum(1 for r in results if r.open_access)
    pdf_count = sum(1 for r in results if r.pdf_url)
    doi_count = sum(1 for r in results if r.doi)
    abstract_count = sum(1 for r in results if r.abstract and len(r.abstract) > 50)

    col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
    col_m1.metric("去重前", dedup_report.get("before_count", len(results)))
    col_m2.metric("去重后", dedup_report.get("after_count", len(results)))
    col_m3.metric("有DOI", doi_count)
    col_m4.metric("有摘要", abstract_count)
    col_m5.metric("OA全文", oa_count)
    col_m6.metric("PDF", pdf_count)

    if cached:
        st.info("📦 结果来自本地缓存。勾选「强制刷新」可重新检索。")

    # Source counts
    sc = search_result.get("source_counts", {})
    if sc:
        sc_text = " | ".join(f"{k}: {v}" for k, v in sc.items())
        st.caption(f"各来源返回: {sc_text}")

    # Errors/warnings
    for err in search_result.get("errors", []):
        st.warning(f"⚠️ {err['source']}: {err['message']}")

    st.divider()

    # ── Results table ──
    st.subheader(f"检索结果 ({len(results)} 篇)")

    if st.session_state.get("lit_show_extraction", False):
        with st.spinner("正在执行免费规则抽取..."):
            extractions = batch_extract(results)
            st.session_state["lit_extractions"] = extractions
            matrix = generate_evidence_matrix(query, results, extractions)
            st.session_state["lit_matrix"] = matrix
        st.session_state["lit_show_extraction"] = False

    # Display each result
    for i, r in enumerate(results):
        with st.expander(
            f"#{i+1} [{r.year or '?'}] {r.title[:100]}{'...' if len(r.title)>100 else ''} "
            f"| OA:{'+' if r.open_access else '-'} | PDF:{'+' if r.pdf_url else '-'} | "
            f"Score:{r.final_score:.4f}" if r.final_score else f"#{i+1} [{r.year or '?'}] {r.title[:100]}"
        ):
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.markdown(f"**{r.title}**")
                st.caption(
                    f"Authors: {', '.join(r.authors[:5])}{' et al.' if len(r.authors)>5 else ''} | "
                    f"Journal: {r.journal or '—'} | Year: {r.year or '—'}"
                )
                st.caption(f"Sources: {', '.join(r.source_records) if r.source_records else r.source_database} | "
                           f"Citations: {r.citation_count or '—'} | OA: {r.open_access_status or 'unknown'}")

                if r.abstract:
                    st.markdown(r.abstract[:800] + ("..." if len(r.abstract or "") > 800 else ""))

                if r.ranking_explanation:
                    st.caption(f"Ranking: {r.ranking_explanation}")

            with col_d2:
                if r.doi:
                    st.markdown(f"[DOI](https://doi.org/{r.doi})")
                if r.pdf_url:
                    st.markdown(f"[📄 PDF]({r.pdf_url})")
                elif r.fulltext_url:
                    st.markdown(f"[🔗 Fulltext]({r.fulltext_url})")
                if r.url:
                    st.markdown(f"[🌐 Source]({r.url})")

                st.caption(f"DOI: {r.doi or '—'}")
                st.caption(f"PMID: {r.pmid or '—'}")
                st.caption(f"PMCID: {r.pmcid or '—'}")
                st.caption(f"Pub type: {r.publication_type or '—'}")

    # ── Evidence Matrix ──
    matrix = st.session_state.get("lit_matrix")
    if matrix:
        st.divider()
        st.subheader("📊 Evidence Matrix")

        summary = matrix.summary
        if summary:
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("总文献", summary.get("total_papers", 0))
                st.metric("OA全文", summary.get("open_access_count", 0))
                st.metric("有PDF", summary.get("pdf_available_count", 0))
            with col_s2:
                cov = summary.get("extraction_coverage", {})
                for k, v in cov.items():
                    st.caption(f"{k}: {v.get('count', 0)}/{v.get('pct', 0)}%")
            with col_s3:
                conf = summary.get("confidence_distribution", {})
                st.caption(f"Confidence: H:{conf.get('high',0)} M:{conf.get('medium',0)} L:{conf.get('low',0)}")

        # Top variables
        top_vars = summary.get("top_performance_variables", [])
        top_intvs = summary.get("top_interventions", [])
        if top_vars:
            var_items = [f"{v.get('variable', '')}({v.get('count', '')})" for v in top_vars[:8]]
            st.caption(f"Top variables: {', '.join(var_items)}")
        if top_intvs:
            intv_items = [f"{v.get('intervention', '')}({v.get('count', '')})" for v in top_intvs[:8]]
            st.caption(f"Top interventions: {', '.join(intv_items)}")

        # Matrix table
        with st.expander("📋 Evidence Matrix 详情表"):
            rows_data = []
            for ext in (st.session_state.get("lit_extractions") or []):
                rows_data.append({
                    "Title": ext.title[:80] + "..." if len(ext.title) > 80 else ext.title,
                    "Sport": "; ".join(ext.sport[:3]) or "—",
                    "Population": "; ".join(ext.population_level[:3]) or "—",
                    "N": ext.sample_size or "—",
                    "Sex": "; ".join(ext.sex) or "—",
                    "Perf. Variables": "; ".join(ext.performance_variables[:5]) or "—",
                    "Interventions": "; ".join(ext.interventions[:3]) or "—",
                    "Methods": "; ".join(ext.measurement_methods[:3]) or "—",
                    "KPI Candidates": "; ".join(k.get("name", "") for k in ext.kpi_implications[:3]) or "—",
                    "Confidence": ext.confidence,
                    "Key Sentences": ext.key_sentences[0][:100] + "..." if ext.key_sentences else "—",
                })
            if rows_data:
                st.dataframe(pd.DataFrame(rows_data), use_container_width=True, height=400)

    # ── Export ──
    if results:
        st.divider()
        st.subheader("导出")
        col_x1, col_x2, col_x3 = st.columns(3)
        with col_x1:
            # CSV export
            csv_rows = []
            for r in results:
                csv_rows.append({
                    "rank": results.index(r) + 1,
                    "title": r.title,
                    "authors": "; ".join(r.authors),
                    "year": r.year,
                    "doi": r.doi,
                    "pmid": r.pmid,
                    "journal": r.journal,
                    "citation_count": r.citation_count,
                    "open_access": r.open_access,
                    "has_pdf": bool(r.pdf_url),
                    "final_score": r.final_score,
                    "abstract": (r.abstract or "")[:300],
                    "ranking_explanation": r.ranking_explanation,
                })
            csv_df = pd.DataFrame(csv_rows)
            st.download_button("📥 CSV", csv_df.to_csv(index=False).encode("utf-8-sig"),
                               f"literature_search_{len(results)}.csv", "text/csv")

        with col_x2:
            if st.session_state.get("lit_matrix"):
                st.download_button("📝 Markdown Matrix",
                                   matrix.to_markdown().encode("utf-8"),
                                   "evidence_matrix.md", "text/markdown")

        with col_x3:
            import json as _json
            json_data = _json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)
            st.download_button("📦 JSON", json_data.encode("utf-8"),
                               f"literature_results_{len(results)}.json", "application/json")


# ═══════════════════════════════════════════════════════════════════
#  Main: Route to selected page
# ═══════════════════════════════════════════════════════════════════

# Initialize session state
if "selected_kpi" not in st.session_state:
    st.session_state.selected_kpi = None
if "force_project" not in st.session_state:
    st.session_state.force_project = None
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None
if "confirm_delete_name" not in st.session_state:
    st.session_state.confirm_delete_name = None

# Handle project selection from create page
if st.session_state.force_project:
    # Find the project ID matching forced name
    db3 = get_fresh_db()
    try:
        all_projs = crud.get_projects(db3)
        for p in all_projs:
            if p.name == st.session_state.force_project:
                project_id = p.id
                selected_name = p.name
                break
    finally:
        db3.close()
    st.session_state.force_project = None

if project_id <= 0:
    page_create_project()
elif page == "📊 项目总览":
    page_dashboard()
elif page == "🎯 表现目标 PO":
    page_outcomes()
elif page == "🌳 表现模型":
    page_model()
elif page == "📈 KPI 管理":
    page_kpis()
elif page == "🏃 运动员评估":
    page_athletes()
elif page == "📋 干预计划":
    page_interventions()
elif page == "📚 证据资料库":
    page_evidence()
elif page == "📝 报告中心":
    page_reports()
elif page == "🤖 Agent 工作流":
    page_agent()
elif page == "🔬 免费文献检索增强版":
    page_literature_search()
elif page == "🧬 文献→表现模型":
    page_literature_to_performance_model()
