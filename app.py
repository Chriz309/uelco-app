import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import requests
import base64
import os
from fpdf import FPDF

# --- CONFIGURATION ---
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

def create_job_card(data):
    """Generates a Professional PDF Job Card with Template."""
    pdf = FPDF()
    pdf.add_page()
    
    # 1. LOAD BACKGROUND TEMPLATE
    # Checks if template.jpg exists. If yes, uses it.
    if os.path.exists("template.jpg"):
        try:
            pdf.image("template.jpg", x=0, y=0, w=210) 
            # Move cursor down to avoid typing over the header logo
            # Adjust '50' if your logo is taller/shorter
            pdf.set_y(50) 
        except Exception as e:
            st.error(f"Template Error: {e}")
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "UELCO SERVICES (Template Error)", ln=True, align='C')
    else:
        # Fallback if no template found
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "UELCO SERVICES - JOB CARD", ln=True, align='C')
        pdf.ln(10)

    # 2. JOB DETAILS TITLE
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(230, 230, 230) # Light Gray
    pdf.cell(0, 8, "  JOB CARD DETAILS", ln=True, fill=True)
    pdf.ln(5)
    
    # 3. DYNAMIC DATA
    pdf.set_font("Arial", size=10)
    
    def clean(text):
        """Cleans text to prevent PDF errors with special characters"""
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # Define fields to print
    fields = [
        ("Reference / Cat", "Category"),
        ("Client Name", "Client_Name"),
        ("Contact No", "Client_Contact"),
        ("Service Type", "Service_Type"),
        ("Date", "Date"),
        ("Date Received", "Date_Received"),
        ("Technician", "Technician"),
        ("Location", "Location"),
        ("Quote Amount", "Quote_Amount"),
    ]

    line_height = 7
    
    for label, key in fields:
        val = data.get(key, "")
        
        # Skip empty fields or NaT
        if val and str(val).strip() != "" and str(val) != "NaT":
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(40, line_height, f"{label}:", border=0)
            
            pdf.set_font("Arial", size=10)
            # clean(val) ensures special chars don't crash the PDF
            pdf.cell(0, line_height, clean(val), border=0, ln=1)

    # 4. NOTES SECTION
    notes = data.get("Notes", "")
    if notes:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Notes / Description of Work:", ln=True, fill=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 6, clean(notes), border=0)

    # 5. SIGNATURE SECTION
    # Move to bottom of page (but above footer)
    if pdf.get_y() < 220:
        pdf.set_y(220) 
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    
    # Signature Lines
    pdf.cell(80, 5, "Technician Signature", 0, 0, 'L')
    pdf.cell(30, 5, "", 0, 0) # Spacer
    pdf.cell(80, 5, "Client Signature", 0, 1, 'L')
    
    pdf.ln(10) # Space for signing
    
    pdf.cell(80, 0, "", "B", 0) # Bottom Border
    pdf.cell(30, 0, "", 0, 0)
    pdf.cell(80, 0, "", "B", 1) # Bottom Border
    
    pdf.ln(2)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(80, 5, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 0)
    pdf.cell(30, 5, "", 0, 0)
    pdf.cell(80, 5, "Date: __________________", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

def upload_to_drive(file_obj, filename):
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

def save_entry(conn, df, data, index=None, rerun=True):
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
        
        # Clear cache to force refresh on next load
        st.cache_data.clear()
        
        if rerun:
            st.toast(msg, icon='💾')
            st.rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")

def delete_entry(conn, df, index):
    try:
        updated_df = df.drop(index).reset_index(drop=True)
        conn.update(worksheet="Sheet1", data=updated_df)
        st.cache_data.clear()
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
    # Filter Data by Category
    if "Category" in full_df.columns:
        category_df = full_df[full_df["Category"] == category_name]
    else:
        category_df = pd.DataFrame()

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
            uploaded_file = st.file_uploader("📎 Upload Document/Photo", key=f"add_up_{category_name}")
            input_data["Notes"] = st.text_area("Notes", key=f"add_nt_{category_name}")
            input_data["Completed"] = False
            input_data["Invoiced"] = False

            if st.form_submit_button("💾 Save New Job"):
                if uploaded_file:
                    with st.spinner("Uploading..."):
                        ext = uploaded_file.name.split('.')[-1]
                        fname = f"{category_name}_{input_data.get('Client_Name', 'Unk')}_{datetime.now().strftime('%M%S')}.{ext}"
                        link = upload_to_drive(uploaded_file, fname)
                        input_data["Photo_Link"] = link if link else ""
                else:
                    input_data["Photo_Link"] = ""
                
                save_entry(conn, full_df, input_data)

    # --- SEARCH BAR ---
    st.divider()
    search_term = st.text_input(f"🔍 Search {category_name}", placeholder="Search Client, Location, or details...", key=f"search_{category_name}")

    if not category_df.empty and search_term:
        mask = category_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
        category_df = category_df[mask]

    # --- DEFINE COLUMNS & CONFIG ---
    if category_name == "Transformer Servicing":
        display_cols = ["Client_Name", "Client_Contact", "Service_Type", "Date_Received", "Quote_Amount", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    else:
        display_cols = ["Date", "Client_Name", "Client_Contact", "Service_Type", "Location", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]

    valid_cols = [c for c in display_cols if c in category_df.columns]
    
    column_settings = {
        "Select": st.column_config.CheckboxColumn("Edit?", default=False, width="small"),
        "Photo_Link": st.column_config.LinkColumn("📎 File", display_text="Open"),
        "OneDrive_Link": st.column_config.LinkColumn("📂 OneDrive", display_text="Folder"),
        "Completed": st.column_config.CheckboxColumn("Done", default=False),
        "Invoiced": st.column_config.CheckboxColumn("Inv", default=False),
        "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "Date_Received": st.column_config.DateColumn("Recv", format="YYYY-MM-DD"),
        "Quote_Amount": st.column_config.TextColumn("Quote"),
    }
    disabled_cols = [c for c in valid_cols if c not in ["Completed", "Invoiced"]]

    # --- SPLIT INTO ACTIVE vs OLD ---
    if not category_df.empty:
        active_jobs = category_df[category_df["Completed"] == False].copy()
        old_jobs = category_df[category_df["Completed"] == True].copy()
    else:
        active_jobs = pd.DataFrame()
        old_jobs = pd.DataFrame()

    def render_job_table(sub_df, title, key_suffix):
        if sub_df.empty:
            st.info(f"No {title.lower()} found.")
            return None

        st.subheader(title)
        
        # Add Select Column (Safe Mode)
        df_editor = sub_df[valid_cols].copy()
        df_editor.insert(0, "Select", False)

        edited_df = st.data_editor(
            df_editor, 
            use_container_width=True, 
            hide_index=True,
            column_config=column_settings,
            disabled=disabled_cols,
            key=f"editor_{category_name}_{key_suffix}"
        )

        try:
            original_subset = sub_df.loc[edited_df.index]
            diff_completed = not edited_df["Completed"].equals(original_subset["Completed"])
            diff_invoiced = not edited_df["Invoiced"].equals(original_subset["Invoiced"])
            
            if diff_completed or diff_invoiced:
                full_df.update(edited_df[["Completed", "Invoiced"]])
                conn.update(worksheet="Sheet1", data=full_df)
                st.cache_data.clear()
                st.toast("Status Updated!", icon="✅")
                st.rerun()
        except:
            pass

        return edited_df

    # Render Tables
    edited_active = render_job_table(active_jobs, "⚡ Current Jobs", "active")
    st.divider()
    edited_old = render_job_table(old_jobs, "✅ Old Jobs (Completed)", "old")

    # --- EDIT LOGIC ---
    selected_index = None
    if edited_active is not None:
        sel_active = edited_active[edited_active["Select"] == True]
        if not sel_active.empty:
            selected_index = sel_active.index[0]

    if edited_old is not None:
        sel_old = edited_old[edited_old["Select"] == True]
        if not sel_old.empty:
            selected_index = sel_old.index[0]

    if selected_index is not None:
        row_data = full_df.loc[selected_index]
        
        st.divider()
        col_head, col_dl = st.columns([2, 1])
        with col_head:
            st.markdown(f"### ✏️ Editing: {row_data.get('Client_Name', 'Job')}")
        with col_dl:
            # --- PDF GENERATION BUTTON ---
            pdf_bytes = create_job_card(row_data)
            st.download_button(
                label="📄 Download Job Card",
                data=pdf_bytes,
                file_name=f"JobCard_{row_data.get('Client_Name', 'Job')}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{selected_index}"
            )
        
        with st.form(f"edit_form_{selected_index}"):
            edit_data = {"Category": category_name}

            if category_name == "Transformer Servicing":
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_data["Date_Received"] = st.date_input("Date Received", parse_date_safe(row_data.get("Date_Received")), key=f"e_dr_{selected_index}")
                    edit_data["Place_Received"] = st.text_input("Place Received", row_data.get("Place_Received", ""), key=f"e_pr_{selected_index}")
                    edit_data["Quote_Amount"] = st.text_input("Quote Amount", row_data.get("Quote_Amount", ""), key=f"e_qa_{selected_index}")
                with col_e2:
                    edit_data["Date_Sent_To_PT"] = st.date_input("Date Sent to PT", parse_date_safe(row_data.get("Date_Sent_To_PT")), key=f"e_ds_{selected_index}")
                    edit_data["Date_Back_From_PT"] = st.date_input("Date Back from PT", parse_date_safe(row_data.get("Date_Back_From_PT")), key=f"e_db_{selected_index}")
                    edit_data["Date_Client_Pickup"] = st.date_input("Date Client Pickup", parse_date_safe(row_data.get("Date_Client_Pickup")), key=f"e_dp_{selected_index}")

                st.markdown("---")
                edit_data["Client_Name"] = st.text_input("Client Name", row_data.get("Client_Name", ""), key=f"e_cn_{selected_index}")
                edit_data["Client_Contact"] = st.text_input("Client Contact", row_data.get("Client_Contact", ""), key=f"e_cc_{selected_index}")
                curr_serv = row_data.get("Service_Type", "")
                s_idx = sub_services.index(curr_serv) if sub_services and curr_serv in sub_services else None
                edit_data["Service_Type"] = st.selectbox("Work Required", sub_services, index=s_idx, key=f"e_st_{selected_index}")

            else:
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_data["Date"] = st.date_input("Date", parse_date_safe(row_data.get("Date")), key=f"e_d_{selected_index}")
                    edit_data["Technician"] = st.text_input("Technician", row_data.get("Technician", ""), key=f"e_t_{selected_index}")
                with col_e2:
                    if sub_services:
                        curr_serv = row_data.get("Service_Type", "")
                        s_idx = sub_services.index(curr_serv) if sub_services and curr_serv in sub_services else None
                        edit_data["Service_Type"] = st.selectbox("Service Type", sub_services, index=s_idx, key=f"e_st_{selected_index}")
                    else:
                        edit_data["Service_Type"] = category_name

                edit_data["Client_Name"] = st.text_input("Client Name", row_data.get("Client_Name", ""), key=f"e_cn_{selected_index}")
                edit_data["Client_Contact"] = st.text_input("Client Contact", row_data.get("Client_Contact", ""), key=f"e_cc_{selected_index}")
                edit_data["Location"] = st.text_input("Location", row_data.get("Location", ""), key=f"e_loc_{selected_index}")

            st.markdown("---")
            edit_data["OneDrive_Link"] = st.text_input("OneDrive Link", row_data.get("OneDrive_Link", ""), key=f"e_od_{selected_index}")
            
            curr_photo = row_data.get("Photo_Link", "")
            if curr_photo and len(str(curr_photo)) > 5:
                st.caption(f"Current File: [Open File]({curr_photo})")
            
            new_file = st.file_uploader("Upload New File (Overwrites old)", key=f"e_up_{selected_index}")
            edit_data["Notes"] = st.text_area("Notes", row_data.get("Notes", ""), key=f"e_nt_{selected_index}")

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.form_submit_button("💾 Update Job Details"):
                    if new_file:
                        with st.spinner("Uploading New File..."):
                            ext = new_file.name.split('.')[-1]
                            fname = f"{category_name}_{edit_data.get('Client_Name', 'Unk')}_UPDATED.{ext}"
                            link = upload_to_drive(new_file, fname)
                            edit_data["Photo_Link"] = link if link else curr_photo
                    else:
                        edit_data["Photo_Link"] = curr_photo
                    save_entry(conn, full_df, edit_data, index=selected_index)

            with col_btn2:
                if st.form_submit_button("🗑️ Delete Job"):
                    delete_entry(conn, full_df, index=selected_index)


# --- MAIN APP ---
def main():
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.title("⚡ UELCO System")
    with col_btn:
        st.write("") 
        if st.button("🔄 Refresh Data", type="primary"):
            st.cache_data.clear()
            st.rerun()
            
    st.markdown(f'<a href="{ONEDRIVE_URL}" target="_blank" class="header-link">📂 Open OneDrive</a>', unsafe_allow_html=True)

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # TTL set to 10 mins (600s) to stop random refreshing
        df = conn.read(worksheet="Sheet1", ttl=600).dropna(how='all')
        
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
            note_file = st.file_uploader("📎 Attach File (Optional)", key="note_file_up")

            if st.form_submit_button("📌 Pin Note"):
                note_data = {"Date": datetime.now(), "Category": "General Note", "Notes": note_content}
                
                if note_file:
                    with st.spinner("Uploading attachment..."):
                        ext = note_file.name.split('.')[-1]
                        fname = f"Note_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                        link = upload_to_drive(note_file, fname)
                        note_data["Photo_Link"] = link if link else ""
                else:
                    note_data["Photo_Link"] = ""

                save_entry(conn, df, note_data)

        st.divider()
        st.subheader("📌 Manage Notes")
        
        search_note = st.text_input("🔍 Search Notes", key="search_notes")
        
        if "Category" in df.columns:
            notes_df = df[df["Category"] == "General Note"]
            
            if search_note and not notes_df.empty:
                mask = notes_df["Notes"].astype(str).str.contains(search_note, case=False, na=False)
                notes_df = notes_df[mask]

            if not notes_df.empty:
                if "Photo_Link" not in notes_df.columns:
                    notes_df["Photo_Link"] = ""
                
                note_config = {
                    "Photo_Link": st.column_config.LinkColumn("📎 File", display_text="Open"),
                    "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    "Notes": st.column_config.TextColumn("Content", width="large")
                }
                
                display_cols = ["Date", "Notes", "Photo_Link"]
                valid_note_cols = [c for c in display_cols if c in notes_df.columns]

                st.dataframe(
                    notes_df[valid_note_cols], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config=note_config
                )

                note_options = notes_df.apply(lambda x: f"{x.name} | {x.get('Notes', '')[:30]}...", axis=1).tolist()
                sel_note = st.selectbox("Select Note to Delete", note_options, index=None)
                if sel_note:
                    n_idx = int(sel_note.split(" | ")[0])
                    if st.button("🗑️ Delete Selected Note"):
                        delete_entry(conn, df, n_idx)

if __name__ == "__main__":
    main()
