import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import requests
import base64
import os
import re
from fpdf import FPDF

# --- CONFIGURATION ---
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwJcYe-EOQ9sDKoha3ZSNTVjxuh2EbL1rWYiBS5zvxZnPwK3bPD9nNtm1NGVI-_S_yNLQ/exec" 
ONEDRIVE_URL = "https://uelcoservices-my.sharepoint.com/personal/sonelle_uelco_co_za/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Fsonelle%5Fuelco%5Fco%5Fza%2FDocuments%2FUelco%20APP%20testing&viewid=610b061b%2Db513%2D4114%2D8c76%2D59a9d605bddf&ga=1"

st.set_page_config(page_title="UELCO-MANAGER", layout="wide")

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .header-link { 
        display: inline-block; background-color: #0078D4; color: white; 
        padding: 10px 20px; border-radius: 8px; text-decoration: none; 
        font-weight: bold; text-align: center;
    }
    .status-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; font-weight: bold; text-align: center; }
    .unsaved { background-color: #ffeeba; color: #856404; border: 1px solid #ffeeba; }
    .saved { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def clean_phone_for_whatsapp(phone):
    if not phone: return None
    digits = re.sub(r'\D', '', str(phone))
    if digits.startswith('0'): digits = '27' + digits[1:]
    return f"https://wa.me/{digits}"

def create_job_card(data):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists("template.jpg"):
        try:
            pdf.image("template.jpg", x=0, y=0, w=210) 
            pdf.set_y(50) 
        except:
            pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "UELCO SERVICES", ln=True, align='C')
    else:
        pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "UELCO SERVICES - JOB CARD", ln=True, align='C'); pdf.ln(10)

    pdf.set_font("Arial", 'B', 12); pdf.set_fill_color(230, 230, 230); pdf.cell(0, 8, "  JOB CARD DETAILS", ln=True, fill=True); pdf.ln(5)
    pdf.set_font("Arial", size=10)
    
    def clean(text): return str(text).encode('latin-1', 'replace').decode('latin-1')

    fields = [("Ref", "Category"), ("Client", "Client_Name"), ("Contact", "Client_Contact"), ("Service", "Service_Type"), ("Date", "Date"), ("Date Recv", "Date_Received"), ("Tech", "Technician"), ("Loc", "Location"), ("Quote", "Quote_Amount")]
    for label, key in fields:
        val = data.get(key, "")
        if val and str(val).strip() != "" and str(val) != "NaT":
            pdf.set_font("Arial", 'B', 10); pdf.cell(40, 7, f"{label}:", border=0)
            pdf.set_font("Arial", size=10); pdf.cell(0, 7, clean(val), border=0, ln=1)

    if data.get("Notes"):
        pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, "Notes:", ln=True, fill=True)
        pdf.set_font("Arial", size=10); pdf.multi_cell(0, 6, clean(data.get("Notes")), border=0)

    if pdf.get_y() < 220: pdf.set_y(220)
    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 5, "Technician Signature", 0, 0); pdf.cell(30, 5, ""); pdf.cell(80, 5, "Client Signature", 0, 1)
    pdf.ln(10); pdf.cell(80, 0, "", "B"); pdf.cell(30, 0, ""); pdf.cell(80, 0, "", "B", 1)
    return pdf.output(dest='S').encode('latin-1')

def upload_to_drive(file_obj, filename):
    if "script.google.com" not in APPS_SCRIPT_URL: return None
    try:
        data = base64.b64encode(file_obj.getvalue()).decode('utf-8')
        resp = requests.post(APPS_SCRIPT_URL, data={'filename': filename, 'mimetype': file_obj.type, 'data': data})
        return resp.json().get('link') if resp.status_code == 200 and resp.json().get('result') == 'success' else None
    except: return None

def parse_date_safe(date_val):
    if pd.isnull(date_val) or date_val == "": return None
    try: return pd.to_datetime(date_val).date()
    except: return None

# --- CORE DATA LOGIC (ROBUST VERSION) ---

