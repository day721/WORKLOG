import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date

# App Configuration
st.set_page_config(page_title="Work Shift Tracker", layout="centered")

# Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Use ttl=0 to ensure we always fetch the latest data from the sheet
        # We explicitly specify the worksheet name 'Sheet1'
        data = conn.read(worksheet="Sheet1", ttl=0)
        return data
    except Exception as e:
        # If the sheet is empty or the connection fails, return an empty DataFrame with headers
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"])

# UI Header
st.title("🕒 Daily Shift Tracker")

# Sidebar for Input
with st.sidebar:
    st.header("Log Your Shift")
    today = st.date_input("Date", date.today())
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    # Defaults to current time
    check_in = st.time_input("Check-In Time", datetime.now().time())
    check_out = st.time_input("Check-Out Time", datetime.now().time())
    
    if st.button("Save to Google Sheets"):
        start_dt = datetime.combine(today, check_in)
        end_dt = datetime.combine(today, check_out)
        
        if end_dt <= start_dt:
            st.error("Check-out time must be after check-in time.")
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
            
            try:
                # Read current data and append new entry
                existing_data = load_data()
                # Clean existing data to remove empty/NaN rows before appending
                existing_data = existing_data.dropna(how='all')
                
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                # Update the Google Sheet
                conn.update(worksheet="Sheet1", data=updated_df)
                st.success("Shift successfully recorded!")
                st.balloons()
            except Exception as e:
                st.error(f"Error saving data: {e}")

# Main Dashboard
df = load_data()

# Remove any empty rows that might exist in the sheet
df = df.dropna(how='all')

if not df.empty:
    st.subheader("Monthly Report")
    
    # Ensure proper data types for calculations
    df['Date'] = pd.to_datetime(df['Date'])
    df['Total Minutes'] = pd.to_numeric(df['Total Minutes'], errors='coerce').fillna(0)
    
    # Create Month/Year column for grouping
    df['Month Year'] = df['Date'].dt.strftime('%B %Y')
    
    # Month selection filter
    unique_months = df['Month Year'].unique()
    selected_month = st.selectbox("Select Month for Report", unique_months)
    
    # Filter the data for the selected month
    month_df = df[df['Month Year'] == selected_month].copy()
    
    # Calculations for metrics
    total_min = int(month_df['Total Minutes'].sum())
    total_hrs = total_min / 60
    
    # Display Summary Metrics
    col1, col2 = st.columns(2)
    col1.metric("Total Hours Worked", f"{total_hrs:.2f} hrs")
    col2.metric("Total Minutes Worked", f"{total_min} min")
    
    # Display the detailed table
    st.write(f"### Shift Details for {selected_month}")
    display_df = month_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]].copy()
    display_df['Date'] = display_df['Date'].dt.date # Clean date for display
    st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("No data found in the spreadsheet. Log your first shift in the sidebar to get started!")
