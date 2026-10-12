import streamlit as st
import pytz

# --- CONFIGURATION CONSTANTS ---
# Now pulling BOTH sensitive URLs from Streamlit Secrets
APPS_SCRIPT_URL = st.secrets["APPS_SCRIPT_URL"]
LIVE_EXCEL_URL = st.secrets["LIVE_EXCEL_URL"]

IST = pytz.timezone('Asia/Kolkata')
WHITEBOARD_FILE = "whiteboard.json"
LONG_OUTAGE_FILE = "long_outages.json"

DEPT_COLORS = {
    "MM": "🔴 MM", "EMD": "🟡 EMD", "C&I": "🔵 C&I",
    "OPR": "🟢 OPR", "MGR": "🟣 MGR", "CHEM": "🧪 CHEM", "OTHER": "⚪ OTHER"
}

def setup_page():
    st.set_page_config(page_title="Rake Data Entry", layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""
        <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 98%; }
        input[disabled] { -webkit-text-fill-color: #0ea5e9 !important; color: #0ea5e9 !important; font-weight: 900 !important; background-color: rgba(14, 165, 233, 0.05) !important; border: 1px solid #0ea5e9 !important; }
        h1 { color: #003366; font-size: 1.8rem !important; margin-bottom: 0rem !important; padding-bottom: 0rem !important; padding-top: 0rem !important; }
        h5 { color: #003366; font-size: 1.1rem !important; margin-top: 0rem !important; margin-bottom: 0.2rem !important; padding-bottom: 0rem !important;}
        hr { margin: 0.4em 0 !important; }
        label { font-weight: 600 !important; font-size: 0.85rem !important; margin-bottom: 0.1rem !important; }
        .stRadio > div { flex-direction: row; gap: 1rem; }
        .stCheckbox { margin-top: -10px; }
        .streamlit-expanderHeader { padding-top: 0.4rem !important; padding-bottom: 0.4rem !important; font-weight: 600; }
        [data-testid="stToolbar"] {visibility: hidden !important;}
        footer {visibility: hidden !important;}
        header {visibility: hidden !important;}
        </style>
    """, unsafe_allow_html=True)

def init_session_state():
    defaults = {
        'logged_in': False, 'role': None, 'username': None,
        'outages_list': [], 'pending_new_sr': None, 'pending_new_rake': None,
        'form_key': 0, 'outage_key': 0, 'current_mode': "➕ New Entry",
        'current_edit_rake': None, 'retro_updates': []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
