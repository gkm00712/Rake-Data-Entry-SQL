import streamlit as st
import config
from datetime import datetime
from data_manager import save_whiteboard, save_long_outages

def render_header(now_ist):
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; background-color: #f8f9fa; padding: 10px 20px; border-radius: 8px; border: 1px solid #e9ecef;">
            <h3 style="margin: 0; color: #1f77b4; font-family: sans-serif;">🚂 NTPC Unchahar - CHP Rake Operations</h3>
            <p style="margin: 0; font-weight: bold; color: #333;">📅 {now_ist.strftime('%d-%m-%Y %H:%M:%S')} IST</p>
        </div>
    """, unsafe_allow_html=True)

def render_whiteboard(wb_data):
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        col_title, col_add = st.columns([4, 1])
        with col_title:
            st.markdown("##### 📋 Whiteboard / Shift Notes *(Auto-deletes after 24 hours)*")
        
        # --- AVAILABLE TO BOTH: ADD NOTE ---
        with col_add:
            with st.popover("➕ Add Note"):
                with st.form("wb_add_form"):
                    note_title = st.text_input("Title / Shift", value="Shift Note")
                    note_content = st.text_area("Message")
                    submitted = st.form_submit_button("Post Note", type="primary")
                    if submitted and note_content:
                        now_ist = datetime.now(config.IST)
                        wb_data.append({
                            "title": note_title.strip(),
                            "content": note_content.strip(),
                            "timestamp": now_ist.isoformat()
                        })
                        save_whiteboard(wb_data)
                        st.success("✅ Note posted!")
                        st.rerun()

        if not wb_data:
            st.caption("No active shift notes.")
            return
            
        for idx, note in enumerate(wb_data):
            # --- AVAILABLE TO BOTH: DELETE NOTE ---
            cols = st.columns([0.1, 8.5, 0.4])
            with cols[0]:
                st.markdown("📌")
            with cols[1]:
                st.markdown(f"**{note.get('title', 'Note')}**: {note.get('content', '')}")
            
            with cols[2]:
                if st.button("❌", key=f"del_wb_{idx}", help="Delete this whiteboard note"):
                    wb_data.pop(idx)
                    save_whiteboard(wb_data)
                    st.success("✅ Note deleted!")
                    st.rerun()

def render_long_outages(lo_data, today_ist, is_super_admin):
    active_los = [lo for lo in lo_data if lo.get('status') != 'restored']

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        col_title, col_add = st.columns([4, 1])
        with col_title:
            st.markdown("##### 🚨 Active Equipment Long Outages")
            
        # --- AVAILABLE TO BOTH: ADD LONG OUTAGE ---
        with col_add:
            with st.popover("➕ Add Outage"):
                with st.form("lo_add_form"):
                    st.markdown("**Log a New Equipment Outage**")
                    dept = st.selectbox("Department", ["MM", "EMD", "C&I", "OPR", "MGR", "CHEM", "OTHER"])
                    equip = st.text_input("Equipment Name (e.g., STACKER-1)")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        since_date = st.date_input("Since Date", value=today_ist)
                    with col2:
                        since_time = st.time_input("Since Time", step=60)
                        
                    reason = st.text_area("Reason for Outage")
                    affects = st.selectbox("Affects Rake Type", ["BOTH", "N", "R"], help="Which type of rakes does this delay?")
                    
                    submitted = st.form_submit_button("Add Long Outage", type="primary")
                    if submitted and equip and reason:
                        new_lo = {
                            "dept": dept,
                            "equip": equip.strip().upper(),
                            "since_date": since_date.strftime('%d.%m'),
                            "since_time": since_time.strftime('%H:%M') if since_time else "00:00",
                            "reason": reason.strip().upper(),
                            "affects": affects,
                            "status": "ongoing"
                        }
                        lo_data.append(new_lo)
                        save_long_outages(lo_data)
                        st.success("✅ Long Outage Added!")
                        st.rerun()

        if not active_los:
            st.caption("No active long outages.")
            return
            
        for idx, lo in enumerate(lo_data):
            if lo.get('status') == 'restored': continue
            
            dept_lbl = config.DEPT_COLORS.get(lo.get('dept', ''), lo.get('dept', ''))
            equip = lo.get('equip', '')
            since = f"{lo.get('since_date', '')} {lo.get('since_time', '')}"
            reason = lo.get('reason', '')
            
            # Admins get an extra column for Restore & Delete buttons
            cols = st.columns([7.5, 1.5] if is_super_admin else [9.0])
            with cols[0]:
                st.error(f"🔴 **{dept_lbl}** | **{equip}** (Outage Since: {since}) — Reason: *{reason}*")
            
            # --- AVAILABLE TO ADMIN ONLY: RESTORE & DELETE ---
            if is_super_admin:
                with cols[1]:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🔄", key=f"res_lo_{idx}", help="Mark as Restored (Will be automatically logged in the next finalized rake's remarks)"):
                            now_ist = datetime.now(config.IST)
                            lo['status'] = 'restored'
                            lo['rest_date'] = now_ist.strftime('%d.%m')
                            lo['rest_time'] = now_ist.strftime('%H:%M')
                            save_long_outages(lo_data)
                            st.success("✅ Outage restored! It will append to the next submitted rake.")
                            st.rerun()
                    with c2:
                        if st.button("❌", key=f"del_lo_{idx}", help="Delete permanently (Will NOT be logged in any rakes)"):
                            lo_data.pop(idx)
                            save_long_outages(lo_data)
                            st.success("✅ Outage removed!")
                            st.rerun()
