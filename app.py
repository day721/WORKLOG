import streamlit as st
import pandas as pd
import io
from github import Github, GithubException
from datetime import datetime, timedelta, date, time
from fpdf import FPDF

# --- APP CONFIG & STYLING ---
st.set_page_config(page_title="Shift Tracker Pro", layout="wide")

# Custom CSS for better mobile appearance
st.markdown("""
    <style>
    .stButton > button { width: 100%; border-radius: 10px; height: 3em; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- SETTINGS & GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    FILE_PATH = st.secrets["FILE_PATH"]
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception:
    st.error("Missing Secrets! Check GITHUB_TOKEN, REPO_NAME, and FILE_PATH.")
    st.stop()

def get_bahrain_now():
    return datetime.utcnow() + timedelta(hours=3)

# --- DATA OPERATIONS ---
def load_data():
    try:
        content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        df['Date'] = df['Date'].astype(str)
        # Handle empty/NaN values for times
        df['Check-In'] = df['Check-In'].fillna("")
        df['Check-Out'] = df['Check-Out'].fillna("")
        return df, content.sha
    except Exception:
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]), None

def save_data(df, sha):
    csv_content = df.to_csv(index=False)
    try:
        repo.update_file(FILE_PATH, "Update Shift Data", csv_content, sha)
        return True
    except Exception as e:
        st.error(f"GitHub Error: {e}")
        return False

def calculate_minutes(start_str, end_str):
    if not start_str or not end_str: return 0
    try:
        t1 = datetime.strptime(start_str, "%H:%M")
        t2 = datetime.strptime(end_str, "%H:%M")
        # Handle overnight shift
        if t2 < t1:
            t2 += timedelta(days=1)
        return int((t2 - t1).total_seconds() / 60)
    except: return 0

# --- INITIALIZATION ---
df, sha = load_data()
now = get_bahrain_now()
today_str = now.strftime("%Y-%m-%d")

# --- MAIN UI ---
st.title("🕒 Daily Shift Tracker")

# 1. SHIFT SELECTION
shift_num = st.radio("Select Shift:", ["Shift 1", "Shift 2", "Shift 3", "Shift 4"], horizontal=True)

# Find if a record exists for today + this shift
mask = (df['Date'] == today_str) & (df['Shift'] == shift_num)
existing_idx = df.index[mask].tolist()

# 2. THE MORNING/EVENING BUTTONS
st.subheader("Quick Log")
c1, c2 = st.columns(2)

with c1:
    if st.button("🟢 MORNING: CHECK IN", type="primary"):
        current_t = get_bahrain_now().strftime("%H:%M")
        if not existing_idx:
            # Create NEW record with only Check-In
            new_row = pd.DataFrame([{"Date": today_str, "Shift": shift_num, "Check-In": current_t, "Check-Out": "", "Total Minutes": 0}])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            # Update existing record's Check-In
            df.at[existing_idx[0], "Check-In"] = current_t
            df.at[existing_idx[0], "Total Minutes"] = calculate_minutes(current_t, df.at[existing_idx[0], "Check-Out"])
        
        if save_data(df, sha):
            st.success(f"Check-In saved: {current_t}")
            st.rerun()

with c2:
    if st.button("🔴 AFTERNOON: CHECK OUT"):
        current_t = get_bahrain_now().strftime("%H:%M")
        if not existing_idx:
            st.warning("No Check-In found. Creating one with default 08:00...")
            new_row = pd.DataFrame([{"Date": today_str, "Shift": shift_num, "Check-In": "08:00", "Check-Out": current_t, "Total Minutes": calculate_minutes("08:00", current_t)}])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df.at[existing_idx[0], "Check-Out"] = current_t
            df.at[existing_idx[0], "Total Minutes"] = calculate_minutes(df.at[existing_idx[0], "Check-In"], current_t)
        
        if save_data(df, sha):
            st.success(f"Check-Out saved: {current_t}")
            st.rerun()

# 3. MANUAL EDIT / DELETE SECTION
st.divider()
with st.expander("🛠️ Manage / Remove Records"):
    st.write("Edit or Delete specific entries below:")
    
    # Let user select a date to manage
    edit_date = st.date_input("Target Date", now.date())
    edit_date_str = edit_date.strftime("%Y-%m-%d")
    
    # Filter data for that day
    day_data = df[df['Date'] == edit_date_str]
    
    if day_data.empty:
        st.info("No records for this date.")
    else:
        for idx, row in day_data.iterrows():
            with st.container():
                cols = st.columns([2, 2, 2, 1])
                # Native Clock Picker (st.time_input)
                new_in = cols[0].time_input(f"In ({row['Shift']})", value=datetime.strptime(row['Check-In'], "%H:%M").time() if row['Check-In'] else now.time(), key=f"in_{idx}")
                new_out = cols[1].time_input(f"Out ({row['Shift']})", value=datetime.strptime(row['Check-Out'], "%H:%M").time() if row['Check-Out'] else now.time(), key=f"out_{idx}")
                
                # Update Button
                if cols[2].button("💾 Save", key=f"save_{idx}"):
                    df.at[idx, "Check-In"] = new_in.strftime("%H:%M")
                    df.at[idx, "Check-Out"] = new_out.strftime("%H:%M")
                    df.at[idx, "Total Minutes"] = calculate_minutes(df.at[idx, "Check-In"], df.at[idx, "Check-Out"])
                    if save_data(df, sha):
                        st.success("Updated!")
                        st.rerun()
                
                # Remove Button
                if cols[3].button("🗑️", key=f"del_{idx}"):
                    df = df.drop(idx)
                    if save_data(df, sha):
                        st.error("Deleted!")
                        st.rerun()

# 4. VIEW LOGS
st.divider()
if not df.empty:
    df['Date_DT'] = pd.to_datetime(df['Date'])
    df['Month'] = df['Date_DT'].dt.strftime('%B %Y')
    
    view_month = st.selectbox("Monthly Report", df['Month'].unique(), index=len(df['Month'].unique())-1)
    report_df = df[df['Month'] == view_month].copy()
    
    total_min = int(report_df['Total Minutes'].sum())
    m1, m2 = st.columns(2)
    m1.metric("Total Hours", f"{total_min/60:.2f}h")
    m2.metric("Days Worked", len(report_df['Date'].unique()))
    
    st.dataframe(report_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]].sort_values("Date", ascending=False), 
                 use_container_width=True, hide_index=True)
