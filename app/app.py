"""
Sports Agent — 运动员监测仪表盘与训练负荷分析
==============================================
主要功能：
  1. 仪表盘: RMSSD / HRrest 趋势 + 移动平均线
  2. 训练负荷: 单日负荷 + 训练单调性双轴折线图
  3. 文献查询: 基于 RAG 的运动科学文献检索
  4. 数据管理: CSV 上传与手动录入
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime, timedelta
import sys

# ── 基础配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="Sports Agent Pro",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 数据路径
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"

# ── 运动员系统 ──────────────────────────────────────────
sys.path.insert(0, str(ROOT))
from src.athlete_manager import list_athletes
from src.baseline_calculator import get_baseline_status, rebuild_baseline
from src.risk_analyzer import analyze_daily_record
from src import athlete_storage as athlete_store


def _athlete_daily_to_dataframes(athlete_id: str):
    """Convert athlete daily_data.json to wellness/training DataFrames."""
    records = athlete_store.load_daily_data(athlete_id)
    if not records:
        return None, None

    import pandas as pd
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # Wellness columns — map hrv→rmssd, resting_hr→hr_rest if present
    wellness_df = pd.DataFrame({"date": df["date"]})
    for src, dst in [("hrv", "rmssd"), ("resting_hr", "hr_rest"),
                      ("sleep_quality", "sleep_quality"), ("fatigue", "fatigue"),
                      ("mood", "mood")]:
        if src in df.columns:
            wellness_df[dst] = df[src]
        else:
            wellness_df[dst] = np.nan

    # Training columns
    training_df = pd.DataFrame({"date": df["date"]})
    for col in ["session_rpe", "duration_min", "training_load"]:
        if col in df.columns:
            training_df[col] = df[col]
        else:
            training_df[col] = np.nan

    if "training_load" in df.columns and df["training_load"].notna().any():
        training_df["acute_load_7d"] = training_df["training_load"].rolling(7, min_periods=4).mean().round(0)
        training_df["chronic_load_28d"] = training_df["training_load"].rolling(28, min_periods=14).mean().round(0)
        chronic_safe = training_df["chronic_load_28d"].replace(0, np.nan)
        training_df["acwr"] = (training_df["acute_load_7d"] / chronic_safe).round(2)
        rolling_mean = training_df["training_load"].rolling(7, min_periods=4).mean()
        rolling_std = training_df["training_load"].rolling(7, min_periods=4).std().replace(0, np.nan)
        training_df["training_monotony"] = (rolling_mean / rolling_std).round(2)
        training_df["training_strain"] = (training_df["acute_load_7d"] * training_df["training_monotony"]).round(0)
    else:
        for col in ["acute_load_7d", "chronic_load_28d", "acwr", "training_monotony", "training_strain"]:
            training_df[col] = np.nan

    return wellness_df, training_df

# ── 工具函数 ──────────────────────────────────────────
@st.cache_data
def load_wellness_data(file=None):
    """加载或生成健康监测数据"""
    if file is not None:
        return pd.read_csv(file, parse_dates=["date"])
    demo = SAMPLE_DIR / "wellness_demo.csv"
    if demo.exists():
        return pd.read_csv(demo, parse_dates=["date"])
    return _generate_empty_wellness()


@st.cache_data
def load_training_data(file=None):
    """加载或生成训练数据"""
    if file is not None:
        return pd.read_csv(file, parse_dates=["date"])
    demo = SAMPLE_DIR / "training_demo.csv"
    if demo.exists():
        return pd.read_csv(demo, parse_dates=["date"])
    return _generate_empty_training()


def _generate_empty_wellness():
    dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
    return pd.DataFrame({
        "date": dates, "rmssd": [np.nan] * 30, "hr_rest": [np.nan] * 30,
        "sleep_quality": [np.nan] * 30, "fatigue": [np.nan] * 30, "mood": [np.nan] * 30,
    })


def _generate_empty_training():
    dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
    return pd.DataFrame({
        "date": dates, "session_rpe": [np.nan] * 30, "duration_min": [np.nan] * 30,
        "training_load": [np.nan] * 30,
    })


def _safe_dropna(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """dropna(subset=cols) without KeyError — missing columns treated as all-NaN."""
    available = [c for c in cols if c in df.columns]
    if not available:
        return pd.DataFrame()
    return df.dropna(subset=available)


def compute_moving_average(series, window=7):
    return series.rolling(window, min_periods=max(2, window // 2)).mean()


def compute_rmssd_zones(rmssd_baseline):
    """RMSSD 正常区间: ±20% 基线"""
    return {
        "optimal": (rmssd_baseline * 0.85, rmssd_baseline * 1.15),
        "warning": (rmssd_baseline * 0.70, rmssd_baseline * 1.30),
    }


def compute_hr_zones(hr_baseline):
    """HRrest 正常区间: ±15% 基线"""
    return {
        "optimal": (hr_baseline * 0.88, hr_baseline * 1.12),
        "warning": (hr_baseline * 0.80, hr_baseline * 1.20),
    }


# ── CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #2a2f3f 100%);
        border-radius: 16px; padding: 24px 28px; margin: 8px 0;
        border: 1px solid #3a3f50;
    }
    .metric-value { font-size: 42px; font-weight: 700; line-height: 1.1; }
    .metric-label { font-size: 13px; color: #8890a0; text-transform: uppercase; letter-spacing: 1px; }
    .metric-delta { font-size: 14px; margin-top: 4px; }
    .status-green  { color: #4ade80; }
    .status-orange { color: #fbbf24; }
    .status-red    { color: #f87171; }
    .status-blue   { color: #60a5fa; }
    hr.divider { border-color: #2a2f3f; margin: 8px 0 20px 0; }
</style>
""", unsafe_allow_html=True)


