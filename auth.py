import streamlit as st
import bcrypt
import os

QUALITY_FILE = "quality_data.xlsx"

def login_screen():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; margin-top: 10vh; color: #003366;'>🚂 Rake Data Entry System</h2>", unsafe_allow_html=True)
        
        # --- NEW: MASTER DATA UPLOAD ---
        st.markdown("### 📁 Master Data Upload")
        st.caption("Upload the GCV & VM Master Sheet (.xlsx). Operators cannot log in without it.")
        uploaded_file = st.file_uploader("Quality Master Sheet", type=["xlsx"], key="qual_upload_login", label_visibility="collapsed")
        if uploaded_file is not None:
            with open(QUALITY_FILE, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("✅ Master file uploaded successfully!")
        
        st.write("") # Spacer

        # --- LOGIN FORM ---
        with st.form("login_form"):
            st.markdown("**Please sign in to continue**")
            username = st.text_input("Username", autocomplete="off").strip().lower()
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Secure Login", use_container_width=True):
                if "users" in st.secrets and username in st.secrets["users"]:
                    user_data = st.secrets["users"][username]
                    
                    stored_hash = user_data["password"].encode('utf-8')
                    entered_password = password.encode('utf-8')
                    
                    if bcrypt.checkpw(entered_password, stored_hash):
                        role = user_data["role"]
                        
                        # --- STRICT GATEKEEPER ---
                        if role == "Operator" and not os.path.exists(QUALITY_FILE):
                            st.error("❌ Login Denied: The Quality Master Sheet must be uploaded first.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.role = role
                            st.session_state.username = username
                            st.rerun()
                    else: 
                        st.error("❌ Invalid Credentials")
                else:
                    st.error("❌ Invalid Credentials")

        # --- FOOTER CREDIT ---
        st.markdown("""
            <div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                <p style="color: #666666; font-size: 0.95em; font-family: sans-serif;">
                    <em>App Design, conceptualized and created by:</em><br>
                    <strong>Krishan Mohan Gupta, AGM (CHP-O), Unchahar</strong>
                </p>
            </div>
        """, unsafe_allow_html=True)
