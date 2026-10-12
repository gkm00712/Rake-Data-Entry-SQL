import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text

# --- CONNECT TO SUPABASE ---
def get_db():
    return st.connection("supabase", type="sql")

# --- FETCH DATA (Replaces Google Sheets Fetch) ---
@st.cache_data(ttl=10)
def get_all_excel_data():
    conn = get_db()
    
    # Query the database
    df = conn.query("SELECT * FROM rakes_data ORDER BY receipt_dt ASC", ttl=0)
    if df.empty:
        return pd.DataFrame()

    # Rename columns to match what the UI (form_entry.py) expects
    rename_map = {
        'sr_no': 'Sr. No.', 'rake_no': 'RAKE No', 'source': 'Coal siding/ Company', 
        'wagon_spec': '(BOXN / BOBR)', 'u_duration': 'U/L Duration', 'r_duration': 'Cycle Time',
        'demurrage': 'Demurrage', 'remarks': 'REMARKS', 'nth': 'NTH', 'muth': 'MUTH',
        'wt1': 'WT-1', 'wt2': 'WT-2', 'wt3': 'WT-3', 'wt4': 'WT-4', 'gcv': 'GCV', 'vm': 'VM'
    }
    df = df.rename(columns=rename_map)
    
    # Recreate the old Excel Date/Time strings so the UI parses them perfectly
    def format_dt(dt):
        if pd.isnull(dt): return ""
        return dt.strftime("%d.%m.%Y/%H:%M")
        
    df['Receipt Date/Time'] = df['receipt_dt'].apply(format_dt)
    df['Placement Date/Time'] = df['placement_dt'].apply(format_dt)
    df['U/L End Date/Time'] = df['ul_end_dt'].apply(format_dt)
    df['Rake Rel. Date/Time'] = df['release_dt'].apply(format_dt)
    df['Parsed_DateTime'] = pd.to_datetime(df['receipt_dt'])

    return df

# --- SAVE RAKE (Replaces requests.post to Google) ---
def save_rake_to_db(payload):
    conn = get_db()
    
    def parse_str_to_dt(dt_str):
        if not dt_str: return None
        return datetime.strptime(dt_str, "%d.%m.%Y/%H:%M")
        
    with conn.session as s:
        # Check if rake already exists (Edit Mode)
        existing = s.execute(text("SELECT id FROM rakes_data WHERE rake_no = :r"), {"r": payload['rake_no']}).fetchone()
        
        if existing:
            sql = text("""
                UPDATE rakes_data SET 
                    month_tab=:mt, sr_no=:sr, source=:src, wagon_spec=:ws,
                    receipt_dt=:r_dt, placement_dt=:p_dt, ul_end_dt=:u_dt, release_dt=:rel_dt,
                    u_duration=:u_d, r_duration=:r_d, demurrage=:dem, remarks=:rem,
                    nth=:n, muth=:m, wt1=:w1, wt2=:w2, wt3=:w3, wt4=:w4, gcv=:gcv, vm=:vm
                WHERE rake_no=:r
            """)
        else:
            sql = text("""
                INSERT INTO rakes_data (
                    month_tab, sr_no, rake_no, source, wagon_spec, receipt_dt, placement_dt, ul_end_dt, release_dt,
                    u_duration, r_duration, demurrage, remarks, nth, muth, wt1, wt2, wt3, wt4, gcv, vm
                ) VALUES (
                    :mt, :sr, :r, :src, :ws, :r_dt, :p_dt, :u_dt, :rel_dt,
                    :u_d, :r_d, :dem, :rem, :n, :m, :w1, :w2, :w3, :w4, :gcv, :vm
                )
            """)
            
        s.execute(sql, {
            "mt": payload['tab_name'], "sr": payload['sr_no'], "r": payload['rake_no'], "src": payload['source'], 
            "ws": payload['wagon_spec'], "r_dt": parse_str_to_dt(payload['receipt']), "p_dt": parse_str_to_dt(payload['placement']), 
            "u_dt": parse_str_to_dt(payload['u_end']), "rel_dt": parse_str_to_dt(payload['release']),
            "u_d": payload['u_duration'].replace("'", "") if payload['u_duration'] else "",
            "r_d": payload['r_duration'].replace("'", "") if payload['r_duration'] else "",
            "dem": payload['demurrage'], "rem": payload['remarks'], "n": payload['nth'], "m": payload['muth'],
            "w1": payload['wt1'], "w2": payload['wt2'], "w3": payload['wt3'], "w4": payload['wt4'],
            "gcv": int(payload['gcv']) if payload['gcv'] else None, "vm": float(payload['vm']) if payload['vm'] else None
        })
        s.commit()
    get_all_excel_data.clear() # Clear cache so UI refreshes instantly

