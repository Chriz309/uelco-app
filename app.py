import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import requests
import base64

# --- CONFIGURATION ---
# ⚠️ PASTE YOUR WORKING APPS SCRIPT URL HERE
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwJcYe-EOQ9sDKoha3ZSNTVjxuh2EbL1rWYiBS5zvxZnPwK3bPD9nNtm1NGVI-_S_yNLQ/exec" 

ONEDRIVE_URL = "https://uelcoservices-my.sharepoint.com/personal/sonelle_uelco_co_za/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Fsonelle%5Fuelco%5Fco%5Fza%2FDocuments%2FUelco%20APP%20testing&viewid=610b061b%2Db513%2D4114%2D8c76%2D59a9d605bddf&ga=1"

st.set_page_config(page_title="UELCO Mobile", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .header-link { 
        display: inline-block; background-color: #0078D4; color: white; 
        padding: 10px 20px; border-radius: 8px; text-decoration: none; 
        font-weight: bold; text-align: center;
    }
    .header-link:hover { background-color: #005a9e; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def upload_to_drive(file_obj, filename):
    """Uploads to Drive via Apps Script."""
    if "script.google.com" not in APPS_SCRIPT_URL:
        st.error("❌ Error: You haven't pasted the Apps Script Web App URL yet.")
        return None

    try:
        file_content = file_obj.getvalue()
        base64_data = base64.b64encode(file_content).decode('utf-8')
        
        payload = {
            'filename': filename,
            'mimetype': file_obj.type,
            'data': base64_data
        }
        
        response = requests.post(APPS_SCRIPT_URL, data=payload)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('result') == 'success':
                return result.get('link')
            else:
                st.error(f"❌ Upload Script Error: {result.get('error')}")
                return None
        else:
            st.error(f"❌ Connection Error: {response.status_code}")
            return None
            
    except Exception as e:
        st.error(f"❌ Upload Failed Details: {e}") 
        return None

def save_entry(conn, df, data, index=None):
    """Saves a new entry or updates an existing one."""
    for k, v in data.items():
        if isinstance(v, (datetime, pd.Timestamp)):
            data[k] = v.strftime("%Y-%m-%d")
        if v is None:
            data[k] = ""

    try:
        if index is not None:
            for col, val in data.items():
                df.at[index, col] = val
            updated_df = df
            msg = "Job Updated Successfully!"
        else:
            new_row = pd.DataFrame([data])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            msg = "New Job Added Successfully!"
        
        conn.update(worksheet="Sheet1", data=updated_df)
        st.toast(msg, icon='💾')
        st.rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")

def delete_entry(conn, df, index):
    """Deletes a row from the dataframe."""
    try:
        updated_df = df.drop(index).reset_index(drop=True)
        conn.update(worksheet="Sheet1", data=updated_df)
        st.toast("Job Deleted Successfully!", icon='🗑️')
        st.rerun()
    except Exception as e:
        st.error(f"Delete failed: {e}")

def parse_date_safe(date_val):
    if pd.isnull(date_val) or date_val == "":
        return None
    try:
        return pd.to_datetime(date_val).date()
    except:
        return None

def render_category_tab(conn, full_df, category_name, sub_services=None):
    # Filter Data
    if "Category" in full_df.columns:
        category_df = full_df[full_df["Category"] == category_name]
    else:
        category_df = pd.DataFrame()

    if "Completed" in category_df.columns:
        active_df = category_df[category_df["Completed"] == False]
        completed_df = category_df[category_df["Completed"] == True]
    else:
        active_df = category_df
        completed_df = pd.DataFrame()

    # --- ADD NEW FORM ---
    with st.expander(f"➕ Add New {category_name}", expanded=False):
        with st.form(f"add_form_{category_name}", clear_on_submit=True):
            input_data = {"Category": category_name}
            
            if category_name == "Transformer Servicing":
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    input_data["Date_Received"] = st.date_input("Date Received", datetime.now(), key=f"add_dr_{category_name}")
                    input_data["Place_Received"] = st.text_input("Place Received", key=f"add_pr_{category_name}")
                    input_data["Quote_Amount"] = st.text_input("Quote Amount (R)", key=f"add_qa_{category_name}")
                with col_t2:
                    input_data["Date_Sent_To_PT"] = st.date_input("Date Sent to PT", None, key=f"add_ds_{category_name}")
                    input_data["Date_Back_From_PT"] = st.date_input("Date Back from PT", None, key=f"add_db_{category_name}")
                    input_data["Date_Client_Pickup"] = st.date_input("Date Client Pickup", None, key=f"add_dp_{category_name}")
                
                st.markdown("---")
                input_data["Client_Name"] = st.text_input("Client Name", key=f"add_cn_{category_name}")
                input_data["Client_Contact"] = st.text_input("Client Contact", key=f"add_cc_{category_name}")
                input_data["Service_Type"] = st.selectbox("Work Required", sub_services, index=None, key=f"add_st_{category_name}")

            else:
                col1, col2 = st.columns(2)
                with col1:
                    input_data["Date"] = st.date_input("Date", datetime.now(), key=f"add_d_{category_name}")
                    input_data["Technician"] = st.text_input("Technician Name", key=f"add_tech_{category_name}")
                with col2:
                    if sub_services:
                        input_data["Service_Type"] = st.selectbox("Service Type", sub_services, index=None, key=f"add_st_{category_name}")
                    else:
                        input_data["Service_Type"] = category_name

                input_data["Client_Name"] = st.text_input("Client Name", key=f"add_cn_{category_name}")
                input_data["Client_Contact"] = st.text_input("Client Contact", key=f"add_cc_{category_name}")
                input_data["Location"] = st.text_input("Location", key=f"add_loc_{category_name}")

            st.markdown("---")
            input_data["OneDrive_Link"] = st.text_input("🔗 OneDrive Folder Link", key=f"add_od_{category_name}")
            uploaded_file = st.file_uploader("📷 Upload Job Photo", type=['jpg', 'png', 'jpeg'], key=f"add_up_{category_name}")
            input_data["Notes"] = st.text_area("Notes", key=f"add_nt_{category_name}")
            input_data["Completed"] = False
            input_data["Invoiced"] = False

            if st.form_submit_button("💾 Save New Job"):
                if uploaded_file:
                    with st.spinner("Uploading..."):
                        fname = f"{category_name}_{input_data.get('Client_Name', 'Unk')}_{datetime.now().strftime('%M%S')}.jpg"
                        link = upload_to_drive(uploaded_file, fname)
                        input_data["Photo_Link"] = link if link else ""
                else:
                    input_data["Photo_Link"] = ""
                
                save_entry(conn, full_df, input_data)

    # --- VIEW LISTS (CLEANED UP) ---
    st.subheader(f"⚡ Active Jobs")
    
    # 1. Define distinct visible columns based on category
    if category_name == "Transformer Servicing":
        display_cols = [
            "Client_Name", "Client_Contact", "Service_Type", 
            "Date_Received", "Place_Received", "Quote_Amount", 
            "Date_Sent_To_PT", "Date_Back_From_PT", "Date_Client_Pickup",
            "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"
        ]
    else:
        # For Sales and Cable Faults
        display_cols = [
            "Date", "Client_Name", "Client_Contact", "Service_Type",
            "Technician", "Location", 
            "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"
        ]

    # 2. Filter dataframe to only show columns that actually exist in the sheet
    valid_cols = [c for c in display_cols if c in active_df.columns]
    
    # 3. Define Column Config (This makes links clickable)
    column_settings = {
        "Photo_Link": st.column_config.LinkColumn("📷 Photo", display_text="View Photo"),
        "OneDrive_Link": st.column_config.LinkColumn("📂 OneDrive", display_text="Open Folder"),
        "Completed": st.column_config.CheckboxColumn("Done", default=False),
        "Invoiced": st.column_config.CheckboxColumn("Inv", default=False),
        "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "Date_Received": st.column_config.DateColumn("Recv", format="YYYY-MM-DD"),
        "Quote_Amount": st.column_config.TextColumn("Quote (R)"),
    }

    # Show Active
    if not active_df.empty:
        st.dataframe(
            active_df[valid_cols], 
            use_container_width=True, 
            hide_index=True,
            column_config=column_settings
        )
    else:
        st.info("No active jobs.")

    # Show Completed
    with st.expander(f"Show Completed Jobs"):
        if not completed_df.empty:
            st.dataframe(
                completed_df[valid_cols], 
                use_container_width=True, 
                hide_index=True,
                column_config=column_settings
            )
        else:
            st.info("No completed jobs.")

    # --- EDIT / DELETE SECTION ---
    st.divider()
    st.subheader(f"✏️ Manage / Edit Job")
    
    if not category_df.empty:
        options = category_df.apply(
            lambda x: f"{x.name} | {x.get('Client_Name', 'Unknown')} ({x.get('Service_Type', 'Job')})", 
            axis=1
        ).tolist()
        
        selected_option = st.selectbox(f"Select a {category_name} Job to Edit or Delete:", options, index=None, key=f"sel_{category_name}")

        if selected_option:
            row_idx = int(selected_option.split(" | ")[0])
            row_data = full_df.loc[row_idx]

            with st.form(f"edit_form_{row_idx}"):
                edit_data = {"Category": category_name}

                if category_name == "Transformer Servicing":
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        edit_data["Date_Received"] = st.date_input("Date Received", parse_date_safe(row_data.get("Date_Received")), key=f"e_dr_{row_idx}")
                        edit_data["Place_Received"] = st.text_input("Place Received", row_data.get("Place_Received", ""), key=f"e_pr_{row_idx}")
                        edit_data["Quote_Amount"] = st.text_input("Quote Amount", row_data.get("Quote_Amount", ""), key=f"e_qa_{row_idx}")
                    with col_e2:
                        edit_data["Date_Sent_To_PT"] = st.date_input("Date Sent to PT", parse_date_safe(row_data.get("Date_Sent_To_PT")), key=f"e_ds_{row_idx}")
                        edit_data["Date_Back_From_PT"] = st.date_input("Date Back from PT", parse_date_safe(row_data.get("Date_Back_From_PT")), key=f"e_db_{row_idx}")
                        edit_data["Date_Client_Pickup"] = st.date_input("Date Client Pickup", parse_date_safe(row_data.get("Date_Client_Pickup")), key=f"e_dp_{row_idx}")

                    st.markdown("---")
                    edit_data["Client_Name"] = st.text_input("Client Name", row_data.get("Client_Name", ""), key=f"e_cn_{row_idx}")
                    edit_data["Client_Contact"] = st.text_input("Client Contact", row_data.get("Client_Contact", ""), key=f"e_cc_{row_idx}")
                    curr_serv = row_data.get("Service_Type", "")
                    s_idx = sub_services.index(curr_serv) if sub_services and curr_serv in sub_services else None
                    edit_data["Service_Type"] = st.selectbox("Work Required", sub_services, index=s_idx, key=f"e_st_{row_idx}")

                else:
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        edit_data["Date"] = st.date_input("Date", parse_date_safe(row_data.get("Date")), key=f"e_d_{row_idx}")
                        edit_data["Technician"] = st.text_input("Technician", row_data.get("Technician", ""), key=f"e_t_{row_idx}")
                    with col_e2:
                        if sub_services:
                            curr_serv = row_data.get("Service_Type", "")
                            s_idx = sub_services.index(curr_serv) if sub_services and curr_serv in sub_services else None
                            edit_data["Service_Type"] = st.selectbox("Service Type", sub_services, index=s_idx, key=f"e_st_{row_idx}")
                        else:
                            edit_data["Service_Type"] = category_name

                    edit_data["Client_Name"] = st.text_input("Client Name", row_data.get("Client_Name", ""), key=f"e_cn_{row_idx}")
                    edit_data["Client_Contact"] = st.text_input("Client Contact", row_data.get("Client_Contact", ""), key=f"e_cc_{row_idx}")
                    edit_data["Location"] = st.text_input("Location", row_data.get("Location", ""), key=f"e_loc_{row_idx}")

                st.markdown("---")
                edit_data["OneDrive_Link"] = st.text_input("OneDrive Link", row_data.get("OneDrive_Link", ""), key=f"e_od_{row_idx}")
                
                curr_photo = row_data.get("Photo_Link", "")
                if curr_photo and len(str(curr_photo)) > 5:
                    st.caption(f"Current Photo: [View Link]({curr_photo})")
                
                new_file = st.file_uploader("Upload New Photo (Overwrites old)", type=['jpg', 'png'], key=f"e_up_{row_idx}")
                edit_data["Notes"] = st.text_area("Notes", row_data.get("Notes", ""), key=f"e_nt_{row_idx}")

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    edit_data["Completed"] = st.checkbox("✅ Job Completed", value=bool(row_data.get("Completed", False)), key=f"e_comp_{row_idx}")
                with col_s2:
                    edit_data["Invoiced"] = st.checkbox("💰 Invoiced", value=bool(row_data.get("Invoiced", False)), key=f"e_inv_{row_idx}")

                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    if st.form_submit_button("💾 Update Job Details"):
                        if new_file:
                            with st.spinner("Uploading New Photo..."):
                                fname = f"{category_name}_{edit_data.get('Client_Name', 'Unk')}_UPDATED.jpg"
                                link = upload_to_drive(new_file, fname)
                                edit_data["Photo_Link"] = link if link else curr_photo
                        else:
                            edit_data["Photo_Link"] = curr_photo
                        save_entry(conn, full_df, edit_data, index=row_idx)

                with col_btn2:
                    if st.form_submit_button("🗑️ Delete Job"):
                        delete_entry(conn, full_df, index=row_idx)
    else:
        st.info("No jobs found in this category.")

# --- MAIN APP ---
def main():
    col_title, col_link = st.columns([3, 1])
    with col_title:
        st.title("⚡ UELCO System")
    with col_link:
        st.markdown(f'<br><a href="{ONEDRIVE_URL}" target="_blank" class="header-link">📂 Open OneDrive</a>', unsafe_allow_html=True)

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=5).dropna(how='all')
        
        date_cols = ["Date", "Date_Received", "Date_Sent_To_PT", "Date_Back_From_PT", "Date_Client_Pickup"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        bool_cols = ["Completed", "Invoiced"]
        for col in bool_cols:
            if col in df.columns:
                df[col] = df[col].fillna(False).astype(bool)

        text_cols = ["Notes", "OneDrive_Link", "Photo_Link", "Client_Contact", "Location", "Place_Received", "Quote_Amount", "Technician", "Service_Type", "Client_Name"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)

    except Exception as e:
        st.error(f"⚠️ Connection Error: {e}")
        df = pd.DataFrame()

    tab_sales, tab_trans, tab_cable, tab_notes = st.tabs(["💰 Sales & Install", "⚡ Transformer Servicing", "🔌 Cable Faults", "📝 Notes"])

    with tab_sales:
        render_category_tab(conn, df, "Sales & Install", ["Order", "Order + Delivery", "Order + Installation"])
    with tab_trans:
        render_category_tab(conn, df, "Transformer Servicing", ["Oil Change", "Gasket Replacement", "General Service", "Testing"])
    with tab_cable:
        render_category_tab(conn, df, "Cable Faults", ["Thumping/Locating", "Jointing"])

    with tab_notes:
        st.header("📝 Quick Notes")
        with st.form("note_form", clear_on_submit=True):
            note_content = st.text_area("Note Content")
            if st.form_submit_button("📌 Pin Note"):
                note_data = {"Date": datetime.now(), "Category": "General Note", "Notes": note_content}
                save_entry(conn, df, note_data)

        st.divider()
        st.subheader("📌 Manage Notes")
        if "Category" in df.columns:
            notes_df = df[df["Category"] == "General Note"]
            if not notes_df.empty:
                st.dataframe(notes_df[["Date", "Notes"]], use_container_width=True, hide_index=True)
                note_options = notes_df.apply(lambda x: f"{x.name} | {x.get('Notes', '')[:30]}...", axis=1).tolist()
                sel_note = st.selectbox("Select Note to Delete", note_options, index=None)
                if sel_note:
                    n_idx = int(sel_note.split(" | ")[0])
                    if st.button("🗑️ Delete Selected Note"):
                        delete_entry(conn, df, n_idx)

if __name__ == "__main__":
    main()
