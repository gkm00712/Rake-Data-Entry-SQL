import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import json
import os
import config
import utils

QUALITY_FILE = "quality_data.xlsx"

# --- CONNECT TO SUPABASE (OPTIMIZED CONNECTION POOLING) ---
@st.cache_resource(show_spinner=False)
def get_db():
    db_secrets = st.secrets["connections"]["supabase"]
    db_url = f"postgresql+psycopg2://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['database']}"
    return create_engine(db_url, pool_size=10, max_overflow=20)

# --- STRICT CUSTOM INDIAN DATE PARSER ---
def parse_indian_date(date_val):
    if pd.isnull(date_val) or str(date_val).strip() in ['', 'NaT', 'None', 'nan']:
        return pd.NaT
    
    if isinstance(date_val, datetime):
        return pd.to_datetime(date_val)
        
    date_str = str(date_val).strip()
    
    # Clean the string: convert slashes and dots to standardize everything
    clean_str = date_str.replace('/', ' ').replace('.', '-').replace('T', ' ')
    
    # Explicit format checklist. Checks Indian formats FIRST, then SQL standard formats.
    formats = [
        '%d-%m-%Y %H:%M',       # Standard Indian App Input
        '%d-%m-%Y %H:%M:%S',    # Standard Indian with Seconds
        '%Y-%m-%d %H:%M:%S',    # SQL Database Standard
        '%Y-%m-%d %H:%M:%S.%f', # SQL Database Extended
        '%Y-%m-%d %H:%M',       # SQL Database Short
        '%d-%m-%Y',             # Date Only Indian
        '%Y-%m-%d'              # Date Only SQL
    ]
    
    for fmt in formats:
        try:
            return pd.to_datetime(datetime.strptime(clean_str, fmt))
        except ValueError:
            continue
            
    # Absolute fallback for totally mangled strings
    try:
        return pd.to_datetime(clean_str, dayfirst=True)
    except:
        return pd.NaT