# --- RETAINED: GCV/VM MASTER LOOKUP ---
def lookup_gcv_vm(mine_part, company_part):
    try:
        df_q = pd.read_excel('quality_data.xlsx')
        mine_clean = str(mine_part).strip().upper()
        comp_clean = str(company_part).strip().upper()
        
        df_q['Mine_Upper'] = df_q['Mine'].astype(str).str.strip().str.upper()
        df_q['Company_Upper'] = df_q['Company'].astype(str).str.strip().str.upper()
        
        exact_match = df_q[(df_q['Mine_Upper'] == mine_clean) & (df_q['Company_Upper'] == comp_clean)]
        if not exact_match.empty:
            return exact_match.iloc[-1]['GCV'], exact_match.iloc[-1]['VM']
            
        mine_match = df_q[df_q['Mine_Upper'] == mine_clean]
        if not mine_match.empty:
            return mine_match.iloc[-1]['GCV'], mine_match.iloc[-1]['VM']
    except Exception:
        pass
    return None, None

def get_next_rake_details(df_all, today_ist):
    df_clean = df_all.copy()
    if not df_clean.empty and 'RAKE No' in df_clean.columns:
        df_clean['RAKE No'] = df_clean['RAKE No'].astype(str).str.strip().str.lstrip("'")
        df_clean = df_clean[~df_clean['RAKE No'].isin(['nan', '', 'None'])]
        if not df_clean.empty:
            last_row = df_clean.iloc[-1]
            try: last_sr = int(last_row.get('Sr. No.', 0))
            except: last_sr = 0
            
            try:
                last_rake = str(last_row.get('RAKE No', '00/0000'))
                parts = last_rake.split('/')
                len_a, len_b = len(parts[0]), len(parts[1])
                prev_a, prev_b = int(parts[0]), int(parts[1])
                
                # Financial Year Reset Logic
                if today_ist.month == 4 and today_ist.day == 1 and prev_a != 1:
                    return 1, f"01/0001"
                # Monthly Reset Logic
                if today_ist.day == 1 and prev_a != 1:
                    return last_sr + 1, f"01/{prev_b + 1:0{len_b}d}"
                    
                return last_sr + 1, f"{prev_a + 1:0{len_a}d}/{prev_b + 1:0{len_b}d}"
            except:
                pass
    return 1, ""

# --- RESTORED & UPGRADED: WHITEBOARD & OUTAGES IN POSTGRESQL ---
def load_whiteboard():
    conn = get_db()
    try:
        df = conn.query("SELECT message, updated_by, updated_at FROM whiteboard WHERE id = 1", ttl=0)
        if not df.empty:
            return {
                "message": df.iloc[0]['message'],
                "updated_by": df.iloc[0]['updated_by'],
                "updated_at": df.iloc[0]['updated_at']
            }
    except Exception:
        pass
    return {"message": "Welcome to CHP-O Data Entry.", "updated_by": "System", "updated_at": datetime.now().strftime("%d-%m-%Y %H:%M")}

def save_whiteboard(data):
    conn = get_db()
    with conn.session as s:
        s.execute(text("""
            UPDATE whiteboard 
            SET message=:m, updated_by=:ub, updated_at=:ua 
            WHERE id=1
        """), {"m": data['message'], "ub": data['updated_by'], "ua": data['updated_at']})
        s.commit()

def load_long_outages():
    conn = get_db()
    try:
        df = conn.query("SELECT dept, equip, affects, since_date, since_time, status, rest_date, rest_time FROM long_outages ORDER BY id ASC", ttl=0)
        if not df.empty:
            return df.to_dict('records')
    except Exception:
        pass
    return []

def save_long_outages(outages_list):
    conn = get_db()
    with conn.session as s:
        # Wipe the old active outages and save the exact current state
        s.execute(text("TRUNCATE TABLE long_outages"))
        
        if outages_list:
            for o in outages_list:
                s.execute(text("""
                    INSERT INTO long_outages (dept, equip, affects, since_date, since_time, status, rest_date, rest_time)
                    VALUES (:d, :e, :a, :sd, :st, :stat, :rd, :rt)
                """), {
                    "d": o.get('dept',''), "e": o.get('equip',''), "a": o.get('affects','BOTH'),
                    "sd": o.get('since_date',''), "st": o.get('since_time',''),
                    "stat": o.get('status',''), "rd": o.get('rest_date',''), "rt": o.get('rest_time','')
                })
        s.commit()
