import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date

# App Configuration
st.set_page_config(page_title="Work Shift Tracker", layout="centered")

# Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(worksheet="Sheet1", ttl="0")

# UI Header
st.title("🕒 Daily Shift Tracker")

# Sidebar for Input
with st.sidebar:
    st.header("Log Your Shift")
    today = st.date_input("Date", date.today())
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    check_in = st.time_input("Check-In Time", datetime.now().time())
    check_out = st.time_input("Check-Out Time", datetime.now().time())
    
    if st.button("Save to Google Sheets"):
        start_dt = datetime.combine(today, check_in)
        end_dt = datetime.combine(today, check_out)
        
        if end_dt < start_dt:
            st.error("Check-out cannot be before Check-in.")
        else:
            diff = end_dt - start_dt
            total_minutes = int(diff.total_seconds() / 60)
            
            # Prepare new row
            new_row = pd.DataFrame([{
                "Date": today.strftime("%Y-%m-%d"),
                "Shift": shift_type,
                "Check-In": check_in.strftime("%H:%M"),
                "Check-Out": check_out.strftime("%H:%M"),
                "Total Minutes": total_minutes
            }])
            
            # Read existing data and append
            existing_data = load_data()
            updated_df = pd.concat([existing_data, new_row], ignore_index=True)
            
            # Update the Google Sheet
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("Data synced to Google Sheets!")

# Main Dashboard
df = load_data()

if not df.empty:
    st.subheader("Monthly Report")
    
    # Ensure Date column is datetime
    df['Date'] = pd.to_datetime(df['Date'])
    df['Month'] = df['Date'].dt.strftime('%B %Y')
    
    unique_months = df['Month'].unique()
    selected_month = st.selectbox("Select Month", unique_months)
    
    month_df = df[df['Month'] == selected_month]
    
    total_min = pd.to_numeric(month_df['Total Minutes']).sum()
    total_hrs = total_min / 60
    
    col1, col2 = st.columns(2)
    col1.metric("Total Hours", f"{total_hrs:.2f} hrs")
    col2.metric("Total Minutes", f"{total_min} min")
    
    st.dataframe(month_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], use_container_width=True)
