"""Athlete management — list, create, edit, delete athletes."""

import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.athlete_manager import (
    list_athletes, get_athlete, create_athlete, update_athlete,
    delete_athlete, restore_athlete, get_athlete_detail, get_last_entry_date,
)
from src.baseline_calculator import get_baseline_status, rebuild_baseline

st.set_page_config(page_title="运动员管理", page_icon="👥", layout="wide")

# ── CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .athlete-card {
        background: linear-gradient(135deg, #1e2130 0%, #2a2f3f 100%);
        border-radius: 12px; padding: 20px; margin: 8px 0;
        border: 1px solid #3a3f50;
    }
    .baseline-not_started { color: #6b7280; }
    .baseline-in_progress { color: #fbbf24; }
    .baseline-completed { color: #4ade80; }
    .baseline-needs_review { color: #f87171; }
    .deleted-badge { background: #f87171; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────
if "show_deleted" not in st.session_state:
    st.session_state.show_deleted = False
if "editing_athlete" not in st.session_state:
    st.session_state.editing_athlete = None
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None


# ── Callbacks ─────────────────────────────────────────
def toggle_deleted():
    st.session_state.show_deleted = not st.session_state.show_deleted


def start_edit(aid):
    st.session_state.editing_athlete = aid


def cancel_edit():
    st.session_state.editing_athlete = None


def start_delete_confirm(aid):
    st.session_state.confirm_delete = aid


def cancel_delete():
    st.session_state.confirm_delete = None


# ═══════════════════════════════════════════════════════
st.title("👥 运动员数据管理")
st.markdown('<hr style="border-color:#2a2f3f; margin:8px 0 20px 0;">', unsafe_allow_html=True)

# ── Toolbar ──────────────────────────────────────────
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    st.markdown("### 运动员列表")
with col3:
    st.toggle("显示已删除运动员", key="show_deleted_toggle", on_change=toggle_deleted)
with col4:
    if st.button("➕ 新增运动员", type="primary", use_container_width=True):
        st.session_state.editing_athlete = "__new__"

# ── New athlete form ─────────────────────────────────
if st.session_state.editing_athlete == "__new__":
    st.markdown("---")
    st.subheader("📝 新增运动员")

    with st.form("new_athlete_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("姓名 *", placeholder="张三")
            sex = st.selectbox("性别", ["", "男", "女"])
            date_of_birth = st.text_input("出生日期", placeholder="2002-05-12")
        with c2:
            sport = st.text_input("运动项目", placeholder="篮球")
            event_or_position = st.text_input("位置/专项", placeholder="后卫")
            training_level = st.selectbox("训练水平", ["", "业余", "半专业", "专业", "精英"])
        with c3:
            team = st.text_input("队伍", placeholder="A队")
            coach = st.text_input("教练", placeholder="李教练")
        notes = st.text_area("备注", placeholder="伤病史、特殊需求等")

        submitted = st.form_submit_button("✅ 创建运动员", type="primary", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("姓名不能为空")
            else:
                try:
                    profile = create_athlete(
                        name=name, sex=sex, date_of_birth=date_of_birth,
                        sport=sport, event_or_position=event_or_position,
                        training_level=training_level, team=team, coach=coach,
                        notes=notes,
                    )
                    st.success(f"运动员 {profile['name']} 创建成功! ID: {profile['athlete_id']}")
                    st.session_state.editing_athlete = None
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")

    if st.button("❌ 取消", use_container_width=True):
        st.session_state.editing_athlete = None
        st.rerun()


# ── Edit athlete form ────────────────────────────────
if st.session_state.editing_athlete and st.session_state.editing_athlete != "__new__":
    aid = st.session_state.editing_athlete
    profile = get_athlete(aid)
    if profile:
        st.markdown("---")
        st.subheader(f"✏️ 编辑运动员: {profile.get('name', '')} ({aid})")

        with st.form("edit_athlete_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("姓名 *", value=profile.get("name", ""))
                sex = st.selectbox("性别", ["", "男", "女"], index=0 if not profile.get("sex") else (1 if profile.get("sex") == "男" else 2))
                date_of_birth = st.text_input("出生日期", value=profile.get("date_of_birth", ""))
            with c2:
                sport = st.text_input("运动项目", value=profile.get("sport", ""))
                event_or_position = st.text_input("位置/专项", value=profile.get("event_or_position", ""))
                training_level = st.selectbox("训练水平", ["", "业余", "半专业", "专业", "精英"],
                    index=["", "业余", "半专业", "专业", "精英"].index(profile.get("training_level", "")) if profile.get("training_level") in ["业余", "半专业", "专业", "精英"] else 0)
            with c3:
                team = st.text_input("队伍", value=profile.get("team", ""))
                coach = st.text_input("教练", value=profile.get("coach", ""))
            notes = st.text_area("备注", value=profile.get("notes", ""))

            saved = st.form_submit_button("💾 保存修改", type="primary", use_container_width=True)
            if saved:
                updates = {
                    "name": name, "sex": sex, "date_of_birth": date_of_birth,
                    "sport": sport, "event_or_position": event_or_position,
                    "training_level": training_level, "team": team, "coach": coach,
                    "notes": notes,
                }
                update_athlete(aid, updates)
                st.success("已保存!")
                st.session_state.editing_athlete = None
                st.rerun()

    if st.button("❌ 取消编辑", use_container_width=True):
        st.session_state.editing_athlete = None
        st.rerun()


# ── Delete confirmation ──────────────────────────────
if st.session_state.confirm_delete:
    aid = st.session_state.confirm_delete
    profile = get_athlete(aid)
    if profile:
        st.markdown("---")
        st.error(f"⚠️ 确认删除运动员: **{profile.get('name', '')}** ({aid})?")

        c1, c2 = st.columns(2)
        with c1:
            st.warning("**软删除**: 仅隐藏档案，保留全部历史数据")
            if st.button("🗑 软删除", use_container_width=True):
                delete_athlete(aid, hard=False)
                st.success(f"{profile.get('name')} 已软删除")
                st.session_state.confirm_delete = None
                st.rerun()

        with c2:
            st.error("**硬删除**: 永久删除档案及全部关联数据（自动备份）")
            hard_confirm = st.text_input("输入 DELETE 确认硬删除", key="hard_delete_input")
            if st.button("💀 硬删除", type="secondary", use_container_width=True, disabled=(hard_confirm != "DELETE")):
                delete_athlete(aid, hard=True)
                st.success(f"{profile.get('name')} 已硬删除（已自动备份）")
                st.session_state.confirm_delete = None
                st.rerun()

    if st.button("❌ 取消删除", use_container_width=True):
        st.session_state.confirm_delete = None
        st.rerun()


# ── Athlete list ─────────────────────────────────────
st.markdown("---")
athletes = list_athletes(include_deleted=st.session_state.show_deleted)

if not athletes:
    st.info("暂无运动员档案。点击「新增运动员」创建第一个档案。")
else:
    for a in athletes:
        aid = a.get("athlete_id", "")
        is_deleted = not a.get("is_active", True)
        status = get_baseline_status(aid)
        last_date = get_last_entry_date(aid) or "—"

        status_class = f"baseline-{status}" if not is_deleted else ""

        col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 1, 1, 1, 1, 1.2, 1.8])

        with col1:
            name_display = f"{a.get('name', '—')}"
            if is_deleted:
                name_display += ' <span class="deleted-badge">已删除</span>'
            st.markdown(f"**{name_display}**<br><small style='color:#6b7280;'>{aid}</small>", unsafe_allow_html=True)
        with col2:
            st.caption(f"性别: {a.get('sex') or '—'}")
        with col3:
            sport = a.get('sport') or '—'
            pos = a.get('event_or_position') or ''
            st.caption(f"项目: {sport}{' / ' + pos if pos else ''}")
        with col4:
            st.caption(f"水平: {a.get('training_level') or '—'}")
        with col5:
            status_names = {
                'not_started': '未开始', 'in_progress': '进行中',
                'completed': '已完成', 'needs_review': '需复核'
            }
            st.markdown(f"<span class='{status_class}'>{status_names.get(status, status)}</span>", unsafe_allow_html=True)
        with col6:
            st.caption(f"最近: {last_date}")
        with col7:
            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                st.page_link("pages/02_个人数据中心.py", label="📂 数据", icon="📂",
                             use_container_width=True)
            with bc2:
                if not is_deleted:
                    st.button("✏️ 编辑", key=f"edit_{aid}", use_container_width=True,
                              on_click=lambda a=aid: start_edit(a))
            with bc3:
                if not is_deleted:
                    st.button("🗑 删除", key=f"del_{aid}", use_container_width=True,
                              on_click=lambda a=aid: start_delete_confirm(a))
                else:
                    if st.button("♻️ 恢复", key=f"restore_{aid}", use_container_width=True):
                        restore_athlete(aid)
                        st.rerun()

st.markdown("---")
st.caption("运动员数据管理 · 所有数据独立存储于 data/athletes/ 目录")
