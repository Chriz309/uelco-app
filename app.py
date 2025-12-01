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

st.set_page_config(page_title="UELCO Mobile", layout="wide")

# --- CSS ---
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

def save_entry(conn, df, data, index=None, rerun=True):
    for k, v in data.items():
        if isinstance(v, (datetime, pd.Timestamp)): data[k] = v.strftime("%Y-%m-%d")
        if v is None: data[k] = ""
    if index is not None:
        for col, val in data.items(): df.at[index, col] = val
    else:
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    conn.update(worksheet="Sheet1", data=df)
    st.cache_data.clear()
    if rerun: st.toast("Saved!", icon='💾'); st.rerun()

def delete_entry(conn, df, index):
    df = df.drop(index).reset_index(drop=True)
    conn.update(worksheet="Sheet1", data=df)
    st.cache_data.clear()
    st.toast("Deleted!", icon='🗑️'); st.rerun()

def parse_date_safe(date_val):
    if pd.isnull(date_val) or date_val == "": return None
    try: return pd.to_datetime(date_val).date()
    except: return None

def render_category_tab(conn, full_df, category_name, sub_services=None):
    if "Category" in full_df.columns:
        category_df = full_df[full_df["Category"] == category_name]
    else:
        category_df = pd.DataFrame()

    # --- ADD NEW FORM ---
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

            if st.form_submit_button("💾 Save"):
                if up_file:
                    ext = up_file.name.split('.')[-1]
                    link = upload_to_drive(up_file, f"{category_name}_{datetime.now().strftime('%M%S')}.{ext}")
                    input_data["Photo_Link"] = link or ""
                save_entry(conn, full_df, input_data)

    # --- SEARCH & FILTER ---
    st.divider()
    search = st.text_input(f"🔍 Search {category_name}", key=f"s_{category_name}")
    if not category_df.empty and search:
        mask = category_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        category_df = category_df[mask]

    # --- TABLE CONFIG ---
    # FORCE Date columns to be present even if data is missing
    cols_order = []
    if category_name == "Transformer Servicing":
        cols_order = ["Date_Received", "Client_Name", "Client_Contact", "Service_Type", "Notes", "Quote_Amount", "WA_Link", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    else:
        cols_order = ["Date", "Client_Name", "Client_Contact", "Service_Type", "Notes", "Location", "WA_Link", "Photo_Link", "OneDrive_Link", "Completed", "Invoiced"]
    
    # Define columns to show (intersect with actual columns)
    valid_cols = [c for c in cols_order if c in category_df.columns or c == "WA_Link"]

    col_config = {
        "Select": st.column_config.CheckboxColumn("Edit", width="small", default=False),
        "WA_Link": st.column_config.LinkColumn("Chat", display_text="WhatsApp"),
        "Photo_Link": st.column_config.LinkColumn("File", display_text="Open"),
        "OneDrive_Link": st.column_config.LinkColumn("Drive", display_text="Folder"),
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
        
        # Prepare Display DF
        df_show = sub_df.copy()
        
        # Add Select Column (Stateful)
        df_show.insert(0, "Select", False)
        # If this row is currently selected in Session State, mark it True
        if st.session_state.get("selected_idx") in df_show.index:
            df_show.at[st.session_state["selected_idx"], "Select"] = True

        # Add WhatsApp
        if "Client_Contact" in df_show.columns:
            df_show["WA_Link"] = df_show["Client_Contact"].apply(clean_phone_for_whatsapp)

        # Reorder columns explicitly
        final_cols = ["Select"] + [c for c in cols_order if c in df_show.columns]
        
        edited = st.data_editor(
            df_show[final_cols], 
            use_container_width=True, 
            hide_index=True,
            column_config=col_config,
            disabled=["WA_Link", "Photo_Link", "OneDrive_Link"], # Allow Select to be edited
            key=f"ed_{category_name}_{key_suf}"
        )

        # LOGIC: Detect Changes
        # 1. Did Selection Change?
        sel_rows = edited[edited["Select"] == True]
        if not sel_rows.empty:
            new_sel = sel_rows.index[0]
            if new_sel != st.session_state.get("selected_idx"):
                st.session_state["selected_idx"] = new_sel
                st.rerun()
        elif st.session_state.get("selected_idx") in edited.index and edited.at[st.session_state["selected_idx"], "Select"] == False:
            # User unchecked the box
            st.session_state["selected_idx"] = None
            st.rerun()

        # 2. Did Data Change? (Ignore Select and Links)
        data_cols = [c for c in final_cols if c not in ["Select", "WA_Link", "Photo_Link", "OneDrive_Link"]]
        try:
            old_data = sub_df.loc[edited.index, data_cols]
            new_data = edited[data_cols]
            # Loose comparison (astype str) to avoid type mismatch refresh loops
            if not old_data.astype(str).equals(new_data.astype(str)):
                full_df.update(edited[data_cols + ["Completed", "Invoiced"]])
                conn.update(worksheet="Sheet1", data=full_df)
                st.cache_data.clear()
                st.toast("Saved!", icon="✅")
                st.rerun()
        except: pass

    # Render Active/Old
    active = category_df[~category_df["Completed"]]
    old = category_df[category_df["Completed"]]
    render_table(active, "⚡ Current Jobs", "act")
    st.divider()
    render_table(old, "✅ Old Jobs", "old")

    # --- EDIT FORM (Persistent) ---
    sel_idx = st.session_state.get("selected_idx")
    # Only show form if selected index belongs to THIS category
    if sel_idx is not None and sel_idx in category_df.index:
        row = full_df.loc[sel_idx]
        st.divider()
        c_h, c_b = st.columns([2, 1])
        c_h.markdown(f"### ✏️ Editing: {row.get('Client_Name', 'Job')}")
        c_b.download_button("📄 Download Job Card", create_job_card(row), f"Job_{sel_idx}.pdf", "application/pdf")

        with st.form(f"edit_{sel_idx}"):
            edit_d = row.to_dict()
            
            # Simplified Form (Focus on criticals that aren't in table)
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
                save_entry(conn, full_df, edit_d, sel_idx)

            if st.form_submit_button("🗑️ Delete"):
                st.session_state["selected_idx"] = None # Clear selection before delete
                delete_entry(conn, full_df, sel_idx)

# --- MAIN ---
def main():
    c1, c2 = st.columns([3, 1])
    c1.title("⚡ UELCO System")
    if c2.button("🔄 Refresh"): st.cache_data.clear(); st.rerun()
    st.markdown(f'<a href="{ONEDRIVE_URL}" target="_blank" class="header-link">📂 Open OneDrive</a>', unsafe_allow_html=True)

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=600).dropna(how='all')
        # Ensure Dates are datetime
        for c in ["Date", "Date_Received", "Date_Sent_To_PT", "Date_Back_From_PT"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        # Ensure Booleans
        for c in ["Completed", "Invoiced"]:
            if c in df.columns: df[c] = df[c].fillna(False).astype(bool)
        # Ensure Strings
        for c in ["Client_Name", "Client_Contact", "Service_Type", "Notes", "Location", "Place_Received", "Quote_Amount", "Technician"]:
            if c in df.columns: df[c] = df[c].fillna("").astype(str)
    except: st.error("Connection Error"); df = pd.DataFrame()

    t1, t2, t3, t4 = st.tabs(["💰 Sales", "⚡ Transformer", "🔌 Cables", "📝 Notes"])
    
    with t1: render_category_tab(conn, df, "Sales & Install", ["Order", "Order + Delivery", "Order + Installation", "Quoted", "To Quote"])
    with t2: render_category_tab(conn, df, "Transformer Servicing", ["Oil Change", "Gasket Replacement", "General Service", "Testing", "Quoted", "To Quote"])
    with t3: render_category_tab(conn, df, "Cable Faults", ["Thumping/Locating", "Jointing", "Quoted", "To Quote"])
    
    with t4:
        st.header("📝 Notes")
        with st.form("new_note"):
            txt = st.text_area("Note"); up = st.file_uploader("File")
            if st.form_submit_button("Pin"):
                d = {"Date": datetime.now(), "Category": "General Note", "Notes": txt}
                if up: d["Photo_Link"] = upload_to_drive(up, f"Note_{datetime.now()}.jpg")
                save_entry(conn, df, d)
        
        st.divider()
        n_df = df[df["Category"] == "General Note"] if "Category" in df.columns else pd.DataFrame()
        if not n_df.empty:
            st.data_editor(n_df[["Date", "Notes", "Photo_Link"]], hide_index=True, column_config={"Photo_Link": st.column_config.LinkColumn("File")})

if __name__ == "__main__":
    main()
