import streamlit as st
import pandas as pd
import io
from github import Github, GithubException
from datetime import datetime, timedelta, date, time
from fpdf import FPDF

# --- APP CONFIG ---
st.set_page_config(page_title="Shift Tracker Pro", layout="wide")

# Custom CSS for Mobile "Master" View
st.markdown("""
    <style>
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    div[data-testid="stMetric"] { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- GITHUB & TIMEZONE ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    FILE_PATH = st.secrets["FILE_PATH"]
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception:
    st.error("Secrets missing! Check GITHUB_TOKEN, REPO_NAME, and FILE_PATH.")
    st.stop()

def get_bahrain_now():
    # Adjusting for local time (UTC + 3)
    return datetime.utcnow() + timedelta(hours=3)

# --- LOGIC ENGINES ---
def load_data():
    try:
        content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        df['Date'] = df['Date'].astype(str)
        df['Check-In'] = df['Check-In'].fillna("")
        df['Check-Out'] = df['Check-Out'].fillna("")
        return df, content.sha
    except Exception:
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]), None

def save_data(df, sha):
    csv_content = df.to_csv(index=False)
    try:
        repo.update_file(FILE_PATH, "Manual Edit - Minutes Master", csv_content, sha)
        return True
    except Exception as e:
        st.error(f"GitHub Sync Error: {e}")
        return False

def format_duration(total_minutes):
    """Converts minutes to Master HH:MM format like your HTML version."""
    hrs = total_minutes // 60
    mins = total_minutes % 60
    return f"{hrs:02d}:{mins:02d}"

def calculate_minutes(start_str, end_str):
    if not start_str or not end_str: return 0
    try:
        t1 = datetime.strptime(start_str, "%H:%M")
        t2 = datetime.strptime(end_str, "%H:%M")
        if t2 < t1: # Handle overnight logic
            t2 += timedelta(days=1)
        return int((t2 - t1).total_seconds() / 60)
    except: return 0

# --- DATA INITIALIZATION ---
df, sha = load_data()
now = get_bahrain_now()
today_str = now.strftime("%Y-%m-%d")

# --- UI START ---
st.title("🕒 Minutes Master Tracker")

# 1. SHIFT SELECTION
shift_num = st.radio("Current Shift:", ["Shift 1", "Shift 2", "Shift 3", "Shift 4"], horizontal=True)

# Check if record exists for today
mask = (df['Date'] == today_str) & (df['Shift'] == shift_num)
existing_idx = df.index[mask].tolist()

# 2. QUICK LOG BUTTONS
st.subheader("Direct Entry")
c1, c2 = st.columns(2)

with c1:
    if st.button("🟢 CHECK IN NOW", type="primary"):
        current_t = get_bahrain_now().strftime("%H:%M")
        if not existing_idx:
            new_row = pd.DataFrame([{"Date": today_str, "Shift": shift_num, "Check-In": current_t, "Check-Out": "", "Total Minutes": 0}])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df.at[existing_idx[0], "Check-In"] = current_t
        if save_data(df, sha):
            st.rerun()

with c2:
    if st.button("🔴 CHECK OUT NOW"):
        current_t = get_bahrain_now().strftime("%H:%M")
        if existing_idx:
            df.at[existing_idx[0], "Check-Out"] = current_t
            df.at[existing_idx[0], "Total Minutes"] = calculate_minutes(df.at[existing_idx[0], "Check-In"], current_t)
            if save_data(df, sha):
                st.rerun()
        else:
            st.warning("Please Check-In first!")

# 3. MANUAL EDIT / MINUTES MASTER CONTROL
st.divider()
with st.expander("✏️ Master Manual Edit & Delete"):
    # This keeps your edits from resetting
    target_date = st.date_input("Select Date to Edit", now.date())
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    day_entries = df[df['Date'] == target_date_str]
    
    if day_entries.empty:
        st.info("No entries found for this date.")
    else:
        for idx, row in day_entries.iterrows():
            with st.container():
                st.write(f"**{row['Shift']}**")
                edit_col1, edit_col2, edit_col3 = st.columns([2, 2, 1])
                
                # STEP=60 ensures you can select every single minute (1-minute increments)
                new_in = edit_col1.time_input(f"In", 
                                            value=datetime.strptime(row['Check-In'], "%H:%M").time() if row['Check-In'] else now.time(),
                                            key=f"manual_in_{idx}", 
                                            step=60)
                
                new_out = edit_col2.time_input(f"Out", 
                                             value=datetime.strptime(row['Check-Out'], "%H:%M").time() if row['Check-Out'] else now.time(),
                                             key=f"manual_out_{idx}", 
                                             step=60)
                
                # Action Buttons
                if edit_col3.button("💾 Save", key=f"btn_save_{idx}"):
                    df.at[idx, "Check-In"] = new_in.strftime("%H:%M")
                    df.at[idx, "Check-Out"] = new_out.strftime("%H:%M")
                    df.at[idx, "Total Minutes"] = calculate_minutes(df.at[idx, "Check-In"], df.at[idx, "Check-Out"])
                    if save_data(df, sha):
                        st.success("Entry Mastered!")
                        st.rerun()
                
                if edit_col3.button("🗑️", key=f"btn_del_{idx}"):
                    df = df.drop(idx)
                    if save_data(df, sha):
                        st.rerun()
                st.write("---")

# 4. MASTER REPORTING
st.divider()
if not df.empty:
    df['Date_DT'] = pd.to_datetime(df['Date'])
    df['Month'] = df['Date_DT'].dt.strftime('%B %Y')
    
    selected_month = st.selectbox("View Report", df['Month'].unique(), index=len(df['Month'].unique())-1)
    report_df = df[df['Month'] == selected_month].copy()
    
    total_m = int(report_df['Total Minutes'].sum())
    
    r1, r2 = st.columns(2)
    r1.metric("Total Duration", format_duration(total_m))
    r2.metric("Minutes Sum", f"{total_m} min")
    
    st.dataframe(report_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]].sort_values("Date", ascending=False), 
                 use_container_width=True, hide_index=True)
