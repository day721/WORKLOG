import streamlit as st
import pandas as pd
import io
from github import Github, GithubException
from datetime import datetime, timedelta, date, time

# --- APP CONFIG ---
st.set_page_config(page_title="Shift Master", layout="wide")

# Custom CSS for Mobile
st.markdown("""
    <style>
    .stButton > button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- GITHUB CONNECTION ---
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(st.secrets["REPO_NAME"])
    FILE_PATH = st.secrets["FILE_PATH"]
except Exception:
    st.error("Please check your GitHub Secrets!")
    st.stop()

def get_bahrain_now():
    return datetime.utcnow() + timedelta(hours=3)

# --- DATA STORAGE ---
def load_data():
    try:
        content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        df['Date'] = df['Date'].astype(str)
        return df, content.sha
    except Exception:
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]), None

def save_data(df, sha, msg="Update"):
    csv_content = df.to_csv(index=False)
    repo.update_file(FILE_PATH, msg, csv_content, sha)
    return True

def calc_mins(start_str, end_str):
    if not start_str or not end_str: return 0
    t1 = datetime.strptime(start_str, "%H:%M")
    t2 = datetime.strptime(end_str, "%H:%M")
    if t2 < t1: t2 += timedelta(days=1) # Overnight
    return int((t2 - t1).total_seconds() / 60)

# --- APP LOGIC ---
df, sha = load_data()
now = get_bahrain_now()
today_str = now.strftime("%Y-%m-%d")

st.title("⏰ Minutes Master")

# 1. SELECT SHIFT
shift_name = st.selectbox("Current Duty:", ["Shift 1", "Shift 2", "Shift 3", "Shift 4"])

# Find if there is a record for today + this shift
mask = (df['Date'] == today_str) & (df['Shift'] == shift_name)
today_idx = df.index[mask].tolist()

# 2. QUICK BUTTONS
st.subheader("Daily Action")
c1, c2 = st.columns(2)

with c1:
    if st.button("🟢 CHECK IN NOW", type="primary"):
        curr_t = get_bahrain_now().strftime("%H:%M")
        if not today_idx:
            new_row = pd.DataFrame([{"Date": today_str, "Shift": shift_name, "Check-In": curr_t, "Check-Out": "", "Total Minutes": 0}])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df.at[today_idx[0], "Check-In"] = curr_t
        save_data(df, sha, f"In: {shift_name}")
        st.rerun()

with c2:
    if st.button("🔴 CHECK OUT NOW"):
        if today_idx:
            curr_t = get_bahrain_now().strftime("%H:%M")
            df.at[today_idx[0], "Check-Out"] = curr_t
            df.at[today_idx[0], "Total Minutes"] = calc_mins(df.at[today_idx[0], "Check-In"], curr_t)
            save_data(df, sha, f"Out: {shift_name}")
            st.rerun()
        else:
            st.error("No Check-In found for today!")

# 3. MANUAL CLOCK EDIT (The method from your image)
st.divider()
with st.expander("✏️ Edit Times (Opens Clock Picker)"):
    edit_date = st.date_input("Date", now.date())
    date_str = edit_date.strftime("%Y-%m-%d")
    
    # Filter for that date
    day_df = df[df['Date'] == date_str]
    
    if day_df.empty:
        st.info("No records for this date.")
        # Option to add a fresh record
        if st.button("+ Add New Manual Record"):
            new_row = pd.DataFrame([{"Date": date_str, "Shift": shift_name, "Check-In": "08:00", "Check-Out": "17:00", "Total Minutes": 540}])
            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df, sha, "Added Manual")
            st.rerun()
    else:
        for idx, row in day_df.iterrows():
            st.write(f"**{row['Shift']}**")
            # Convert string time to object for the picker
            try:
                val_in = datetime.strptime(row['Check-In'], "%H:%M").time() if row['Check-In'] else now.time()
                val_out = datetime.strptime(row['Check-Out'], "%H:%M").time() if row['Check-Out'] else now.time()
            except:
                val_in, val_out = now.time(), now.time()

            # The 'key' ensures the clock stays on the time you select
            new_in = st.time_input("Set Check-In", value=val_in, key=f"in_{idx}")
            new_out = st.time_input("Set Check-Out", value=val_out, key=f"out_{idx}")
            
            ec1, ec2 = st.columns(2)
            if ec1.button("💾 Save Changes", key=f"sv_{idx}"):
                df.at[idx, "Check-In"] = new_in.strftime("%H:%M")
                df.at[idx, "Check-Out"] = new_out.strftime("%H:%M")
                df.at[idx, "Total Minutes"] = calc_mins(df.at[idx, "Check-In"], df.at[idx, "Check-Out"])
                save_data(df, sha, "Manual Update")
                st.success("Saved!")
                st.rerun()
            
            if ec2.button("🗑️ Delete", key=f"dl_{idx}"):
                df = df.drop(idx)
                save_data(df, sha, "Deleted Entry")
                st.rerun()
            st.write("---")

# 4. VIEW LOGS
if not df.empty:
    st.divider()
    df['DT'] = pd.to_datetime(df['Date'])
    view_month = st.selectbox("Month:", df['DT'].dt.strftime('%B %Y').unique())
    report = df[df['DT'].dt.strftime('%B %Y') == view_month].copy()
    
    total_h = report['Total Minutes'].sum() / 60
    st.metric("Total Hours", f"{total_h:.2f} hrs")
    
    st.dataframe(report[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]].sort_values("Date", ascending=False), 
                 use_container_width=True, hide_index=True)
