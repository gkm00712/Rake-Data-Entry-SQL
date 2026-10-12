import streamlit as st
import pandas as pd
import requests
import io
import time
import json
import os
import threading
import gc
from datetime import datetime
import config
import utils

file_lock = threading.Lock()
QUALITY_FILE = "quality_data.xlsx"

# --- NEW: GCV / VM VLOOKUP LOGIC ---
def lookup_gcv_vm(mine_input, company_input):
    if not os.path.exists(QUALITY_FILE):
        return None, None

    try:
        df = pd.read_excel(QUALITY_FILE, engine='openpyxl', header=None)
        mine_search = str(mine_input).strip().upper()
        co_search = str(company_input).strip().upper()
        
        # Mapping: 
        # H(7),I(8)->K(10),L(11) | P(15),Q(16)->S(18),T(19) | X(23),Y(24)->AA(26),AB(27) | AF(31),AG(32)->AI(34),AJ(35)
        search_sets = [
            (7, 8, 10, 11),
            (15, 16, 18, 19),
            (23, 24, 26, 27),
            (31, 32, 34, 35)
        ]
        
        mine_only_match = None
        
        for m_col, c_col, g_col, v_col in search_sets:
            if m_col >= len(df.columns) or v_col >= len(df.columns):
                continue
                
            for _, row in df.iterrows():
                sheet_mine = str(row[m_col]).strip().upper()
                sheet_co = str(row[c_col]).strip().upper()
                
                if not sheet_mine or sheet_mine == "NAN":
                    continue
                
                if sheet_mine == mine_search:
                    raw_gcv = row[g_col]
                    raw_vm = row[v_col]
                    
                    try: final_gcv = int(float(raw_gcv))
                    except: final_gcv = 0
                    
                    try: final_vm = round(float(raw_vm), 2)
                    except: final_vm = 0.00
                    
                    if final_gcv > 0:
                        # 1. Highest Priority: Exact match on both Mine and Company
                        if sheet_co == co_search:
                            return final_gcv, final_vm
                        # 2. Fallback Priority: Match on Mine only (saving first instance found)
                        elif mine_only_match is None:
                            mine_only_match = (final_gcv, final_vm)
                            
        # If we finished all columns and didn't find an exact match, return the Mine-only match if it exists
        if mine_only_match:
            return mine_only_match
            
        return None, None
    except Exception as e:
        return None, None

@st.cache_data(ttl=600, max_entries=2, show_spinner="🚂 Downloading live database from Google Sheets...")
def get_all_excel_data():
    try:
        req_url = f"{config.LIVE_EXCEL_URL}&t={int(time.time())}"
        r = requests.get(req_url, timeout=20)
        
        excel_file = io.BytesIO(r.content)
        all_sheets = pd.read_excel(excel_file, engine='openpyxl', sheet_name=None)
        
        cleaned_sheets = []
        for sheet_name, sheet_df in all_sheets.items():
            if not sheet_df.empty:
                sheet_df.columns = sheet_df.columns.astype(str).str.strip()
                sheet_df['Loaded_From_Tab'] = sheet_name 
                try: tab_date = datetime.strptime(sheet_name.strip().upper(), "%b-%y")
                except: tab_date = datetime.min 
                cleaned_sheets.append((tab_date, sheet_df))
                
        del all_sheets
        excel_file.close()
        del r
        gc.collect() 
                
        if not cleaned_sheets: return pd.DataFrame()
        
        cleaned_sheets.sort(key=lambda x: x[0])
        sorted_dfs = [item[1] for item in cleaned_sheets]
        df = pd.concat(sorted_dfs, ignore_index=True).dropna(how='all')
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        import datetime as dt
        def safe_duration_format(val):
            if pd.isna(val): return ""
            if isinstance(val, (dt.time, dt.datetime)): return val.strftime('%H:%M')
            if isinstance(val, (int, float)):
                try:
                    total_seconds = int(val * 24 * 3600)
                    if total_seconds <= 0: return ""
                    return f"{total_seconds // 3600:02d}:{(total_seconds % 3600) // 60:02d}"
                except: return str(val)
            s = str(val).lstrip("'").strip()
            return s if s not in ['nan', 'None', 'NaT', ''] else ""
        
        for col in df.columns:
            if "DURATION" in col.upper() or "CYCLE TIME" in col.upper():
                df[col] = df[col].apply(safe_duration_format)
            
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(lambda x: x.strftime('%H:%M') if isinstance(x, dt.time) else x)
                df[col] = df[col].apply(lambda x: str(x).lstrip("'").strip() if isinstance(x, str) else x)
                df[col] = df[col].replace({'nan': '', 'NaT': '', 'None': ''})
                
        if 'Receipt Date/Time' in df.columns:
            df['Parsed_DateTime'] = df['Receipt Date/Time'].apply(utils.safe_datetime_parse)
            df['Parsed_Date'] = df['Receipt Date/Time'].apply(utils.safe_date_parse)
        else:
            df['Parsed_DateTime'] = None
            df['Parsed_Date'] = None
            
        return df
    except Exception as e: 
        st.error(f"🚨 Database Sync Error: {e}")
        return pd.DataFrame()