# --- BULLETPROOF FORMATTING ---
def format_rake_dataframe(df):
    if 'id' in df.columns:
        df = df.drop(columns=['id'])
        
    if not df.empty:
        if 'receipt_dt' in df.columns:
            df['Parsed_DateTime'] = df['receipt_dt'].apply(parse_indian_date)
            df['Parsed_Date'] = df['Parsed_DateTime'].dt.date
            df['Receipt Date/Time'] = df['Parsed_DateTime'].dt.strftime('%d-%m-%Y %H:%M').fillna('')
            
        if 'placement_dt' in df.columns: 
            df['Placement Date/Time'] = df['placement_dt'].apply(parse_indian_date).dt.strftime('%d-%m-%Y %H:%M').fillna('')
        if 'ul_end_dt' in df.columns: 
            df['U/L End Date/Time'] = df['ul_end_dt'].apply(parse_indian_date).dt.strftime('%d-%m-%Y %H:%M').fillna('')
        if 'release_dt' in df.columns: 
            df['Rake Rel. Date/Time'] = df['release_dt'].apply(parse_indian_date).dt.strftime('%d-%m-%Y %H:%M').fillna('')
            
        if 'u_duration' in df.columns: df['Unloading Duration'] = pd.to_datetime(df['u_duration'].astype(str), errors='coerce').dt.strftime('%H:%M').fillna('')
        if 'r_duration' in df.columns: df['Cycle Time'] = pd.to_datetime(df['r_duration'].astype(str), errors='coerce').dt.strftime('%H:%M').fillna('')
            
        if 'demurrage' in df.columns: df['Demurrage'] = df['demurrage']
        if 'demurrage_in_rs' in df.columns: df['Demurrage (in Rs)'] = df['demurrage_in_rs']
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
        
        # Sort strictly by true chronological date, IGNORING the database ID
        if 'Parsed_DateTime' in df.columns:
            df = df.sort_values(by='Parsed_DateTime', ascending=False)
            
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_all_excel_data():
    try:
        engine = get_db()
        query = "SELECT * FROM rakes_data"
        df = pd.read_sql(query, con=engine)
        return format_rake_dataframe(df)
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def get_recent_excel_data():
    try:
        # Guarantee we get the perfectly sorted dataset based on real dates, 
        # then strictly slice the TOP 50 for instantaneous UI loading.
        df = get_all_excel_data()
        if not df.empty:
            return df.head(50)
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def get_next_rake_details(df_all, today_ist):
    try:
        if df_all.empty or 'RAKE No' not in df_all.columns:
            return 1, "01/01"
            
        df_clean = df_all.copy()
        df_clean['RAKE No'] = df_clean['RAKE No'].astype(str).str.strip().str.lstrip("'")
        df_clean = df_clean[~df_clean['RAKE No'].isin(['nan', '', 'None'])]
        
        if df_clean.empty:
            return 1, "01/01"
            
        if 'Parsed_DateTime' in df_clean.columns:
            df_clean = df_clean.sort_values(by='Parsed_DateTime', ascending=False)
            
        last_row = df_clean.iloc[0] 
        last_rake = str(last_row.get('RAKE No', ''))
        last_date = last_row.get('Parsed_Date')
        
        if today_ist.month == 4 and today_ist.day == 1:
            if pd.isnull(last_date) or last_date != today_ist:
                return 1, "01/01"
                
        is_new_month = False
        if pd.notnull(last_date):
            if today_ist.year > last_date.year or (today_ist.year == last_date.year and today_ist.month > last_date.month):
                is_new_month = True
                
        try: calc_sr = int(float(last_row.get('Sr. No.', 0))) + 1
        except: calc_sr = 1
        
        if '/' in last_rake:
            parts = last_rake.split('/')
            try:
                prev_part1 = int(parts[0].strip())
                prev_part2 = int(parts[1].strip())
                
                if is_new_month or (today_ist.month == 4 and today_ist.day == 1):
                    next_part1 = 1
                else:
                    next_part1 = prev_part1 + 1
                    
                next_part2 = prev_part2 + 1
                len_a = len(parts[0].strip())
                len_b = len(parts[1].strip())
                
                formatted_rake = f"{next_part1:0{len_a}d}/{next_part2:0{len_b}d}"
                return calc_sr, formatted_rake
            except:
                pass
                
        return calc_sr, f"{calc_sr:02d}/{calc_sr}"
    except Exception:
        return 1, "01/01"

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
                    try: final_gcv = int(float(raw_gcv))
                    except: final_gcv = 0
                    try: final_vm = round(float(raw_vm), 2)
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
            "demurrage": entry_dict.get("demurrage"), 
            "demurrage_in_rs": entry_dict.get("demurrage_in_rs"),
            "remarks": entry_dict.get("remarks"),
            "nth": entry_dict.get("nth"), "muth": entry_dict.get("muth"),
            "wt1": entry_dict.get("wt1"), "wt2": entry_dict.get("wt2"),
            "wt3": entry_dict.get("wt3"), "wt4": entry_dict.get("wt4"),
            "gcv": entry_dict.get("gcv"), "vm": entry_dict.get("vm")
        }
        engine = get_db()
        df_new = pd.DataFrame([db_row])
        with engine.begin() as connection:
            df_new.to_sql('rakes_data', con=connection, if_exists='append', index=False)
            
        get_recent_excel_data.clear()
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
        query = "SELECT message FROM whiteboard ORDER BY id DESC LIMIT 1"
        df = pd.read_sql(query, con=engine)
        if not df.empty and df.iloc[0]['message']:
            val = df.iloc[0]['message']
            try:
                notes = json.loads(val)
                if isinstance(notes, list):
                    now_ist = datetime.now(config.IST)
                    valid_notes = []
                    for note in notes:
                        timestamp_str = note.get('timestamp')
                        if timestamp_str:
                            try:
                                note_dt = datetime.fromisoformat(timestamp_str)
                                if note_dt.tzinfo is None:
                                    note_dt = config.IST.localize(note_dt)
                                if (now_ist - note_dt).total_seconds() <= 24 * 3600:
                                    valid_notes.append(note)
                            except:
                                valid_notes.append(note)
                    return valid_notes
            except:
                pass
    except Exception:
        pass
    return []

def save_whiteboard(wb_data):
    try:
        now_ist = datetime.now(config.IST)
        for note in wb_data:
            if 'timestamp' not in note or not note['timestamp']:
                note['timestamp'] = now_ist.isoformat()
                
        engine = get_db()
        json_str = json.dumps(wb_data)
        with engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE TABLE whiteboard;")
            conn.exec_driver_sql(
                "INSERT INTO whiteboard (message, updated_by, updated_at) VALUES (%s, %s, %s);",
                (json_str, 'System', now_ist.strftime('%d-%m-%Y %H:%M'))
            )
        load_whiteboard.clear()
    except Exception as e:
        st.error(f"Error saving whiteboard: {e}")

@st.cache_data(ttl=600, show_spinner=False)
def load_long_outages():
    try:
        engine = get_db()
        query = "SELECT * FROM long_outages ORDER BY id ASC"
        df = pd.read_sql(query, con=engine)
        if not df.empty:
            return df.to_dict('records')
        return []
    except Exception as e: 
        st.error(f"Load Error (Long Outages): {e}") 
        return []

def save_long_outages(lo_list):
    try:
        engine = get_db()
        with engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE TABLE long_outages RESTART IDENTITY;")
            
            if lo_list:
                for lo in lo_list:
                    excluded_keys = ['id', 'created_at', 'updated_at']
                    clean_lo = {k: v for k, v in lo.items() if k not in excluded_keys}
                    
                    keys = list(clean_lo.keys())
                    columns_str = ", ".join(keys)
                    placeholders = ", ".join([f"%({k})s" for k in keys])
                    
                    insert_query = f"INSERT INTO long_outages ({columns_str}) VALUES ({placeholders})"
                    conn.exec_driver_sql(insert_query, clean_lo)
                    
        load_long_outages.clear()
    except Exception as e:
        st.error(f"❌ Database Save Error: {e}")
