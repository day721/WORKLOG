import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date

# App Configuration
st.set_page_config(page_title="Work Shift Tracker", layout="centered")

# Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # ttl=0 ensures we don't show old cached data
    return conn.read(worksheet="Sheet1", ttl=0)

# UI Header
st.title("🕒 Daily Shift Tracker")

# Sidebar for Input
with st.sidebar:
    st.header("Log Your Shift")
    today = st.date_input("Date", date.today())
    # You mentioned you have two shifts
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    check_in = st.time_input("Check-In Time", datetime.now().time())
    check_out = st.time_input("Check-Out Time", datetime.now().time())
    
    if st.button("Save to Google Sheets"):
        start_dt = datetime.combine(today, check_in)
        end_dt = datetime.combine(today, check_out)
        
        if end_dt <= start_dt:
            st.error("Check-out must be after Check-in.")
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
            
            # Read current data and append
            existing_data = load_data()
            updated_df = pd.concat([existing_data, new_row], ignore_index=True)
            
            # Update the Google Sheet
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("Shift recorded successfully!")

# Main Dashboard
df = load_data()

if not df.empty:
    st.subheader("Monthly Report")
    
    # Data Cleaning: Convert to proper types for calculation
    df['Date'] = pd.to_datetime(df['Date'])
    df['Total Minutes'] = pd.to_numeric(df['Total Minutes'], errors='coerce').fillna(0)
    
    # Create Month column for filtering
    df['Month Year'] = df['Date'].dt.strftime('%B %Y')
    
    # Month Selector
    unique_months = df['Month Year'].unique()
    selected_month = st.selectbox("Select Month", unique_months)
    
    # Filtered Data
    month_df = df[df['Month Year'] == selected_month].copy()
    
    # Totals
    total_min = int(month_df['Total Minutes'].sum())
    total_hrs = total_min / 60
    
    # Display Metrics
    m1, m2 = st.columns(2)
    m1.metric("Total Duration (Hours)", f"{total_hrs:.2f} hrs")
    m2.metric("Total Duration (Minutes)", f"{total_min} min")
    
    # Show Table
    st.write(f"### Log for {selected_month}")
    # Formatting for display
    display_df = month_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]].copy()
    display_df['Date'] = display_df['Date'].dt.date
    st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("No data found. Use the sidebar to log your first shift.")