# ── 侧边栏 ────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/running.png", width=64) if False else None
    st.title("🏃 Sports Agent Pro")

    st.markdown("---")
    page = st.radio(
        "导航", ["📊 仪表盘", "📈 训练负荷分析", "📚 文献查询", "⚙️ 数据管理"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("运动员监测与训练管理平台 v2.0")

    # ── 运动员选择器 ─────────────────────────────────
    athletes = list_athletes(include_deleted=False)

    # No demo fallback — always use real athlete data
    if not athletes:
        # Fallback: use global demo CSVs when no athletes exist
        selected_athlete_id = None
        st.caption("暂无运动员，显示演示数据。请前往「运动员管理」创建档案。")
    else:
        athlete_options = [f"{a['name']} ({a['athlete_id']})" for a in athletes]
        # If session has a previously selected athlete, use it; else default to first
        default_idx = 0
        if "global_athlete_label" in st.session_state:
            try:
                default_idx = athlete_options.index(st.session_state["global_athlete_label"])
            except ValueError:
                default_idx = 0
        selected_athlete_label = st.selectbox(
            "👤 当前运动员", athlete_options,
            index=default_idx, key="global_athlete_select",
        )
        st.session_state["global_athlete_label"] = selected_athlete_label
        selected_athlete_id = selected_athlete_label.split("(")[-1].rstrip(")")

    st.markdown("---")

    # 时间范围选择器（全局）
    # Default to a wide range — will be narrowed by actual data
    default_start = datetime(2025, 1, 1)
    default_end = datetime.now()
    date_range = st.date_input(
        "📅 时间范围",
        value=(default_start, default_end),
    )

    # 移动平均窗口
    ma_windows = st.multiselect(
        "移动平均窗口（天）",
        options=[3, 7, 14, 21, 28],
        default=[7, 14],
    )
    if not ma_windows:
        ma_windows = [7]


# ── 加载数据 ──────────────────────────────────────────
if selected_athlete_id:
    wellness_df, training_df = _athlete_daily_to_dataframes(selected_athlete_id)
    if wellness_df is None or wellness_df.empty:
        wellness_df = _generate_empty_wellness()
    if training_df is None or training_df.empty:
        training_df = _generate_empty_training()
    # Use athlete's personal baseline
    baseline_data = athlete_store.load_baseline(selected_athlete_id)
    if baseline_data.get("baseline_status") == "completed" and baseline_data.get("metrics"):
        bm = baseline_data["metrics"]
        rmssd_baseline = bm.get("hrv", {}).get("mean", 45.0) if "hrv" in bm else 45.0
        hr_baseline = bm.get("resting_hr", {}).get("mean", 55.0) if "resting_hr" in bm else 55.0
    else:
        real_wellness = wellness_df[wellness_df["rmssd"].notna()] if "rmssd" in wellness_df.columns else pd.DataFrame()
        rmssd_baseline = real_wellness["rmssd"].mean() if not real_wellness.empty else 45.0
        real_hr = wellness_df[wellness_df["hr_rest"].notna()] if "hr_rest" in wellness_df.columns else pd.DataFrame()
        hr_baseline = real_hr["hr_rest"].mean() if not real_hr.empty else 55.0
else:
    # Demo fallback — only when zero athletes exist
    wellness_df = load_wellness_data()
    training_df = load_training_data()
    if len(wellness_df) >= 7:
        base14 = wellness_df.head(14)
        rmssd_baseline = base14["rmssd"].mean()
        hr_baseline = base14["hr_rest"].mean()
    else:
        rmssd_baseline = wellness_df["rmssd"].mean() if not wellness_df.empty else 45.0
        hr_baseline = wellness_df["hr_rest"].mean() if not wellness_df.empty else 55.0
    st.info("当前使用演示数据。请在「运动员管理」中创建运动员档案，录入真实数据后将自动切换。")

# 合并数据用于交叉分析
if not wellness_df.empty and not training_df.empty:
    merged_df = pd.merge(wellness_df, training_df, on="date", how="outer", suffixes=("", "_train"))
else:
    merged_df = wellness_df.copy() if not wellness_df.empty else training_df.copy()

# 过滤时间范围
if len(date_range) == 2:
    start_d, end_d = date_range
    wellness_df = wellness_df[(wellness_df["date"] >= pd.Timestamp(start_d)) & (wellness_df["date"] <= pd.Timestamp(end_d))]
    training_df = training_df[(training_df["date"] >= pd.Timestamp(start_d)) & (training_df["date"] <= pd.Timestamp(end_d))]
    merged_df = merged_df[(merged_df["date"] >= pd.Timestamp(start_d)) & (merged_df["date"] <= pd.Timestamp(end_d))]


# ╔══════════════════════════════════════════════════════╗
# ║              📊 仪表盘                               ║
# ╚══════════════════════════════════════════════════════╝
if page == "📊 仪表盘":
    st.title("运动员监测仪表盘")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── 顶部指标卡片行 ──────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)

    hr_valid = _safe_dropna(wellness_df, ["rmssd", "hr_rest"])
    latest = hr_valid.iloc[-1] if not hr_valid.empty else None
    prev = hr_valid.iloc[-2] if len(hr_valid) > 1 else None

    # RMSSD 卡片
    with col1:
        if latest is not None:
            val = latest["rmssd"]
            delta = val - prev["rmssd"] if prev is not None else 0
            pct = abs(delta / rmssd_baseline * 100)
            if 0.85 * rmssd_baseline <= val <= 1.15 * rmssd_baseline:
                color = "status-green"
                status_text = "正常"
            elif 0.70 * rmssd_baseline <= val <= 1.30 * rmssd_baseline:
                color = "status-orange"
                status_text = "关注"
            else:
                color = "status-red"
                status_text = "异常"

            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">RMSSD (ms)</div>
                <div class="metric-value {color}">{val:.0f}</div>
                <div class="metric-delta">{'↑' if delta > 0 else '↓'} {abs(delta):.1f} ms vs 前日</div>
                <div style="font-size:12px; color:#8890a0; margin-top:4px;">基线: {rmssd_baseline:.0f} ms · {status_text}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("暂无 RMSSD 数据")

    # HRrest 卡片
    with col2:
        if latest is not None:
            val = latest["hr_rest"]
            delta = val - prev["hr_rest"] if prev is not None else 0
            if 0.88 * hr_baseline <= val <= 1.12 * hr_baseline:
                color = "status-green"
                status_text = "正常"
            elif 0.80 * hr_baseline <= val <= 1.20 * hr_baseline:
                color = "status-orange"
                status_text = "关注"
            else:
                color = "status-red"
                status_text = "异常"

            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">静息心率 (bpm)</div>
                <div class="metric-value {color}">{val:.0f}</div>
                <div class="metric-delta">{'↑' if delta > 0 else '↓'} {abs(delta):.1f} bpm vs 前日</div>
                <div style="font-size:12px; color:#8890a0; margin-top:4px;">基线: {hr_baseline:.0f} bpm · {status_text}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("暂无 HRrest 数据")

    # ACWR 卡片
    with col3:
        if "acwr" in training_df.columns and not training_df.dropna(subset=["acwr"]).empty:
            latest_tr = training_df.dropna(subset=["acwr"]).iloc[-1]
            acwr = latest_tr["acwr"]
            if 0.8 <= acwr <= 1.3:
                color, risk = "status-green", "安全区"
            elif 0.7 <= acwr <= 1.5:
                color, risk = "status-orange", "警戒区"
            else:
                color, risk = "status-red", "危险区"

            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">ACWR</div>
                <div class="metric-value {color}">{acwr:.2f}</div>
                <div class="metric-delta">急性 {latest_tr.get('acute_load_7d', 0):.0f} / 慢性 {latest_tr.get('chronic_load_28d', 0):.0f}</div>
                <div style="font-size:12px; color:#8890a0; margin-top:4px;">{risk}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("暂无 ACWR 数据")

    # 训练负荷卡片
    with col4:
        if "training_load" in training_df.columns and not training_df.dropna(subset=["training_load"]).empty:
            latest_tr = training_df.dropna(subset=["training_load"]).iloc[-1]
            load = latest_tr["training_load"]
            acute = latest_tr.get("acute_load_7d", np.nan)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">训练负荷 (AU)</div>
                <div class="metric-value status-blue">{load:.0f}</div>
                <div class="metric-delta">7d 均值: {acute:.0f} AU</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("暂无训练数据")

    # 训练单调性卡片
    with col5:
        if "training_monotony" in training_df.columns and not training_df.dropna(subset=["training_monotony"]).empty:
            latest_tr = training_df.dropna(subset=["training_monotony"]).iloc[-1]
            mono = latest_tr["training_monotony"]
            if mono < 1.5:
                color = "status-green"
            elif mono < 2.5:
                color = "status-orange"
            else:
                color = "status-red"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">训练单调性</div>
                <div class="metric-value {color}">{mono:.2f}</div>
                <div class="metric-delta">应变: {latest_tr.get('training_strain', 0):.0f} AU</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("暂无单调性数据")

    # ── RMSSD 趋势图 + 移动平均线 ──────────────────
    st.markdown("---")
    st.subheader("🔬 RMSSD 趋势分析")

    rmssd_data = _safe_dropna(wellness_df, ["rmssd"])

    if not rmssd_data.empty:
        fig_rmssd = go.Figure()

        # 原始数据柱状图
        fig_rmssd.add_trace(go.Bar(
            x=rmssd_data["date"], y=rmssd_data["rmssd"],
            name="每日 RMSSD",
            marker_color="rgba(96, 165, 250, 0.5)",
            marker_line=dict(color="rgba(96, 165, 250, 0.8)", width=1),
            hovertemplate="<b>%{x|%m-%d}</b><br>RMSSD: %{y:.1f} ms<extra></extra>",
        ))

        # 移动平均线
        ma_colors = {3: "#fbbf24", 7: "#4ade80", 14: "#f87171", 21: "#c084fc", 28: "#fb923c"}
        for w in ma_windows:
            ma = compute_moving_average(rmssd_data["rmssd"], w)
            fig_rmssd.add_trace(go.Scatter(
                x=rmssd_data["date"], y=ma,
                mode="lines",
                name=f"{w}日移动均线",
                line=dict(color=ma_colors.get(w, "#60a5fa"), width=2.5 + w * 0.05),
                hovertemplate=f"<b>%{{x|%m-%d}}</b><br>{w}d MA: %{{y:.1f}} ms<extra></extra>",
            ))

        # 基线 ± 区间
        fig_rmssd.add_hline(y=rmssd_baseline, line_dash="dash", line_color="white", opacity=0.4,
                            annotation_text=f"基线 {rmssd_baseline:.0f}", annotation_position="bottom right")
        for pct, color, label in [(0.85, "rgba(251,191,36,0.15)", "-15%"), (1.15, "rgba(251,191,36,0.15)", "+15%")]:
            fig_rmssd.add_hrect(
                y0=rmssd_baseline * 0.7, y1=rmssd_baseline * 0.85,
                fillcolor="rgba(248,113,113,0.08)", line_width=0, name="警告区"
            )
            fig_rmssd.add_hrect(
                y0=rmssd_baseline * 1.15, y1=rmssd_baseline * 1.30,
                fillcolor="rgba(248,113,113,0.08)", line_width=0,
            )

        fig_rmssd.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(orientation="h", yanchor="top", y=1.12, xanchor="left", x=0),
            xaxis=dict(title=None, gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title="RMSSD (ms)", gridcolor="rgba(255,255,255,0.06)"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_rmssd, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
    else:
        st.info("暂无 RMSSD 数据。请上传 CSV 或生成演示数据。")

    # ── HRrest 趋势图 + 移动平均线 ──────────────────
    st.subheader("💓 静息心率趋势分析")

    hr_data = _safe_dropna(wellness_df, ["hr_rest"])

    if not hr_data.empty:
        fig_hr = go.Figure()

        fig_hr.add_trace(go.Bar(
            x=hr_data["date"], y=hr_data["hr_rest"],
            name="每日 HRrest",
            marker_color="rgba(248, 113, 113, 0.4)",
            marker_line=dict(color="rgba(248, 113, 113, 0.7)", width=1),
            hovertemplate="<b>%{x|%m-%d}</b><br>HRrest: %{y:.1f} bpm<extra></extra>",
        ))

        ma_colors = {3: "#fbbf24", 7: "#4ade80", 14: "#60a5fa", 21: "#c084fc", 28: "#fb923c"}
        for w in ma_windows:
            ma = compute_moving_average(hr_data["hr_rest"], w)
            fig_hr.add_trace(go.Scatter(
                x=hr_data["date"], y=ma,
                mode="lines",
                name=f"{w}日移动均线",
                line=dict(color=ma_colors.get(w, "#60a5fa"), width=2.5 + w * 0.05),
                hovertemplate=f"<b>%{{x|%m-%d}}</b><br>{w}d MA: %{{y:.1f}} bpm<extra></extra>",
            ))

        fig_hr.add_hline(y=hr_baseline, line_dash="dash", line_color="white", opacity=0.4,
                         annotation_text=f"基线 {hr_baseline:.0f}", annotation_position="bottom right")
        fig_hr.add_hrect(y0=hr_baseline * 0.8, y1=hr_baseline * 0.88,
                         fillcolor="rgba(248,113,113,0.08)", line_width=0)
        fig_hr.add_hrect(y0=hr_baseline * 1.12, y1=hr_baseline * 1.20,
                         fillcolor="rgba(248,113,113,0.08)", line_width=0)

        fig_hr.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(orientation="h", yanchor="top", y=1.12, xanchor="left", x=0),
            xaxis=dict(title=None, gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title="HRrest (bpm)", gridcolor="rgba(255,255,255,0.06)"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_hr, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
    else:
        st.info("暂无 HRrest 数据。")

    # ── 综合健康概览 ──────────────────────────────
    st.markdown("---")
    st.subheader("📋 综合健康概览")
    c1, c2 = st.columns(2)

    with c1:
        sub = _safe_dropna(wellness_df, ["sleep_quality", "fatigue", "mood"]).tail(30)
        if not sub.empty:

            fig_sub = make_subplots(specs=[[{"secondary_y": False}]])
            for col, name, color in [
                ("sleep_quality", "睡眠质量", "#a78bfa"),
                ("fatigue", "疲劳度", "#fbbf24"),
                ("mood", "情绪", "#4ade80"),
            ]:
                fig_sub.add_trace(go.Scatter(
                    x=sub["date"], y=sub[col], mode="lines+markers",
                    name=name, line=dict(color=color, width=2), marker=dict(size=5),
                ))

            fig_sub.update_layout(
                template="plotly_dark", height=300, margin=dict(l=20, r=20, t=10, b=20),
                legend=dict(orientation="h", yanchor="top", y=1.1),
                yaxis=dict(range=[0.5, 5.5], tickvals=[1, 2, 3, 4, 5], gridcolor="rgba(255,255,255,0.06)"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig_sub, use_container_width=True)
        else:
            st.info("暂无主观感受数据")

    with c2:
        if "acwr" in training_df.columns and not training_df.dropna(subset=["acwr"]).empty:
            sub = training_df.dropna(subset=["acwr"]).tail(30)
            fig_acwr = go.Figure()

            # ACWR 线
            fig_acwr.add_trace(go.Scatter(
                x=sub["date"], y=sub["acwr"],
                mode="lines+markers", name="ACWR",
                line=dict(color="#60a5fa", width=3), marker=dict(size=6),
                hovertemplate="<b>%{x|%m-%d}</b><br>ACWR: %{y:.2f}<extra></extra>",
            ))
            # 安全区
            fig_acwr.add_hrect(y0=0.8, y1=1.3, fillcolor="rgba(74,222,128,0.08)", line_width=0,
                               annotation_text="安全区 (0.8–1.3)", annotation_position="inside")
            fig_acwr.add_hrect(y0=0.5, y1=0.8, fillcolor="rgba(251,191,36,0.06)", line_width=0)
            fig_acwr.add_hrect(y0=1.3, y1=2.0, fillcolor="rgba(251,191,36,0.06)", line_width=0)

            fig_acwr.update_layout(
                template="plotly_dark", height=300, margin=dict(l=20, r=20, t=10, b=20),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(title="ACWR", gridcolor="rgba(255,255,255,0.06)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig_acwr, use_container_width=True)
        else:
            st.info("暂无 ACWR 数据")

    # ── SRSS 恢复压力趋势（仅运动员模式）──────────────
    if selected_athlete_id:
        all_raw = athlete_store.load_daily_data(selected_athlete_id)
        srss_raw = [
            {"date": r["date"], "recovery_avg": r["srss_scored"]["recovery_avg"],
             "stress_avg": r["srss_scored"]["stress_avg"],
             "red_count": len(r.get("srss_red_lights", []))}
            for r in all_raw if "srss_scored" in r and "date" in r
        ]
        if srss_raw:
            srss_df = pd.DataFrame(srss_raw)
            srss_df["date"] = pd.to_datetime(srss_df["date"])
            srss_df = srss_df.sort_values("date")
            if len(date_range) == 2:
                srss_df = srss_df[(srss_df["date"] >= pd.Timestamp(start_d)) & (srss_df["date"] <= pd.Timestamp(end_d))]

            st.markdown("---")
            st.subheader("🫀 SRSS 恢复压力趋势")

            srss_c1, srss_c2 = st.columns(2)

            with srss_c1:
                fig_srss = go.Figure()
                fig_srss.add_trace(go.Scatter(
                    x=srss_df["date"], y=srss_df["recovery_avg"],
                    mode="lines+markers", name="恢复均值",
                    line=dict(color="#4ade80", width=2.5), marker=dict(size=7, color="#4ade80"),
                ))
                fig_srss.add_trace(go.Scatter(
                    x=srss_df["date"], y=srss_df["stress_avg"],
                    mode="lines+markers", name="压力均值",
                    line=dict(color="#f87171", width=2.5), marker=dict(size=7, color="#f87171"),
                ))
                fig_srss.add_hline(y=60, line_dash="dash", line_color="#4ade80", opacity=0.3,
                                   annotation_text="恢复良好线 (60)")
                fig_srss.add_hline(y=35, line_dash="dash", line_color="#f87171", opacity=0.3,
                                   annotation_text="压力较低线 (35)")
                fig_srss.update_layout(
                    template="plotly_dark", height=320,
                    margin=dict(l=20, r=20, t=10, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.05),
                    hovermode="x unified",
                    xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", range=[0, 100], title="得分 (0-100)"),
                )
                st.plotly_chart(fig_srss, use_container_width=True)

            with srss_c2:
                fig_red = go.Figure()
                colors_red = ["#f87171" if c > 0 else "#4ade80" for c in srss_df["red_count"]]
                fig_red.add_trace(go.Bar(
                    x=srss_df["date"], y=srss_df["red_count"],
                    name="红灯数", marker_color=colors_red,
                    text=srss_df["red_count"], textposition="outside",
                ))
                fig_red.update_layout(
                    template="plotly_dark", height=320,
                    margin=dict(l=20, r=20, t=10, b=20),
                    showlegend=False,
                    xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickformat="d", title="红灯数",
                               range=[0, max(8, srss_df["red_count"].max() + 1)]),
                )
                st.plotly_chart(fig_red, use_container_width=True)


# ╔══════════════════════════════════════════════════════╗
# ║           📈 训练负荷分析                            ║
# ╚══════════════════════════════════════════════════════╝
elif page == "📈 训练负荷分析":
    st.title("训练负荷与单调性分析")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    tr_data = training_df.dropna(subset=["training_load"])

    if tr_data.empty:
        st.warning("暂无训练数据。请上传 CSV 文件或生成演示数据。")
        st.stop()

    # ── 核心图表: 训练负荷 + 单调性 双轴折线图 ─────
    st.subheader("📊 单日训练负荷 × 训练单调性")

    # 计算必要的滚动指标（如果尚未在数据中）
    if "training_monotony" not in tr_data.columns:
        rolling_mean = tr_data["training_load"].rolling(7, min_periods=4).mean()
        rolling_std = tr_data["training_load"].rolling(7, min_periods=4).std().replace(0, np.nan)
        tr_data = tr_data.copy()
        tr_data["training_monotony"] = (rolling_mean / rolling_std).round(2)

    if "acute_load_7d" not in tr_data.columns:
        tr_data = tr_data.copy()
        tr_data["acute_load_7d"] = tr_data["training_load"].rolling(7, min_periods=4).mean().round(0)
        tr_data["chronic_load_28d"] = tr_data["training_load"].rolling(28, min_periods=14).mean().round(0)
        tr_data["acwr"] = (tr_data["acute_load_7d"] / tr_data["chronic_load_28d"].replace(0, np.nan)).round(2)

    # 创建双 Y 轴图表
    fig_load = make_subplots(specs=[[{"secondary_y": True}]])

    # 左 Y 轴: 训练负荷（柱状图）
    colors_load = np.where(
        tr_data["training_load"] > tr_data["acute_load_7d"] * 1.5,
        "rgba(248,113,113,0.7)",  # 高负荷红色
        "rgba(96,165,250,0.6)",    # 正常蓝色
    )
    fig_load.add_trace(go.Bar(
        x=tr_data["date"], y=tr_data["training_load"],
        name="单日训练负荷 (AU)",
        marker_color=colors_load,
        marker_line=dict(color="rgba(96,165,250,0.9)", width=0.5),
        hovertemplate="<b>%{x|%m-%d}</b><br>负荷: %{y:.0f} AU<extra></extra>",
    ), secondary_y=False)

    # 左 Y 轴: 7日滚动均线
    fig_load.add_trace(go.Scatter(
        x=tr_data["date"], y=tr_data["acute_load_7d"],
        mode="lines", name="7日急性负荷",
        line=dict(color="#4ade80", width=2.5, dash="solid"),
        hovertemplate="<b>%{x|%m-%d}</b><br>7d负荷: %{y:.0f} AU<extra></extra>",
    ), secondary_y=False)

    # 左 Y 轴: 28日滚动均线
    fig_load.add_trace(go.Scatter(
        x=tr_data["date"], y=tr_data["chronic_load_28d"],
        mode="lines", name="28日慢性负荷",
        line=dict(color="#fbbf24", width=2, dash="dot"),
        hovertemplate="<b>%{x|%m-%d}</b><br>28d负荷: %{y:.0f} AU<extra></extra>",
    ), secondary_y=False)

    # 右 Y 轴: 训练单调性
    mono_data = tr_data.dropna(subset=["training_monotony"])
    if not mono_data.empty:
        # 单调性分段着色
        fig_load.add_trace(go.Scatter(
            x=mono_data["date"], y=mono_data["training_monotony"],
            mode="lines+markers",
            name="训练单调性",
            line=dict(color="#fb923c", width=3),
            marker=dict(
                size=7,
                color=np.where(mono_data["training_monotony"] > 2.0, "#f87171",
                        np.where(mono_data["training_monotony"] > 1.5, "#fbbf24", "#4ade80")),
                line=dict(width=1, color="white"),
                symbol="diamond",
            ),
            hovertemplate="<b>%{x|%m-%d}</b><br>单调性: %{y:.2f}<extra></extra>",
        ), secondary_y=True)

    # 危险区标注
    fig_load.add_hrect(
        y0=0, y1=1.0, fillcolor="rgba(74,222,128,0.04)", line_width=0,
        annotation_text="多变", annotation_position="inside",
        secondary_y=True,
    )
    fig_load.add_hrect(
        y0=1.5, y1=2.5, fillcolor="rgba(251,191,36,0.06)", line_width=0,
        secondary_y=True,
    )
    fig_load.add_hrect(
        y0=2.5, y1=5.0, fillcolor="rgba(248,113,113,0.08)", line_width=0,
        annotation_text="⚠ 高单调性风险", annotation_position="inside",
        secondary_y=True,
    )

    fig_load.update_layout(
        template="plotly_dark",
        height=500,
        margin=dict(l=20, r=60, t=10, b=20),
        legend=dict(orientation="h", yanchor="top", y=1.12, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig_load.update_xaxes(title=None, gridcolor="rgba(255,255,255,0.06)")
    fig_load.update_yaxes(title_text="训练负荷 (AU)", gridcolor="rgba(255,255,255,0.06)", secondary_y=False)
    fig_load.update_yaxes(title_text="训练单调性", gridcolor="rgba(255,255,255,0.06)",
                           range=[0, max(tr_data["training_monotony"].max() * 1.2, 4.0)],
                           secondary_y=True)

    st.plotly_chart(fig_load, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    # ── 应变 vs 负荷 散点图 ───────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🔵 训练应变分析")
        strain_data = tr_data.dropna(subset=["training_strain", "training_monotony"])
        if not strain_data.empty:
            fig_strain = go.Figure()
            fig_strain.add_trace(go.Scatter(
                x=strain_data["date"], y=strain_data["training_strain"],
                mode="lines+markers",
                name="训练应变",
                fill="tozeroy",
                fillcolor="rgba(192,132,252,0.1)",
                line=dict(color="#c084fc", width=2.5),
                marker=dict(size=5, color="#c084fc"),
            ))
            fig_strain.update_layout(
                template="plotly_dark", height=320,
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(title="应变 (AU)", gridcolor="rgba(255,255,255,0.06)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig_strain, use_container_width=True)
        else:
            st.info("暂无应变数据")

    with col_b:
        st.subheader("🔴 负荷-单调性交叉视图")
        cross_data = tr_data.dropna(subset=["acute_load_7d", "training_monotony"])
        if not cross_data.empty:
            fig_cross = go.Figure()
            fig_cross.add_trace(go.Scatter(
                x=cross_data["acute_load_7d"],
                y=cross_data["training_monotony"],
                mode="markers",
                marker=dict(
                    size=10,
                    color=cross_data["training_monotony"],
                    colorscale="RdYlGn_r",
                    showscale=True,
                    colorbar=dict(title="单调性", thickness=12),
                    line=dict(width=1, color="white"),
                ),
                text=[f"{d.strftime('%m-%d')}" for d in cross_data["date"]],
                hovertemplate="<b>%{text}</b><br>7d负荷: %{x:.0f} AU<br>单调性: %{y:.2f}<extra></extra>",
            ))
            # 高风险象限线
            fig_cross.add_vline(x=cross_data["acute_load_7d"].quantile(0.8), line_dash="dash",
                                line_color="rgba(248,113,113,0.5)", annotation_text="高负荷")
            fig_cross.add_hline(y=2.0, line_dash="dash",
                                line_color="rgba(248,113,113,0.5)", annotation_text="高单调")

            fig_cross.update_layout(
                template="plotly_dark", height=320,
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis=dict(title="7日急性负荷 (AU)", gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(title="训练单调性", gridcolor="rgba(255,255,255,0.06)"),
                hovermode="closest",
            )
            st.plotly_chart(fig_cross, use_container_width=True)
        else:
            st.info("数据不足，无法生成交叉视图")

    # ── 数据摘要表 ──────────────────────────────────
    st.markdown("---")
    st.subheader("📋 近 14 天训练数据摘要")

    summary = tr_data.tail(14)[[
        "date", "training_load", "acute_load_7d", "chronic_load_28d",
        "acwr", "training_monotony", "training_strain"
    ]].sort_values("date", ascending=False)

    # 格式化
    display = summary.copy()
    display["date"] = display["date"].dt.strftime("%m-%d")
    for col in ["acute_load_7d", "chronic_load_28d", "training_strain"]:
        if col in display.columns:
            display[col] = display[col].round(0).astype(int)

    st.dataframe(
        display.rename(columns={
            "date": "日期", "training_load": "日负荷",
            "acute_load_7d": "7d负荷", "chronic_load_28d": "28d负荷",
            "acwr": "ACWR", "training_monotony": "单调性",
            "training_strain": "应变",
        }),
        use_container_width=True,
        hide_index=True,
    )


# ╔══════════════════════════════════════════════════════╗
# ║              📚 文献查询 (RAG)                       ║
# ╚══════════════════════════════════════════════════════╝
elif page == "📚 文献查询":
    st.title("运动科学文献检索")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    st.markdown("基于运动科学论文库的智能问答系统。上传 PDF 后运行 `parse_pdfs.py → chunk_texts.py → build_index.py` 构建知识库。")

    query = st.text_input("🔍 输入你的问题", placeholder="例如: 训练负荷与运动损伤的关系是什么？RMSSD 如何用于监测过度训练？")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        top_k = st.slider("返回片段数", 1, 10, 4)
    with col2:
        threshold = st.slider("相似度阈值", 0.0, 1.0, 0.35, 0.05)

    if query.strip():
        # 尝试加载本地索引
        db_dir = ROOT / "db"
        chunks_path = db_dir / "chunks.pkl"
        embeddings_path = db_dir / "embeddings.pkl"

        if chunks_path.exists() and embeddings_path.exists():
            import pickle
            from sentence_transformers import SentenceTransformer

            with st.spinner("正在检索相关文献片段..."):
                try:
                    chunks = pickle.loads(chunks_path.read_bytes())
                    embeddings = pickle.loads(embeddings_path.read_bytes())

                    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
                    q_emb = model.encode([query], normalize_embeddings=True)
                    scores = np.dot(embeddings, q_emb.T).flatten()

                    top_idx = np.argsort(scores)[::-1][:top_k]
                    top_idx = [i for i in top_idx if scores[i] >= threshold]

                    if not top_idx:
                        st.warning("未找到相似度足够高的文献片段。请尝试换个问法。")
                    else:
                        for rank, idx in enumerate(top_idx):
                            chunk = chunks[idx]
                            score = scores[idx]
                            with st.expander(f"#{rank + 1} 「{chunk['doc_id']}」 相似度: {score:.3f}", expanded=(rank == 0)):
                                st.text(chunk["text"][:1500])
                                st.caption(f"Chunk ID: {chunk['chunk_id']}")

                except Exception as e:
                    st.error(f"检索失败: {e}")
        else:
            st.warning("尚未构建知识库索引。请运行: `python scripts/build_index.py`")

            # 展示已解析的文档
            parsed_dir = DATA_DIR / "parsed"
            txt_files = list(parsed_dir.glob("*.txt")) if parsed_dir.exists() else []
            if txt_files:
                st.markdown("**已解析的文档:**")
                for f in txt_files:
                    st.caption(f"📄 {f.stem}")


# ╔══════════════════════════════════════════════════════╗
# ║              ⚙️ 数据管理                             ║
# ╚══════════════════════════════════════════════════════╝
elif page == "⚙️ 数据管理":
    st.title("数据管理")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Quick links to athlete pages ──────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.page_link("pages/01_运动员管理.py", label="👥 运动员管理", icon="👥")
        st.caption("创建、编辑、删除运动员档案")
    with col2:
        st.page_link("pages/02_个人数据中心.py", label="📋 个人数据中心", icon="📋")
        st.caption("每日数据录入、基线建立、趋势分析")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📤 上传 CSV（全局）", "📥 生成演示数据", "🔄 批量导入"])

    with tab1:
        st.subheader("上传 CSV 文件（全局数据，非运动员独立）")
        st.markdown("CSV 需包含 `date` 列（格式 YYYY-MM-DD）。上传后在「当前运动员」选择「全局演示数据」查看。")

        c1, c2 = st.columns(2)
        with c1:
            wellness_file = st.file_uploader("健康监测数据 (RMSSD, HRrest, ...)", type=["csv"], key="wellness")
            if wellness_file:
                df = pd.read_csv(wellness_file)
                st.dataframe(df.head(), use_container_width=True)
                required = ["date", "rmssd", "hr_rest"]
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"缺少必需列: {missing}")
                else:
                    st.success(f"已加载 {len(df)} 行数据")

        with c2:
            training_file = st.file_uploader("训练数据 (training_load, session_rpe, ...)", type=["csv"], key="training")
            if training_file:
                df = pd.read_csv(training_file)
                st.dataframe(df.head(), use_container_width=True)
                required = ["date", "training_load"]
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"缺少必需列: {missing}")
                else:
                    st.success(f"已加载 {len(df)} 行数据")

    with tab2:
        st.subheader("生成演示数据")
        st.markdown("运行以下命令生成 90 天的模拟训练数据：")
        st.code("python data/sample/gen_demo.py", language="bash")

        if st.button("🚀 立即生成", use_container_width=True):
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(SAMPLE_DIR / "gen_demo.py")],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
                st.success("演示数据已生成!")
                st.text(result.stdout)
                if result.stderr:
                    st.warning(result.stderr)
                st.rerun()
            except Exception as e:
                st.error(f"生成失败: {e}")

    with tab3:
        st.subheader("从 CSV 导入到运动员")
        st.markdown("将 CSV 数据批量导入到已创建的运动员档案中。CSV 需包含 `date` 列。")

        athletes = list_athletes(include_deleted=False)
        if not athletes:
            st.warning("请先在「运动员管理」中创建运动员档案。")
        else:
            import_athlete = st.selectbox(
                "目标运动员",
                [f"{a['name']} ({a['athlete_id']})" for a in athletes],
                key="import_athlete",
            )
            import_aid = import_athlete.split("(")[-1].rstrip(")")
            import_file = st.file_uploader("上传 CSV（列名需与运动员数据字段匹配）", type=["csv"], key="import_csv")

            if import_file and st.button("📥 开始导入", use_container_width=True):
                df = pd.read_csv(import_file)
                imported = 0
                for _, row in df.iterrows():
                    record = row.to_dict()
                    record["record_id"] = f"REC_{import_aid}_{record.get('date', '')}_{imported}"
                    record["athlete_id"] = import_aid
                    if "created_at" not in record:
                        record["created_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    athlete_store.add_daily_record(import_aid, record)
                    imported += 1
                rebuild_baseline(import_aid)
                st.success(f"已导入 {imported} 条数据到 {import_athlete}")


# ── 页脚 ──────────────────────────────────────────────
st.markdown("---")
st.caption("Sports Agent Pro · 基于运动科学文献的运动员监测平台 · Powered by Streamlit + Plotly")
