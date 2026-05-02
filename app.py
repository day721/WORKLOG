import streamlit as st
import pandas as pd
import io
from github import Github, GithubException
from datetime import datetime, date, time
from fpdf import FPDF # For PDF export

# App Configuration
st.set_page_config(page_title="Shift Tracker Pro", layout="wide")

# GitHub Connection Setup
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    FILE_PATH = st.secrets["FILE_PATH"]
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except KeyError:
    st.error("Missing Secrets! Check GITHUB_TOKEN, REPO_NAME, and FILE_PATH.")
    st.stop()

# --- HELPER FUNCTIONS ---

def load_data_from_github():
    try:
        content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        return df, content.sha
    except GithubException as e:
        if e.status == 404:
            return pd.DataFrame(columns=["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]), None
        return pd.DataFrame(), None

def save_data_to_github(df, sha):
    csv_content = df.to_csv(index=False)
    try:
        if sha:
            repo.update_file(FILE_PATH, "Update logs", csv_content, sha)
        else:
            repo.create_file(FILE_PATH, "Init logs", csv_content)
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def to_pdf(df, month_name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(40, 10, f"Work Log Report - {month_name}")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 10)
    # Headers
    cols = ["Date", "Shift", "In", "Out", "Mins"]
    for col in cols:
        pdf.cell(35, 10, col, 1)
    pdf.ln()
    
    pdf.set_font("Arial", "", 10)
    for i, row in df.iterrows():
        pdf.cell(35, 10, str(row['Date']), 1)
        pdf.cell(35, 10, str(row['Shift']), 1)
        pdf.cell(35, 10, str(row['Check-In']), 1)
        pdf.cell(35, 10, str(row['Check-Out']), 1)
        pdf.cell(35, 10, str(row['Total Minutes']), 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- UI LAYOUT ---

st.title("🕒 Daily Shift Tracker")

# Sidebar for Mobile-Friendly Input
with st.sidebar:
    st.header("📝 Log New Shift")
    today = st.date_input("Select Date", date.today())
    shift_type = st.selectbox("Shift Type", ["Shift 1", "Shift 2"])
    
    # Defaults to CURRENT TIME as requested
    current_time = datetime.now().time()
    check_in = st.time_input("Check-In Time", value=current_time)
    check_out = st.time_input("Check-Out Time", value=current_time)
    
    if st.button("🚀 Save to GitHub", use_container_width=True):
        start_dt = datetime.combine(today, check_in)
        end_dt = datetime.combine(today, check_out)
        
        if end_dt <= start_dt:
            st.warning("Note: Check-out is before/same as Check-in. If overnight, ensure logic accounts for next day.")
            # Basic logic: assume same day for now.
        
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
        updated_df = pd.concat([df, new_row], ignore_index=True)
        if save_data_to_github(updated_df, sha):
            st.success("Saved!")
            st.rerun()

# --- MAIN DASHBOARD ---
df, _ = load_data_from_github()

if not df.empty:
    df['Date'] = pd.to_datetime(df['Date'])
    df['Month Year'] = df['Date'].dt.strftime('%B %Y')
    
    selected_month = st.selectbox("📅 View Month", df['Month Year'].unique())
    month_df = df[df['Month Year'] == selected_month].copy()
    
    # Responsive Metrics
    m1, m2 = st.columns(2)
    total_min = int(month_df['Total Minutes'].sum())
    m1.metric("Total Hours", f"{total_min/60:.2f}h")
    m2.metric("Total Minutes", f"{total_min}m")

    # Export Section
    st.write("---")
    st.subheader("📥 Export Report")
    ex1, ex2 = st.columns(2)
    
    with ex1:
        st.download_button(
            label="📊 Download Excel",
            data=to_excel(month_df),
            file_name=f"Work_Log_{selected_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with ex2:
        pdf_data = to_pdf(month_df, selected_month)
        st.download_button(
            label="📄 Download PDF",
            data=pdf_data,
            file_name=f"Work_Log_{selected_month}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    st.write("---")
    # Clean up Date for display
    display_df = month_df.copy()
    display_df['Date'] = display_df['Date'].dt.date
    st.dataframe(display_df[["Date", "Shift", "Check-In", "Check-Out", "Total Minutes"]], 
                 use_container_width=True, hide_index=True)
else:
    st.info("No data found. Log your first shift in the sidebar!")
