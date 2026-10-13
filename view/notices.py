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
    is_super_admin = (st.session_state.get('role') == "Super Admin")
    
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        col_title, col_add = st.columns([4, 1])
        with col_title:
            st.markdown("##### 📋 Whiteboard / Shift Notes *(Auto-deletes after 24 hours)*")
        with col_add:
            with st.popover("➕ Add Note"):
                with st.form("wb_add_form"):
                    note_title = st.text_input("Title / Shift", value="Shift Note")
                    note_content = st.text_area("Message")
                    submitted = st.form_submit_button("Post Note")
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
            cols = st.columns([0.1, 8.5, 0.4] if is_super_admin else [0.1, 8.9])
            with cols[0]:
                st.markdown("📌")
            with cols[1]:
                st.markdown(f"**{note.get('title', 'Note')}**: {note.get('content', '')}")
            
            # --- ADMIN DELETE BUTTON FOR WHITEBOARD ---
            if is_super_admin:
                with cols[2]:
                    if st.button("❌", key=f"del_wb_{idx}", help="Delete this whiteboard note"):
                        wb_data.pop(idx)
                        save_whiteboard(wb_data)
                        st.success("✅ Note deleted!")
                        st.rerun()

def render_long_outages(lo_data, today_ist, is_super_admin):
    if not lo_data: return
    
    active_los = [lo for lo in lo_data if lo.get('status') != 'restored']
    if not active_los: return

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("##### 🚨 Active Equipment Long Outages")
        
        for idx, lo in enumerate(lo_data):
            if lo.get('status') == 'restored': continue
            
            dept_lbl = config.DEPT_COLORS.get(lo.get('dept', ''), lo.get('dept', ''))
            equip = lo.get('equip', '')
            since = f"{lo.get('since_date', '')} {lo.get('since_time', '')}"
            reason = lo.get('reason', '')
            
            cols = st.columns([8.5, 0.5] if is_super_admin else [9.0])
            with cols[0]:
                st.error(f"🔴 **{dept_lbl}** | **{equip}** (Outage Since: {since}) — Reason: *{reason}*")
            
            if is_super_admin:
                with cols[1]:
                    if st.button("❌", key=f"del_lo_{idx}", help="Delete this long outage"):
                        lo_data.pop(idx)
                        save_long_outages(lo_data)
                        st.success("✅ Outage removed!")
                        st.rerun()
