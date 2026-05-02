import streamlit as st
import pandas as pd
import io
from github import Github
from datetime import datetime, date, time

# App Configuration
st.set_page_config(page_title="GitHub DB Shift Tracker", layout="centered")

# GitHub Connection Setup
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

def load_data_from_github():
    try:
        content = repo.get_contents(FILE_PATH)
        return pd.read_csv(io.StringIO(content.decoded_content.decode())), content.sha
    except:
        # Create empty dataframe if file doesn't exist
        df = pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"])
        return df, None

def save_data_to_github(df, sha):
    csv_content = df.to_csv(index=False)
    if sha:
        repo.update_file(FILE_PATH, "Update work logs", csv_content, sha)
    else:
        repo.create_file(FILE_PATH, "Initial work log commit", csv_content)

st.title("🕒 Daily Shift Tracker")
st.caption("Database: work_log.csv on GitHub")

# Sidebar for Input
with st.sidebar:
    st.header("Log Your Shift")
    today = st.date_input("Date", date.today())
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    # Default time set to 00:00
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
            
            # Load, Append, and Push
            df, sha = load_data_from_github()
            updated_df = pd.concat([df, new_row], ignore_index=True)
            save_data_to_github(updated_df, sha)
            
            st.success("Data pushed to GitHub!")
            st.rerun()

# Main Dashboard
df, _ = load_data_from_github()

if not df.empty:
    st.subheader("Monthly Report")
    
    # Cleaning
    df['Date'] = pd.to_datetime(df['Date'])
    df['Total Minutes'] = pd.to_numeric(df['Total Minutes'])
    df['Month Year'] = df['Date'].dt.strftime('%B %Y')
    
    selected_month = st.selectbox("Select Month", df['Month Year'].unique())
    month_df = df[df['Month Year'] == selected_month].copy()
    
    total_min = int(month_df['Total Minutes'].sum())
    total_hrs = total_min / 60
    
    col1, col2 = st.columns(2)
    col1.metric("Total Hours", f"{total_hrs:.2f} hrs")
    col2.metric("Total Minutes", f"{total_min} min")
    
    st.dataframe(month_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], 
                 use_container_width=True, hide_index=True)
else:
    st.info("Your work_log.csv is currently empty. Add your first shift!")
