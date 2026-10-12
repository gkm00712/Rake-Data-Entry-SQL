import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import math
import config
import utils
from data_manager import get_next_rake_details, save_long_outages, get_all_excel_data, lookup_gcv_vm, save_rake_to_db

def render_rake_form(df_all, now_ist, today_ist, min_date_allowed, is_super_admin, lo_data_current):
    # --- 96-HOUR (4-DAY) WINDOW FOR OPERATORS ---
    if not is_super_admin:
        min_date_allowed = today_ist - timedelta(days=4)

    default_sr = 1; default_rake = ""; default_source = ""; default_qty = 58; default_type_idx = 0; default_nth = ""; default_muth = ""; default_gcv = 0; default_vm = 0.00
    d_rec_def = None; t_rec_def = None; d_pla_def = None; t_pla_def = None; d_end_def = None; t_end_def = None; d_rel_def = None; t_rel_def = None
    tip_defaults = { "WT-1": (0, None, None), "WT-2": (0, None, None), "WT-3": (0, None, None), "WT-4": (0, None, None) }
    show_form = True; form_is_valid = True; is_partial_default = False
    
    def_tip_list = []
    def_assignment_type = "Assign Tippler(s)"
    tippler_status = []

    all_partial_rakes = []
    blocked_rakes = []
    if not df_all.empty and 'REMARKS' in df_all.columns:
        partial_df = df_all[df_all['REMARKS'].astype(str).str.contains(r'\[PARTIAL\]', na=False)]
        for _, row in partial_df.iterrows():
            rake_val = str(row.get('RAKE No')).strip()
            all_partial_rakes.append(rake_val)
            rec_dt = row.get('Parsed_DateTime')
            if pd.notnull(rec_dt) and isinstance(rec_dt, datetime):
                rec_dt_aware = config.IST.localize(rec_dt)
                # 96 HOUR LIMIT FOR PARTIAL RAKES
                if (now_ist - rec_dt_aware).total_seconds() > 96 * 3600:
                    blocked_rakes.append(rake_val)

    if all_partial_rakes:
        st.warning(f"⚠️ **Pending Partial Rakes ({len(all_partial_rakes)}/5):** The following rakes are incomplete and need to be edited to finalize: **{', '.join(all_partial_rakes)}**")

    col_mode, col_edit, col_warn = st.columns([1.5, 2, 3], gap="small")
    with col_mode:
        mode_options = ["➕ New Entry", "✏️ Edit Existing"]
        curr_idx = 0 if st.session_state.get('current_mode', '➕ New Entry') == "➕ New Entry" else 1
        
        entry_mode = st.radio("Operation Mode", mode_options, index=curr_idx, label_visibility="collapsed")
        
        if entry_mode != st.session_state.get('current_mode', '➕ New Entry'):
            st.session_state.current_mode = entry_mode
            st.session_state.current_edit_rake = None
            st.session_state.outages_list.clear()
            st.session_state.form_key += 1
            st.session_state.outage_key = 0
            st.rerun()

    if entry_mode == "➕ New Entry":
        if (blocked_rakes or len(all_partial_rakes) >= 5) and not is_super_admin:
            if blocked_rakes: st.error(f"🚨 **SYSTEM LOCKED (96-HOUR RULE):** The following Partial Rakes have been pending for > 96 hours: **{', '.join(blocked_rakes)}**")
            if len(all_partial_rakes) >= 5: st.error(f"🚨 **SYSTEM LOCKED (5-RAKE LIMIT):** There are currently {len(all_partial_rakes)} pending partial rakes. Maximum allowed is 5.")
            st.error("You MUST switch to '✏️ Edit Existing', fill their missing data, and uncheck 'Partial Entry' before making any new entries.")
            show_form = False
        else:
            with col_warn:
                if is_super_admin: st.success("🛡️ Super Admin: Restrictions Disabled.")
                else: st.info("ℹ️ Strict Dual Chronological Sequence Active (+1/+1).")
            default_sr, default_rake = get_next_rake_details(df_all, today_ist)
        
    elif entry_mode == "✏️ Edit Existing":
        df_dropdown = df_all.copy()
        existing_rakes = [str(r) for r in df_dropdown.get('RAKE No', pd.Series(dtype=str)).astype(str).str.strip().str.lstrip("'").tolist() if str(r).lower() not in ['nan', 'none', '<na>', '']]
        unique_rakes = list(dict.fromkeys(reversed(existing_rakes)))
        unique_rakes.reverse()
        display_rakes = unique_rakes if is_super_admin else unique_rakes[-25:]
        
        if display_rakes:
            options = list(reversed(display_rakes))
            sel_idx = options.index(st.session_state.current_edit_rake) if st.session_state.current_edit_rake in options else 0
            
            with col_edit:
                selected_edit_rake = st.selectbox("🔍 Search RAKE to Edit:", options, index=sel_idx, label_visibility="collapsed")
            
            if selected_edit_rake:
                if selected_edit_rake != st.session_state.current_edit_rake:
                    clean_rakes = df_all['RAKE No'].astype(str).str.strip().str.lstrip("'")
                    matched_rakes = df_all[clean_rakes == selected_edit_rake]
                    if not matched_rakes.empty:
                        row = matched_rakes.iloc[-1]
                        st.session_state.current_edit_rake = selected_edit_rake
                        st.session_state.outages_list = utils.parse_outages(row.get('REMARKS', ''))
                        st.session_state.form_key += 1
                        st.session_state.outage_key = 0
                        st.rerun()

                clean_rakes = df_all['RAKE No'].astype(str).str.strip().str.lstrip("'")
                matched_rakes = df_all[clean_rakes == selected_edit_rake]
                if not matched_rakes.empty:
                    row = matched_rakes.iloc[-1]
                
                try: default_sr = int(row.get('Sr. No.', 1))
                except: pass
                default_rake = selected_edit_rake
                val_source = row.get('Coal siding/ Company'); default_source = str(val_source).replace(" ", "") if pd.notna(val_source) else ""
                val_nth = row.get('NTH'); default_nth = str(val_nth) if pd.notna(val_nth) else ""
                val_muth = row.get('MUTH'); default_muth = str(val_muth) if pd.notna(val_muth) else ""
                
                try: default_gcv = int(float(row.get('GCV', 0))) if pd.notna(row.get('GCV')) else 0
                except: default_gcv = 0
                try: default_vm = float(row.get('VM', 0.0)) if pd.notna(row.get('VM')) else 0.00
                except: default_vm = 0.00
                
                spec_str = str(row.get('(BOXN / BOBR)', ''))
                if spec_str and spec_str.lower() != 'nan':
                    try: default_qty = int(''.join(filter(str.isdigit, spec_str)))
                    except: pass
                    if 'R' in spec_str.upper(): default_type_idx = 1
                        
                d_rec_def, t_rec_def = utils.parse_excel_datetime(row.get('Receipt Date/Time'))
                d_pla_def, t_pla_def = utils.parse_excel_datetime(row.get('Placement Date/Time'))
                d_end_def, t_end_def = utils.parse_excel_datetime(row.get('U/L End Date/Time'))
                d_rel_def, t_rel_def = utils.parse_excel_datetime(row.get('Rake Rel. Date/Time'))
                
                for w in ["WT-1", "WT-2", "WT-3", "WT-4"]: tip_defaults[w] = utils.parse_excel_tippler(row.get(w, ''))
                is_partial_default = "[PARTIAL]" in str(row.get('REMARKS', ''))
                
                if is_partial_default:
                    rem_text = str(row.get('REMARKS', '')).upper()
                    if "RAKE WAITING" in rem_text:
                        def_assignment_type = "Rake Waiting"
                        
                    for wt in ["WT-1", "WT-2", "WT-3", "WT-4"]:
                        v = str(row.get(wt, '')).strip()
                        if v and v.lower() not in ['nan', 'none', '']:
                            def_tip_list.append(wt)
            else:
                st.info("👆 Please select a RAKE No. to edit.")
                show_form = False
        else:
            st.warning("No data available to edit."); show_form = False

    if show_form:
        with st.container(border=True):
            cp1, cp2 = st.columns([1, 3], gap="small")
            with cp1: st.markdown("##### 1. Rake Identity & Coal Details")
            with cp2: is_partial = st.checkbox("⚠️ Submit as Partial Entry (Allows empty/incomplete dates)", value=is_partial_default, key=f"partial_{st.session_state.form_key}")

            c1, c2, c3, c4, c5, c6, c7 = st.columns([0.8, 1.5, 2, 1, 0.8, 1, 1], gap="small")
            with c1: sr_no = st.number_input("Sr.No", min_value=1, step=1, value=default_sr, key=f"sr_{st.session_state.form_key}")
            with c2: rake_no = st.text_input("RAKE No (XX/XXXX)*", value=default_rake, disabled=not is_super_admin, key=f"rk_{st.session_state.form_key}").strip().upper() 
            with c3: source = st.text_input("Coal siding/ Company*", value=default_source, key=f"src_{st.session_state.form_key}").strip().upper().replace(" ", "")
            with c4: w_qty = st.number_input("Wagons*", min_value=1, max_value=99, value=default_qty, key=f"wq_{st.session_state.form_key}")
            with c5: w_type = st.selectbox("Type*", ["N", "R"], index=default_type_idx, key=f"wt_{st.session_state.form_key}")
            
            auto_gcv, auto_vm = None, None
            if "/" in source:
                parts = source.split("/")
                if len(parts) == 2:
                    auto_gcv, auto_vm = lookup_gcv_vm(parts[0], parts[1])
            
            is_quality_locked = auto_gcv is not None
            display_gcv = auto_gcv if auto_gcv is not None else default_gcv
            display_vm = auto_vm if auto_vm is not None else default_vm

            if is_quality_locked:
                st.session_state[f"gcv_{st.session_state.form_key}"] = int(display_gcv)
                st.session_state[f"vm_{st.session_state.form_key}"] = float(display_vm)

            with c6: gcv_val = st.number_input("GCV (xxxx)", min_value=0, max_value=9999, value=int(display_gcv), step=1, format="%d", disabled=is_quality_locked, key=f"gcv_{st.session_state.form_key}")
            with c7: vm_val = st.number_input("VM % (xx.xx)", min_value=0.00, max_value=99.99, value=float(display_vm), step=0.01, format="%.2f", disabled=is_quality_locked, key=f"vm_{st.session_state.form_key}")
            
            if is_quality_locked:
                st.caption("✅ Data locked from Master")
            
            is_ntpc_owned = False
            if w_type == "R":
                is_ntpc_owned = st.checkbox("NTPC Owned Rake? (Forces 0 Demurrage)", key=f"ntpc_owned_{st.session_state.form_key}")
                
            wagon_spec = f"{w_qty}{w_type}"

            if not rake_no or not source:
                st.warning("⚠️ RAKE No and Coal siding/ Company are mandatory."); form_is_valid = False
            elif not re.match(r"^\d{1,3}/\d{1,4}$", rake_no): 
                st.error("❌ **Format Error:** RAKE No must strictly be numeric format: (e.g., 01/1234)."); form_is_valid = False
            elif not re.match(r"^[A-Z]{1,4}/[A-Z]{1,4}$", source):
                st.error("❌ **Format Error:** Coal siding/ Company must strictly be in format 'XXXX/XXXX' (up to 4 letters on each side, e.g., KDH/CCL)."); form_is_valid = False
            elif entry_mode == "➕ New Entry" and not df_all.empty and 'RAKE No' in df_all.columns:
                df_clean = df_all.copy()
                df_clean['RAKE No'] = df_clean['RAKE No'].astype(str).str.strip().str.lstrip("'")
                df_clean = df_clean[~df_clean['RAKE No'].isin(['nan', '', 'None'])]
                if not df_clean.empty:
                    existing_rakes = df_clean['RAKE No'].tolist()
                    if rake_no not in existing_rakes and len(existing_rakes) > 0:
                        last_rake = existing_rakes[-1]
                        if '/' in last_rake and '/' in rake_no:
                            try:
                                prev_a, prev_b = map(int, last_rake.split('/'))
                                curr_a, curr_b = map(int, rake_no.split('/'))
                                if not is_super_admin:
                                    is_valid_sequence = False
                                    if (curr_a == 1) and (curr_b == 1): 
                                        is_valid_sequence = True
                                    elif (curr_a == 1) and (curr_b == prev_b + 1): 
                                        is_valid_sequence = True
                                    elif (curr_a == prev_a + 1) and (curr_b == prev_b + 1): 
                                        is_valid_sequence = True
                                        
                                    if not is_valid_sequence:
                                        len_a, len_b = len(last_rake.split('/')[0]), len(last_rake.split('/')[1])
                                        st.error(f"❌ **Sequence Error:** The last RAKE was **{last_rake}**. Valid sequences: Normal days (+1/+1), start of month (01/+1), or April 1st (01/0001).")
                                        form_is_valid = False
                            except ValueError: pass

            if not is_partial:
                if not (1000 <= gcv_val <= 9999) and not is_quality_locked:
                    st.error("❌ **Coal Quality Error:** GCV must be exactly a 4-digit number (e.g., 4200).")
                    form_is_valid = False
                if (vm_val <= 0.0 or vm_val >= 100.0) and not is_quality_locked:
                    st.error("❌ **Coal Quality Error:** VM % must be a valid percentage greater than 0.")
                    form_is_valid = False

        with st.container(border=True):
            st.markdown("##### 2. Operational Timeline (IST)")
            t1, t2, t3, t4 = st.columns(4, gap="small")
            req_mark = "" if is_partial else "*"
            
            ui_policy_min = min_date_allowed
                
            def safe_min(def_dt):
                if ui_policy_min is None: return None
                if def_dt is None: return ui_policy_min
                return min(def_dt, ui_policy_min)

            with t1:
                d_rec = st.date_input("Receipt Date*", value=d_rec_def, key=f"dr_{st.session_state.form_key}", min_value=safe_min(d_rec_def), max_value=today_ist)
                ti_rec = st.time_input("Receipt Time*", value=t_rec_def, step=60, key=f"tr_{st.session_state.form_key}")
            with t2:
                d_pla = st.date_input(f"Placement Date{req_mark}", value=d_pla_def, key=f"dp_{st.session_state.form_key}", min_value=safe_min(d_pla_def), max_value=today_ist)
                ti_pla = st.time_input(f"Placement Time{req_mark}", value=t_pla_def, step=60, key=f"tp_{st.session_state.form_key}")
            with t3:
                d_end = st.date_input(f"U/L End Date{req_mark}", value=d_end_def, key=f"de_{st.session_state.form_key}", min_value=safe_min(d_end_def), max_value=today_ist)
                ti_end = st.time_input(f"U/L End Time{req_mark}", value=t_end_def, step=60, key=f"te_{st.session_state.form_key}")
            with t4:
                d_rel = st.date_input(f"Release Date{req_mark}", value=d_rel_def, key=f"drel_{st.session_state.form_key}", min_value=safe_min(d_rel_def), max_value=today_ist)
                ti_rel = st.time_input(f"Release Time{req_mark}", value=t_rel_def, step=60, key=f"trel_{st.session_state.form_key}")

            dt_rec = config.IST.localize(datetime.combine(d_rec, ti_rec)) if d_rec and ti_rec else None
            dt_pla = config.IST.localize(datetime.combine(d_pla, ti_pla)) if d_pla and ti_pla else None
            dt_end = config.IST.localize(datetime.combine(d_end, ti_end)) if d_end and ti_end else None
            dt_rel = config.IST.localize(datetime.combine(d_rel, ti_rel)) if d_rel and ti_rel else None

            u_duration_str, r_duration_str, demurrage_val, timeline_valid = "00:00", "00:00", 0, True

            if is_partial:
                if not dt_rec: 
                    st.error("❌ Receipt Date and Time are mandatory, even for partial entries.")
                    form_is_valid = False; timeline_valid = False
                    
                if dt_rec and dt_pla and dt_rec > dt_pla: st.error("❌ Placement cannot be before Receipt."); form_is_valid = False; timeline_valid = False
                if dt_end and dt_pla and dt_end < dt_pla: st.error("❌ End cannot be before Placement."); form_is_valid = False; timeline_valid = False
                if dt_rel and dt_end and dt_rel < dt_end: st.error("❌ Release cannot be before End."); form_is_valid = False; timeline_valid = False
            else:
                if not (dt_rec and dt_pla and dt_end and dt_rel): st.warning("⚠️ ALL 4 Dates and Times are required for a complete submission."); form_is_valid = False; timeline_valid = False
                elif not (dt_rec <= dt_pla <= dt_end <= dt_rel): st.error("❌ Dates/Times must strictly follow: Receipt ➔ Placement ➔ U/L End ➔ Release."); form_is_valid = False; timeline_valid = False

            if timeline_valid and dt_rec and dt_pla and dt_end and dt_rel:
                u_sec, r_sec = int((dt_end - dt_pla).total_seconds()), int((dt_rel - dt_rec).total_seconds())
                u_duration_str = f"{u_sec//3600:02d}:{(u_sec%3600)//60:02d}"
                r_duration_str = f"{r_sec//3600:02d}:{(r_sec%3600)//60:02d}"
                r_hours = r_sec / 3600.0
                free_time = 7.0 if w_type == "N" else 2.0
                if r_hours > free_time: demurrage_val = math.ceil(r_hours - free_time)
                if is_ntpc_owned: demurrage_val = 0

            if timeline_valid:
                for dt_val, lbl in [(dt_rec, "Receipt"), (dt_pla, "Placement"), (dt_end, "U/L End"), (dt_rel, "Release")]:
                    if dt_val:
                        is_ok, msg = utils.validate_time_window(dt_val, lbl, demurrage_val, is_super_admin, now_ist, entry_mode, w_type, is_ntpc_owned)
                        if not is_ok: st.error(msg); form_is_valid = False

        col_left, col_right = st.columns([1.3, 1], gap="small")

        with col_left:
            with st.container(border=True):
                st.markdown("##### 3. Tippler Operations")
                
                # --- FOOLPROOF UI: MASTER SWITCH FOR TIPPLER ASSIGNMENT ---
                if is_partial and w_type == "N":
                    st.markdown("**🚨 Tippler Assignment (Mandatory)**")
                    a_idx = 1 if def_assignment_type == "Rake Waiting" else 0
                    
                    assignment_type = st.radio(
                        "Status", 
                        ["Assign Tippler(s)", "Rake Waiting"], 
                        index=a_idx, 
                        horizontal=True, 
                        label_visibility="collapsed", 
                        key=f"atype_{st.session_state.form_key}"
                    )
                    
                    if assignment_type == "Assign Tippler(s)":
                        safe_defaults = [t for t in def_tip_list if t in ["WT-1", "WT-2", "WT-3", "WT-4"]]
                        tippler_status = st.multiselect(
                            "Select Tippler(s)", 
                            ["WT-1", "WT-2", "WT-3", "WT-4"], 
                            default=safe_defaults, 
                            key=f"tstat_{st.session_state.form_key}"
                        )
                        if not tippler_status:
                            st.error("❌ You MUST select at least one Tippler.")
                            form_is_valid = False
                    else:
                        # Rake Waiting is selected, lock out multiselect
                        tippler_status = ["Rake Waiting"]
                        st.info("ℹ️ Rake will be safely marked as waiting for a tippler.")
                        
                    st.markdown("<hr style='margin:0.2em 0;'>", unsafe_allow_html=True)
                
                allow_nth_muth = (w_type == "R")
                n1, n2 = st.columns(2, gap="small")
                
                with n1: 
                    nth = st.text_input("NTH (BOBR)", value=default_nth if allow_nth_muth else "", max_chars=2, disabled=not allow_nth_muth, key=f"nth_{st.session_state.form_key}").strip()
                    if nth and not nth.isdigit(): 
                        st.error("❌ NTH Qty must be strictly numeric (0-99).")
                        form_is_valid = False
                with n2: 
                    muth = st.text_input("MUTH (BOBR)", value=default_muth if allow_nth_muth else "", max_chars=2, disabled=not allow_nth_muth, key=f"muth_{st.session_state.form_key}").strip()
                    if muth and not muth.isdigit(): 
                        st.error("❌ MUTH Qty must be strictly numeric (0-99).")
                        form_is_valid = False
                
                if not allow_nth_muth: nth, muth = "", ""
                    
                st.markdown("<hr style='margin:0.2em 0;'>", unsafe_allow_html=True)
                
                tippler_data = {}
                actual_tip_starts = []
                actual_tip_ends = []
                
                for name in ["WT-1", "WT-2", "WT-3", "WT-4"]:
                    def_qty, def_s, def_e = tip_defaults[name]
                    w1, w2, w3 = st.columns(3, gap="small")
                    with w1: t_qty = st.number_input(f"{name} Wagons", min_value=0, value=def_qty, key=f"q_{name}_{st.session_state.form_key}")
                    with w2: t_start = st.time_input("Start*", value=def_s, key=f"s_{name}_{st.session_state.form_key}", step=60)
                    with w3: t_end = st.time_input("End", value=def_e, key=f"e_{name}_{st.session_state.form_key}", step=60)
                    
                    if t_qty > 0:
                        if t_start and t_end:
                            tippler_data[name] = f"{t_qty}\n{t_start.strftime('%H:%M')}-{t_end.strftime('%H:%M')}"
                        elif t_start and not t_end:
                            tippler_data[name] = f"{t_qty}\n{t_start.strftime('%H:%M')}-Ongoing"
                        elif not t_start and t_end:
                            tippler_data[name] = f"{t_qty}\nOngoing-{t_end.strftime('%H:%M')}"
                        else:
                            tippler_data[name] = f"{t_qty}"
                    else: tippler_data[name] = ""

                total_handled = sum(st.session_state.get(f"q_{n}_{st.session_state.form_key}", 0) for n in ["WT-1", "WT-2", "WT-3", "WT-4"])
                total_handled += (int(nth) if nth.isdigit() else 0) + (int(muth) if muth.isdigit() else 0)

                if not is_partial and total_handled != w_qty:
                    st.error(f"❌ **Mismatch!** Declared: {w_qty}, Handled: {total_handled}."); form_is_valid = False
                
                if timeline_valid:
                    for name in ["WT-1", "WT-2", "WT-3", "WT-4"]:
                        qty = st.session_state.get(f"q_{name}_{st.session_state.form_key}", 0)
                        if qty > 0:
                            t_s = st.session_state.get(f"s_{name}_{st.session_state.form_key}")
                            t_e = st.session_state.get(f"e_{name}_{st.session_state.form_key}")
                            
                            if not t_s:
                                st.error(f"❌ Start Time required for {name}."); form_is_valid = False
                            elif not t_e and not is_partial:
                                st.error(f"❌ End Time required for {name} (Check 'Submit as Partial Entry' if ongoing)."); form_is_valid = False
                            elif t_s and dt_rec and dt_end:
                                dt_tip_start = utils.resolve_tippler_time(t_s, dt_rec, dt_end)
                                if not dt_tip_start: 
                                    st.error(f"❌ {name} Start outside Receipt-End window!"); form_is_valid = False
                                else:
                                    actual_tip_starts.append(dt_tip_start)
                                    
                                if t_e:
                                    dt_tip_end = utils.resolve_tippler_time(t_e, dt_tip_start, dt_end)
                                    if not utils.resolve_tippler_time(t_e, dt_tip_start, dt_end): 
                                        st.error(f"❌ {name} End outside Start-End window!"); form_is_valid = False
                                    else:
                                        actual_tip_ends.append(dt_tip_end)
                                        
                if not is_partial and actual_tip_starts and len(actual_tip_starts) == len(actual_tip_ends):
                    min_start = min(actual_tip_starts)
                    max_end = max(actual_tip_ends)
                    if max_end >= min_start:
                        u_sec_new = int((max_end - min_start).total_seconds())
                        u_duration_str = f"{u_sec_new//3600:02d}:{(u_sec_new%3600)//60:02d}"

        with col_right:
            with st.container(border=True):
                st.markdown("##### 4. Summary & Add Outages")
                ca1, ca2, ca3 = st.columns(3, gap="small")
                with ca1: st.text_input("U/L Duration", value=u_duration_str, disabled=True)
                with ca2: st.text_input("Cycle Time", value=r_duration_str, disabled=True)
                with ca3: st.text_input("Demurrage (Hrs)", value=str(demurrage_val) if not is_partial else "0", disabled=True)

                auto_bunching_remark = ""
                if timeline_valid and w_type == "N" and dt_rec:
                    df_hist = df_all.copy()
                    df_hist['RAKE No'] = df_hist['RAKE No'].astype(str).str.strip().str.lstrip("'")
                    df_hist = df_hist[~df_hist['RAKE No'].isin(['nan', '', 'None'])]
                    if entry_mode == "✏️ Edit Existing" and rake_no:
                        df_hist = df_hist[df_hist['RAKE No'] != rake_no]
                    
                    df_hist = df_hist.dropna(subset=['Parsed_DateTime']).sort_values(by='Parsed_DateTime', ascending=True)
                    
                    dt_rec_naive = datetime.combine(d_rec, ti_rec)
                    df_hist = df_hist[df_hist['Parsed_DateTime'] < dt_rec_naive]
                    
                    boxn_mask = df_hist['(BOXN / BOBR)'].astype(str).str.upper().apply(lambda x: 'N' in x and 'R' not in x)
                    df_boxn = df_hist[boxn_mask]
                    
                    if len(df_boxn) >= 2:
                        last_2 = df_boxn.iloc[-2]
                        dt_1 = last_2.get('Parsed_DateTime') 
                        if pd.notnull(dt_1) and isinstance(dt_1, datetime):
                            dt_1_aware = config.IST.localize(dt_1)
                            if dt_rec > dt_1_aware and dt_rec <= (dt_1_aware + timedelta(hours=5)):
                                b_sec = (dt_1_aware + timedelta(hours=5) - dt_rec).total_seconds()
                                if b_sec > 0:
                                    b_hrs, b_mins = int(b_sec // 3600), int((b_sec % 3600) // 60)
                                    auto_bunching_remark = f"⚪ OTHER | Railway -Bunching {b_hrs:02d}:{b_mins:02d} hrs"
                                    st.info(f"🚂 **Auto-Bunching Math:** Rake 1 arrived at {dt_1_aware.strftime('%H:%M')}. The 5-hr window expires at {(dt_1_aware + timedelta(hours=5)).strftime('%H:%M')}. This rake arrived at {dt_rec.strftime('%H:%M')}. The system is auto-logging `{b_hrs:02d}:{b_mins:02d} hrs`.")

                is_finalizing = False
                if entry_mode == "➕ New Entry" and not is_partial: is_finalizing = True
                elif entry_mode == "✏️ Edit Existing" and is_partial_default and not is_partial: is_finalizing = True
                
                with st.expander("🛠️ Add Outages (Mandatory if Demurrage > 0)", expanded=True):
                    okey_add = f"add_{st.session_state.form_key}_{st.session_state.outage_key}"
                    o1, o2 = st.columns([1.5, 3], gap="small")
                    with o1: dept = st.selectbox("Dept", ["MM", "EMD", "C&I", "OPR", "MGR", "CHEM", "OTHER"], key=f"o_dept_{okey_add}")
                    with o2: o_reason = st.text_input("Reason", autocomplete="off", key=f"o_reason_{okey_add}")
                    
                    o_start_date = today_ist
                    o_start_time = None
                    o_end_date = today_ist
                    o_end_time = None
                    
                    if dept != "OTHER":
                        od1, od2 = st.columns(2, gap="small")
                        with od1: 
                            o_start_date = st.date_input("Start Date", value=today_ist, min_value=min_date_allowed, max_value=today_ist, key=f"o_sd_{okey_add}")
                            o_start_time = st.time_input("Start Time", value=None, step=60, key=f"o_st_{okey_add}")
                        with od2: 
                            o_end_date = st.date_input("Rest Date", value=today_ist, min_value=min_date_allowed, max_value=today_ist, key=f"o_ed_{okey_add}")
                            o_end_time = st.time_input("Rest Time", value=None, step=60, key=f"o_et_{okey_add}")
                    
                    if st.button("➕ Add Outage", use_container_width=True):
                        safe_reason = o_reason.replace("|", "-").strip().upper()
                        dept_label = config.DEPT_COLORS.get(dept, dept)
                        
                        if not safe_reason: 
                            st.error("❌ Reason mandatory.")
                        elif dept == "OTHER":
                            st.session_state.outages_list.append({"Dept": "OTHER", "Start": "-", "End": "-", "Reason": safe_reason, "Log": f"{dept_label} | {safe_reason}"})
                            st.session_state.outage_key += 1; st.rerun()
                        else:
                            if not is_partial and not o_end_time and ti_end:
                                o_end_time = ti_end
                                o_end_date = d_end

                            if not o_start_time:
                                st.error("❌ Start time is required.")
                            elif not o_end_time and not is_partial:
                                st.error("❌ Rest time is required. (Check 'Submit as Partial Entry' if ongoing)")
                            else:
                                dt_o_s = config.IST.localize(datetime.combine(o_start_date, o_start_time))
                                is_ok_start, msg_s = utils.validate_time_window(dt_o_s, "Outage Start", demurrage_val, is_super_admin, now_ist, entry_mode, w_type, is_ntpc_owned)
                                
                                if not is_ok_start: 
                                    st.error(msg_s)
                                else:
                                    if o_end_time:
                                        dt_o_e = config.IST.localize(datetime.combine(o_end_date, o_end_time))
                                        is_ok_end, msg_e = utils.validate_time_window(dt_o_e, "Outage End", demurrage_val, is_super_admin, now_ist, entry_mode, w_type, is_ntpc_owned)
                                        if dt_o_e < dt_o_s: st.error("❌ Invalid: Rest Date/Time < Start Date/Time.")
                                        elif not is_ok_end: st.error(msg_e)
                                        else:
                                            if o_start_date == o_end_date: str_s, str_e = f"{o_start_time.strftime('%H:%M')}", f"{o_end_time.strftime('%H:%M')}"
                                            else: str_s, str_e = f"{o_start_date.strftime('%d.%m')} {o_start_time.strftime('%H:%M')}", f"{o_end_date.strftime('%d.%m')} {o_end_time.strftime('%H:%M')}"
                                            st.session_state.outages_list.append({"Dept": dept, "Start": str_s, "End": str_e, "Reason": safe_reason, "Log": f"{dept_label} | {str_s} to {str_e} | {safe_reason}"})
                                            st.session_state.outage_key += 1; st.rerun()
                                    else: 
                                        str_s = f"{o_start_time.strftime('%H:%M')}" if o_start_date == today_ist else f"{o_start_date.strftime('%d.%m')} {o_start_time.strftime('%H:%M')}"
                                        str_e = "Ongoing"
                                        st.session_state.outages_list.append({"Dept": dept, "Start": str_s, "End": str_e, "Reason": safe_reason, "Log": f"{dept_label} | {str_s} to {str_e} | {safe_reason}"})
                                        st.session_state.outage_key += 1; st.rerun()

        okey_edit = f"edit_{st.session_state.form_key}_{st.session_state.outage_key}"
        if st.session_state.outages_list:
            with st.container(border=True):
                st.markdown("##### 5. Review & Edit Logged Outages")
                st.caption("✏️ **Edit times or mark ongoing outages as 'Fixed' before final submission:**")
                
                h1, h2, h3, h4, h5 = st.columns([1, 1.5, 2.5, 4, 0.5], gap="medium")
                with h1: st.markdown("**Dept**")
                with h2: st.markdown("**Start Time**")
                with h3: st.markdown("**End Status & Time**")
                with h4: st.markdown("**Reason**")
                
                for idx, outg in enumerate(st.session_state.outages_list):
                    if outg['Dept'] == "OTHER":
                        c1, c2, c3 = st.columns([1, 8.5, 0.5], gap="medium")
                        with c1: st.text_input("Dept", value=outg['Dept'], key=f"ed_d_{idx}_{okey_edit}", disabled=True, label_visibility="collapsed")
                        with c2: new_rsn = st.text_input("Reason", value=outg['Reason'], key=f"ed_r_{idx}_{okey_edit}", label_visibility="collapsed")
                        with c3:
                            if st.button("❌", key=f"del_o_{idx}_{okey_edit}"): 
                                st.session_state.outages_list.pop(idx); st.session_state.outage_key += 1; st.rerun()
                                
                        safe_new_rsn = new_rsn.replace("|", "-").strip().upper()
                        if safe_new_rsn != outg['Reason']:
                            outg['Reason'] = safe_new_rsn
                            dept_label = config.DEPT_COLORS.get(outg['Dept'], outg['Dept'])
                            outg['Log'] = f"{dept_label} | {outg['Reason']}"
                    else:
                        s_parts = outg['Start'].split()
                        s_date_prefix = s_parts[0] + " " if len(s_parts) == 2 else ""
                        t_str = s_parts[1] if len(s_parts) == 2 else (s_parts[0] if s_parts else "")
                        try: s_time_obj = datetime.strptime(t_str, "%H:%M").time()
                        except: s_time_obj = None

                        is_ongoing = (outg['End'] == "Ongoing")
                        e_time_obj = None
                        e_date_prefix = ""
                        
                        if not is_partial and is_ongoing and ti_end:
                            is_ongoing = False
                            e_time_obj = ti_end
                            if d_end and d_end != today_ist:
                                e_date_prefix = f"{d_end.strftime('%d.%m')} "
                        else:
                            e_parts = outg['End'].split() if not is_ongoing and outg['End'] != "Ongoing" else []
                            e_date_prefix = e_parts[0] + " " if len(e_parts) == 2 else ""
                            e_t_str = e_parts[1] if len(e_parts) == 2 else (e_parts[0] if e_parts else "")
                            try: e_time_obj = datetime.strptime(e_t_str, "%H:%M").time()
                            except: e_time_obj = None

                        c1, c2, c3, c4, c5 = st.columns([1, 1.5, 2.5, 4, 0.5], gap="medium")
                        with c1: 
                            st.text_input("Dept", value=outg['Dept'], key=f"ed_d_{idx}_{okey_edit}", disabled=True, label_visibility="collapsed")
                        with c2: 
                            new_s_time = st.time_input("Start", value=s_time_obj, key=f"ed_s_{idx}_{okey_edit}", label_visibility="collapsed", step=60)
                        with c3:
                            cs1, cs2 = st.columns([1, 1.5], gap="small")
                            with cs1: 
                                e_status = st.selectbox("Status", ["Fixed", "Ongoing"], index=1 if is_ongoing else 0, key=f"stat_{idx}_{okey_edit}", label_visibility="collapsed")
                            with cs2:
                                if e_status == "Fixed":
                                    new_e_time = st.time_input("End", value=e_time_obj, key=f"ed_e_{idx}_{okey_edit}", label_visibility="collapsed", step=60)
                                else:
                                    new_e_time = "Ongoing"
                                    st.text_input("End", value="Ongoing", disabled=True, key=f"fake_e_{idx}_{okey_edit}", label_visibility="collapsed")
                        with c4: 
                            new_rsn = st.text_input("Reason", value=outg['Reason'], key=f"ed_r_{idx}_{okey_edit}", label_visibility="collapsed")
                        with c5:
                            if st.button("❌", key=f"del_o_{idx}_{okey_edit}"): 
                                st.session_state.outages_list.pop(idx); st.session_state.outage_key += 1; st.rerun()
                                
                        new_start_str = f"{s_date_prefix}{new_s_time.strftime('%H:%M')}" if new_s_time else outg['Start']
                        
                        if e_status == "Ongoing": new_end_str = "Ongoing"
                        elif new_e_time and new_e_time != "Ongoing": new_end_str = f"{e_date_prefix}{new_e_time.strftime('%H:%M')}"
                        else: new_end_str = outg['End']
                        
                        safe_new_rsn = new_rsn.replace("|", "-").strip().upper()

                        if new_start_str != outg['Start'] or new_end_str != outg['End'] or safe_new_rsn != outg['Reason']:
                            outg['Start'], outg['End'], outg['Reason'] = new_start_str, new_end_str, safe_new_rsn
                            dept_label = config.DEPT_COLORS.get(outg['Dept'], outg['Dept'])
                            outg['Log'] = f"{dept_label} | {outg['Start']} to {outg['End']} | {outg['Reason']}"

        applicable_lo_count = sum(1 for lo in lo_data_current if lo.get('affects', 'BOTH') in ["BOTH", w_type]) if is_finalizing else 0
        
        if not is_partial and demurrage_val > 0 and (len(st.session_state.outages_list) + applicable_lo_count) == 0:
            st.error("❌ Demurrage is > 0! You MUST enter a reason or have an active applicable Equipment Long Outage."); form_is_valid = False

        if not is_partial:
            for outg in st.session_state.outages_list:
                if "Ongoing" in outg.get("End", ""):
                    st.error(f"❌ Cannot submit final entry: Outage for **{outg['Dept']}** is marked as 'Ongoing'. It must be 'Fixed'.")
                    form_is_valid = False
                    break

        st.write("") 
        c_sub1, c_sub2 = st.columns([3, 1], gap="small")
        with c_sub2:
            if st.button("🧹 Reset", use_container_width=True):
                st.session_state.outages_list.clear(); st.session_state.current_edit_rake = None if entry_mode == "✏️ Edit Existing" else st.session_state.current_edit_rake; st.session_state.form_key += 1; st.session_state.outage_key = 0; st.rerun()
        with c_sub1:
            if st.button("🚀 SUBMIT", type="primary", use_container_width=True, disabled=not form_is_valid):
                
                current_dept_sel = st.session_state.get(f"o_dept_{okey_add}")
                current_reason_val = st.session_state.get(f"o_reason_{okey_add}", "").strip()
                if current_dept_sel == "OTHER" and current_reason_val:
                    safe_reason = current_reason_val.replace("|", "-").upper()
                    dept_label = config.DEPT_COLORS.get("OTHER", "OTHER")
                    st.session_state.outages_list.append({
                        "Dept": "OTHER", "Start": "-", "End": "-", 
                        "Reason": safe_reason, "Log": f"{dept_label} | {safe_reason}"
                    })

                get_all_excel_data.clear()
                tab_date = d_rec if d_rec else today_ist
                month_tab_name = tab_date.strftime('%b-%y').upper()
                outage_summary = "\n".join([o["Log"] for o in st.session_state.outages_list])
                
                # --- AUTO-STAMP TIPPLER ASSIGNMENT TO PAYLOAD ---
                if is_partial and w_type == "N" and isinstance(tippler_status, list):
                    for t_stat in tippler_status:
                        if t_stat.startswith("WT-"):
                            if not tippler_data[t_stat]:
                                tippler_data[t_stat] = "Assigned"
                
                remaining_lo_to_save = lo_data_current.copy() if lo_data_current else []
                
                if is_finalizing and lo_data_current:
                    lo_lines = []
                    remaining_lo_to_save = []
                    
                    for lo in lo_data_current:
                        affects = lo.get('affects', 'BOTH')
                        if affects in ["BOTH", w_type]:
                            dept_lbl = config.DEPT_COLORS.get(lo.get('dept', ''), lo.get('dept', ''))
                            if lo.get('status') == 'restored': 
                                lo_lines.append(f"{dept_lbl} | {lo.get('equip', '')} (OUTAGE: {lo.get('since_date', '')} {lo.get('since_time', '')} TO {lo.get('rest_date', '')} {lo.get('rest_time', '')})")
                            else: 
                                lo_lines.append(f"{dept_lbl} | {lo.get('equip', '')} (OUTAGE SINCE {lo.get('since_date', '')} {lo.get('since_time', '')})")
                                remaining_lo_to_save.append(lo)
                        else: 
                            remaining_lo_to_save.append(lo)
                    
                    for line in lo_lines:
                        if line not in outage_summary: outage_summary += f"\n{line}"
                    outage_summary = outage_summary.strip()
                    
                clean_lines = [line for line in outage_summary.split('\n') if "BUNCHING" not in line.upper() and "NTPC OWNED" not in line.upper() and "RAKE WAITING" not in line.upper()]
                outage_summary = "\n".join(clean_lines).strip()
                
                if auto_bunching_remark:
                    outage_summary = (outage_summary + f"\n{auto_bunching_remark}").strip()
                    
                if is_ntpc_owned:
                    outage_summary = (outage_summary + "\n⚪ OTHER | NTPC OWNED RAKE").strip()
                    
                # --- ADD WAITING STATUS TO REMARKS ---
                if is_partial and w_type == "N" and isinstance(tippler_status, list) and "Rake Waiting" in tippler_status:
                    outage_summary = (outage_summary + "\n⚪ OTHER | RAKE WAITING FOR TIPPLER").strip()
                
                outage_summary = outage_summary.replace("[PARTIAL]\n", "").replace("[PARTIAL]", "").strip()
                if is_partial:
                    outage_summary = f"[PARTIAL]\n{outage_summary}" if outage_summary else "[PARTIAL]"
                    
                def safe_num(val):
                    try: return float(val) if pd.notna(val) else 0.0
                    except: return 0.0
                
                def safe_int(val):
                    try: return int(float(val)) if pd.notna(val) else 0
                    except: return 0
                    
                payload = {
                    "action": "save", "tab_name": month_tab_name, "sr_no": sr_no, "rake_no": rake_no, "source": source, "wagon_spec": wagon_spec,
                    "receipt": f"{d_rec.strftime('%d.%m.%Y')}/{ti_rec.strftime('%H:%M')}" if d_rec and ti_rec else "",
                    "placement": f"{d_pla.strftime('%d.%m.%Y')}/{ti_pla.strftime('%H:%M')}" if d_pla and ti_pla else "",
                    "u_end": f"{d_end.strftime('%d.%m.%Y')}/{ti_end.strftime('%H:%M')}" if d_end and ti_end else "",
                    "release": f"{d_rel.strftime('%d.%m.%Y')}/{ti_rel.strftime('%H:%M')}" if d_rel and ti_rel else "",
                    "u_duration": f"'{u_duration_str}" if not is_partial else "", 
                    "r_duration": f"'{r_duration_str}" if not is_partial else "", 
                    "demurrage": safe_num(demurrage_val) if not is_partial else 0.0, "remarks": outage_summary, "nth": nth, "muth": muth, 
                    "wt1": tippler_data["WT-1"], "wt2": tippler_data["WT-2"], "wt3": tippler_data["WT-3"], "wt4": tippler_data["WT-4"], "gcv": str(safe_int(gcv_val)) if gcv_val else "", "vm": safe_num(vm_val)
                }
                
                # --- NEW: POSTGRESQL DATABASE SAVE ---
                with st.spinner(f"Saving to secure database..."):
                    try:
                        save_rake_to_db(payload)
                        st.success(f"✅ Rake {rake_no} saved securely to PostgreSQL!")
                        
                        if is_finalizing: save_long_outages(remaining_lo_to_save)
                        if entry_mode == "➕ New Entry":
                            st.session_state.pending_new_sr = sr_no + 1
                            try:
                                prev_a, prev_b = map(int, rake_no.split('/'))
                                len_a, len_b = len(rake_no.split('/')[0]), len(rake_no.split('/')[1])
                                st.session_state.pending_new_rake = f"{prev_a+1:0{len_a}d}/{prev_b+1:0{len_b}d}"
                            except: pass
                        
                        st.session_state.outages_list.clear()
                        st.session_state.form_key += 1
                        st.session_state.outage_key = 0
                        st.session_state.current_mode = "➕ New Entry" 
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Database connection failed: {e}")

        st.markdown("""
            <div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                <p style="color: #666666; font-size: 0.95em; font-family: sans-serif;">
                    <em>App Design, conceptualized and created by:</em><br>
                    <strong>Krishan Mohan Gupta, AGM (CHP-O), Unchahar</strong>
                </p>
            </div>
        """, unsafe_allow_html=True)
