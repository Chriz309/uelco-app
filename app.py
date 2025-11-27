import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION SECTION ---
# NOTE: We no longer need EXCEL_FILE. 
# The spreadsheet link is handled in your secrets.toml file.

# Form Configuration
FORM_FIELDS = {
    "Date": "date",       
    "Job_ID": "text",     
    "Client_Name": "text",
    "Location": "text",
    "Service_Type": ["Installation", "Maintenance", "Inspection", "Emergency"], 
    "Technician": "text",
    "Status": ["Pending", "In Progress", "Completed"], 
    "Notes": "area"       
}

# --- PAGE SETTINGS (Mobile Optimization) ---
st.set_page_config(page_title="UELCO Mobile", layout="centered")

# --- CUSTOM CSS FOR MOBILE FRIENDLINESS ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 3em;
        font-size: 20px;
        margin-top: 10px;
        border-radius: 10px;
    }
    div[data-testid="stExpander"] div[role="button"] p {
        font-size: 1.2rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- BACKEND FUNCTIONS (Google Sheets Logic) ---

def get_connection():
    """Establishes the connection to Google Sheets using secrets.toml"""
    return st.connection("gsheets", type=GSheetsConnection)

def load_data(conn):
    """Loads the Google Sheet data."""
    try:
        # ttl=5 ensures we don't cache old data for too long (5 seconds)
        df = conn.read(worksheet="Sheet1", ttl=5)
        
        # If the sheet is empty or just created, ensure columns exist
        if df.empty:
            return pd.DataFrame(columns=FORM_FIELDS.keys())
            
        # Ensure we don't have completely empty rows (ghost data)
        df = df.dropna(how='all')
        return df
    except Exception as e:
        st.error(f"Error reading Google Sheet: {e}")
        return pd.DataFrame(columns=FORM_FIELDS.keys())

def save_data(conn, df):
    """Updates the Google Sheet with the new dataframe."""
    try:
        conn.update(worksheet="Sheet1", data=df)
        return True
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")
        return False

# --- MAIN APP INTERFACE ---

def main():
    st.title("⚡ UELCO System")
    
    # Initialize Connection
    conn = get_connection()
    
    # Load current database
    df = load_data(conn)

    # Create Tabs
    tab1, tab2, tab3 = st.tabs(["📝 New Entry", "📊 Database", "📈 Analytics"])

    # --- TAB 1: NEW ENTRY ---
    with tab1:
        st.header("New Service Record")
        
        with st.form("uelco_form", clear_on_submit=True):
            input_data = {}
            
            # Dynamically generate fields
            for field, field_type in FORM_FIELDS.items():
                label = field.replace("_", " ")
                
                if field_type == "date":
                    input_data[field] = st.date_input(label, datetime.now())
                elif field_type == "area":
                    input_data[field] = st.text_area(label)
                elif isinstance(field_type, list): 
                    input_data[field] = st.selectbox(label, field_type)
                else:
                    input_data[field] = st.text_input(label)

            submitted = st.form_submit_button("💾 Save to Cloud")
            
            if submitted:
                # Convert date objects to string for cleaner GSheets storage
                for k, v in input_data.items():
                    if isinstance(v, (datetime, pd.Timestamp)):
                        input_data[k] = v.strftime("%Y-%m-%d")
                
                # Create new row
                new_row = pd.DataFrame([input_data])
                
                # Append to existing data
                updated_df = pd.concat([df, new_row], ignore_index=True)
                
                # Save via Connection
                if save_data(conn, updated_df):
                    st.success("Entry saved successfully!")
                    st.toast('Data saved to Google Sheets', icon='☁️')
                    
                    # Force a rerun so the "Database" tab updates immediately
                    # st.rerun() # Uncomment this if you want immediate page refresh

    # --- TAB 2: VIEW DATABASE ---
    with tab2:
        st.header("Live Cloud Data")
        
        search_term = st.text_input("🔍 Search Database")
        
        display_df = df
        if not df.empty and search_term:
            mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            display_df = display_df[mask]

        st.dataframe(display_df, use_container_width=True)
        st.caption(f"Total Records: {len(df)}")
        
        # Note: Direct download from GSheets works differently, 
        # so we removed the file download button as the data lives in the cloud now.

    # --- TAB 3: ANALYTICS ---
    with tab3:
        st.header("Overview")
        if not df.empty:
            if "Status" in df.columns:
                st.subheader("Project Status")
                st.bar_chart(df["Status"].value_counts())
            
            if "Service_Type" in df.columns:
                st.subheader("Service Types")
                st.bar_chart(df["Service_Type"].value_counts())
        else:
            st.info("No data available for analytics yet.")

if __name__ == "__main__":
    main()