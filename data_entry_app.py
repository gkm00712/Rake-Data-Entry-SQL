import streamlit as st
from datetime import datetime, timedelta
import config
import auth
from data_manager import get_all_excel_data, load_whiteboard, load_long_outages
from view import notices, form_entry, reports, admin_tools

# 1. Setup & Init
config.setup_page()
config.init_session_state()

# 2. Authentication Gate
if not st.session_state.logged_in:
    auth.login_screen()
    st.stop()

# 3. Time Logic
now_ist = datetime.now(config.IST)
today_ist = now_ist.date()
yesterday_ist = today_ist - timedelta(days=1)
is_super_admin = (st.session_state.role == "Super Admin")
min_date_allowed = None if is_super_admin else yesterday_ist

# 4. Global Data Fetch
df_all = get_all_excel_data()
wb_data = load_whiteboard()
lo_data = load_long_outages()

# 5. Render Header & Notices
notices.render_header(now_ist)
notices.render_whiteboard(wb_data)
notices.render_long_outages(lo_data, today_ist, is_super_admin)

# 6. Render Main Tabs
tabs_list = ["📝 Form Dashboard", "📅 Daily Data", "📆 Monthly Data"]

if is_super_admin: 
    tabs_list.extend(["🗓️ Yearly Data (Admin)", "🏭 Mine-Wise (Admin)", "⚙️ Admin Tools"])

tabs = st.tabs(tabs_list)

with tabs[0]:
    form_entry.render_rake_form(df_all, now_ist, today_ist, min_date_allowed, is_super_admin, lo_data)
with tabs[1]:
    reports.render_daily_tab(df_all, today_ist)
with tabs[2]:
    reports.render_monthly_tab(df_all, today_ist)

if is_super_admin:
    with tabs[3]:
        admin_tools.render_yearly_tab(df_all, today_ist)
    with tabs[4]:
        admin_tools.render_mine_wise(df_all, today_ist)
    with tabs[5]:
        admin_tools.render_bunching_report(df_all, today_ist)
