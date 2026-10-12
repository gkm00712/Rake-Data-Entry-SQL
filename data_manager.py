import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import json
import config

# --- CONNECT TO SUPABASE ---
def get_db():
    db_secrets = st.secrets["connections"]["supabase"]
    db_url = f"postgresql+psycopg2://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['database']}"
    return create_engine(db_url)

@st.cache_data(ttl=30)
def get_all_excel_data():
    try:
        engine = get_db()
        query = "SELECT * FROM rakes_data ORDER BY sr_no DESC"
        df = pd.read_sql(query, con=engine)
        
        if not df.empty:
            # Map database columns back to what the UI / reports expect
            if 'receipt_dt' in df.columns:
                df['Receipt Date/Time'] = df['receipt_dt']
                df['Parsed_DateTime'] = pd.to_datetime(df['receipt_dt'], format='%d.%m.%Y/%H:%M', errors='coerce')
                df['Parsed_Date'] = pd.to_datetime(df['receipt_dt'], format='%d.%m.%Y/%H:%M', errors='coerce').dt.date
            if 'placement_dt' in df.columns: df['Placement Date/Time'] = df['placement_dt']
            if 'ul_end_dt' in df.columns: df['U/L End Date/Time'] = df['ul_end_dt']
            if 'release_dt' in df.columns: df['Rake Rel. Date/Time'] = df['release_dt']
            if 'u_duration' in df.columns: 
                df['Unloading Duration'] = pd.to_datetime(df['u_duration'], format='%H:%M:%S', errors='coerce').dt.time
            if 'r_duration' in df.columns: 
                df['Cycle Time'] = pd.to_datetime(df['r_duration'], format='%H:%M:%S', errors='coerce').dt.time
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
            
        return df
    except Exception as e:
        st.error(f"Error fetching data from Supabase: {e}")
        return pd.DataFrame()

def save_new_rake_entry(entry_dict):
    try:
        engine = get_db()
        df_new = pd.DataFrame([entry_dict])
        with engine.begin() as connection:
            df_new.to_sql('rakes_data', con=connection, if_exists='append', index=False)
        get_all_excel_data.clear()
        return True
    except Exception as e:
        st.error(f"Error saving rake entry: {e}")
        return False

# Aliases expected by form_entry.py
def save_rake_to_db(entry_dict):
    return save_new_rake_entry(entry_dict)

def get_next_rake_details(df_all):
    try:
        if df_all.empty or 'sr_no' not in df_all.columns:
            return 1, "001/001"
        max_sr = int(df_all['sr_no'].max()) + 1
        return max_sr, f"{max_sr:03d}"
    except Exception:
        return 1, "001/001"

def lookup_gcv_vm(source_name):
    # Default fallback lookup if needed by form entry
    return 3500, 20.0

@st.cache_data(ttl=10)
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
                (wb_dict.get('message'), wb_dict.get('updated_by'), wb_dict.get('updated_at'))
            )
        load_whiteboard.clear()
    except Exception as e:
        st.error(f"Error saving whiteboard: {e}")

@st.cache_data(ttl=10)
def load_long_outages():
    try:
        engine = get_db()
        query = "SELECT data FROM long_outages ORDER BY id DESC LIMIT 1"
        df = pd.read_sql(query, con=engine)
        if not df.empty and df.iloc[0]['data']:
            val = df.iloc[0]['data']
            return json.loads(val) if isinstance(val, str) else val
        return []
    except Exception:
        return []

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
    except Exception as e:
        st.error(f"Error saving long outages: {e}")
