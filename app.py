import streamlit as st
import pandas as pd
from datetime import datetime, date

# App Configuration
st.set_page_config(page_title="Work Shift Tracker", layout="centered")

# Data Storage Setup
DATA_FILE = "work_logs.csv"

def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# UI Header
st.title("🕒 Daily Shift Tracker")

# Sidebar for Input
with st.sidebar:
    st.header("Log Your Shift")
    today = st.date_input("Date", date.today())
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    # Time Inputs
    check_in = st.time_input("Check-In Time", datetime.now().time())
    check_out = st.time_input("Check-Out Time", datetime.now().time())
    
    if st.button("Save Record"):
        # Calculate duration
        start_dt = datetime.combine(today, check_in)
        end_dt = datetime.combine(today, check_out)
        
        # Handle overnight shifts if necessary
        if end_dt < start_dt:
            st.error("Check-out cannot be before Check-in.")
        else:
            diff = end_dt - start_dt
            total_minutes = int(diff.total_seconds() / 60)
            
            new_data = pd.DataFrame([[
                today, shift_type, check_in.strftime("%H:%M"), 
                check_out.strftime("%H:%M"), total_minutes
            ]], columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"])
            
            df = load_data()
            df = pd.concat([df, new_data], ignore_index=True)
            save_data(df)
            st.success("Record Saved!")

# Main Dashboard
df = load_data()

if not df.empty:
    st.subheader("Monthly Report")
    
    # Filter by Month
    df['Month'] = pd.to_datetime(df['Date']).dt.strftime('%B %Y')
    selected_month = st.selectbox("Select Month", df['Month'].unique())
    
    month_df = df[df['Month'] == selected_month]
    
    # Calculations
    total_min = month_df['Total Minutes'].sum()
    total_hrs = total_min / 60
    
    # Display Stats
    col1, col2 = st.columns(2)
    col1.metric("Total Hours", f"{total_hrs:.2f} hrs")
    col2.metric("Total Minutes", f"{total_min} min")
    
    st.dataframe(month_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], use_container_width=True)
else:
    st.info("No records found. Start by logging a shift in the sidebar.")