def get_next_rake_details(df, today_ist):
    calculated_sr = 1
    calculated_rake = ""
    if not df.empty and 'RAKE No' in df.columns:
        df_clean = df.copy()
        df_clean['RAKE No'] = df_clean['RAKE No'].astype(str).str.strip().str.lstrip("'")
        df_clean = df_clean[~df_clean['RAKE No'].isin(['nan', '', 'None'])]
        if not df_clean.empty:
            last_row = df_clean.iloc[-1] 
            try: calculated_sr = int(float(last_row.get('Sr. No.', 0))) + 1
            except: calculated_sr = 1
            
            last_date = last_row.get('Parsed_Date')
            try:
                parts = str(last_row.get('RAKE No', '')).split('/')
                if len(parts) == 2: 
                    len_a, len_b = len(parts[0]), len(parts[1])
                    if today_ist.day == 1 and (pd.isnull(last_date) or last_date != today_ist):
                        if today_ist.month == 4:
                            calculated_rake = f"{1:0{len_a}d}/{1:0{len_b}d}"
                        else:
                            calculated_rake = f"{1:0{len_a}d}/{int(parts[1])+1:0{len_b}d}"
                    else:
                        calculated_rake = f"{int(parts[0])+1:0{len_a}d}/{int(parts[1])+1:0{len_b}d}"
            except: pass

    if st.session_state.pending_new_sr and st.session_state.pending_new_rake:
        if st.session_state.pending_new_sr > calculated_sr:
            return st.session_state.pending_new_sr, st.session_state.pending_new_rake
    return calculated_sr, calculated_rake

def load_whiteboard():
    with file_lock:
        if os.path.exists(config.WHITEBOARD_FILE):
            try:
                with open(config.WHITEBOARD_FILE, "r") as f: data = json.load(f)
                current_time = time.time()
                filtered_data = [msg for msg in data if (current_time - msg.get('time', 0)) <= 86400]
                if len(filtered_data) != len(data):
                    with open(config.WHITEBOARD_FILE, "w") as f: json.dump(filtered_data, f)
                return filtered_data
            except: return []
        return []

def save_whiteboard(data):
    with file_lock:
        with open(config.WHITEBOARD_FILE, "w") as f: json.dump(data, f)

def load_long_outages():
    with file_lock:
        if os.path.exists(config.LONG_OUTAGE_FILE):
            try:
                with open(config.LONG_OUTAGE_FILE, "r") as f: return json.load(f)
            except: return []
        return []

def save_long_outages(data):
    with file_lock:
        with open(config.LONG_OUTAGE_FILE, "w") as f: json.dump(data, f)
