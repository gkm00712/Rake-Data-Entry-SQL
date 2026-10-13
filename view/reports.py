import streamlit as st
import pandas as pd
import utils

# Removed 'Demurrage (in Rs)' from drop list so it renders correctly
cols_to_drop = ['Parsed_DateTime', 'Parsed_Date', 'Loaded_From_Tab', 'id']

def render_daily_tab(df_all, today_ist):
    daily_date = st.date_input("Target Date:", value=today_ist, key="daily_date")
    if not df_all.empty and 'Parsed_Date' in df_all.columns:
        filtered_df = df_all[df_all['Parsed_Date'] == daily_date]
        if filtered_df.empty: 
            st.info(f"No records for {daily_date.strftime('%d.%m.%Y')}.")
        else:
            # FORCE ASCENDING CHRONOLOGICAL ORDER (OLDEST FIRST)
            if 'Parsed_DateTime' in filtered_df.columns:
                filtered_df = filtered_df.sort_values(by='Parsed_DateTime', ascending=True)
                
            display_df = filtered_df.drop(columns=[c for c in cols_to_drop if c in filtered_df.columns], errors='ignore')
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.download_button(
                f"💾 Download {daily_date.strftime('%d.%m.%Y')} Report", 
                utils.generate_formatted_excel(filtered_df), 
                file_name=f"Daily_Report_{daily_date.strftime('%Y%m%d')}.xlsx", 
                type="primary"
            )

def render_monthly_tab(df_all, today_ist):
    cm, cy = st.columns(2, gap="small")
    with cm: month_sel = st.selectbox("Month:", range(1, 13), index=today_ist.month - 1)
    with cy: year_sel = st.number_input("Year:", value=today_ist.year, step=1)
    
    if st.button("🔍 Generate Monthly", type="primary"):
        with st.spinner("Fetching..."):
            if not df_all.empty and 'Parsed_Date' in df_all.columns:
                filtered_df = df_all[df_all['Parsed_Date'].apply(lambda d: d.month == month_sel and d.year == year_sel if pd.notnull(d) else False)]
                if filtered_df.empty: 
                    st.warning(f"No records for {month_sel:02d}/{year_sel}.")
                else:
                    # FORCE ASCENDING CHRONOLOGICAL ORDER (OLDEST FIRST)
                    if 'Parsed_DateTime' in filtered_df.columns:
                        filtered_df = filtered_df.sort_values(by='Parsed_DateTime', ascending=True)
                        
                    display_df = filtered_df.drop(columns=[c for c in cols_to_drop if c in filtered_df.columns], errors='ignore')
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.download_button(
                        f"💾 Download {month_sel:02d}/{year_sel}", 
                        utils.generate_formatted_excel(filtered_df), 
                        file_name=f"Monthly_Report_{year_sel}_{month_sel:02d}.xlsx",
                        type="primary"
                    )