def load_data():
    """Fetches data and ensures ALL required columns exist with correct types."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0).dropna(how='all')
        
        # 1. Force Creation of Missing Columns (Self-Repair Schema)
        expected_cols = [
            "Date", "Date_Received", "Date_Sent_To_PT", "Date_Back_From_PT", "Date_Client_Pickup",
            "Completed", "Invoiced", "Client_Name", "Client_Contact", "Service_Type", "Notes", 
            "Location", "Place_Received", "Quote_Amount", "Technician", "Category", 
            "Photo_Link", "OneDrive_Link"
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = pd.NA

        # 2. Strict Type Enforcement (Prevents StreamlitAPIException)
        # Dates
        date_cols = ["Date", "Date_Received", "Date_Sent_To_PT", "Date_Back_From_PT", "Date_Client_Pickup"]
        for c in date_cols:
            df[c] = pd.to_datetime(df[c], errors='coerce')
            
        # Booleans
        for c in ["Completed", "Invoiced"]:
            df[c] = df[c].fillna(False).astype(bool)
            
        # Strings (Everything else)
        str_cols = [c for c in df.columns if c not in date_cols and c not in ["Completed", "Invoiced"]]
        for c in str_cols:
            df[c] = df[c].astype(str).replace("nan", "").replace("None", "").replace("<NA>", "")
            
        return df
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

def sync_data(force_reload=False):
    """Writes the current Local State to Google Sheets, then reloads."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = st.session_state["master_df"]
    # Ensure Dates are converted to string for storage
    save_df = df.copy()
    for col in save_df.select_dtypes(include=['datetime64']).columns:
        save_df[col] = save_df[col].dt.strftime('%Y-%m-%d').replace("NaT", "")
        
    conn.update(worksheet="Sheet1", data=save_df)
    st.cache_data.clear()
    
    if force_reload:
        st.session_state["master_df"] = load_data()
        st.session_state["unsaved_changes"] = False
        st.toast("Saved & Synced!", icon="✅")
        st.rerun()

# --- INITIALIZATION ---
if "master_df" not in st.session_state:
    st.session_state["master_df"] = load_data()
    st.session_state["unsaved_changes"] = False

if "selected_idx" not in st.session_state:
    st.session_state["selected_idx"] = None

