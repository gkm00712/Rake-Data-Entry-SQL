import streamlit as st
import time
from datetime import datetime, timedelta
import config
from data_manager import save_whiteboard, save_long_outages

def render_header(now_ist):
    APP_UPDATE_RELEASE = config.IST.localize(datetime(2026, 4, 1, 7, 0)) 
    show_update_alert = now_ist < APP_UPDATE_RELEASE + timedelta(hours=24)

    if show_update_alert:
        st.success("🚀 **APP UPDATE:** Resolved the Financial Year Rake ID collision issue!")

    col_head, col_sync, col_log = st.columns([6, 1, 1], gap="small")
    with col_head:
        st.markdown("<h1>🚂 Rake Data Entry System</h1>", unsafe_allow_html=True)
        st.caption(f"Logged in as: **{st.session_state.username}** | Role: **{st.session_state.role}**")
    with col_sync:
        st.write("")
        if st.button("🔄 Sync Data", use_container_width=True): 
            from data_manager import get_all_excel_data
            get_all_excel_data.clear()
            st.rerun()
    with col_log:
        st.write("")
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

def render_whiteboard(wb_data):
    with st.expander("📋 Control Room Whiteboard", expanded=bool(wb_data)):
        if not wb_data: st.info("No active notices.")
        else:
            for idx, msg in enumerate(wb_data):
                col_msg, col_del = st.columns([8, 1], gap="small")
                with col_msg: st.markdown(f"🗓️ **[{datetime.fromtimestamp(msg['time'], config.IST).strftime('%d-%b %H:%M')}]** ➔ {msg['text']}")
                with col_del:
                    if st.button("❌", key=f"del_wb_{idx}", use_container_width=True): 
                        wb_data.pop(idx); save_whiteboard(wb_data); st.rerun()

        with st.form("wb_form", clear_on_submit=True):
            col_inp, col_btn = st.columns([5, 1], gap="small")
            with col_inp: new_msg = st.text_input("Post notice...", placeholder="E.g., WT-2 is under maintenance until 14:00", label_visibility="collapsed")
            with col_btn:
                if st.form_submit_button("📌 Post", use_container_width=True) and new_msg.strip():
                    wb_data.append({"text": new_msg.strip(), "time": time.time()}); save_whiteboard(wb_data); st.rerun()

def render_long_outages(lo_data, today_ist, is_super_admin):
    with st.expander("🚨 Active Equipment Long Outages", expanded=bool(lo_data)):
        for idx, lo in enumerate(lo_data):
            dept_label = config.DEPT_COLORS.get(lo['dept'], lo['dept'])
            affects_label = lo.get('affects', 'BOTH')
            aff_text = "" if affects_label == "BOTH" else f" [Applies to {affects_label} Rakes]"
            
            if lo.get('status') == 'restored':
                st.success(f"✅ **RESTORED:** {dept_label} **{lo['equip']}** (Waiting to punch into the next finalized {affects_label} rake)")
                if is_super_admin and st.button("🗑️ Drop Restored", key=f"force_drop_rest_{idx}"):
                    lo_data.pop(idx); save_long_outages(lo_data); st.rerun()
            else:
                st.error(f"🚨 {dept_label} **{lo['equip']}**{aff_text} ➔ Outage since: **{lo['since_date']} {lo['since_time']}**")
                c_d, c_t, c_b1, c_b2 = st.columns([1.5, 1.5, 1.5, 1.5], gap="small")
                with c_d: rest_date = st.date_input("Rest. Date", value=today_ist, key=f"rd_{idx}")
                with c_t: rest_time = st.time_input("Rest. Time", value=None, step=60, key=f"rt_{idx}")
                with c_b1:
                    st.write("")
                    if st.button("✅ Restore", key=f"rbtn_{idx}", use_container_width=True):
                        if rest_time is None: st.error("❌ Time mandatory.")
                        else:
                            lo['status'] = 'restored'; lo['rest_date'] = rest_date.strftime('%d.%m.%Y'); lo['rest_time'] = rest_time.strftime('%H:%M')
                            save_long_outages(lo_data); st.rerun()
                with c_b2:
                    if is_super_admin:
                        st.write("")
                        if st.button("🗑️ Drop", key=f"fdrop_{idx}", type="secondary", use_container_width=True):
                            lo_data.pop(idx); save_long_outages(lo_data); st.rerun()
            st.markdown("<hr style='margin:0.2em 0;'>", unsafe_allow_html=True)

        with st.form("lo_form", clear_on_submit=True):
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2.5, 1.2, 1.5, 1.5, 1.5], gap="small")
            with c1: lo_dept = st.selectbox("Dept", ["MM", "EMD", "C&I", "OPR", "MGR", "CHEM", "OTHER"])
            with c2: lo_equip = st.text_input("Equipment", placeholder="E.g., WT-1 CONVEYOR")
            with c3: lo_affects = st.selectbox("Affects", ["BOTH", "N", "R"])
            with c4: lo_date = st.date_input("Since Date", value=today_ist)
            with c5: lo_time = st.time_input("Since Time", value=None, step=60)
            with c6:
                st.write("")
                if st.form_submit_button("➕ Add Outage", use_container_width=True):
                    if not lo_equip.strip() or lo_time is None: st.error("❌ Equip and Time mandatory.")
                    else:
                        lo_data.append({"dept": lo_dept, "equip": lo_equip.replace("|", "-").strip().upper(), "affects": lo_affects, "status": "active", "since_date": lo_date.strftime('%d.%m.%Y'), "since_time": lo_time.strftime('%H:%M')})
                        save_long_outages(lo_data); st.rerun()
