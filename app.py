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

# --- CORE DATA LOGIC ---

def load_data():
    """Fetches data from Google Sheets."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0).dropna(how='all')
        
        # Normalize
        for c in ["Date", "Date_Received", "Date_Sent_To_PT", "Date_Back_From_PT"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        for c in ["Completed", "Invoiced"]:
            if c in df.columns: df[c] = df[c].fillna(False).astype(bool)
        for c in ["Client_Name", "Client_Contact", "Service_Type", "Notes", "Location", "Place_Received", "Quote_Amount", "Technician", "Category", "Photo_Link", "OneDrive_Link"]:
            if c in df.columns: df[c] = df[c].fillna("").astype(str)
            
        return df
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

def sync_data(force_reload=False):
    """Writes the current Local State to Google Sheets, then reloads."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = st.session_state["master_df"]
    
    # 1. Write to GSheets
    conn.update(worksheet="Sheet1", data=df)
    
    # 2. Clear Cache & Reload
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
                
                # Append to Local
                new_row = pd.DataFrame([input_data])
                st.session_state["master_df"] = pd.concat([st.session_state["master_df"], new_row], ignore_index=True)
                
                # Push to Cloud IMMEDIATELY
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
        cols_order = ["Date_Received", "Client_Name", "Client_Contact", "Service_Type", "Notes", "Quote_Amount", "WA_Link", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    else:
        cols_order = ["Date", "Client_Name", "Client_Contact", "Service_Type", "Notes", "Location", "WA_Link", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    
    col_config = {
        "Select": st.column_config.CheckboxColumn("Edit", width="small", default=False),
        "WA_Link": st.column_config.LinkColumn("Chat", display_text="WhatsApp"),
        "Photo_Link": st.column_config.LinkColumn("File", display_text="Open"),
        # REMOVED display_text="Folder" so you can paste URLS
        "OneDrive_Link": st.column_config.LinkColumn("Drive", width="medium"),
        "Completed": st.column_config.CheckboxColumn("Done"),
        "Invoiced": st.column_config.CheckboxColumn("Inv"),
        "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "Date_Received": st.column_config.DateColumn("Recv", format="YYYY-MM-DD"),
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
            # Removed OneDrive_Link from disabled so it is editable
            disabled=["WA_Link", "Photo_Link"],
            key=f"ed_{category_name}_{key_suf}"
        )

        # UPDATE LOCAL STATE ONLY (Batched)
        data_cols = [c for c in final_cols if c not in ["Select", "WA_Link", "Photo_Link", "OneDrive_Link"]]
        
        # Check if data changed
        if not edited[data_cols].astype(str).equals(df_show[data_cols].astype(str)):
            # Safe assignment
            st.session_state["master_df"].loc[edited.index, data_cols] = edited[data_cols]
            st.session_state["unsaved_changes"] = True
            st.rerun()
            
        # Check if OneDrive Link changed specifically (since it's not in data_cols above for safety, let's catch it)
        if "OneDrive_Link" in edited.columns:
             if not edited["OneDrive_Link"].astype(str).equals(df_show["OneDrive_Link"].astype(str)):
                st.session_state["master_df"].loc[edited.index, "OneDrive_Link"] = edited["OneDrive_Link"]
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
                
                edit_d["Notes"] = st.text_area("Notes", row.get("Notes"))
                up_new = st.file_uploader("Upload New File")
                
                if st.form_submit_button("💾 Save Changes"):
                    if up_new:
                        ext = up_new.name.split('.')[-1]
                        edit_d["Photo_Link"] = upload_to_drive(up_new, f"Update_{sel_idx}.{ext}")
                    
                    for k, v in edit_d.items():
                        if isinstance(v, (datetime, pd.Timestamp)): v = v.strftime("%Y-%m-%d")
                        st.session_state["master_df"].at[sel_idx, k] = v
                    
                    with st.spinner("Saving..."):
                        sync_data(force_reload=True)

                if st.form_submit_button("🗑️ Delete"):
                    st.session_state["master_df"] = st.session_state["master_df"].drop(sel_idx).reset_index(drop=True)
                    st.session_state["selected_idx"] = None
                    with st.spinner("Deleting..."):
                        sync_data(force_reload=True)

# --- MAIN ---
def main():
    c1, c2 = st.columns([3, 1])
    c1.title("⚡ UELCO-MANAGER")
    
    # REFRESH / SYNC BUTTON
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

    t1, t2, t3, t4 = st.tabs(["💰 Sales", "⚡ Transformer", "🔌 Cables", "📝 Notes"])
    
    with t1: render_category_tab("Sales & Install", ["Order", "Order + Delivery", "Order + Installation", "Quoted", "To Quote"])
    with t2: render_category_tab("Transformer Servicing", ["Oil Change", "Gasket Replacement", "General Service", "Testing", "Quoted", "To Quote"])
    with t3: render_category_tab("Cable Faults", ["Thumping/Locating", "Jointing", "Quoted", "To Quote"])
    
    with t4:
        st.header("📝 Notes")
        with st.form("new_note"):
            txt = st.text_area("Note"); up = st.file_uploader("File")
            if st.form_submit_button("Pin Note"):
                d = {"Date": datetime.now(), "Category": "General Note", "Notes": txt}
                if up: d["Photo_Link"] = upload_to_drive(up, f"Note_{datetime.now()}.jpg")
                st.session_state["master_df"] = pd.concat([st.session_state["master_df"], pd.DataFrame([d])], ignore_index=True)
                with st.spinner("Saving Note..."):
                    sync_data(force_reload=True)
        
        st.divider()
        n_df = st.session_state["master_df"]
        n_df = n_df[n_df["Category"] == "General Note"] if "Category" in n_df.columns else pd.DataFrame()
        if not n_df.empty:
            st.data_editor(n_df[["Date", "Notes", "Photo_Link"]], hide_index=True, column_config={"Photo_Link": st.column_config.LinkColumn("File")})

if __name__ == "__main__":
    main()