def render_category_tab(category_name, sub_services=None):
    df = st.session_state["master_df"]
    
    if "Category" not in df.columns: return
    category_df = df[df["Category"] == category_name]

    # --- ADD NEW (INSTANT SAVE) ---
    with st.expander(f"➕ Add New {category_name}", expanded=False):
        with st.form(f"add_form_{category_name}", clear_on_submit=True):
            input_data = {"Category": category_name}
            
            if category_name == "Transformer Servicing":
                c1, c2 = st.columns(2)
                with c1: input_data["Date_Received"] = st.date_input("Date Received", datetime.now())
                with c1: input_data["Place_Received"] = st.text_input("Place Received")
                with c1: input_data["Quote_Amount"] = st.text_input("Quote Amount (R)")
                with c2: input_data["Date_Sent_To_PT"] = st.date_input("Date Sent to PT", None)
                with c2: input_data["Date_Back_From_PT"] = st.date_input("Date Back from PT", None)
                with c2: input_data["Date_Client_Pickup"] = st.date_input("Date Client Pickup", None)
            else:
                c1, c2 = st.columns(2)
                with c1: input_data["Date"] = st.date_input("Date", datetime.now())
                with c1: input_data["Technician"] = st.text_input("Technician")
                input_data["Location"] = st.text_input("Location")

            input_data["Client_Name"] = st.text_input("Client Name")
            input_data["Client_Contact"] = st.text_input("Client Contact")
            input_data["Service_Type"] = st.selectbox("Work Required", sub_services or [category_name], index=None)
            input_data["Notes"] = st.text_area("Notes")
            input_data["OneDrive_Link"] = st.text_input("OneDrive Link")
            up_file = st.file_uploader("Upload File")
            input_data["Completed"] = False; input_data["Invoiced"] = False

            if st.form_submit_button("💾 Save New Job"):
                if up_file:
                    ext = up_file.name.split('.')[-1]
                    link = upload_to_drive(up_file, f"{category_name}_{datetime.now().strftime('%M%S')}.{ext}")
                    input_data["Photo_Link"] = link or ""
                
                # Append to Local & Sync
                new_row = pd.DataFrame([input_data])
                # Ensure new row has compatible types
                st.session_state["master_df"] = pd.concat([st.session_state["master_df"], new_row], ignore_index=True)
                with st.spinner("Saving..."):
                    sync_data(force_reload=True)

    # --- SEARCH ---
    st.divider()
    search = st.text_input(f"🔍 Search {category_name}", key=f"s_{category_name}")
    if not category_df.empty and search:
        mask = category_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        category_df = category_df[mask]

    # --- TABLE CONFIG ---
    if category_name == "Transformer Servicing":
        cols_order = ["Date_Received", "Client_Name", "Client_Contact", "Place_Received", "Service_Type", "Notes", "Quote_Amount", "Date_Sent_To_PT", "Date_Back_From_PT", "Date_Client_Pickup", "WA_Link", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    else:
        # Technician Removed from here as requested
        cols_order = ["Date", "Client_Name", "Client_Contact", "Location", "Service_Type", "Notes", "WA_Link", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    
    col_config = {
        "Select": st.column_config.CheckboxColumn("Edit", width="small", default=False),
        "WA_Link": st.column_config.LinkColumn("Chat", display_text="WhatsApp"),
        "Photo_Link": st.column_config.LinkColumn("File", display_text="Open"),
        "OneDrive_Link": st.column_config.LinkColumn("Drive", width="medium"),
        "Completed": st.column_config.CheckboxColumn("Done"),
        "Invoiced": st.column_config.CheckboxColumn("Inv"),
        # Dates
        "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "Date_Received": st.column_config.DateColumn("Recv", format="YYYY-MM-DD"),
        "Date_Sent_To_PT": st.column_config.DateColumn("Sent PT", format="YYYY-MM-DD"),
        "Date_Back_From_PT": st.column_config.DateColumn("Back PT", format="YYYY-MM-DD"),
        "Date_Client_Pickup": st.column_config.DateColumn("Pickup", format="YYYY-MM-DD"),
        # Text
        "Service_Type": st.column_config.SelectboxColumn("Service", options=sub_services or []),
        "Notes": st.column_config.TextColumn("Notes", width="large")
    }

    def render_table(sub_df, title, key_suf):
        if sub_df.empty:
            st.info(f"No {title} found."); return
        
        st.subheader(title)
        
        # Prepare View
        df_show = sub_df.copy()
        df_show.insert(0, "Select", False)
        if st.session_state["selected_idx"] in df_show.index:
            df_show.at[st.session_state["selected_idx"], "Select"] = True

        if "Client_Contact" in df_show.columns:
            df_show["WA_Link"] = df_show["Client_Contact"].apply(clean_phone_for_whatsapp)

        final_cols = ["Select"] + [c for c in cols_order if c in df_show.columns]
        
        # RENDER EDITOR
        edited = st.data_editor(
            df_show[final_cols], 
            use_container_width=True, 
            hide_index=True,
            column_config=col_config,
            disabled=["WA_Link", "Photo_Link"],
            key=f"ed_{category_name}_{key_suf}"
        )

        # UPDATE LOCAL STATE
        data_cols = [c for c in final_cols if c not in ["Select", "WA_Link", "Photo_Link"]]
        
        # Comparison logic: Convert both to str to avoid type issues (Naive vs Aware datetimes)
        if not edited[data_cols].astype(str).equals(df_show[data_cols].astype(str)):
            # Safe Update
            st.session_state["master_df"].loc[edited.index, data_cols] = edited[data_cols]
            st.session_state["unsaved_changes"] = True
            st.rerun()

        # Handle Select
        sel = edited[edited["Select"] == True]
        if not sel.empty:
            if sel.index[0] != st.session_state["selected_idx"]:
                st.session_state["selected_idx"] = sel.index[0]
                st.rerun()
        elif st.session_state["selected_idx"] in edited.index and not edited.at[st.session_state["selected_idx"], "Select"]:
            st.session_state["selected_idx"] = None
            st.rerun()

    active = category_df[~category_df["Completed"]]
    old = category_df[category_df["Completed"]]
    render_table(active, "⚡ Current Jobs", "act")
    st.divider()
    render_table(old, "✅ Old Jobs", "old")

    # --- EDIT FORM ---
    sel_idx = st.session_state["selected_idx"]
    if sel_idx is not None and sel_idx in st.session_state["master_df"].index:
        row = st.session_state["master_df"].loc[sel_idx]
        
        if row.get("Category") == category_name:
            st.divider()
            c_h, c_b = st.columns([2, 1])
            c_h.markdown(f"### ✏️ Editing: {row.get('Client_Name', 'Job')}")
            
            c_b.download_button("📄 Download Job Card", create_job_card(row.to_dict()), f"Job_{sel_idx}.pdf", "application/pdf", key=f"dl_pdf_{category_name}_{sel_idx}")

            with st.form(f"edit_{sel_idx}"):
                edit_d = row.to_dict()
                if category_name == "Transformer Servicing":
                    c1, c2 = st.columns(2)
                    edit_d["Date_Received"] = c1.date_input("Recv Date", parse_date_safe(row.get("Date_Received")))
                    edit_d["Place_Received"] = c1.text_input("Place", row.get("Place_Received"))
                    edit_d["Date_Sent_To_PT"] = c2.date_input("Sent PT", parse_date_safe(row.get("Date_Sent_To_PT")))
                    edit_d["Date_Back_From_PT"] = c2.date_input("Back PT", parse_date_safe(row.get("Date_Back_From_PT")))
                else:
                    c1, c2 = st.columns(2)
                    edit_d["Date"] = c1.date_input("Date", parse_date_safe(row.get("Date")))
                    edit_d["Technician"] = c2.text_input("Technician", row.get("Technician"))
                
                edit_d["Notes"] = st.text_area("Notes", row.get("Notes"))
                up_new = st.file_uploader("Upload New File")
                
                if st.form_submit_button("💾 Save Changes"):
                    if up_new:
                        ext = up_new.name.split('.')[-1]
                        edit_d["Photo_Link"] = upload_to_drive(up_new, f"Update_{sel_idx}.{ext}")
                    
                    for k, v in edit_d.items():
                        # Keep it as datetime in session state
                        if isinstance(v, (datetime, pd.Timestamp)): 
                            st.session_state["master_df"].at[sel_idx, k] = v
                        else:
                            st.session_state["master_df"].at[sel_idx, k] = v
                    
                    with st.spinner("Saving..."):
                        sync_data(force_reload=True)

                if st.form_submit_button("🗑️ Delete"):
                    st.session_state["master_df"] = st.session_state["master_df"].drop(sel_idx).reset_index(drop=True)
                    st.session_state["selected_idx"] = None
                    with st.spinner("Deleting..."):
                        sync_data(force_reload=True)

# --- RENDER NOTES TAB ---
def render_notes_tab():
    df = st.session_state["master_df"]
    notes_df = df[df["Category"] == "General Note"] if "Category" in df.columns else pd.DataFrame()

    with st.expander("➕ Add New Note", expanded=False):
        with st.form("add_note_form", clear_on_submit=True):
            note_date = st.date_input("Date", datetime.now())
            note_content = st.text_area("Note Content")
            note_file = st.file_uploader("📎 Attach File (Optional)")
            
            if st.form_submit_button("💾 Save New Note"):
                new_note = {"Date": note_date, "Category": "General Note", "Notes": note_content}
                if note_file:
                    ext = note_file.name.split('.')[-1]
                    link = upload_to_drive(note_file, f"Note_{datetime.now().strftime('%M%S')}.{ext}")
                    new_note["Photo_Link"] = link or ""
                
                st.session_state["master_df"] = pd.concat([st.session_state["master_df"], pd.DataFrame([new_note])], ignore_index=True)
                with st.spinner("Saving Note..."):
                    sync_data(force_reload=True)

    st.divider()
    st.subheader("📝 My Notes")

    if notes_df.empty:
        st.info("No notes found.")
        return

    df_show = notes_df.copy()
    df_show.insert(0, "Select", False)
    if st.session_state["selected_idx"] in df_show.index:
        df_show.at[st.session_state["selected_idx"], "Select"] = True

    cols_order = ["Date", "Notes", "Photo_Link"]
    final_cols = ["Select"] + [c for c in cols_order if c in df_show.columns]

    col_config = {
        "Select": st.column_config.CheckboxColumn("Edit", width="small", default=False),
        "Photo_Link": st.column_config.LinkColumn("File", display_text="Open"),
        "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "Notes": st.column_config.TextColumn("Content", width="large")
    }

    edited = st.data_editor(
        df_show[final_cols], 
        use_container_width=True, 
        hide_index=True,
        column_config=col_config,
        disabled=["Photo_Link"],
        key="editor_notes"
    )

    data_cols = [c for c in final_cols if c not in ["Select", "Photo_Link"]]
    if not edited[data_cols].astype(str).equals(df_show[data_cols].astype(str)):
        st.session_state["master_df"].loc[edited.index, data_cols] = edited[data_cols]
        st.session_state["unsaved_changes"] = True
        st.rerun()

    sel = edited[edited["Select"] == True]
    if not sel.empty:
        if sel.index[0] != st.session_state["selected_idx"]:
            st.session_state["selected_idx"] = sel.index[0]
            st.rerun()
    elif st.session_state["selected_idx"] in edited.index and not edited.at[st.session_state["selected_idx"], "Select"]:
        st.session_state["selected_idx"] = None
        st.rerun()

    sel_idx = st.session_state["selected_idx"]
    if sel_idx is not None and sel_idx in st.session_state["master_df"].index:
        row = st.session_state["master_df"].loc[sel_idx]
        if row.get("Category") == "General Note":
            st.divider()
            st.markdown(f"### ✏️ Editing Note")
            with st.form(f"edit_note_{sel_idx}"):
                edit_d = row.to_dict()
                edit_d["Date"] = st.date_input("Date", parse_date_safe(row.get("Date")))
                edit_d["Notes"] = st.text_area("Content", row.get("Notes"))
                curr_file = row.get("Photo_Link", "")
                if curr_file and len(str(curr_file)) > 5: st.caption(f"Current File: [View]({curr_file})")
                up_new = st.file_uploader("Replace File")

                c_save, c_del = st.columns([1, 1])
                with c_save:
                    if st.form_submit_button("💾 Save Changes"):
                        if up_new:
                            ext = up_new.name.split('.')[-1]
                            edit_d["Photo_Link"] = upload_to_drive(up_new, f"Update_Note_{sel_idx}.{ext}")
                        for k, v in edit_d.items():
                            if isinstance(v, (datetime, pd.Timestamp)): 
                                st.session_state["master_df"].at[sel_idx, k] = v
                            else:
                                st.session_state["master_df"].at[sel_idx, k] = v
                        with st.spinner("Saving..."): sync_data(force_reload=True)
                with c_del:
                    if st.form_submit_button("🗑️ Delete Note"):
                        st.session_state["master_df"] = st.session_state["master_df"].drop(sel_idx).reset_index(drop=True)
                        st.session_state["selected_idx"] = None
                        with st.spinner("Deleting..."): sync_data(force_reload=True)

# --- MAIN ---
def main():
    c1, c2 = st.columns([3, 1])
    c1.title("⚡ UELCO-MANAGER")
    
    if st.session_state["unsaved_changes"]:
        status = '<div class="status-box unsaved">⚠️ Unsaved Changes - Click Sync</div>'
        btn_label = "💾 Save & Sync"
    else:
        status = '<div class="status-box saved">✅ All Saved</div>'
        btn_label = "🔄 Sync / Refresh"
        
    c2.markdown(status, unsafe_allow_html=True)
    if c2.button(btn_label, type="primary"):
        with st.spinner("Syncing data..."):
            sync_data(force_reload=True)

    st.markdown(f'<a href="{ONEDRIVE_URL}" target="_blank" class="header-link">📂 Open OneDrive</a>', unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs(["💰 Sales", "⚡ Transformer Servicing", "🔌 Fault Finding", "📝 Notes"])
    
    with t1: render_category_tab("Sales", ["Order", "Order + Delivery", "Order + Installation", "Quoted", "To Quote"])
    with t2: render_category_tab("Transformer Servicing", ["Oil Change", "Gasket Replacement", "General Service", "Testing", "Quoted", "To Quote"])
    with t3: render_category_tab("Fault Finding", ["Thumping/Locating", "Jointing", "Quoted", "To Quote"])
    
    with t4: render_notes_tab()

if __name__ == "__main__":
    main()
