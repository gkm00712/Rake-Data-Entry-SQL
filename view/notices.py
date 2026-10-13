import streamlit as st
import config
from datetime import datetime
from data_manager import save_whiteboard, save_long_outages

def render_header(now_ist):
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; background-color: #f8f9fa; padding: 10px 20px; border-radius: 8px; border: 1px solid #e9ecef;">
            <h3 style="margin: 0; color: #1f77b4; font-family: sans-serif;">🚂 CHP Operation Rake Data Entry System</h3>
            <p style="margin: 0; font-weight: bold; color: #333;">📅 {now_ist.strftime('%d-%m-%Y %H:%M:%S')} IST</p>
        </div>
    """, unsafe_allow_html=True)

def render_whiteboard(wb_data):
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("##### 📋 Whiteboard / Shift Notes *(Auto-deletes after 24 hours)*")
        
        with st.expander("➕ Add New Shift Note", expanded=False):
            with st.form("wb_add_form", clear_on_submit=True):
                col1, col2 = st.columns([1, 3])
                with col1:
                    note_title = st.text_input("Title / Shift", value="Shift Note")
                with col2:
                    note_content = st.text_input("Message / Instruction")
                    
                submitted = st.form_submit_button("Post Note", type="primary")
                if submitted:
                    if not note_content:
                        st.error("❌ Message cannot be empty!")
                    else:
                        now_ist = datetime.now(config.IST)
                        updated_wb = list(wb_data)
                        updated_wb.append({
                            "title": note_title.strip(),
                            "content": note_content.strip(),
                            "timestamp": now_ist.isoformat()
                        })
                        save_whiteboard(updated_wb)
                        st.rerun()

        if not wb_data:
            st.caption("No active shift notes.")
            return
            
        st.markdown("---")
        for idx, note in enumerate(wb_data):
            time_str = ""
            ts = note.get('timestamp', '')
            if ts:
                try:
                    dt_obj = datetime.fromisoformat(ts)
                    time_str = dt_obj.strftime('%d-%m %H:%M')
                except:
                    time_str = ts
            
            time_display = f" `[{time_str}]`" if time_str else ""
            
            cols = st.columns([0.1, 8.5, 0.4])
            with cols[0]:
                st.markdown("📌")
            with cols[1]:
                st.markdown(f"**{note.get('title', 'Note')}**{time_display}: {note.get('content', '')}")
            
            with cols[2]:
                if st.button("❌", key=f"del_wb_{idx}", help="Delete this whiteboard note"):
                    updated_wb = list(wb_data)
                    updated_wb.pop(idx)
                    save_whiteboard(updated_wb)
                    st.rerun()

def render_long_outages(lo_data, today_ist, is_super_admin):
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("##### 🚨 Active Equipment Long Outages")
            
        with st.expander("➕ Log New Equipment Outage", expanded=False):
            with st.form("lo_add_form", clear_on_submit=True):
                c1, c2, c3, c4, c5 = st.columns([1, 1.5, 1, 1, 1])
                with c1: dept = st.selectbox("Dept", ["MM", "EMD", "C&I", "OPR", "MGR", "CHEM", "OTHER"])
                with c2: equip = st.text_input("Equipment (e.g., WT-1)")
                with c3: since_date = st.date_input("Since Date", value=today_ist)
                with c4: since_time = st.time_input("Since Time", step=60)
                with c5: affects = st.selectbox("Affects", ["BOTH", "N", "R"])
                
                reason = st.text_input("Reason for Outage")
                
                submitted = st.form_submit_button("Add Long Outage", type="primary")
                if submitted:
                    if not equip or not reason:
                        st.error("❌ Both Equipment Name and Reason are mandatory!")
                    else:
                        new_lo = {
                            "dept": dept,
                            "equip": equip.strip().upper(),
                            "since_date": since_date.strftime('%d.%m'),
                            "since_time": since_time.strftime('%H:%M') if since_time else "00:00",
                            "reason": reason.strip().upper(),
                            "affects": affects,
                            "status": "ongoing"
                        }
                        
                        updated_lo = list(lo_data)
                        updated_lo.append(new_lo)
                        save_long_outages(updated_lo)
                        st.rerun()

        active_los = [lo for lo in lo_data if lo.get('status') != 'restored']

        if not active_los:
            st.caption("No active long outages.")
            return
            
        st.markdown("---")
        h1, h2, h3, h4, h5 = st.columns([1.5, 2, 2, 4, 1.5] if is_super_admin else [1.5, 2, 2, 5, 0.1])
        with h1: st.markdown("**Dept**")
        with h2: st.markdown("**Equipment**")
        with h3: st.markdown("**Since**")
        with h4: st.markdown("**Reason**")
        if is_super_admin:
            with h5: st.markdown("**Action**")

        for idx, lo in enumerate(lo_data):
            if lo.get('status') == 'restored': continue
            
            dept_lbl = config.DEPT_COLORS.get(lo.get('dept', ''), lo.get('dept', ''))
            equip = lo.get('equip', '')
            since = f"{lo.get('since_date', '')} {lo.get('since_time', '')}"
            reason = lo.get('reason', '')
            
            cols = st.columns([1.5, 2, 2, 4, 1.5] if is_super_admin else [1.5, 2, 2, 5, 0.1])
            with cols[0]: st.markdown(f"🔴 **{dept_lbl}**")
            with cols[1]: st.markdown(f"**{equip}**")
            with cols[2]: st.markdown(f"{since}")
            with cols[3]: st.markdown(f"*{reason}*")
            
            if is_super_admin:
                with cols[4]:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🔄", key=f"res_lo_{idx}", help="Mark as Restored"):
                            now_ist = datetime.now(config.IST)
                            updated_lo = list(lo_data)
                            updated_lo[idx]['status'] = 'restored'
                            updated_lo[idx]['rest_date'] = now_ist.strftime('%d.%m')
                            updated_lo[idx]['rest_time'] = now_ist.strftime('%H:%M')
                            save_long_outages(updated_lo)
                            st.rerun()
                    with c2:
                        if st.button("❌", key=f"del_lo_{idx}", help="Delete permanently"):
                            updated_lo = list(lo_data)
                            updated_lo.pop(idx)
                            save_long_outages(updated_lo)
                            st.rerun()
