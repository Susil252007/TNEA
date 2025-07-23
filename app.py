# ✅ Combined TNEA Streamlit App
# Includes: 
# - Authentication & session logic
# - Rank & Cutoff Viewer
# - Vacancy Viewer (Branch & College wise)

import streamlit as st
import pandas as pd
import yaml
import requests
import io
import uuid
import time
from datetime import timedelta
import plotly.express as px

# --- SESSION SETTINGS ---
SESSION_TIMEOUT = 180  # 3 minutes

st.set_page_config(page_title="TNEA Unified App", layout="wide")

# --- Force black font in DataFrames ---
st.markdown("""
    <style>
    .stDataFrame div {
        color: black !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- PATHS ---
config_path = "config.yaml"
device_session_path = "device_session.yaml"

# --- CONFIG ---
try:
    with open(config_path) as file:
        config = yaml.safe_load(file)
    user_data = config["credentials"]["users"]
except Exception as e:
    st.error(f"Failed to load config.yaml: {e}")
    st.stop()

# --- DEVICE SESSION ---
try:
    with open(device_session_path) as session_file:
        session_data = yaml.safe_load(session_file)
except Exception:
    session_data = {"active_users": {}}

def save_session():
    with open(device_session_path, "w") as f:
        yaml.dump(session_data, f)

def is_session_expired(mobile, device_id):
    user = session_data["active_users"].get(mobile, None)
    if not user:
        return True
    saved_device_id = user.get("device_id", "")
    timestamp = user.get("timestamp", 0)
    if saved_device_id != device_id:
        return True
    return (time.time() - timestamp) > SESSION_TIMEOUT

def update_session(mobile, device_id):
    session_data["active_users"][mobile] = {
        "device_id": device_id,
        "timestamp": time.time()
    }
    save_session()

def logout_user():
    if st.session_state.mobile in session_data["active_users"]:
        session_data["active_users"].pop(st.session_state.mobile)
        save_session()
    st.session_state.logged_in = False
    st.session_state.mobile = ""
    st.session_state.device_id = str(uuid.uuid4())

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "mobile" not in st.session_state:
    st.session_state.mobile = ""
if "device_id" not in st.session_state:
    st.session_state.device_id = str(uuid.uuid4())

# --- LOGGED IN SESSION CHECK ---
if st.session_state.logged_in:
    if is_session_expired(st.session_state.mobile, st.session_state.device_id):
        logout_user()
        st.warning("Session expired. Please log in again.")
        st.stop()
    else:
        update_session(st.session_state.mobile, st.session_state.device_id)
        with st.sidebar:
            remaining_time = max(0, SESSION_TIMEOUT - int(time.time() - session_data["active_users"][st.session_state.mobile]["timestamp"]))
            st.info(f"Session expires in {str(timedelta(seconds=remaining_time))}")

if st.session_state.logged_in:
    with st.sidebar:
        st.success(f"Logged in as: {st.session_state.mobile}")
        if st.button("Logout"):
            logout_user()
            st.rerun()
else:
    st.title("🔐 Login to Access TNEA App")
    mobile = st.text_input("📱 Mobile Number")
    password = st.text_input("🔑 Password", type="password")
    if st.button("Login"):
        if mobile in user_data and user_data[mobile]["password"] == password:
            if mobile in session_data["active_users"] and session_data["active_users"][mobile]["device_id"] != st.session_state.device_id and (time.time() - session_data["active_users"][mobile]["timestamp"]) < SESSION_TIMEOUT:
                st.error("⚠️ Already logged in on another device.")
                st.stop()
            update_session(mobile, st.session_state.device_id)
            st.session_state.logged_in = True
            st.session_state.mobile = mobile
            st.success(f"Welcome, {mobile}!")
            st.rerun()
        else:
            st.error("❌ Invalid mobile number or password")
    st.stop()

# --- LOAD CUTOFF DATA ---
st.title("🎓 TNEA Info Dashboard")
st.markdown(f"🆔 Accessed by: **{st.session_state.mobile}**")

cutoff_url = "https://docs.google.com/spreadsheets/d/1rASGgYC9RZA0vgmtuFYRG0QO3DOGH_jW/export?format=xlsx"
cutoff_df = pd.read_excel(io.BytesIO(requests.get(cutoff_url).content))

for col in cutoff_df.columns:
    if col.endswith("_C") or col.endswith("_GR"):
        cutoff_df[col] = pd.to_numeric(cutoff_df[col], errors="coerce")

cutoff_df['College_Option'] = cutoff_df['CL'].astype(str) + " - " + cutoff_df['College']
college_options = sorted(cutoff_df['College_Option'].unique())

# --- LOAD VACANCY DATA ---
vacancy_url = "https://docs.google.com/spreadsheets/d/17otzGFO0AhKzx5ChSUhW18HnqA8Ed2sY/export?format=xlsx"
vacancy_df = pd.read_excel(io.BytesIO(requests.get(vacancy_url).content), sheet_name=None)

# === Tabs ===
tabs = st.tabs(["📊 Cutoff Finder", "📘 Vacancy Viewer"])

# === TAB 1: CUT OFF RANK FINDER ===
with tabs[0]:
    selected_college = st.selectbox("🏛️ Select College", options=["All"] + college_options)
    community = st.selectbox("Community", options=["All", "OC", "BC", "BCM", "MBC", "SC", "SCA", "ST"])
    dept = st.selectbox("Department", options=["All"] + sorted(cutoff_df['Br'].dropna().unique()))
    zone = st.selectbox("Zone", options=["All"] + sorted(cutoff_df['zone'].dropna().unique()))

    filtered_df = cutoff_df.copy()
    if selected_college != "All":
        cl = selected_college.split(" - ")[0]
        filtered_df = filtered_df[filtered_df['CL'].astype(str) == cl]
    if community != "All":
        filtered_df = filtered_df[["CL", "College", "Br", "zone", f"{community}_C", f"{community}_GR"]]
    if dept != "All":
        filtered_df = filtered_df[filtered_df['Br'] == dept]
    if zone != "All":
        filtered_df = filtered_df[filtered_df['zone'] == zone]

    st.dataframe(filtered_df, use_container_width=True)

# === TAB 2: VACANCY VIEWER ===
with tabs[1]:
    sheet_names = list(vacancy_df.keys())
    st.markdown("## 🗂️ Vacancy Viewer")

    cat1_col1, cat1_col2, cat1_col3 = st.columns(3)
    with cat1_col1:
        sheet1 = st.selectbox("📂 Select Vacancy Category", sheet_names, key="sheet1")
        df1 = vacancy_df[sheet1].copy()

    rename_map = {
        'COLLEGE CODE': 'College Code', 'COLLEGE NAME': 'College Name',
        'BRANCH CODE': 'Branch Code', 'BRANCH NAME': 'Branch Name'
    }
    df1.columns = [str(c).upper().replace("\n", " ").strip() for c in df1.columns]
    df1.rename(columns=rename_map, inplace=True)
    community_cols = ['OC', 'BC', 'BCM', 'MBC', 'SC', 'SCA', 'ST']
    id_vars = ['College Name', 'College Code', 'Branch Code', 'Branch Name']
    df1 = df1[[c for c in df1.columns if c in id_vars + community_cols]]
    df1_melt = df1.melt(id_vars=id_vars, value_vars=community_cols, var_name='Community', value_name='Seats')
    df1_melt['Seats'] = pd.to_numeric(df1_melt['Seats'], errors='coerce').fillna(0).astype(int)

    with cat1_col2:
        branch_code = st.selectbox("🔍 Select Branch Code", sorted(df1_melt['Branch Code'].unique()))
    with cat1_col3:
        community = st.selectbox("🧑‍🤝‍🧑 Filter by Community", ['All'] + sorted(df1_melt['Community'].unique()))

    filtered_df = df1_melt[df1_melt['Branch Code'] == branch_code]
    if community != "All":
        filtered_df = filtered_df[filtered_df['Community'] == community]

    st.dataframe(filtered_df, use_container_width=True)
    fig = px.bar(filtered_df.groupby("Community")["Seats"].sum().reset_index(), x="Community", y="Seats", color="Community")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("## 🏫 College-wise Filter")

    sheet2 = st.selectbox("📂 Select Vacancy Category Again", sheet_names, key="sheet2")
    df2 = vacancy_df[sheet2].copy()
    df2.columns = [str(c).upper().replace("\n", " ").strip() for c in df2.columns]
    df2.rename(columns=rename_map, inplace=True)
    df2 = df2[[c for c in df2.columns if c in id_vars + community_cols]]
    df2_melt = df2.melt(id_vars=id_vars, value_vars=community_cols, var_name='Community', value_name='Seats')
    df2_melt['Seats'] = pd.to_numeric(df2_melt['Seats'], errors='coerce').fillna(0).astype(int)

    df2_melt['College Combined'] = df2_melt['College Code'].astype(str) + ' - ' + df2_melt['College Name']
    college_list = sorted(df2_melt['College Combined'].unique())

    col2_1, col2_2 = st.columns(2)
    with col2_1:
        selected_college_combined = st.selectbox("🏫 Select College", ['All'] + college_list)
    with col2_2:
        selected_branch_code = st.selectbox("🔍 Filter by Branch Code", ['All'] + sorted(df2_melt['Branch Code'].unique()))

    college_df = df2_melt.copy()
    if selected_college_combined != "All":
        code, name = selected_college_combined.split(" - ", 1)
        college_df = college_df[(college_df['College Code'].astype(str) == code.strip()) & (college_df['College Name'].str.strip() == name.strip())]

    if selected_branch_code != "All":
        college_df = college_df[college_df['Branch Code'] == selected_branch_code]

    st.dataframe(college_df, use_container_width=True)
    fig2 = px.bar(college_df.groupby("Community")["Seats"].sum().reset_index(), x="Community", y="Seats", color="Community")
    st.plotly_chart(fig2, use_container_width=True)

# --- Footer ---
st.markdown("---")
st.markdown("""
<div style='font-size:14px;'>
<strong>Contact</strong>: +91-8248696926<br>
<strong>Email</strong>: rajumurugannp@gmail.com<br>
<strong>Developer</strong>: Dr. Raju Murugan<br>
&copy; 2025 TNEA Info App. All rights reserved.
</div>
""", unsafe_allow_html=True)
