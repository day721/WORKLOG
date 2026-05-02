import streamlit as st
import pandas as pd
import io
from github import Github, GithubException
from datetime import datetime, timedelta, date, time
from fpdf import FPDF

# App Config
st.set_page_config(page_title="Shift Tracker Pro", layout="wide")

# --- GITHUB SETUP ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    FILE_PATH = st.secrets["FILE_PATH"]
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception:
    st.error("Check Streamlit Secrets! GITHUB_TOKEN, REPO_NAME, and FILE_PATH must be set.")
    st.stop()

# Bahrain Time Adjustment (UTC + 3)
def get_bahrain_now():
    return datetime.utcnow() + timedelta(hours=3)

# --- DATA ENGINE ---
def load_data():
    try:
        content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        df['Date'] = df['Date'].astype(str)
        return df, content.sha
    except Exception:
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]), None

def save_to_github(df, sha):
    csv_content = df.to_csv(index=False)
    if sha:
        repo.update_file(FILE_PATH, "Update Shift Log", csv_content, sha)
    else:
        repo.create_file(FILE_PATH, "Initialize Log", csv_content)

# --- INITIALIZE SESSION STATE ---
# This prevents manual time from resetting to 'current' on every click
if 'manual_in_time' not in st.session_state:
    st.session_state.manual_in_time = get_bahrain_now().time()
if 'manual_out_time' not in st.session_state:
    st.session_state.manual_out_time = get_bahrain_now().time()

# --- MAIN UI ---
st.title("🕒 Quick Shift Logger")
now = get_bahrain_now()
today_str = now.strftime("%Y-%m-%d")

# 1. SHIFT SELECTION
shift_type = st.radio("Current Shift:", ["Shift 1", "Shift 2"], horizontal=True)

# 2. ONE-CLICK BUTTONS
st.subheader("Quick Actions")
col1, col2 = st.columns(2)

df, sha = load_data()
mask = (df['Date'] == today_str) & (df['Shift'] == shift_type)
existing_idx = df.index[mask].tolist()

with col1:
    if st.button("🟢 CHECK IN NOW", use_container_width=True):
        current_t = get_bahrain_now().strftime("%H:%M")
        if not existing_idx:
            new_row = pd.DataFrame([{"Date": today_str, "Shift": shift_type, "Check-In": current_t, "Check-Out": "", "Total Minutes": 0}])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df.at[existing_idx[0], "Check-In"] = current_t
        save_to_github(df, sha)
        st.success(f"Checked In: {current_t}")
        st.rerun()

with col2:
    if st.button("🔴 CHECK OUT NOW", use_container_width=True):
        if not existing_idx:
            st.error("No Check-In found! Please Check In first.")
        else:
            current_t = get_bahrain_now().strftime("%H:%M")
            df.at[existing_idx[0], "Check-Out"] = current_t
            
            # Duration Calculation
            in_t = datetime.strptime(df.at[existing_idx[0], "Check-In"], "%H:%M")
            out_t = datetime.strptime(current_t, "%H:%M")
            delta = (out_t - in_t).total_seconds() / 60
            df.at[existing_idx[0], "Total Minutes"] = int(delta)
            
            save_to_github(df, sha)
            st.success(f"Checked Out: {current_t}")
            st.rerun()

# 3. MANUAL EDIT (Persistent State)
with st.expander("✏️ Edit or Add Time Manually"):
    m_date = st.date_input("Date to Edit", now.date())
    
    # These will use the OS native clock picker on mobile
    m_in = st.time_input("Set Check-In", key="manual_in_widget", value=st.session_state.manual_in_time)
    m_out = st.time_input("Set Check-Out", key="manual_out_widget", value=st.session_state.manual_out_time)
    
    # Update session state whenever these change
    st.session_state.manual_in_time = m_in
    st.session_state.manual_out_time = m_out

    if st.button("Update Entry", use_container_width=True):
        m_date_str = m_date.strftime("%Y-%m-%d")
        m_mask = (df['Date'] == m_date_str) & (df['Shift'] == shift_type)
        m_idx = df.index[m_mask].tolist()
        
        in_str = m_in.strftime("%H:%M")
        out_str = m_out.strftime("%H:%M")
        
        # Calculation for manual entry
        in_dt = datetime.combine(date.today(), m_in)
        out_dt = datetime.combine(date.today(), m_out)
        m_delta = int((out_dt - in_dt).total_seconds() / 60)

        if not m_idx:
            new_row = pd.DataFrame([{"Date": m_date_str, "Shift": shift_type, "Check-In": in_str, "Check-Out": out_str, "Total Minutes": m_delta}])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df.at[m_idx[0], "Check-In"] = in_str
            df.at[m_idx[0], "Check-Out"] = out_str
            df.at[m_idx[0], "Total Minutes"] = m_delta
        
        save_to_github(df, sha)
        st.success("Manual Entry Updated!")
        st.rerun()

# --- REPORTS & EXPORT ---
st.divider()
if not df.empty:
    df['Date_DT'] = pd.to_datetime(df['Date'])
    df['Month'] = df['Date_DT'].dt.strftime('%B %Y')
    
    view_month = st.selectbox("Monthly Overview", df['Month'].unique())
    report_df = df[df['Month'] == view_month].copy()
    
    total_m = int(report_df['Total Minutes'].sum())
    
    # Compact Metrics for Mobile
    c1, c2 = st.columns(2)
    c1.metric("Total Hours", f"{total_m/60:.2f}h")
    c2.metric("Total Minutes", f"{total_m}m")
    
    # Hide technical columns for mobile display
    st.dataframe(report_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], 
                 use_container_width=True, hide_index=True)
else:
    st.info("No records yet.")
