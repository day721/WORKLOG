import streamlit as st
import pandas as pd
import io
from github import Github, GithubException # Added GithubException
from datetime import datetime, date, time

# App Configuration
st.set_page_config(page_title="GitHub DB Shift Tracker", layout="centered")

# GitHub Connection Setup
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    FILE_PATH = st.secrets["FILE_PATH"]
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except KeyError:
    st.error("Please check your Streamlit Secrets. Keys are missing!")
    st.stop()

def load_data_from_github():
    try:
        content = repo.get_contents(FILE_PATH)
        return pd.read_csv(io.StringIO(content.decoded_content.decode())), content.sha
    except GithubException as e:
        # If file doesn't exist (404), return empty df
        if e.status == 404:
            df = pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"])
            return df, None
        else:
            st.error(f"GitHub Error (Load): {e.data.get('message', str(e))}")
            return pd.DataFrame(), None

def save_data_to_github(df, sha):
    csv_content = df.to_csv(index=False)
    try:
        if sha:
            repo.update_file(FILE_PATH, "Update work logs", csv_content, sha)
        else:
            repo.create_file(FILE_PATH, "Initial work log commit", csv_content)
        return True
    except GithubException as e:
        st.error(f"GitHub Error (Save): {e.data.get('message', str(e))}")
        return False

st.title("🕒 Daily Shift Tracker")

# Sidebar for Input
with st.sidebar:
    st.header("Log Your Shift")
    today = st.date_input("Date", date.today())
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    # Default time 00:00 as requested
    default_t = time(0, 0)
    check_in = st.time_input("Check-In Time", default_t)
    check_out = st.time_input("Check-Out Time", default_t)
    
    if st.button("Save to GitHub"):
        start_dt = datetime.combine(today, check_in)
        end_dt = datetime.combine(today, check_out)
        
        if end_dt <= start_dt:
            st.error("Check-out must be after Check-in.")
        else:
            diff = end_dt - start_dt
            total_minutes = int(diff.total_seconds() / 60)
            
            new_row = pd.DataFrame([{
                "Date": today.strftime("%Y-%m-%d"),
                "Shift": shift_type,
                "Check-In": check_in.strftime("%H:%M"),
                "Check-Out": check_out.strftime("%H:%M"),
                "Total Minutes": total_minutes
            }])
            
            df, sha = load_data_from_github()
            if not df.empty or sha is None:
                updated_df = pd.concat([df, new_row], ignore_index=True)
                if save_data_to_github(updated_df, sha):
                    st.success("Successfully saved to GitHub!")
                    st.rerun()

# Main Dashboard
df, _ = load_data_from_github()

if not df.empty:
    st.subheader("Monthly Report")
    
    # Ensure proper data types
    df['Date'] = pd.to_datetime(df['Date'])
    df['Total Minutes'] = pd.to_numeric(df['Total Minutes'])
    df['Month Year'] = df['Date'].dt.strftime('%B %Y')
    
    selected_month = st.selectbox("Select Month", df['Month Year'].unique())
    month_df = df[df['Month Year'] == selected_month].copy()
    
    total_min = int(month_df['Total Minutes'].sum())
    total_hrs = total_min / 60
    
    c1, c2 = st.columns(2)
    c1.metric("Total Hours", f"{total_hrs:.2f} hrs")
    c2.metric("Total Minutes", f"{total_min} min")
    
    st.dataframe(month_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], 
                 use_container_width=True, hide_index=True)
