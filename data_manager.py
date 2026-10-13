import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import json
import os
import time
import config
import utils

QUALITY_FILE = "quality_data.xlsx"

# --- CONNECT TO SUPABASE ---
def get_db():
    db_secrets = st.secrets["connections"]["supabase"]
    db_url = f"postgresql+psycopg2://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['database']}"
    return create_engine(db_url)

# --- FAST LOADING & CORRECT SQL DATE PARSING ---
@st.cache_data(ttl=600, show_spinner=False)
def get_all_excel_data():
    try:
        engine = get_db()
        query = "SELECT * FROM rakes_data"
        df = pd.read_sql(query, con=engine)
        
        if not df.empty:
            if 'receipt_dt' in df.columns:
                df['Parsed_DateTime'] = pd.to_datetime(df['receipt_dt'], errors='coerce')
                df['Parsed_Date'] = df['Parsed_DateTime'].dt.date
                df['Receipt Date/Time'] = df['Parsed_DateTime'].dt.strftime('%d.%m.%Y/%H:%M').fillna('')
                
            if 'placement_dt' in df.columns: df['Placement Date/Time'] = pd.to_datetime(df['placement_dt'], errors='coerce').dt.strftime('%d.%m.%Y/%H:%M').fillna('')
            if 'ul_end_dt' in df.columns: df['U/L End Date/Time'] = pd.to_datetime(df['ul_end_dt'], errors='coerce').dt.strftime('%d.%m.%Y/%H:%M').fillna('')
            if 'release_dt' in df.columns: df['Rake Rel. Date/Time'] = pd.to_datetime(df['release_dt'], errors='coerce').dt.strftime('%d.%m.%Y/%H:%M').fillna('')
                
            if 'u_duration' in df.columns: df['Unloading Duration'] = pd.to_datetime(df['u_duration'].astype(str), errors='coerce').dt.strftime('%H:%M').fillna('')
            if 'r_duration' in df.columns: df['Cycle Time'] = pd.to_datetime(df['r_duration'].astype(str), errors='coerce').dt.strftime('%H:%M').fillna('')
                
            if 'demurrage' in df.columns: df['Demurrage'] = df['demurrage']
            if 'rake_no' in df.columns: df['RAKE No'] = df['rake_no']
            if 'source' in df.columns: df['Coal siding/ Company'] = df['source']
            if 'wagon_spec' in df.columns: df['(BOXN / BOBR)'] = df['wagon_spec']
            if 'remarks' in df.columns: df['REMARKS'] = df['remarks']
            if 'sr_no' in df.columns: df['Sr. No.'] = df['sr_no']
            if 'nth' in df.columns: df['NTH'] = df['nth']
            if 'muth' in df.columns: df['MUTH'] = df['muth']
            if 'wt1' in df.columns: df['WT-1'] = df['wt1']
            if 'wt2' in df.columns: df['WT-2'] = df['wt2']
            if 'wt3' in df.columns: df['WT-3'] = df['wt3']
            if 'wt4' in df.columns: df['WT-4'] = df['wt4']
            if 'gcv' in df.columns: df['GCV'] = df['gcv']
            if 'vm' in df.columns: df['VM'] = df['vm']
            
            def extract_absolute_rake(r_val):
                try:
                    parts = str(r_val).split('/')
                    if len(parts) > 1 and parts[-1].strip().isdigit(): return int(parts[-1].strip())
                    return 0
                except: return 0
                    
            if 'RAKE No' in df.columns:
                df['Abs_Counter'] = df['RAKE No'].apply(extract_absolute_rake)
                df = df.sort_values(by=['Abs_Counter', 'Parsed_DateTime'], ascending=[True, True]).drop(columns=['Abs_Counter'])
            elif 'Parsed_DateTime' in df.columns:
                df = df.sort_values(by='Parsed_DateTime', ascending=True)
            
        return df
    except Exception as e:
        return pd.DataFrame()

# --- PRECISE RAKE NUMBERING & APRIL 1ST / MONTHLY RESET ---
def get_next_rake_details(df_all, today_ist):
    try:
        if df_all.empty or 'RAKE No' not in df_all.columns:
            return 1, "01/01"
            
        df_clean = df_all.copy()
        df_clean['RAKE No'] = df_clean['RAKE No'].astype(str).str.strip().str.lstrip("'")
        df_clean = df_clean[~df_clean['RAKE No'].isin(['nan', '', 'None'])]
        
        if df_clean.empty:
            return 1, "01/01"
            
        last_row = df_clean.iloc[-1]  # Most recent entry
        last_rake = str(last_row.get('RAKE No', ''))
        last_date = last_row.get('Parsed_Date')
        
        # Check if today is April 1st (Reset both to 01/01)
        if today_ist.month == 4 and today_ist.day == 1:
            if pd.isnull(last_date) or last_date != today_ist:
                return 1, "01/01"
                
        # Check if it's a new month compared to the last entry
        is_new_month = False
        if pd.notnull(last_date):
            if today_ist.year > last_date.year or (today_ist.year == last_date.year and today_ist.month > last_date.month):
                is_new_month = True
                
        try: calc_sr = int(float(last_row.get('Sr. No.', 0))) + 1
        except: calc_sr = 1
        
        if '/' in last_rake:
            parts = last_rake.split('/')
            try:
                prev_month_seq = int(parts[0])
                prev_abs_seq = int(parts[1])
            except:
                return calc_sr, f"{calc_sr:02d}/{calc_sr}"
                
            if is_new_month or (today_ist.month == 4 and today_ist.day == 1):
                new_month_seq = 1
            else:
                new_month_seq = prev_month_seq + 1
                
            new_abs_seq = prev_abs_seq + 1
            return calc_sr, f"{new_month_seq:02d}/{new_abs_seq}"
            
        return calc_sr, f"{calc_sr:02d}/{calc_sr}"
    except Exception:
        return 1, "01/01"

