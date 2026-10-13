import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
import config
import utils
from data_manager import get_all_excel_data, get_db
import plotly.express as px
import re  

cols_to_drop = ['Parsed_DateTime', 'Parsed_Date', 'Loaded_From_Tab', 'id']

def render_migration_tool():
    st.markdown("---")
    st.subheader("📥 Migrate Multi-Tab Master Database to Supabase")
    st.info("Upload your multi-tab Excel master file (.xlsx) here to bulk-insert all monthly sheets into your database.")
    
    uploaded_file = st.file_uploader("Upload Master Database (.xlsx)", type=["xlsx"], key="mig_file")
    clear_data = st.checkbox("⚠️ Clear existing Supabase data before migrating (Recommended)", value=True)
    
    if uploaded_file and st.button("🚀 Push All Tabs to Supabase", type="primary"):
        with st.spinner("Processing, cleaning, and combining all monthly sheets..."):
            try:
                xls = pd.ExcelFile(uploaded_file)
                all_sheets_data = []
                
                for sheet_name in xls.sheet_names:
                    df_sheet = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                    if not df_sheet.empty:
                        df_sheet['month_tab'] = sheet_name.strip().upper()
                        all_sheets_data.append(df_sheet)
                
                if not all_sheets_data:
                    st.error("❌ No data found across any sheets in the uploaded file.")
                    return
                
                df_mig = pd.concat(all_sheets_data, ignore_index=True)
                
                rename_map = {
                    'Sr. No.': 'sr_no', 'RAKE No': 'rake_no', 'Coal siding/ Company': 'source', '(BOXN / BOBR)': 'wagon_spec',
                    'Receipt Date/Time': 'receipt_dt', 'Placement Date/Time': 'placement_dt', 'U/L End Date/Time': 'ul_end_dt',
                    'Rake Rel. Date/Time': 'release_dt', 'Unloading Duration': 'u_duration', 'Rake Rel. Duration': 'r_duration',
                    'Cycle Time': 'r_duration', 'Demurrage (Hrs)': 'demurrage', 'REMARKS': 'remarks',
                    'NTH': 'nth', 'MUTH': 'muth', 'WT-1': 'wt1', 'WT-2': 'wt2', 'WT-3': 'wt3', 'WT-4': 'wt4', 
                    'GCV': 'gcv', 'VM': 'vm', 'month_tab': 'month_tab', 'Demurrage (in Rs)': 'demurrage_in_rs'
                }
                df_mig = df_mig.rename(columns=rename_map)
                
                valid_columns = list(rename_map.values())
                df_mig = df_mig[[col for col in df_mig.columns if col in valid_columns]]
                
                date_cols = ['receipt_dt', 'placement_dt', 'ul_end_dt', 'release_dt']
                for col in date_cols:
                    if col in df_mig.columns:
                        df_mig[col] = df_mig[col].apply(utils.safe_datetime_parse)
                
                numeric_cols = ['sr_no', 'demurrage', 'demurrage_in_rs', 'nth', 'muth', 'wt1', 'wt2', 'wt3', 'wt4', 'gcv', 'vm']
                for col in numeric_cols:
                    if col in df_mig.columns:
                        def clean_numeric(val):
                            if pd.isna(val): return None
                            try:
                                val_str = str(val).strip()
                                if val_str.upper() in ['XXXX', 'XX', 'NAN', '', 'NONE']: return None
                                match = re.search(r'[-+]?\d*\.\d+|\d+', val_str)
                                if match:
                                    return float(match.group()) if '.' in match.group() else int(match.group())
                            except: pass
                            return None
                        df_mig[col] = df_mig[col].apply(clean_numeric)
                
                from sqlalchemy import create_engine
                db_secrets = st.secrets["connections"]["supabase"]
                db_url = f"postgresql+psycopg2://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['database']}"
                
                engine = create_engine(db_url)
                with engine.begin() as connection:
                    if clear_data:
                        connection.exec_driver_sql("TRUNCATE TABLE rakes_data;")
                    df_mig.to_sql('rakes_data', con=connection, if_exists='append', index=False)
                    
                st.success(f"✅ Successfully migrated {len(df_mig)} total records across {len(xls.sheet_names)} monthly tabs into Supabase!")
                get_all_excel_data.clear() 
            except Exception as e: 
                st.error(f"❌ Error during multi-tab migration: {e}")

