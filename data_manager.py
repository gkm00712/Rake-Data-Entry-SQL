import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import config
from sqlalchemy import create_engine, text

def get_db():
    db_secrets = st.secrets["connections"]["supabase"]
    db_url = f"postgresql+psycopg2://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['database']}"
    return create_engine(db_url)

@st.cache_data(ttl=600, show_spinner=False)
def get_all_excel_data():
    engine = get_db()
    try:
        query = "SELECT * FROM rakes_data;"
        df = pd.read_sql(query, con=engine)
        if not df.empty:
            if 'receipt_dt' in df.columns:
                df['Parsed_DateTime'] = pd.to_datetime(df['receipt_dt'], errors='coerce')
                df['Parsed_Date'] = df['Parsed_DateTime'].dt.date
            
            rename_reverse = {
                'sr_no': 'Sr. No.', 'rake_no': 'RAKE No', 'source': 'Coal siding/ Company', 'wagon_spec': '(BOXN / BOBR)',
                'receipt_dt': 'Receipt Date/Time', 'placement_dt': 'Placement Date/Time', 'ul_end_dt': 'U/L End Date/Time',
                'release_dt': 'Rake Rel. Date/Time', 'u_duration': 'Unloading Duration', 'r_duration': 'Cycle Time',
                'demurrage': 'Demurrage (Hrs)', 'demurrage_in_rs': 'Demurrage (in Rs)', 'remarks': 'REMARKS', 'nth': 'NTH', 'muth': 'MUTH', 
                'wt1': 'WT-1', 'wt2': 'WT-2', 'wt3': 'WT-3', 'wt4': 'WT-4', 'gcv': 'GCV', 'vm': 'VM', 'month_tab': 'Loaded_From_Tab'
            }
            df = df.rename(columns=rename_reverse)
        return df
    except Exception as e:
        st.error(f"Database fetch error: {e}")
        return pd.DataFrame()

def save_rake_to_db(payload):
    engine = get_db()
    with engine.begin() as conn:
        query = text("""
            INSERT INTO rakes_data (
                sr_no, rake_no, source, wagon_spec, receipt_dt, placement_dt, ul_end_dt, release_dt, 
                u_duration, r_duration, demurrage, demurrage_in_rs, remarks, nth, muth, wt1, wt2, wt3, wt4, gcv, vm, month_tab
            ) VALUES (
                :sr_no, :rake_no, :source, :wagon_spec, :receipt, :placement, :u_end, :release, 
                :u_duration, :r_duration, :demurrage, :demurrage_in_rs, :remarks, :nth, :muth, :wt1, :wt2, :wt3, :wt4, :gcv, :vm, :tab_name
            );
        """)
        conn.execute(query, payload)

# --- WHITEBOARD WITH 24-HOUR AUTO-EXPIRY ---
def load_whiteboard():
    engine = get_db()
    try:
        with engine.begin() as conn:
            res = conn.execute(text("SELECT data FROM app_state WHERE key = 'whiteboard';")).fetchone()
            if res and res[0]:
                notes = res[0] if isinstance(res[0], list) else []
                now_ist = datetime.now(config.IST)
                
                # Filter out notes older than 24 hours
                valid_notes = []
                for note in notes:
                    timestamp_str = note.get('timestamp')
                    if timestamp_str:
                        try:
                            note_dt = datetime.fromisoformat(timestamp_str)
                            if note_dt.tzinfo is None:
                                note_dt = config.IST.localize(note_dt)
                            
                            # Keep only if less than 24 hours old
                            if (now_ist - note_dt).total_seconds() <= 24 * 3600:
                                valid_notes.append(note)
                        except:
                            # Fallback if timestamp format is legacy
                            valid_notes.append(note)
                    else:
                        # Legacy notes without timestamps: attach current time or drop
                        pass
                
                # If notes were auto-deleted, update the database state
                if len(valid_notes) != len(notes):
                    conn.execute(
                        text("INSERT INTO app_state (key, data) VALUES ('whiteboard', :data) ON CONFLICT (key) DO UPDATE SET data = :data;"),
                        {"data": str(valid_notes)} # Supabase jsonb handles lists via SQLAlchemy json/text conversion depending on setup
                    )
                return valid_notes
    except Exception:
        pass
    return []

def save_whiteboard(wb_data):
    engine = get_db()
    now_ist = datetime.now(config.IST)
    
    # Ensure every note has a strict ISO timestamp attached when written
    for note in wb_data:
        if 'timestamp' not in note or not note['timestamp']:
            note['timestamp'] = now_ist.isoformat()
            
    try:
        import json
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO app_state (key, data) VALUES ('whiteboard', CAST(:data AS jsonb)) ON CONFLICT (key) DO UPDATE SET data = CAST(:data AS jsonb);"),
                {"data": json.dumps(wb_data)}
            )
    except Exception as e:
        st.error(f"Failed to save whiteboard: {e}")

def load_long_outages():
    engine = get_db()
    try:
        with engine.begin() as conn:
            res = conn.execute(text("SELECT data FROM app_state WHERE key = 'long_outages';")).fetchone()
            if res and res[0]:
                return res[0] if isinstance(res[0], list) else []
    except Exception:
        pass
    return []

def save_long_outages(lo_data):
    engine = get_db()
    try:
        import json
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO app_state (key, data) VALUES ('long_outages', CAST(:data AS jsonb)) ON CONFLICT (key) DO UPDATE SET data = CAST(:data AS jsonb);"),
                {"data": json.dumps(lo_data)}
            )
    except Exception as e:
        st.error(f"Failed to save long outages: {e}")
