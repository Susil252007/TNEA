import streamlit as st
import pandas as pd
import yaml
import requests
import io
import uuid
import time
from datetime import timedelta

# --- FILE PATHS ---
base_path = "./"
config_path = base_path + "config.yaml"
device_session_path = base_path + "device_session.yaml"

# --- SESSION TIMEOUT SETTINGS ---
SESSION_TIMEOUT = 180  # 3 minutes

# --- CONFIG ---
try:
    with open(config_path) as file:
        config = yaml.safe_load(file)
    user_data = config["credentials"]["users"]
except Exception as e:
    st.error(f"❌ Failed to load config.yaml: {e}")
    st.stop()

# --- DEVICE SESSION CONTROL ---
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

# --- SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "mobile" not in st.session_state:
    st.session_state.mobile = ""
if "device_id" not in st.session_state:
    st.session_state.device_id = str(uuid.uuid4())

# --- SESSION EXPIRY CHECK ---
if st.session_state.logged_in:
    user = session_data["active_users"].get(st.session_state.mobile, {})
    last_time = user.get("timestamp", 0)
    remaining_time = max(0, SESSION_TIMEOUT - int(time.time() - last_time))

    if is_session_expired(st.session_state.mobile, st.session_state.device_id):
        logout_user()
        st.warning("⚠️ Session expired. Please log in again.")
        st.stop()
    else:
        update_session(st.session_state.mobile, st.session_state.device_id)

    # Show countdown in sidebar
    with st.sidebar:
        readable = str(timedelta(seconds=remaining_time))
        st.info(f"⏳ Session expires in {readable}")

# --- LOGOUT BUTTON ---
if st.session_state.logged_in:
    with st.sidebar:
        st.success(f"👤 Logged in as: {st.session_state.mobile}")
        if st.button("Logout"):
            logout_user()
            st.rerun()

# --- LOGIN FORM ---
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

# --- LOAD EXCEL DATA ---
excel_url = "https://docs.google.com/spreadsheets/d/1rASGgYC9RZA0vgmtuFYRG0QO3DOGH_jW/export?format=xlsx"
response = requests.get(excel_url)
df = pd.read_excel(io.BytesIO(response.content))

for col in df.columns:
    if col.endswith("_C") or col.endswith("_GR"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

# --- LOGO ---
logo_url = "https://drive.google.com/thumbnail?id=1FPfkRH3BC1BeQRtQVpZDH3P3ilTSMYNA"
st.image(logo_url, width=100)

st.title("📊 TNEA 2025 Cutoff & Rank Finder")
st.markdown(f"🆔 **Accessed by: {st.session_state.mobile}**")

# --- COLLEGE FILTERS ---
df['College_Option'] = df['CL'].astype(str) + " - " + df['College']
college_options = sorted(df['College_Option'].unique().tolist())
selected_college = st.selectbox("🏛️ Select College", options=["All"] + college_options)

st.subheader("🎯 Filter by Community, Department, Zone")
if selected_college == "All":
    community = st.selectbox("Select Community", options=["All", "OC", "BC", "BCM", "MBC", "SC", "SCA", "ST"], key="main_community")
    department = st.selectbox("Select Department (Br)", options=["All"] + sorted(df['Br'].dropna().unique().tolist()))
    zone = st.selectbox("Select Zone", options=["All"] + sorted(df['zone'].dropna().unique().tolist()))

# --- COMPARE COLLEGES ---
st.subheader("📌 Compare Up to 5 Colleges")
compare_colleges = st.multiselect("Select colleges to compare", options=college_options, max_selections=5)

if compare_colleges:
    st.markdown("### 🎯 Filter Inside Compared Colleges")
    comp_dept = st.selectbox("Department", options=["All"] + sorted(df['Br'].dropna().unique().tolist()), key="compare_department")
    comp_comm = st.selectbox("Community", options=["All", "OC", "BC", "BCM", "MBC", "SC", "SCA", "ST"], key="compare_community")

    compare_cls = [c.split(" - ")[0].strip() for c in compare_colleges]
    compare_df = df[df['CL'].astype(str).isin(compare_cls)]

    if comp_dept != "All":
        compare_df = compare_df[compare_df['Br'] == comp_dept]

    color_palette = ['#f7c6c7', '#c6e2ff', '#d5f5e3', '#fff5ba', '#e0ccff']
    college_color_map = {cl: color_palette[i] for i, cl in enumerate(compare_cls)}

    def highlight_college(row):
        return ['background-color: {}'.format(college_color_map.get(str(row['CL']), '#ffffff'))] * len(row)

    compare_cols = ['CL', 'College', 'Br', 'zone']
    if comp_comm != "All":
        compare_cols += [f"{comp_comm}_C", f"{comp_comm}_GR"]
    else:
        compare_cols += [col for col in df.columns if col.endswith("_C") or col.endswith("_GR")]

    format_dict = {col: '{:.2f}' if '_C' in col else '{:.0f}' for col in compare_cols if '_C' in col or '_GR' in col}

    st.markdown("### 🟨 College Comparison Table")
    st.dataframe(
        compare_df[compare_cols]
        .style
        .apply(highlight_college, axis=1)
        .format(format_dict)
        .hide(axis='index'),
        height=450
    )

# --- MAIN FILTERED DATA ---
show_data = False
filtered_df = df.copy()

if selected_college != "All":
    show_data = True
    selected_cl = selected_college.split(" - ")[0].strip()
    filtered_df = filtered_df[filtered_df['CL'].astype(str) == selected_cl]
else:
    if 'zone' in locals() and zone != "All":
        filtered_df = filtered_df[filtered_df['zone'] == zone]
        show_data = True
    if 'department' in locals() and department != "All":
        filtered_df = filtered_df[filtered_df['Br'] == department]
        show_data = True

if selected_college == "All" and 'community' in locals() and community != "All":
    cols_to_show = ['CL', 'College', 'Br', f'{community}_C', f'{community}_GR', 'zone']
else:
    cols_to_show = ['CL', 'College', 'Br', 'zone'] + [col for col in df.columns if col.endswith("_C") or col.endswith("_GR")]

format_dict = {
    col: '{:.2f}' if '_C' in col else '{:.0f}'
    for col in cols_to_show
    if '_C' in col or '_GR' in col
}

st.markdown("### 🔎 Filtered Results")

if show_data:
    st.dataframe(
        filtered_df[cols_to_show]
        .style
        .format(format_dict)
        .hide(axis='index'),
        height=600
    )
else:
    st.info("Please apply filters to see the results.")

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style='font-size:14px; line-height:1.6'>
    <strong>Disclaimer</strong>: This is a privately developed, independent app created to assist students and parents with TNEA-related information.<br>
    The data used in this app is collected from publicly available sources provided by TNEA.<br>
    This app is not affiliated with or endorsed by TNEA or the Directorate of Technical Education (DoTE), Tamil Nadu.<br><br>

    <strong>Contact</strong>: +91-8248696926<br>
    <strong>Email</strong>: rajumurugannp@gmail.com<br>
    <strong>Developed by</strong>: Dr. Raju Murugan<br>
    &copy; 2025 <strong>TNEA Info App</strong>. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True
)