def render_yearly_tab(df_all, today_ist):
    st.info("💡 Yearly reports are based on the Financial Year (April 1st to March 31st).")
    current_fy = today_ist.year if today_ist.month >= 4 else today_ist.year - 1
    y_only_sel = st.number_input("Target Financial Year (Start Year e.g., 2025 for FY 25-26):", value=current_fy, step=1, key="y_only")
    
    if st.button("🔍 Generate Yearly", type="primary"):
        with st.spinner("Compiling..."):
            if not df_all.empty and 'Parsed_Date' in df_all.columns:
                filtered_df = df_all[df_all['Parsed_Date'].apply(lambda d: (d.year if d.month >= 4 else d.year - 1) == y_only_sel if pd.notnull(d) else False)]
                
                if filtered_df.empty: st.warning(f"No records for FY {y_only_sel}-{y_only_sel+1}.")
                else:
                    filtered_df = filtered_df.sort_values(by='Parsed_DateTime', ascending=True)
                        
                    display_df = filtered_df.drop(columns=[c for c in cols_to_drop if c in filtered_df.columns], errors='ignore')
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.download_button(f"💾 Download FY {y_only_sel}-{y_only_sel+1} Annual", utils.generate_formatted_excel(filtered_df), file_name=f"Annual_Report_FY_{y_only_sel}_{y_only_sel+1}.xlsx")

def render_mine_wise(df_all, today_ist):
    st.markdown("### 🏭 Mine-Wise Rake Summary")
    st.info("View the total number of rakes received from each Coal Siding or by Parent Company.")
    
    report_type = st.radio("Report Type:", ["Monthly", "Yearly"], horizontal=True, key="mw_type")
    group_by = st.radio("Group Data By:", ["Exact Siding Name (e.g., KDH / CCL)", "Parent Company Only (e.g., CCL)"], horizontal=True, key="mw_group")
    
    cm1, cm2 = st.columns(2, gap="small")
    current_fy = today_ist.year if today_ist.month >= 4 else today_ist.year - 1
    
    if report_type == "Monthly":
        with cm1: mw_month = st.selectbox("Select Month:", range(1, 13), index=today_ist.month - 1, key="mw_month")
        with cm2: mw_year = st.number_input("Select Year:", value=today_ist.year, step=1, key="mw_year")
    else:
        with cm1: mw_year = st.number_input("Select Financial Year (Start Year):", value=current_fy, step=1, key="mw_year")
        mw_month = None
    
    if st.button(f"📊 Generate {report_type} Report", type="primary"):
        with st.spinner("Calculating totals..."):
            if not df_all.empty and 'Parsed_Date' in df_all.columns:
                if report_type == "Monthly": mask = df_all['Parsed_Date'].apply(lambda d: d.month == mw_month and d.year == mw_year if pd.notnull(d) else False)
                else: mask = df_all['Parsed_Date'].apply(lambda d: (d.year if d.month >= 4 else d.year - 1) == mw_year if pd.notnull(d) else False)
                    
                filtered_df = df_all[mask]
                if filtered_df.empty:
                    if report_type == "Monthly": st.warning(f"No records found for {mw_month:02d}/{mw_year}.")
                    else: st.warning(f"No records found for FY {mw_year}-{mw_year+1}.")
                elif 'Coal siding/ Company' in filtered_df.columns:
                    df_mine = filtered_df.copy()
                    df_mine['Coal siding/ Company'] = df_mine['Coal siding/ Company'].astype(str).str.strip().str.upper()
                    
                    if "Company Only" in group_by:
                        def extract_company(val):
                            if '/' in val: return val.split('/')[-1].strip()
                            if '-' in val: return val.split('-')[-1].strip()
                            return val
                        df_mine['Target_Column'] = df_mine['Coal siding/ Company'].apply(extract_company)
                        display_name = 'Parent Company'
                    else:
                        df_mine['Target_Column'] = df_mine['Coal siding/ Company']
                        display_name = 'Coal Siding'

                    summary_df = df_mine.groupby('Target_Column').size().reset_index(name='Total Rakes')
                    summary_df = summary_df.sort_values(by='Total Rakes', ascending=False).reset_index(drop=True)
                    summary_df = summary_df.rename(columns={'Target_Column': display_name})
                    
                    if not summary_df.empty:
                        fig = px.pie(summary_df, values='Total Rakes', names=display_name, title=f"Distribution of Rakes by {display_name} ({report_type})", hole=0.4)
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True)

                    total_rakes = summary_df['Total Rakes'].sum()
                    summary_df.loc[len(summary_df)] = ['TOTAL SUM', total_rakes]
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)

