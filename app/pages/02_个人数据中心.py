"""Individual athlete data center — daily entry, baseline, history, trends."""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.athlete_manager import list_athletes, get_athlete_detail, get_last_entry_date
from src.baseline_calculator import (
    get_valid_baseline_records, rebuild_baseline, get_baseline_status,
    compute_wellness_score, compute_training_load, is_valid_baseline_day,
)
from src.risk_analyzer import analyze_daily_record
from src import athlete_storage as store
from src.data_backup import backup_on_change

st.set_page_config(page_title="个人数据中心", page_icon="📋", layout="wide")

# ── CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .info-card {
        background: linear-gradient(135deg, #1e2130 0%, #2a2f3f 100%);
        border-radius: 12px; padding: 16px 20px; margin: 4px 0;
        border: 1px solid #3a3f50;
    }
    .risk-green  { color: #4ade80; font-weight: 700; }
    .risk-yellow { color: #fbbf24; font-weight: 700; }
    .risk-red    { color: #f87171; font-weight: 700; }
    .baseline-not_started { color: #6b7280; }
    .baseline-in_progress { color: #fbbf24; }
    .baseline-completed { color: #4ade80; }
    .baseline-needs_review { color: #f87171; }
</style>
""", unsafe_allow_html=True)


# ── Select athlete ────────────────────────────────────
st.title("📋 个人数据中心")

athletes = list_athletes(include_deleted=False)
if not athletes:
    st.warning("暂无运动员档案。请先在「运动员管理」中创建档案。")
    st.page_link("pages/01_运动员管理.py", label="👉 前往运动员管理")
    st.stop()

# Build athlete selector
athlete_options = {f"{a['name']} ({a['athlete_id']})": a["athlete_id"] for a in athletes}
selected_label = st.selectbox("选择运动员", list(athlete_options.keys()), key="athlete_selector")
athlete_id = athlete_options[selected_label]

# Load data
profile = get_athlete_detail(athlete_id)
if not profile:
    st.error("无法加载运动员数据")
    st.stop()

baseline = store.load_baseline(athlete_id)
daily_records = store.load_daily_data(athlete_id)
daily_records.sort(key=lambda r: r.get("date", ""), reverse=True)

# ── Tabs ──────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 概览 & 基线", "✏️ 每日录入", "📋 历史数据", "📈 趋势图表"])

# ╔══════════════════════════════════════════════════════
# Tab 1: Overview & Baseline
# ╔══════════════════════════════════════════════════════
with tab1:
    # --- Info card ---
    status = get_baseline_status(athlete_id)
    valid_days = get_valid_baseline_records(athlete_id)
    last_date = get_last_entry_date(athlete_id) or "—"

    st.markdown("### 运动员信息")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="info-card">
            <small style="color:#8890a0;">姓名</small><br>
            <strong>{profile.get('name', '—')}</strong><br>
            <small style="color:#6b7280;">{athlete_id}</small>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="info-card">
            <small style="color:#8890a0;">项目 / 位置</small><br>
            <strong>{profile.get('sport') or '—'} / {profile.get('event_or_position') or '—'}</strong><br>
            <small style="color:#6b7280;">{profile.get('training_level') or '—'} · {profile.get('team') or '—'}</small>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        status_cn = {"not_started": "未开始", "in_progress": "进行中", "completed": "已完成", "needs_review": "需复核"}
        st.markdown(f"""
        <div class="info-card">
            <small style="color:#8890a0;">基线状态</small><br>
            <strong class="baseline-{status}">{status_cn.get(status, status)}</strong><br>
            <small style="color:#6b7280;">有效天数: {len(valid_days)} / 5</small>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="info-card">
            <small style="color:#8890a0;">数据概览</small><br>
            <strong>{len(daily_records)} 条记录</strong><br>
            <small style="color:#6b7280;">最近录入: {last_date}</small>
        </div>
        """, unsafe_allow_html=True)

    # --- Baseline progress ---
    st.markdown("---")
    st.subheader("🔬 基线建立进度")

    if status == "not_started":
        st.info("尚未录入任何数据。请在「每日录入」标签页中开始录入数据。需要至少 5 天有效数据以建立个人基线。")
    elif status == "in_progress":
        pct = len(valid_days) / 5 * 100
        st.progress(pct / 100, text=f"有效基线天数: {len(valid_days)} / 5")
        st.info(f"还差 {5 - len(valid_days)} 天有效数据即可完成基线。请继续录入每日数据。")

        if valid_days:
            st.caption(f"已有有效数据日期: {', '.join(d['date'] for d in valid_days)}")
    elif status == "completed":
        st.success(f"✅ 个人基线已完成！基于 {len(valid_days)} 天有效数据建立。后续数据将自动与该基线比较。")

        # Show baseline metrics table
        metrics = baseline.get("metrics", {})
        if metrics:
            st.markdown("**基线指标详情:**")
            rows = []
            for metric, stats in metrics.items():
                rows.append({
                    "指标": metric,
                    "均值": stats["mean"],
                    "标准差": stats["sd"],
                    "正常范围": f"{stats['normal_low']} ~ {stats['normal_high']}",
                    "警戒范围": f"{stats['caution_low']} ~ {stats['caution_high']}",
                })
            df_baseline = pd.DataFrame(rows)
            st.dataframe(df_baseline, use_container_width=True, hide_index=True)

        # --- Compare latest day ---
        if daily_records:
            latest = daily_records[0]
            if latest.get("date") not in [d["date"] for d in valid_days]:
                st.markdown("---")
                st.subheader("📊 最新数据 vs 个人基线")

                analysis = analyze_daily_record(latest, baseline)
                st.markdown(f"**{analysis['summary']}**")

                if analysis.get("alerts"):
                    for alert in analysis["alerts"]:
                        emoji = "🔴" if alert["level"] == "red" else "🟡"
                        st.markdown(
                            f"{emoji} **{alert['metric']}**: {alert['direction']} "
                            f"(值={alert['value']}, 基线均值={alert['baseline_mean']}, z={alert['z_score']})"
                        )

        if st.button("🔄 重新计算基线", use_container_width=True):
            rebuild_baseline(athlete_id)
            st.rerun()


# ╔══════════════════════════════════════════════════════
# Tab 2: Daily Entry
# ╔══════════════════════════════════════════════════════
with tab2:
    st.subheader("✏️ 每日数据录入")

    with st.form("daily_entry_form", clear_on_submit=True):
        entry_date = st.date_input("日期", value=datetime.now())

        st.markdown("**主观恢复指标** (1-10)")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            sleep_hours = st.number_input("睡眠时长 (h)", 0.0, 24.0, 8.0, 0.5)
        with c2:
            sleep_quality = st.slider("睡眠质量", 1, 10, 7)
        with c3:
            fatigue = st.slider("疲劳度", 1, 10, 3)
        with c4:
            muscle_soreness = st.slider("肌肉酸痛", 1, 10, 2)
        with c5:
            mood = st.slider("情绪", 1, 10, 7)

        st.markdown("**生理指标**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            stress = st.slider("压力", 1, 10, 3)
        with c2:
            resting_hr = st.number_input("静息心率 (bpm)", 30, 120, 55, 1)
        with c3:
            hrv = st.number_input("HRV (ms)", 0.0, 200.0, 45.0, 1.0)
        with c4:
            body_weight = st.number_input("体重 (kg)", 30.0, 200.0, 70.0, 0.1)

        st.markdown("**训练负荷指标**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            training_type = st.selectbox("训练类型", ["", "力量训练", "耐力训练", "速度训练", "技术训练", "恢复", "比赛", "其他"])
        with c2:
            duration_min = st.number_input("训练时长 (分钟)", 0, 300, 60, 5)
        with c3:
            session_rpe = st.slider("Session RPE", 1, 10, 6)

        # Auto-calc
        training_load = duration_min * session_rpe
        wellness_score = sleep_quality + mood - fatigue - muscle_soreness - stress
        with c4:
            st.metric("训练负荷 (AU)", f"{training_load:.0f}", delta=None)
            st.metric("恢复指数", f"{wellness_score:.0f}", delta=None)

        notes = st.text_area("备注", placeholder="伤病、特殊情况等")

        submitted = st.form_submit_button("💾 保存数据", type="primary", use_container_width=True)
        if submitted:
            record = {
                "record_id": f"REC_{athlete_id}_{entry_date.strftime('%Y%m%d')}",
                "athlete_id": athlete_id,
                "date": entry_date.strftime("%Y-%m-%d"),
                "sleep_hours": sleep_hours,
                "sleep_quality": sleep_quality,
                "fatigue": fatigue,
                "muscle_soreness": muscle_soreness,
                "mood": mood,
                "stress": stress,
                "resting_hr": resting_hr if resting_hr > 0 else None,
                "hrv": hrv if hrv > 0 else None,
                "body_weight": body_weight if body_weight > 0 else None,
                "training_type": training_type,
                "duration_min": duration_min,
                "session_rpe": session_rpe,
                "training_load": training_load,
                "wellness_score": wellness_score,
                "notes": notes,
                "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }

            store.add_daily_record(athlete_id, record)
            rebuild_baseline(athlete_id)
            backup_on_change("daily_entry")

            # Show baseline comparison if completed
            current_baseline = store.load_baseline(athlete_id)
            if current_baseline.get("baseline_status") == "completed":
                st.success("数据已保存！基线比对结果：")
                analysis = analyze_daily_record(record, current_baseline)
                st.markdown(f"**{analysis['summary']}**")
            else:
                valid_after = get_valid_baseline_records(athlete_id)
                st.success(f"数据已保存！当前有效基线天数: {len(valid_after)} / 5")

            st.rerun()


# ╔══════════════════════════════════════════════════════
# Tab 3: History
# ╔══════════════════════════════════════════════════════
with tab3:
    st.subheader("📋 历史数据")

    if not daily_records:
        st.info("暂无数据。请在「每日录入」标签页添加数据。")
    else:
        st.caption(f"共 {len(daily_records)} 条记录 · 按日期倒序排列")

        # Build display dataframe
        display_cols = [
            "date", "sleep_hours", "sleep_quality", "fatigue", "muscle_soreness",
            "mood", "stress", "resting_hr", "hrv", "body_weight",
            "training_type", "duration_min", "session_rpe", "training_load", "wellness_score",
        ]
        df = pd.DataFrame(daily_records)
        for c in display_cols:
            if c not in df.columns:
                df[c] = None
        df_display = df[display_cols].copy()

        # Mark valid baseline days
        valid_dates = {r["date"] for r in get_valid_baseline_records(athlete_id)}
        df_display["基线有效"] = df_display["date"].apply(lambda d: "✅" if d in valid_dates else "❌")

        st.dataframe(
            df_display.rename(columns={
                "date": "日期", "sleep_hours": "睡眠(h)", "sleep_quality": "睡眠质量",
                "fatigue": "疲劳", "muscle_soreness": "酸痛", "mood": "情绪", "stress": "压力",
                "resting_hr": "HRrest", "hrv": "HRV", "body_weight": "体重",
                "training_type": "训练类型", "duration_min": "时长(min)", "session_rpe": "RPE",
                "training_load": "负荷", "wellness_score": "恢复指数",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # --- Edit / Delete ---
        st.markdown("---")
        st.subheader("✏️ 编辑 / 删除单日数据")

        record_dates = [r.get("date", "") for r in daily_records]
        edit_date = st.selectbox("选择要编辑的日期", record_dates, key="edit_date_select")

        target = next((r for r in daily_records if r.get("date") == edit_date), None)

        if target:
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("🗑 删除该日数据", type="secondary", use_container_width=True):
                    confirm_key = f"confirm_del_{edit_date}"
                    if confirm_key not in st.session_state:
                        st.session_state[confirm_key] = True
                    else:
                        store.delete_daily_record(athlete_id, target["record_id"])
                        rebuild_baseline(athlete_id)
                        backup_on_change("delete_entry")
                        del st.session_state[confirm_key]
                        st.success(f"已删除 {edit_date} 的数据")
                        st.rerun()

                if st.session_state.get(f"confirm_del_{edit_date}"):
                    st.warning("再次点击确认删除")

            with c2:
                st.json(target)

        # Export
        st.markdown("---")
        csv = df_display.to_csv(index=False, encoding="utf-8")
        st.download_button(
            "📥 导出 CSV", data=csv,
            file_name=f"{athlete_id}_daily_data.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ╔══════════════════════════════════════════════════════
# Tab 4: Trend Charts
# ╔══════════════════════════════════════════════════════
with tab4:
    st.subheader("📈 趋势图表")

    if not daily_records:
        st.info("暂无数据可绘制图表。")
    else:
        df_chart = pd.DataFrame(daily_records)
        df_chart["date"] = pd.to_datetime(df_chart["date"])
        df_chart = df_chart.sort_values("date")

        # Chart groups
        chart_groups = {
            "主观恢复": [
                ("sleep_hours", "睡眠时长 (h)", "#a78bfa"),
                ("sleep_quality", "睡眠质量", "#818cf8"),
                ("fatigue", "疲劳度", "#fbbf24"),
                ("muscle_soreness", "肌肉酸痛", "#f87171"),
                ("mood", "情绪", "#4ade80"),
                ("stress", "压力", "#fb923c"),
            ],
            "生理指标": [
                ("resting_hr", "静息心率 (bpm)", "#f87171"),
                ("hrv", "HRV (ms)", "#60a5fa"),
                ("body_weight", "体重 (kg)", "#c084fc"),
            ],
            "训练负荷": [
                ("training_load", "训练负荷 (AU)", "#60a5fa"),
                ("duration_min", "训练时长 (min)", "#fbbf24"),
                ("session_rpe", "Session RPE", "#fb923c"),
                ("wellness_score", "恢复指数", "#4ade80"),
            ],
        }

        for group_name, metrics in chart_groups.items():
            st.markdown(f"**{group_name}**")
            available = [(col, name, color) for col, name, color in metrics if col in df_chart.columns and df_chart[col].notna().any()]
            if not available:
                st.caption("暂无数据")
                continue

            # Select which metrics to show
            selected = st.multiselect(
                f"选择指标", [name for _, name, _ in available],
                default=[name for _, name, _ in available][:min(3, len(available))],
                key=f"chart_{group_name}",
                label_visibility="collapsed",
            )

            if selected:
                fig = go.Figure()
                for col, name, color in available:
                    if name in selected:
                        fig.add_trace(go.Scatter(
                            x=df_chart["date"], y=df_chart[col],
                            mode="lines+markers", name=name,
                            line=dict(color=color, width=2), marker=dict(size=5),
                        ))

                # Add baseline reference lines if completed
                if status == "completed" and baseline.get("metrics"):
                    for col, name, color in available:
                        if name in selected and col in baseline["metrics"]:
                            bm = baseline["metrics"][col]
                            fig.add_hline(y=bm["mean"], line_dash="dash", line_color=color, opacity=0.4,
                                          annotation_text=f"{name}基线")

                fig.update_layout(
                    template="plotly_dark", height=300,
                    margin=dict(l=20, r=20, t=10, b=20),
                    legend=dict(orientation="h", yanchor="top", y=1.1),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

st.markdown("---")
st.caption(f"当前运动员: {profile.get('name')} ({athlete_id}) · 数据独立存储")
