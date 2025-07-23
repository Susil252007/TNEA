import streamlit as st
import pandas as pd
import yaml
import requests
import io
import uuid
import time
from datetime import timedelta
import plotly.express as px

# --- Force black font in DataFrames ---
st.markdown("""
    <style>
    .stDataFrame div {
        color: black !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- File paths and session settings ---
config_path = "config.yaml"
device_session_path = "device_session.yaml"
SESSION_TIMEOUT = 180  # 3 minutes

# --- Load credentials ---
try:
    with open(config_path) as file:
        config = yaml.safe_load(file)
    user_data = config["credentials"]["users"]
except Exception as e:
    st.error(f"❌ Failed to load config.yaml: {e}")
    st.stop()

# --- Load or initialize session control ---
try:
    with open(device_session_path) as session_file:
        session_data = yaml.safe_load(session_file)
except Exception:
    session_data = {"active_users": {}}

def save_session():
    with open(device_session_path, "w") as f:
        yaml.dump(session_data, f)

def is_session_expired(mobile, device_id):
    user = session_data["active_users"].get(mobile)
    if not user:
        return True
    if user.get("device_id") != device_id:
        return True
    return (time.time() - user.get("timestamp", 0)) > SESSION_TIMEOUT

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

# --- Initialize session state ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "mobile" not in st.session_state:
    st.session_state.mobile = ""
if "device_id" not in st.session_state:
    st.session_state.device_id = str(uuid.uuid4())

# --- Check session expiration ---
if st.session_state.logged_in:
    if is_session_expired(st.session_state.mobile, st.session_state.device_id):
        logout_user()
        st.warning("⚠️ Session expired. Please log in again.")
        st.stop()
    else:
        update_session(st.session_state.mobile, st.session_state.device_id)
        with st.sidebar:
            remaining = SESSION_TIMEOUT - int(time.time() - session_data["active_users"][st.session_state.mobile]["timestamp"])
            st.info(f"⏳ Session expires in {str(timedelta(seconds=remaining))}")

# --- Logout ---
if st.session_state.logged_in:
    with st.sidebar:
        st.success(f"👤 Logged in as: {st.session_state.mobile}")
        if st.button("Logout"):
            logout_user()
            st.rerun()

# --- Login form ---
if not st.session_state.logged_in:
    st.title("🔐 Login to Access TNEA App")
    mobile = st.text_input("📱 Mobile Number")
    password = st.text_input("🔑 Password", type="password")
    if st.button("Login"):
        if mobile in user_data and user_data[mobile]["password"] == password:
            if mobile in session_data["active_users"]:
                existing = session_data["active_users"][mobile]
                if existing["device_id"] != st.session_state.device_id and (time.time() - existing["timestamp"]) < SESSION_TIMEOUT:
                    st.error("⚠️ Already logged in on another device. Logout there first.")
                    st.stop()
            update_session(mobile, st.session_state.device_id)
            st.session_state.logged_in = True
            st.session_state.mobile = mobile
            st.success(f"✅ Welcome, {mobile}!")
            st.rerun()
        else:
            st.error("❌ Invalid mobile number or password")
    st.stop()

# --- Load both datasets ---
cutoff_url = "https://docs.google.com/spreadsheets/d/1rASGgYC9RZA0vgmtuFYRG0QO3DOGH_jW/export?format=xlsx"
vacancy_url = "https://docs.google.com/spreadsheets/d/17otzGFO0AhKzx5ChSUhW18HnqA8Ed2sY/export?format=xlsx"

df_cutoff = pd.read_excel(io.BytesIO(requests.get(cutoff_url).content))
df_vacancy = pd.read_excel(io.BytesIO(requests.get(vacancy_url).content))

# ✅ Clean column names to avoid KeyError issues
df_cutoff.columns = df_cutoff.columns.str.strip()
df_vacancy.columns = df_vacancy.columns.str.strip()

# --- Cutoff page (with comparison) ---
st.title("📊 TNEA 2025 Cutoff & Rank Finder")
st.markdown(f"🆔 Accessed by: **{st.session_state.mobile}**")

df_cutoff['College_Option'] = df_cutoff['CL'].astype(str) + " - " + df_cutoff['College']
college_options = sorted(df_cutoff['College_Option'].dropna().unique())
selected_college = st.selectbox("🏛️ Select College", ["All"] + college_options)

st.subheader("🎯 Filter by Community, Department, Zone")
community = st.selectbox("Community", ["All", "OC", "BC", "BCM", "MBC", "SC", "SCA", "ST"])
department = st.selectbox("Department", ["All"] + sorted(df_cutoff['Br'].dropna().unique()))
zone = st.selectbox("Zone", ["All"] + sorted(df_cutoff['zone'].dropna().unique()))

st.subheader("📌 Compare Up to 5 Colleges")
compare_colleges = st.multiselect("Compare Colleges", college_options, max_selections=5)
if compare_colleges:
    st.markdown("### 🎯 Inside Comparison")
    comp_dept = st.selectbox("Department", ["All"] + sorted(df_cutoff['Br'].dropna().unique()), key="compare_department")
    comp_comm = st.selectbox("Community", ["All", "OC", "BC", "BCM", "MBC", "SC", "SCA", "ST"], key="compare_community")

    comp_cls = [c.split(" - ")[0] for c in compare_colleges]
    compare_df = df_cutoff[df_cutoff['CL'].astype(str).isin(comp_cls)]
    if comp_dept != "All":
        compare_df = compare_df[compare_df['Br'] == comp_dept]

    color_map = {cl: color for cl, color in zip(comp_cls, ["#f7c6c7", "#c6e2ff", "#d5f5e3", "#fff5ba", "#e0ccff"])}

    def highlight_compare(row):
        return [f"background-color: {color_map.get(str(row['CL']), '#ffffff')}; color: black;" for _ in row]

    cols = ['CL', 'College', 'Br', 'zone']
    if comp_comm != "All":
        cols += [f"{comp_comm}_C", f"{comp_comm}_GR"]
    else:
        cols += [col for col in df_cutoff.columns if col.endswith("_C") or col.endswith("_GR")]

    st.dataframe(
        compare_df[cols].style.apply(highlight_compare, axis=1).hide(axis='index'), height=500
    )

# --- Main filter results ---
filtered_df = df_cutoff.copy()
if selected_college != "All":
    cl_code = selected_college.split(" - ")[0]
    filtered_df = filtered_df[filtered_df['CL'].astype(str) == cl_code]
if department != "All":
    filtered_df = filtered_df[filtered_df['Br'] == department]
if zone != "All":
    filtered_df = filtered_df[filtered_df['zone'] == zone]

cols_to_show = ['CL', 'College', 'Br', 'zone']
if community != "All":
    cols_to_show += [f"{community}_C", f"{community}_GR"]
else:
    cols_to_show += [col for col in df_cutoff.columns if col.endswith("_C") or col.endswith("_GR")]

st.markdown("### 🔎 Filtered Results")
if not filtered_df.empty:
    st.dataframe(filtered_df[cols_to_show].style.hide(axis='index'), height=500)
else:
    st.info("Please apply filters to view results.")

# --- Vacancy Viewer Section ---
st.markdown("---")
st.title("📋 TNEA 2025 Vacancy Viewer")

# ✅ Clean up column cases if needed and verify existence
df_vacancy['College Combined'] = df_vacancy['College Code'].astype(str) + ' - ' + df_vacancy['College Name']
branch_codes = sorted(df_vacancy['Branch Code'].dropna().unique())
communities = sorted(df_vacancy['Community'].dropna().unique())

cat1, cat2 = st.columns(2)

with cat1:
    sel_branch = st.selectbox("🔍 Select Branch Code", branch_codes)
    sel_comm = st.selectbox("🧑‍🤝‍🧑 Filter by Community", ["All"] + communities)

    df1 = df_vacancy[df_vacancy['Branch Code'] == sel_branch]
    if sel_comm != "All":
        df1 = df1[df1['Community'] == sel_comm]

    if not df1.empty:
        total = df1['Seats'].sum()
        st.plotly_chart(px.bar(df1.groupby('Community')["Seats"].sum().reset_index(),
                               x="Community", y="Seats", color="Community",
                               title=f"Community-wise Seat Distribution (Total: {total})"))
        st.dataframe(df1, use_container_width=True)

with cat2:
    sel_college = st.selectbox("🏫 Select College (Code - Name)", sorted(df_vacancy['College Combined'].dropna().unique()))
    sel_branch2 = st.selectbox("🔍 Filter by Branch Code (Optional)", ["All"] + branch_codes)

    code, name = sel_college.split(" - ", 1)
    df2 = df_vacancy[df_vacancy['College Code'].astype(str) == code.strip()]
    if sel_branch2 != "All":
        df2 = df2[df2['Branch Code'] == sel_branch2]

    if not df2.empty:
        total = df2['Seats'].sum()
        st.plotly_chart(px.bar(df2.groupby('Community')["Seats"].sum().reset_index(),
                               x="Community", y="Seats", color="Community",
                               title=f"Community-wise Seat Distribution (Total: {total})"))
        st.dataframe(df2, use_container_width=True)

# --- Footer ---
st.markdown("---")
st.markdown("""
<div style='font-size:14px; line-height:1.6'>
<strong>Disclaimer</strong>: This is a privately developed app to help TNEA aspirants. Data is taken from publicly available resources.<br>
<strong>Contact</strong>: +91-8248696926<br>
<strong>Email</strong>: rajumurugannp@gmail.com<br>
<strong>Developed by</strong>: Dr. Raju Murugan<br>
&copy; 2025 <strong>TNEA Info App</strong>. All rights reserved.
</div>
""", unsafe_allow_html=True)
