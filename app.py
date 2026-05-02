import streamlit as st
import pandas as pd
import io
from github import Github, GithubException
from datetime import datetime, timedelta, date, time
from fpdf import FPDF

# App Config
st.set_page_config(page_title="Day to Day Shift Tracker", layout="wide")

# --- SETTINGS & GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    FILE_PATH = st.secrets["FILE_PATH"]
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception:
    st.error("Check Streamlit Secrets!")
    st.stop()

# Bahrain Time Adjustment (UTC + 3)
def get_bahrain_now():
    return datetime.utcnow() + timedelta(hours=3)

# --- DATA ENGINE ---
def load_data():
    try:
        content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        # Ensure correct types
        df['Date'] = df['Date'].astype(str)
        return df, content.sha
    except Exception:
        return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]), None

def save_to_github(df, sha):
    csv_content = df.to_csv(index=False)
    if sha:
        repo.update_file(FILE_PATH, "Update Shift", csv_content, sha)
    else:
        repo.create_file(FILE_PATH, "Init Log", csv_content)

# --- EXPORTS ---
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def to_pdf(df, month):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"Work Report: {month}", ln=True, align='C')
    pdf.set_font("Arial", "B", 10)
    for col in ["Date", "Shift", "In", "Out", "Mins"]:
        pdf.cell(38, 10, col, 1)
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    for _, row in df.iterrows():
        pdf.cell(38, 10, str(row['Date']), 1)
        pdf.cell(38, 10, str(row['Shift']), 1)
        pdf.cell(38, 10, str(row['Check-In']), 1)
        pdf.cell(38, 10, str(row['Check-Out']), 1)
        pdf.cell(38, 10, str(row['Total Minutes']), 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- MAIN UI ---
st.title("🕒 Quick Shift Logger")

now = get_bahrain_now()
today_str = now.strftime("%Y-%m-%d")

# 1. SELECT SHIFT
shift_type = st.radio("Current Shift:", ["Shift 1", "Shift 2"], horizontal=True)

# 2. CHECK-IN / OUT BUTTONS (One-Click)
col1, col2 = st.columns(2)

df, sha = load_data()

# Find if record exists for today + this shift
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
        st.success(f"Checked In at {current_t}")
        st.rerun()

with col2:
    if st.button("🔴 CHECK OUT NOW", use_container_width=True):
        if not existing_idx:
            st.error("No Check-In found for today! Check in first.")
        else:
            current_t = get_bahrain_now().strftime("%H:%M")
            df.at[existing_idx[0], "Check-Out"] = current_t
            
            # Calculate duration
            in_t = datetime.strptime(df.at[existing_idx[0], "Check-In"], "%H:%M")
            out_t = datetime.strptime(current_t, "%H:%M")
            delta = (out_t - in_t).total_seconds() / 60
            df.at[existing_idx[0], "Total Minutes"] = int(delta)
            
            save_to_github(df, sha)
            st.success(f"Checked Out at {current_t}")
            st.rerun()

# 3. MANUAL EDIT OPTION
with st.expander("✏️ Edit Time Manually"):
    manual_date = st.date_input("Date", now.date())
    manual_in = st.time_input("Manual In", now.time())
    manual_out = st.time_input("Manual Out", now.time())
    if st.button("Update Manually"):
        m_date_str = manual_date.strftime("%Y-%m-%d")
        m_mask = (df['Date'] == m_date_str) & (df['Shift'] == shift_type)
        m_idx = df.index[m_mask].tolist()
        
        in_str = manual_in.strftime("%H:%M")
        out_str = manual_out.strftime("%H:%M")
        
        in_dt = datetime.combine(date.today(), manual_in)
        out_dt = datetime.combine(date.today(), manual_out)
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

# --- REPORTS ---
st.divider()
if not df.empty:
    df['Date_DT'] = pd.to_datetime(df['Date'])
    df['Month'] = df['Date_DT'].dt.strftime('%B %Y')
    
    view_month = st.selectbox("Monthly Report", df['Month'].unique())
    report_df = df[df['Month'] == view_month].copy()
    
    total_m = int(report_df['Total Minutes'].sum())
    c1, c2 = st.columns(2)
    c1.metric("Total Hours", f"{total_m/60:.2f}h")
    c2.metric("Total Minutes", f"{total_m}m")
    
    # DOWNLOADS
    d1, d2 = st.columns(2)
    d1.download_button("📥 Excel", to_excel(report_df), f"Log_{view_month}.xlsx", use_container_width=True)
    d2.download_button("📥 PDF", to_pdf(report_df, view_month), f"Log_{view_month}.pdf", use_container_width=True)

    st.dataframe(report_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], use_container_width=True, hide_index=True)
