"""SRSS (Short Recovery and Stress Scale) — recovery-stress monitoring with radar chart & decision support."""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.athlete_manager import list_athletes
from src import athlete_storage as store
from src.data_backup import backup_on_change
from src.srss_analyzer import (
    RECOVERY_ITEMS, STRESS_ITEMS, SRSS_ITEM_ORDER, ALL_SRSS_ITEMS,
    map_raw_to_100, label_recovery, label_stress,
    score_srss_responses, detect_red_light, assess_readiness,
    compare_training_load, get_previous_srss_record, get_same_weekday_load,
    build_radar_data, build_summary_rows,
)

st.set_page_config(page_title="SRSS 恢复压力监控", page_icon="🫀", layout="wide")

# ── CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .srss-card {
        background: linear-gradient(135deg, #1e2130 0%, #2a2f3f 100%);
        border-radius: 12px; padding: 20px; margin: 8px 0;
        border: 1px solid #3a3f50;
    }
    .srss-readiness-good { color: #4ade80; font-weight: 700; font-size: 20px; }
    .srss-readiness-adjust { color: #f87171; font-weight: 700; font-size: 20px; }
    .srss-item-recovery { color: #4ade80; font-weight: 600; }
    .srss-item-stress   { color: #f87171; font-weight: 600; }
    .srss-red-tag {
        background: #f87171; color: white; padding: 2px 8px;
        border-radius: 4px; font-size: 11px; margin: 0 2px;
    }
    .srss-mini-card {
        background: #1a1d2e; border-radius: 10px; padding: 16px;
        margin: 4px 0; border: 1px solid #2a2f3f;
        text-align: center;
    }
    .srss-mini-value { font-size: 28px; font-weight: 700; line-height: 1.2; }
    .srss-mini-label { font-size: 12px; color: #8890a0; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)


# ── Select athlete ────────────────────────────────────
st.title("🫀 SRSS 恢复压力监控")

athletes = list_athletes(include_deleted=False)
if not athletes:
    st.warning("暂无运动员档案。请先在「运动员管理」中创建档案。")
    st.page_link("pages/01_运动员管理.py", label="前往运动员管理")
    st.stop()

athlete_options = {f"{a['name']} ({a['athlete_id']})": a["athlete_id"] for a in athletes}
selected_label = st.selectbox("选择运动员", list(athlete_options.keys()), key="srss_athlete")
athlete_id = athlete_options[selected_label]

all_records = store.load_daily_data(athlete_id)
all_records.sort(key=lambda r: r.get("date", ""), reverse=True)
srss_records = [r for r in all_records if "srss_scored" in r]

# ── Tabs ──────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📝 数据录入", "📊 监控仪表盘", "📈 历史趋势"])

# ╔══════════════════════════════════════════════════════
# Tab 1: Data Entry
# ╔══════════════════════════════════════════════════════
with tab1:
    st.subheader("📝 SRSS 数据录入")

    with st.form("srss_entry_form", clear_on_submit=True):
        entry_date = st.date_input("日期", value=datetime.now())

        # --- SRSS 8 items ---
        st.markdown("#### 恢复量表 Recovery Scale（1-6 → 0-100）")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            s_ppc = st.slider(
                "体能恢复 (PPC)", 1, 6, 4,
                help="强壮·体力充沛·精力充沛·充满力量",
            )
            s_mpc = st.slider(
                "心理恢复 (MPC)", 1, 6, 4,
                help="专心的·能接受新鲜事物·注意力集中·精神警觉",
            )
        with col_r2:
            s_eb = st.slider(
                "情绪平衡 (EB)", 1, 6, 4,
                help="满足·情绪稳定·心情好·一切在掌握之中",
            )
            s_or = st.slider(
                "整体恢复 (OR)", 1, 6, 4,
                help="完全恢复·充分休息·肌肉放松·身体放松",
            )

        st.markdown("#### 压力量表 Stress Scale（1-6 → 0-100）")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            s_ms = st.slider(
                "肌肉压力 (MS)", 1, 6, 3,
                help="肌肉力竭·肌肉疲劳·肌肉酸痛·肌肉僵硬",
            )
            s_la = st.slider(
                "缺乏活力 (LA)", 1, 6, 3,
                help="积极性低·慵懒·缺乏训练热情·无精打采",
            )
        with col_s2:
            s_nes = st.slider(
                "负面情绪 (NES)", 1, 6, 3,
                help="情绪低落·有压力·烦躁·易怒",
            )
            s_os = st.slider(
                "整体压力 (OS)", 1, 6, 3,
                help="疲劳·消耗殆尽·训练过量·精疲力竭",
            )

        st.markdown("---")
        st.markdown("#### CMJ 反向纵跳测试数据")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            cmj_height = st.number_input("跳跃高度 CMJ Height (cm)", 0.0, 100.0, 0.0, 0.01)
        with col_c2:
            cmj_rsimod = st.number_input("改良反应力量指数 CMJ RSImod", 0.0, 100.0, 0.0, 0.01)

        st.markdown("---")
        st.markdown("#### 训练负荷对比")
        prev_week_load = get_same_weekday_load(all_records, entry_date.strftime("%Y-%m-%d"))
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            load_today = st.number_input(
                "训练负荷 (AU)", 0.0, 10000.0, 0.0, 1.0,
                help="昨日或当日训练负荷",
            )
        with col_l2:
            load_prev = st.number_input(
                "前一周同日负荷 (AU)", 0.0, 10000.0,
                value=float(prev_week_load) if prev_week_load else 0.0, step=1.0,
                help="已自动填入 7 天前数据（如存在）",
            )
        if prev_week_load is not None:
            st.caption(f"已从前 7 天数据中自动填入: {prev_week_load} AU")

        notes = st.text_area("备注", placeholder="伤病、特殊情况等（可选）")

        # --- Live preview ---
        st.markdown("---")
        st.markdown("#### 🔍 实时预览")
        responses = {
            "PPC": s_ppc, "MPC": s_mpc, "EB": s_eb, "OR": s_or,
            "MS": s_ms, "LA": s_la, "NES": s_nes, "OS": s_os,
        }
        scored = score_srss_responses(responses)
        red_lights = detect_red_light(responses)
        readiness = assess_readiness(scored, red_lights)

        preview_c1, preview_c2, preview_c3, preview_c4 = st.columns(4)
        with preview_c1:
            st.markdown(f"""
            <div class="srss-mini-card">
                <div class="srss-mini-label">恢复均值</div>
                <div class="srss-mini-value" style="color:#4ade80">{scored['recovery_avg']}</div>
                <div style="font-size:12px; color:#8890a0;">{label_recovery(scored['recovery_avg'])}</div>
            </div>
            """, unsafe_allow_html=True)
        with preview_c2:
            st.markdown(f"""
            <div class="srss-mini-card">
                <div class="srss-mini-label">压力均值</div>
                <div class="srss-mini-value" style="color:#f87171">{scored['stress_avg']}</div>
                <div style="font-size:12px; color:#8890a0;">{label_stress(scored['stress_avg'])}</div>
            </div>
            """, unsafe_allow_html=True)
        with preview_c3:
            status_color = "#4ade80" if readiness["status"] == "good" else "#f87171"
            st.markdown(f"""
            <div class="srss-mini-card">
                <div class="srss-mini-label">准备状态</div>
                <div class="srss-mini-value" style="color:{status_color}; font-size:18px;">
                    {'✅ 良好' if readiness['status'] == 'good' else '⚠️ 需调整'}
                </div>
                <div style="font-size:11px; color:#8890a0;">{readiness['rationale'][:50]}...</div>
            </div>
            """, unsafe_allow_html=True)
        with preview_c4:
            st.markdown(f"""
            <div class="srss-mini-card">
                <div class="srss-mini-label">红灯信号</div>
                <div class="srss-mini-value" style="color:{'#f87171' if red_lights else '#4ade80'};">
                    {len(red_lights)} 个
                </div>
                <div style="font-size:11px; color:#8890a0;">{
                    ', '.join(a['item'] for a in red_lights) if red_lights else '无'
                }</div>
            </div>
            """, unsafe_allow_html=True)

        # --- Mini radar preview ---
        radar_data = build_radar_data(scored)
        fig_preview = go.Figure()
        fig_preview.add_trace(go.Scatterpolar(
            r=radar_data["recovery_values"] + [radar_data["recovery_values"][0]],
            theta=radar_data["recovery_labels"] + [radar_data["recovery_labels"][0]],
            fill="toself", fillcolor="rgba(74,222,128,0.15)",
            line=dict(color="#4ade80", width=2), name="恢复",
        ))
        fig_preview.add_trace(go.Scatterpolar(
            r=radar_data["stress_values"] + [radar_data["stress_values"][0]],
            theta=radar_data["stress_labels"] + [radar_data["stress_labels"][0]],
            fill="toself", fillcolor="rgba(248,113,113,0.12)",
            line=dict(color="#f87171", width=2), name="压力",
        ))
        fig_preview.update_layout(
            template="plotly_dark", height=280,
            margin=dict(l=40, r=40, t=10, b=10),
            polar=dict(radialaxis=dict(range=[0, 100], tickvals=[0, 20, 40, 60, 80, 100])),
            legend=dict(orientation="h", yanchor="bottom", y=1.1),
        )
        st.plotly_chart(fig_preview, use_container_width=True, config={"displayModeBar": False})

        submitted = st.form_submit_button("💾 保存 SRSS 数据", type="primary", use_container_width=True)
        if submitted:
            date_str = entry_date.strftime("%Y-%m-%d")

            # Merge with existing record for the same date to avoid data loss
            existing = next((r for r in all_records if r.get("date") == date_str), None)

            srss_record = {
                "record_id": f"REC_{athlete_id}_{entry_date.strftime('%Y%m%d')}",
                "athlete_id": athlete_id,
                "date": date_str,
                "srss_responses": responses,
                "srss_scored": scored,
                "srss_readiness": readiness,
                "srss_red_lights": red_lights,
                "cmj_height": cmj_height if cmj_height > 0 else None,
                "cmj_rsimod": cmj_rsimod if cmj_rsimod > 0 else None,
                "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }

            if existing:
                # Merge: keep existing wellness fields, add SRSS fields
                merged = {**existing, **srss_record}
                merged["record_id"] = existing.get("record_id", srss_record["record_id"])
            else:
                merged = srss_record

            store.add_daily_record(athlete_id, merged)
            backup_on_change("srss_entry")
            st.success(f"SRSS 数据已保存！({date_str})")
            st.rerun()


# ╔══════════════════════════════════════════════════════
# Tab 2: Monitoring Dashboard
# ╔══════════════════════════════════════════════════════
with tab2:
    st.subheader("📊 SRSS 监控仪表盘")

    if not srss_records:
        st.info("暂无 SRSS 数据。请在「数据录入」标签页添加数据。")
    else:
        dates_with_srss = sorted([r["date"] for r in srss_records], reverse=True)
        view_date = st.selectbox("选择查看日期", dates_with_srss, key="srss_view_date")
        current = next(r for r in srss_records if r["date"] == view_date)

        scored = current["srss_scored"]
        red_lights = current.get("srss_red_lights", detect_red_light(current.get("srss_responses", {})))
        readiness = current.get("srss_readiness", assess_readiness(scored, red_lights))

        # Find previous SRSS record for CMJ comparison
        prev_srss = get_previous_srss_record(srss_records, view_date)

        # Training load comparison
        load_current = current.get("training_load") or all_records_with_load[0].get("training_load") if False else None
        # Look for training_load across all records for this date
        full_record = next((r for r in all_records if r.get("date") == view_date), current)
        load_current = full_record.get("training_load")
        prev_week_load_val = get_same_weekday_load(all_records, view_date)
        load_cmp = compare_training_load(load_current or 0, prev_week_load_val)

        # ── Readiness card ──
        is_good = readiness["status"] == "good"
        st.markdown(f"""
        <div class="srss-card" style="border-left: 4px solid {'#4ade80' if is_good else '#f87171'};">
            <span class="srss-readiness-{'good' if is_good else 'adjust'}">
                {'🟢' if is_good else '🔴'} {readiness['title']}
            </span>
            <p style="color:#8890a0; margin-top:8px;">判定依据：{readiness['rationale']}</p>
            <p style="color:#c0c0c0; margin-top:4px;">建议：{readiness['recommendation']}</p>
            {"".join(
                f'<span class="srss-red-tag">🚨 {a["item"]}: {a["reason"]}</span>'
                for a in red_lights
            ) if red_lights else ''}
        </div>
        """, unsafe_allow_html=True)

        # ── Score summary row ──
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("恢复均值", f"{scored['recovery_avg']:.1f}", delta=label_recovery(scored['recovery_avg']))
        with c2:
            st.metric("压力均值", f"{scored['stress_avg']:.1f}", delta=label_stress(scored['stress_avg']))
        with c3:
            delta_rec = None
            if prev_srss:
                delta_rec = round(scored['recovery_avg'] - prev_srss['srss_scored']['recovery_avg'], 1)
            st.metric("恢复变化", f"{scored['recovery_avg']:.1f}",
                      delta=f"{'+' if delta_rec and delta_rec > 0 else ''}{delta_rec}" if delta_rec else None)
        with c4:
            delta_str = None
            if prev_srss:
                delta_str = round(scored['stress_avg'] - prev_srss['srss_scored']['stress_avg'], 1)
            st.metric("压力变化", f"{scored['stress_avg']:.1f}",
                      delta=f"{'+' if delta_str and delta_str > 0 else ''}{delta_str}" if delta_str else None)
        with c5:
            st.metric("红灯", f"{len(red_lights)} 个",
                      delta="无" if not red_lights else f"{len(red_lights)} 项")

        st.markdown("---")

        # ── Radar chart ──
        radar_data = build_radar_data(scored)
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_data["recovery_values"] + [radar_data["recovery_values"][0]],
            theta=radar_data["recovery_labels"] + [radar_data["recovery_labels"][0]],
            fill="toself", fillcolor="rgba(74,222,128,0.15)",
            line=dict(color="#4ade80", width=2.5),
            name=f"恢复 (均值: {scored['recovery_avg']})",
            marker=dict(size=8, color="#4ade80"),
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_data["stress_values"] + [radar_data["stress_values"][0]],
            theta=radar_data["stress_labels"] + [radar_data["stress_labels"][0]],
            fill="toself", fillcolor="rgba(248,113,113,0.12)",
            line=dict(color="#f87171", width=2.5),
            name=f"压力 (均值: {scored['stress_avg']})",
            marker=dict(size=8, color="#f87171"),
        ))
        # Optional: all-8 combined trace (hidden by default)
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_data["all_values"] + [radar_data["all_values"][0]],
            theta=radar_data["all_labels"] + [radar_data["all_labels"][0]],
            fill="toself", fillcolor="rgba(52,152,219,0.08)",
            line=dict(color="#3498DB", width=1.5, dash="dot"),
            name="全维度 (隐藏)", visible="legendonly",
        ))
        fig_radar.update_layout(
            template="plotly_dark", height=420,
            margin=dict(l=60, r=60, t=20, b=40),
            polar=dict(
                radialaxis=dict(range=[0, 100], tickvals=[0, 20, 40, 60, 80, 100], tickfont=dict(size=10)),
                angularaxis=dict(tickfont=dict(size=11)),
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.08, font=dict(size=11)),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # ── CMJ + Load comparison ──
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### CMJ 反向纵跳对比")
            cmj_curr_h = current.get("cmj_height") or 0
            cmj_curr_r = current.get("cmj_rsimod") or 0
            cmj_prev_h = prev_srss.get("cmj_height") if prev_srss else None
            cmj_prev_r = prev_srss.get("cmj_rsimod") if prev_srss else None

            if cmj_curr_h > 0 or cmj_curr_r > 0:
                fig_cmj = go.Figure()
                categories = []
                curr_vals = []
                prev_vals = []
                if cmj_curr_h > 0:
                    categories.append("CMJ Height (cm)")
                    curr_vals.append(cmj_curr_h)
                    prev_vals.append(cmj_prev_h if cmj_prev_h else None)
                if cmj_curr_r > 0:
                    categories.append("CMJ RSImod")
                    curr_vals.append(cmj_curr_r)
                    prev_vals.append(cmj_prev_r if cmj_prev_r else None)

                fig_cmj.add_trace(go.Bar(
                    name="本次", x=categories, y=curr_vals,
                    marker_color="#3498DB", text=curr_vals, textposition="outside",
                ))
                if any(v is not None for v in prev_vals):
                    fig_cmj.add_trace(go.Bar(
                        name="前次", x=categories, y=prev_vals,
                        marker_color="#BDC3C7", text=[v if v else "" for v in prev_vals],
                        textposition="outside",
                    ))
                fig_cmj.update_layout(
                    template="plotly_dark", height=300,
                    margin=dict(l=20, r=20, t=20, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.05),
                )
                st.plotly_chart(fig_cmj, use_container_width=True)
            else:
                st.caption("暂无 CMJ 数据")

        with col_right:
            st.markdown("#### 训练负荷同比")
            if load_current:
                fig_load = go.Figure()
                labels = ["前一周同日", "本次"]
                bar_vals = [prev_week_load_val or 0, load_current]
                colors = ["#BDC3C7", "#3498DB"]
                fig_load.add_trace(go.Bar(
                    x=labels, y=bar_vals, marker_color=colors,
                    text=bar_vals, textposition="outside",
                ))
                if load_cmp["pct_change"] is not None:
                    pct_text = f"{'+' if load_cmp['pct_change'] > 0 else ''}{load_cmp['pct_change']}%"
                    fig_load.add_annotation(
                        x="本次", y=load_current, text=pct_text,
                        showarrow=False, yshift=25,
                        font=dict(size=16, color="#f87171" if load_cmp['pct_change'] > 10 else "#fbbf24"),
                    )
                fig_load.update_layout(
                    template="plotly_dark", height=300,
                    margin=dict(l=20, r=20, t=20, b=40),
                )
                st.plotly_chart(fig_load, use_container_width=True)
            else:
                st.caption("暂无训练负荷数据")

        # ── Summary table ──
        st.markdown("---")
        st.markdown("#### 指标汇总表")
        rows = build_summary_rows(scored, readiness, load_cmp)
        df_summary = pd.DataFrame(rows)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)


# ╔══════════════════════════════════════════════════════
# Tab 3: History & Trends
# ╔══════════════════════════════════════════════════════
with tab3:
    st.subheader("📈 SRSS 历史趋势")

    if not srss_records:
        st.info("暂无 SRSS 数据可绘制趋势。")
    else:
        # Sort chronologically
        srss_chart = sorted(srss_records, key=lambda r: r["date"])

        # ── Recovery/Stress trend line chart ──
        dates = [r["date"] for r in srss_chart]
        rec_avgs = [r["srss_scored"]["recovery_avg"] for r in srss_chart]
        str_avgs = [r["srss_scored"]["stress_avg"] for r in srss_chart]
        red_counts = [len(r.get("srss_red_lights", [])) for r in srss_chart]

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=dates, y=rec_avgs, mode="lines+markers",
            name="恢复均值", line=dict(color="#4ade80", width=2),
            marker=dict(size=7, color="#4ade80"),
        ))
        fig_trend.add_trace(go.Scatter(
            x=dates, y=str_avgs, mode="lines+markers",
            name="压力均值", line=dict(color="#f87171", width=2),
            marker=dict(size=7, color="#f87171"),
        ))
        # Add readiness bands
        fig_trend.add_hline(y=60, line_dash="dash", line_color="#4ade80", opacity=0.3,
                            annotation_text="恢复良好线 (60)")
        fig_trend.add_hline(y=35, line_dash="dash", line_color="#f87171", opacity=0.3,
                            annotation_text="压力较低线 (35)")
        fig_trend.update_layout(
            template="plotly_dark", height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.05),
            hovermode="x unified",
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)", range=[0, 100]),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # ── Red light count over time ──
        fig_red = go.Figure()
        fig_red.add_trace(go.Bar(
            x=dates, y=red_counts, name="红灯数",
            marker_color=["#f87171" if c > 0 else "#4ade80" for c in red_counts],
            text=red_counts, textposition="outside",
        ))
        fig_red.update_layout(
            template="plotly_dark", height=200,
            margin=dict(l=20, r=20, t=10, b=20),
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickformat="d", title="红灯数"),
        )
        st.plotly_chart(fig_red, use_container_width=True)

        # ── History table ──
        st.markdown("---")
        st.markdown(f"#### 历史记录 ({len(srss_chart)} 条)")

        history_rows = []
        for r in reversed(srss_chart):
            sc = r["srss_scored"]
            rl = r.get("srss_red_lights", [])
            history_rows.append({
                "日期": r["date"],
                "恢复均值": sc["recovery_avg"],
                "压力均值": sc["stress_avg"],
                "PPC": sc["items"]["PPC"]["raw"],
                "MPC": sc["items"]["MPC"]["raw"],
                "EB": sc["items"]["EB"]["raw"],
                "OR": sc["items"]["OR"]["raw"],
                "MS": sc["items"]["MS"]["raw"],
                "LA": sc["items"]["LA"]["raw"],
                "NES": sc["items"]["NES"]["raw"],
                "OS": sc["items"]["OS"]["raw"],
                "CMJ H": r.get("cmj_height") or "-",
                "CMJ RSI": r.get("cmj_rsimod") or "-",
                "红灯": f"{len(rl)} 个",
                "状态": "✅ 良好" if r.get("srss_readiness", {}).get("status") == "good" else "⚠️ 需调整",
            })

        df_history = pd.DataFrame(history_rows)
        st.dataframe(df_history, use_container_width=True, hide_index=True)

        # ── Export ──
        st.markdown("---")
        csv = df_history.to_csv(index=False, encoding="utf-8")
        st.download_button(
            "📥 导出 SRSS 历史数据 CSV",
            data=csv,
            file_name=f"{athlete_id}_srss_history.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.markdown("---")
st.caption(f"SRSS 恢复压力监控 · 当前运动员: {athlete_id}")