def render_bunching_report(df_all, today_ist):
    st.markdown("<hr style='margin:1em 0;'>", unsafe_allow_html=True)
    st.markdown("### ⏱️ Master Bunching Summary Report")
    report_type = st.radio("Select Timeframe:", ["Daily", "Monthly", "Financial Year", "Custom Range"], horizontal=True, key="br_type")

    cm1, cm2 = st.columns(2, gap="small")
    current_fy = today_ist.year if today_ist.month >= 4 else today_ist.year - 1

    if report_type == "Daily":
        with cm1: target_date = st.date_input("Select Date:", value=today_ist, key="br_date")
    elif report_type == "Monthly":
        with cm1: br_month = st.selectbox("Select Month:", range(1, 13), index=today_ist.month - 1, key="br_mon")
        with cm2: br_year = st.number_input("Select Year:", value=today_ist.year, step=1, key="br_yr")
    elif report_type == "Financial Year":
        with cm1: br_fy = st.number_input("Select Financial Year (Start Year):", value=current_fy, step=1, key="br_fy")
    elif report_type == "Custom Range":
        with cm1: date_range = st.date_input("Select Date Range:", value=(today_ist - timedelta(days=7), today_ist), key="br_range")

    if st.button("📊 Calculate Total Bunching", type="primary"):
        with st.spinner("Extracting bunching data..."):
            if df_all.empty or 'Parsed_DateTime' not in df_all.columns: return
            df_all['Just_Date'] = df_all['Parsed_DateTime'].apply(lambda x: x.date() if pd.notnull(x) else None)

            if report_type == "Daily": mask = df_all['Just_Date'] == target_date
            elif report_type == "Monthly": mask = df_all['Just_Date'].apply(lambda d: d.month == br_month and d.year == br_year if d else False)
            elif report_type == "Financial Year": mask = df_all['Just_Date'].apply(lambda d: (d.year if d.month >= 4 else d.year - 1) == br_fy if d else False)
            elif report_type == "Custom Range":
                if len(date_range) == 2: mask = (df_all['Just_Date'] >= date_range[0]) & (df_all['Just_Date'] <= date_range[1])
                else: return

            filtered_df = df_all[mask].copy()
            if filtered_df.empty: return

            df_boxn = df_all[df_all['(BOXN / BOBR)'].astype(str).str.upper().apply(lambda x: 'N' in str(x) and 'R' not in str(x))].copy()
            df_boxn = df_boxn.dropna(subset=['Parsed_DateTime']).sort_values(by='Parsed_DateTime', ascending=True)

            missing_bunching_map = {}
            for i in range(2, len(df_boxn)):
                rake_1, rake_3 = df_boxn.iloc[i-2], df_boxn.iloc[i]
                dt_1, dt_3 = rake_1.get('Parsed_DateTime'), rake_3.get('Parsed_DateTime')
                if pd.notnull(dt_1) and pd.notnull(dt_3) and isinstance(dt_1, datetime) and isinstance(dt_3, datetime):
                    dt_1_aware, dt_3_aware = config.IST.localize(dt_1), config.IST.localize(dt_3)
                    if dt_3_aware > dt_1_aware and dt_3_aware <= (dt_1_aware + timedelta(hours=5)):
                        b_sec = (dt_1_aware + timedelta(hours=5) - dt_3_aware).total_seconds()
                        if b_sec > 0:
                            b_hrs, b_mins = int(b_sec // 3600), int((b_sec % 3600) // 60)
                            current_remarks = str(rake_3.get('REMARKS', ''))
                            if "BUNCHING" not in current_remarks.upper(): missing_bunching_map[rake_3['RAKE No']] = (b_hrs, b_mins)

            bunching_data = []
            total_bunching_minutes = 0
            cutoff_date = config.IST.localize(datetime(2026, 4, 1, 0, 0))

            for _, row in filtered_df.iterrows():
                rec_dt = row.get('Parsed_DateTime')
                if pd.isnull(rec_dt) or not isinstance(rec_dt, datetime): continue
                rec_dt_aware = config.IST.localize(rec_dt)
                rake_no = str(row.get('RAKE No')); remarks = str(row.get('REMARKS', ''))

                if rec_dt_aware < cutoff_date:
                    if rake_no in missing_bunching_map:
                        hrs, mins = missing_bunching_map[rake_no]
                        total_bunching_minutes += (hrs * 60) + mins
                        bunching_data.append({"Rake No": rake_no, "Receipt Date": row.get('Receipt Date/Time'), "Data Source": "System Calculated (Missed)", "Bunching Time": f"{hrs:02d}:{mins:02d} hrs", "Log Info": "Automatically calculated."})
                    elif "BUNCHING" in remarks.upper():
                        match = re.search(r"BUNCHING.*?(\d{1,2}):(\d{2})", remarks, re.IGNORECASE)
                        if match:
                            hrs, mins = int(match.group(1)), int(match.group(2))
                            total_bunching_minutes += (hrs * 60) + mins
                            bunching_data.append({"Rake No": rake_no, "Receipt Date": row.get('Receipt Date/Time'), "Data Source": "Google Sheet Remark", "Bunching Time": f"{hrs:02d}:{mins:02d} hrs", "Log Info": remarks.replace('\n', ' | ')})
                else:
                    if "BUNCHING" in remarks.upper():
                        match = re.search(r"BUNCHING.*?(\d{1,2}):(\d{2})", remarks, re.IGNORECASE)
                        if match:
                            hrs, mins = int(match.group(1)), int(match.group(2))
                            total_bunching_minutes += (hrs * 60) + mins
                            bunching_data.append({"Rake No": rake_no, "Receipt Date": row.get('Receipt Date/Time'), "Data Source": "Google Sheet Remark", "Bunching Time": f"{hrs:02d}:{mins:02d} hrs", "Log Info": remarks.replace('\n', ' | ')})

            if not bunching_data: st.success("✅ Zero bunching recorded during this period!")
            else:
                total_hrs = total_bunching_minutes // 60
                total_mins = total_bunching_minutes % 60
                m1, m2 = st.columns(2)
                with m1: st.metric("🚂 Total Rakes Affected", len(bunching_data))
                with m2: st.metric("⏱️ Total Bunching Time", f"{total_hrs:02d} hrs {total_mins:02d} mins")
                st.dataframe(pd.DataFrame(bunching_data), use_container_width=True, hide_index=True)

    # --- DIRECT ADMIN DATABASE EDITOR & DELETER ---
    st.markdown("---")
    st.subheader("🛠️ Direct Admin Database Editor & Deleter")
    st.info("Directly delete any historical record bypassing operator time windows.")
    
    if not df_all.empty:
        search_rake = st.text_input("Search Rake No to Delete (e.g., 01/1500):", key="admin_search_rake")
        if search_rake:
            match_df = df_all[df_all['RAKE No'].astype(str).str.contains(search_rake.strip(), case=False, na=False)]
            if match_df.empty:
                st.warning(f"No rake found matching '{search_rake}'.")
            else:
                st.success(f"Found {len(match_df)} record(s).")
                record_options = match_df.apply(lambda row: f"Sr. {row.get('Sr. No.')} | Rake {row.get('RAKE No')} | Date: {row.get('Receipt Date/Time')}", axis=1).tolist()
                selected_option = st.selectbox("Select Record to Delete:", record_options, key="admin_select_record")
                
                selected_idx = record_options.index(selected_option)
                selected_row = match_df.iloc[selected_idx]
                
                if st.button("🗑️ Delete This Record Permanently", type="primary"):
                    try:
                        engine = get_db()
                        rake_to_delete = selected_row.get('RAKE No')
                        sr_to_delete = selected_row.get('Sr. No.')
                        
                        with engine.begin() as conn:
                            conn.exec_driver_sql(
                                "DELETE FROM rakes_data WHERE rake_no = %s AND sr_no = %s;",
                                (rake_to_delete, sr_to_delete)
                            )
                        st.success(f"✅ Successfully deleted Rake {rake_to_delete} (Sr. No. {sr_to_delete}) from Supabase!")
                        get_all_excel_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Deletion failed: {e}")

    render_migration_tool()