# --- QUALITY MASTER VLOOKUP LOGIC (GCV & VM) ---
def lookup_gcv_vm(mine_input, company_input):
    if not os.path.exists(QUALITY_FILE):
        return None, None
    try:
        df = pd.read_excel(QUALITY_FILE, engine='openpyxl', header=None)
        mine_search = str(mine_input).strip().upper()
        co_search = str(company_input).strip().upper()
        
        search_sets = [(7, 8, 10, 11), (15, 16, 18, 19), (23, 24, 26, 27), (31, 32, 34, 35)]
        mine_only_match = None
        
        for m_col, c_col, g_col, v_col in search_sets:
            if m_col >= len(df.columns) or v_col >= len(df.columns):
                continue
            for _, row in df.iterrows():
                sheet_mine = str(row[m_col]).strip().upper()
                sheet_co = str(row[c_col]).strip().upper()
                
                if not sheet_mine or sheet_mine == "NAN": continue
                
                if sheet_mine == mine_search:
                    raw_gcv = row[g_col]
                    raw_vm = row[v_col]
                    try: final_gcv = int(float(raw_gcv)) # 4-digit GCV
                    except: final_gcv = 0
                    try: final_vm = round(float(raw_vm), 2) # 2-digit VM
                    except: final_vm = 0.00
                    
                    if final_gcv > 0:
                        if sheet_co == co_search: return final_gcv, final_vm
                        elif mine_only_match is None: mine_only_match = (final_gcv, final_vm)
                        
        if mine_only_match: return mine_only_match
        return None, None
    except Exception as e:
        return None, None

def save_new_rake_entry(entry_dict):
    try:
        db_row = {
            "month_tab": entry_dict.get("tab_name"), "sr_no": entry_dict.get("sr_no"), "rake_no": entry_dict.get("rake_no"),
            "source": entry_dict.get("source"), "wagon_spec": entry_dict.get("wagon_spec"),
            "receipt_dt": utils.safe_datetime_parse(entry_dict.get("receipt")),
            "placement_dt": utils.safe_datetime_parse(entry_dict.get("placement")),
            "ul_end_dt": utils.safe_datetime_parse(entry_dict.get("u_end")),
            "release_dt": utils.safe_datetime_parse(entry_dict.get("release")),
            "u_duration": entry_dict.get("u_duration", "").replace("'", ""),
            "r_duration": entry_dict.get("r_duration", "").replace("'", ""),
            "demurrage": entry_dict.get("demurrage"), "remarks": entry_dict.get("remarks"),
            "nth": entry_dict.get("nth"), "muth": entry_dict.get("muth"),
            "wt1": entry_dict.get("wt1"), "wt2": entry_dict.get("wt2"),
            "wt3": entry_dict.get("wt3"), "wt4": entry_dict.get("wt4"),
            "gcv": entry_dict.get("gcv"), "vm": entry_dict.get("vm")
        }
        engine = get_db()
        df_new = pd.DataFrame([db_row])
        with engine.begin() as connection:
            df_new.to_sql('rakes_data', con=connection, if_exists='append', index=False)
        get_all_excel_data.clear()
        return True
    except Exception as e:
        return False

def save_rake_to_db(entry_dict):
    return save_new_rake_entry(entry_dict)

@st.cache_data(ttl=600, show_spinner=False)
def load_whiteboard():
    try:
        engine = get_db()
        query = "SELECT * FROM whiteboard ORDER BY id DESC LIMIT 1"
        df = pd.read_sql(query, con=engine)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {"message": "Welcome to CHP-O Data Entry.", "updated_by": "System", "updated_at": ""}
    except Exception:
        return {"message": "Welcome to CHP-O Data Entry.", "updated_by": "System", "updated_at": ""}

def save_whiteboard(wb_dict):
    try:
        engine = get_db()
        with engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE TABLE whiteboard;")
            conn.exec_driver_sql(
                "INSERT INTO whiteboard (message, updated_by, updated_at) VALUES (%s, %s, %s);",
                (wb_dict.get('message', ''), wb_dict.get('updated_by', 'System'), wb_dict.get('updated_at', ''))
            )
        load_whiteboard.clear()
    except Exception as e:
        st.error(f"Error saving whiteboard: {e}")

@st.cache_data(ttl=600, show_spinner=False)
def load_long_outages():
    try:
        engine = get_db()
        query = "SELECT data FROM long_outages ORDER BY id DESC LIMIT 1"
        df = pd.read_sql(query, con=engine)
        if not df.empty and df.iloc[0]['data']:
            val = df.iloc[0]['data']
            return json.loads(val) if isinstance(val, str) else val
        return []
    except Exception: return []

def save_long_outages(lo_list):
    try:
        engine = get_db()
        json_str = json.dumps(lo_list)
        with engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE TABLE long_outages;")
            conn.exec_driver_sql(
                "INSERT INTO long_outages (data) VALUES (%s);",
                (json_str,)
            )
        load_long_outages.clear()
    except Exception as e: pass
