import pandas as pd
from datetime import datetime, timedelta
import re
import config
import io
from openpyxl.utils import get_column_letter  # Added to safely handle >26 columns

def safe_datetime_parse(val):
    if pd.isna(val): return None
    if isinstance(val, datetime): return val
    try:
        if isinstance(val, str):
            parts = val.split('/')
            if len(parts) == 2:
                dt_str = f"{parts[0].strip()} {parts[1].strip()}"
                return datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
    except: pass
    return None

def safe_date_parse(val):
    dt = safe_datetime_parse(val)
    return dt.date() if dt else None

def parse_excel_datetime(val):
    dt = safe_datetime_parse(val)
    if dt: return dt.date(), dt.time()
    return None, None

def parse_excel_tippler(val):
    if pd.isna(val): return 0, None, None
    val_str = str(val).strip()
    if not val_str: return 0, None, None
    if val_str.upper() == "ASSIGNED": return 0, None, None
    
    parts = val_str.split('\n')
    try: qty = int(float(parts[0]))
    except: qty = 0
    
    start_time, end_time = None, None
    if len(parts) > 1:
        time_part = parts[1].strip()
        times = time_part.split('-')
        try: start_time = datetime.strptime(times[0].strip(), "%H:%M").time()
        except: pass
        if len(times) > 1:
            if "Ongoing" in times[1]: end_time = None
            else:
                try: end_time = datetime.strptime(times[1].strip(), "%H:%M").time()
                except: pass
    return qty, start_time, end_time

def parse_outages(remarks_str):
    if pd.isna(remarks_str): return []
    outages = []
    lines = str(remarks_str).split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('[PARTIAL]'): continue
        
        # Skip auto-generated system remarks so they don't appear in the Outage Editor
        if "BUNCHING" in line.upper() or "NTPC OWNED" in line.upper() or "RAKE WAITING" in line.upper(): 
            continue
        
        parts = line.split('|')
        if len(parts) >= 2:
            # Strip emojis to get clean department name
            dept_raw = parts[0].strip().replace('⚪ ', '').replace('🔴 ', '').replace('🟢 ', '').replace('🔵 ', '').replace('🟠 ', '').replace('🟣 ', '').replace('🟡 ', '')
            
            dept = dept_raw
            for k, v in config.DEPT_COLORS.items():
                if dept_raw in v:
                    dept = k
                    break
            
            if len(parts) == 3:
                time_range = parts[1].strip()
                reason = parts[2].strip()
                t_parts = time_range.split(' to ')
                start_str = t_parts[0] if len(t_parts) > 0 else "-"
                end_str = t_parts[1] if len(t_parts) > 1 else "-"
                outages.append({"Dept": dept, "Start": start_str, "End": end_str, "Reason": reason, "Log": line})
            elif len(parts) == 2:
                reason = parts[1].strip()
                outages.append({"Dept": dept, "Start": "-", "End": "-", "Reason": reason, "Log": line})
    return outages

def resolve_tippler_time(time_obj, base_dt, end_dt):
    if not time_obj or not base_dt or not end_dt: return None
    
    # 1. Try same day as base
    dt_candidate = config.IST.localize(datetime.combine(base_dt.date(), time_obj))
    if base_dt <= dt_candidate <= end_dt: return dt_candidate
    
    # 2. Try next day (overnight shifts)
    dt_candidate_next = config.IST.localize(datetime.combine(base_dt.date() + timedelta(days=1), time_obj))
    if base_dt <= dt_candidate_next <= end_dt: return dt_candidate_next
    
    # 3. Try previous day (rare edge cases crossing midnight exactly)
    dt_candidate_prev = config.IST.localize(datetime.combine(base_dt.date() - timedelta(days=1), time_obj))
    if base_dt <= dt_candidate_prev <= end_dt: return dt_candidate_prev
    
    return None

def validate_time_window(dt_val, label, demurrage_val, is_super_admin, now_ist, entry_mode, w_type, is_ntpc_owned):
    if is_super_admin:
        return True, ""
        
    diff_hours = (now_ist - dt_val).total_seconds() / 3600.0
    
    # 96 HOUR LIMIT FOR ALL OPERATORS
    if diff_hours > 96:
        return False, f"❌ {label} is older than 96 hours. Operators cannot log or edit data beyond 4 days."
        
    if dt_val > now_ist:
        return False, f"❌ {label} cannot be in the future!"
        
    return True, ""

# --- BUG FIX: BULLETPROOF EXCEL FORMATTING ---
def generate_formatted_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Daily Report')
        
        # Auto-adjust column widths safely
        worksheet = writer.sheets['Daily Report']
        for idx, col in enumerate(df.columns):
            
            # Safe calculation of string length (prevents TypeError on empty or weird data)
            col_header_len = len(str(col))
            if len(df) > 0:
                max_val_len = max([len(str(val)) for val in df[col].values])
            else:
                max_val_len = 0
                
            max_len = max(col_header_len, max_val_len) + 2
            
            # Use openpyxl to get exact column letter (A, B... Z, AA, AB)
            col_letter = get_column_letter(idx + 1)
            
            # Cap the maximum width at 50
            worksheet.column_dimensions[col_letter].width = min(max_len, 50)
            
    return output.getvalue()
