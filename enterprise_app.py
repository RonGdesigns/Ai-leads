import streamlit as st
import requests
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import google.generativeai as genai
import os
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import sqlite3

# --- 0. PAGE CONFIGURATION & CUSTOM CSS ---
st.set_page_config(page_title="Outbound AI | Enterprise CRM", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white; border-radius: 8px; border: none; font-weight: bold; padding: 0.5rem 1rem; transition: all 0.3s ease;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(75, 108, 183, 0.4); color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; padding-top: 10px; padding-bottom: 10px; }
    input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. SQLITE DATABASE ENGINE ---
DB_FILE = "outbound_crm.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (name TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_name TEXT, Name TEXT, Rating TEXT, Reviews INTEGER, 
                  Website TEXT, Email TEXT, Instagram TEXT, Facebook TEXT, Twitter TEXT, Phone TEXT, Address TEXT, 
                  Maps_Link TEXT, SSL TEXT, Mobile TEXT, Pixels TEXT, Pitch_SSL BOOLEAN, Pitch_Mobile BOOLEAN, 
                  Pitch_Pixels BOOLEAN, Drafted_Email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (date_sent TEXT, business_name TEXT, email_sent_to TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bg_status (id INTEGER PRIMARY KEY, is_running BOOLEAN, total INTEGER, sent INTEGER, errors INTEGER)''')
    c.execute("INSERT OR IGNORE INTO campaigns (name) VALUES ('Default Campaign')")
    c.execute("INSERT OR IGNORE INTO bg_status (id, is_running, total, sent, errors) VALUES (1, 0, 0, 0, 0)")
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return res[0] if res else default

def save_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def log_campaign(business_name, email_address):
    conn = sqlite3.connect(DB_FILE)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO logs (date_sent, business_name, email_sent_to) VALUES (?, ?, ?)", (timestamp, business_name, email_address))
    conn.commit()
    conn.close()

def save_lead_to_db(campaign, lead_dict):
    conn = sqlite3.connect(DB_FILE)
    cols = ", ".join(lead_dict.keys())
    places = ", ".join(["?"] * len(lead_dict))
    sql = f"INSERT INTO leads (campaign_name, {cols}) VALUES (?, {places})"
    conn.execute(sql, (campaign, *lead_dict.values()))
    conn.commit()
    conn.close()

def load_campaign_leads(campaign_name):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM leads WHERE campaign_name=?", conn, params=(campaign_name,))
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id', 'campaign_name'])
        for col in ['Pitch_SSL', 'Pitch_Mobile', 'Pitch_Pixels']:
            if col in df.columns: df[col] = df[col].astype(bool)
        df.columns = df.columns.str.replace('_', ' ')
    return df

def update_lead_draft(campaign, email, draft_text):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE leads SET Drafted_Email=? WHERE campaign_name=? AND Email=?", (draft_text, campaign, email))
    conn.commit()
    conn.close()

# --- 2. BACKGROUND WORKER & API LOGIC ---
def background_email_worker(targets, sender, password, smtp_server, smtp_port, delay, campaign_name):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE bg_status SET is_running=1, total=?, sent=0, errors=0 WHERE id=1", (len(targets),))
    conn.commit()
    sent_count = 0
    err_count = 0
    for target in targets:
        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = target['Email']
            msg['Subject'] = target['Subject']
            msg.attach(MIMEText(target['Body'], 'plain'))
            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            t_conn = sqlite3.connect(DB_FILE)
            t_conn.execute("INSERT INTO logs (date_sent, business_name, email_sent_to) VALUES (?, ?, ?)", (time.strftime("%Y-%m-%d %H:%M:%S"), target['Name'], target['Email']))
            t_conn.execute("UPDATE leads SET Drafted_Email='✅ SENT' WHERE campaign_name=? AND Email=?", (campaign_name, target['Email']))
            sent_count += 1
            t_conn.execute("UPDATE bg_status SET sent=? WHERE id=1", (sent_count,))
            t_conn.commit()
            t_conn.close()
        except:
            err_count += 1
            t_conn = sqlite3.connect(DB_FILE)
            t_conn.execute("UPDATE bg_status SET errors=? WHERE id=1", (err_count,))
            t_conn.commit()
            t_conn.close()
        time.sleep(delay)
    conn.execute("UPDATE bg_status SET is_running=0 WHERE id=1")
    conn.commit()
    conn.close()

def check_background_status():
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT is_running, total, sent, errors FROM bg_status WHERE id=1").fetchone()
    conn.close()
    return {"is_running": bool(res[0]), "total": res[1], "sent": res[2], "errors": res[3]}

@st.cache_data(ttl=86400, show_spinner=False)
def extract_and_audit(url):
    if not url or url == 'No Website Found': return {"Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "N/A", "Mobile": "N/A", "Pixels": "N/A"}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        html_text = response.text
        soup = BeautifulSoup(html_text, 'html.parser')
        emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html_text))
        ig_links = set([a['href'] for a in soup.find_all('a', href=True) if 'instagram.com' in a['href']])
        fb_links = set([a['href'] for a in soup.find_all('a', href=True) if 'facebook.com' in a['href']])
        tw_links = set([a['href'] for a in soup.find_all('a', href=True) if 'twitter.com' in a['href'] or 'x.com' in a['href']])
        has_ssl = "Pass" if url.startswith("https") else "Fail"
        has_mobile = "Pass" if soup.find("meta", attrs={"name": "viewport"}) else "Fail"
        has_pixels = "Pass" if re.search(r'gtm\.js|analytics\.js|gtag|fbevents\.js', html_text, re.I) else "Fail"
        return {"Email": list(emails)[0] if emails else "N/A", "Instagram": list(ig_links)[0] if ig_links else "N/A", "Facebook": list(fb_links)[0] if fb_links else "N/A", "Twitter": list(tw_links)[0] if tw_links else "N/A", "SSL": has_ssl, "Mobile": has_mobile, "Pixels": has_pixels}
    except: return {"Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "Error", "Mobile": "Error", "Pixels": "Error"}

def draft_dynamic_email(business_name, rating, audit_data, pitch_ssl, pitch_mobile, pitch_pixels, profession, offer, proof, cta, name, ai_api_key):
    if not ai_api_key: return "⚠️ Please enter your Gemini API Key."
    try:
        genai.configure(api_key=ai_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"You are a professional {profession}. Write a short, friendly cold email to the owner of {business_name}. Rating: {rating}. Audit: SSL Secure: {audit_data['SSL']}, Mobile Optimized: {audit_data['Mobile']}, Pixels: {audit_data['Pixels']}. Instructions - Pitch SSL: {pitch_ssl}, Pitch Mobile: {pitch_mobile}, Pitch Pixels: {pitch_pixels}. If True, gently mention it as a problem. If all False, congratulate them on a solid business and pivot to offer. Pitch: {offer}. Trust: {proof}. CTA: {cta}. Keep it under 150 words. Sign off as {name}."
        return model.generate_content(prompt).text
    except Exception as e: return f"⚠️ AI Error: {e}"

def send_email(sender, password, recipient, subject, body, smtp_host, smtp_port):
    if not sender or not password: return False, "Missing Credentials."
    if not recipient or recipient == "N/A": return False, "No valid email."
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e: return False, f"SMTP Error: {e}"

# --- 3. SESSION STATE ---
if 'master_dataframe' not in st.session_state: st.session_state.master_dataframe = None
if 'current_campaign' not in st.session_state: st.session_state.current_campaign = None

# --- 4. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=40)
    st.title("⚙️ Engine Room")
    st.success("🔒 **Privacy First & 100% Local**\n\nYour data is saved securely on your local hard drive. Nothing is sent to a central server.")

    with st.expander("📖 Step-by-Step Setup Guide", expanded=False):
        st.markdown("""
        ### 1. Google Places API (For Scraper)
        * **Go here:** [Google Cloud Console](https://console.cloud.google.com/)
        * **New Project:** Look at the top-left (next to the 'Google Cloud' logo). Click the dropdown menu and select **"New Project"**.
        * **Enable API:** Search for "Places API (New)" in the search bar and click **Enable**.
        * **Get Key:** Go to "APIs & Services" > "Credentials" > "Create Credentials" > **API Key**.

        ### 2. Gemini API Key (For AI)
        * **Go here:** [Google AI Studio](https://aistudio.google.com/app/apikey)
        * Click **"Create API key in new project"**.
        * Copy that key and paste it into the AI Engine section below.

        ### 3. Email App Password
        * Go to your Google Account **Security Settings**.
        * Turn on **2-Step Verification**.
        * Search for **"App Passwords"** at the top.
        * Create one named "Outbound AI" and use the 16-character code provided.
        """)

    st.subheader("📁 Campaigns")
    conn = sqlite3.connect(DB_FILE); camp_list = [row[0] for row in conn.execute("SELECT name FROM campaigns").fetchall()]; conn.close()
    active_campaign = st.selectbox("Active:", camp_list)
    new_camp = st.text_input("New Campaign:", placeholder="HVAC Detroit")
    if st.button("➕ Add") and new_camp:
        conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR IGNORE INTO campaigns (name) VALUES (?)", (new_camp,)); conn.commit(); conn.close()
        st.rerun()

    if st.session_state.current_campaign != active_campaign:
        st.session_state.current_campaign = active_campaign
        df = load_campaign_leads(active_campaign)
        st.session_state.master_dataframe = df if not df.empty else None

    with st.expander("🔑 API & SMTP Setup"):
        api_key = st.text_input("Google Places Key:", type="password", value=get_setting("google_key"))
        gemini_key = st.text_input("Gemini API Key:", type="password", value=get_setting("gemini_key"))
        smtp_server = st.text_input("SMTP Server:", value=get_setting("smtp_server", "smtp.gmail.com"))
        smtp_port = st.text_input("SMTP Port:", value=get_setting("smtp_port", "587"))
        imap_server = st.text_input("IMAP Server:", value=get_setting("imap_server", "imap.gmail.com"))
        sender_email = st.text_input("Your Email:", value=get_setting("sender_email"))
        app_password = st.text_input("App Password:", type="password", value=get_setting("app_password"))
        if st.button("💾 Save All Settings", use_container_width=True):
            save_setting("google_key", api_key); save_setting("gemini_key", gemini_key)
            save_setting("smtp_server", smtp_server); save_setting("smtp_port", smtp_port)
            save_setting("imap_server", imap_server); save_setting("sender_email", sender_email); save_setting("app_password", app_password)
            st.toast("✅ Infrastructure Saved!")

# --- 5. MAIN HEADER ---
st.markdown("<h1 style='text-align: center;'>🚀 Outbound AI</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: gray;'>Workspace: <b>{st.session_state.current_campaign}</b></p>", unsafe_allow_html=True)

# --- 6. TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🔍 1. Hunt", "📊 2. Analyze", "🚀 3. Pitch & Send", "📜 4. Logs & Replies"])

# --- TAB 1: HUNT ---
with tab1:
    col1, col2 = st.columns([3, 1])
    niche = col1.text_input("Niche / Industry", placeholder="Roofers")
    lead_dropdown = col2.selectbox("Max Leads", ["5", "10", "20", "50", "100", "Type custom..."], index=2)
    max_results = st.number_input("Count:", min_value=1, value=15) if lead_dropdown == "Type custom..." else int(lead_dropdown)
    col3, col4, col5 = st.columns([2, 2, 1])
    is_international = col5.checkbox("🌍 Int'l")
    city = col3.text_input("City (Optional)", placeholder="Detroit")
    region = col4.text_input("Country" if is_international else "State", placeholder="MI")
        
    if st.button("🚀 Launch Scraper", use_container_width=True):
        if not api_key or not niche or not region: st.warning("⚠️ Fill out API Key, Niche and State/Country.")
        else:
            search_query = f"{niche} in {city}, {region}" if city else f"{niche} in {region}"
            with st.status(f"🚀 Scraping...", expanded=True) as status:
                url = 'https://places.googleapis.com/v1/places:searchText'
                headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.businessStatus,nextPageToken'}
                all_leads = []
                page_token = ""
                while len(all_leads) < max_results:
                    payload = {'textQuery': search_query, 'pageSize': 20}
                    if page_token: payload['pageToken'] = page_token
                    res = requests.post(url, headers=headers, json=payload); data = res.json()
                    for place in data.get('places', []):
                        if place.get('businessStatus') == 'OPERATIONAL':
                            web = place.get('websiteUri', 'No Website Found'); audit = extract_and_audit(web) 
                            lead = {"Name": place.get('displayName', {}).get('text', 'N/A'), "Rating": str(place.get('rating', 'N/A')), "Reviews": int(place.get('userRatingCount', 0)), "Website": web, "Email": audit["Email"], "Instagram": audit["Instagram"], "Facebook": audit["Facebook"], "Twitter": audit["Twitter"], "Phone": place.get('nationalPhoneNumber', 'N/A'), "Address": place.get('formattedAddress', 'N/A'), "Maps_Link": place.get('googleMapsUri', 'N/A'), "SSL": audit["SSL"], "Mobile": audit["Mobile"], "Pixels": audit["Pixels"], "Pitch_SSL": False, "Pitch_Mobile": False, "Pitch_Pixels": False, "Drafted_Email": ""}
                            save_lead_to_db(st.session_state.current_campaign, lead); all_leads.append(lead)
                            if len(all_leads) >= max_results: break
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                    time.sleep(1)
                st.session_state.master_dataframe = load_campaign_leads(st.session_state.current_campaign)
                status.update(label=f"✅ Saved {len(all_leads)} leads.", state="complete")

# --- TAB 2: ANALYZE ---
with tab2:
    if st.session_state.master_dataframe is not None:
        df = st.session_state.master_dataframe
        st.markdown("### 📈 Stats")
        c1, c2, c3 = st.columns(3); c1.metric("Leads", len(df)); c2.metric("SSL Fail", len(df[df['SSL'] == 'Fail'])); c3.metric("Pixel Fail", len(df[df['Pixels'] == 'Fail']))
        f_opt = st.radio("Filter:", ["All", "Missing SSL", "Missing Pixels", "No Website"], horizontal=True)
        disp = df.copy()
        if f_opt == "Missing SSL": disp = disp[disp['SSL'] == 'Fail']
        elif f_opt == "Missing Pixels": disp = disp[disp['Pixels'] == 'Fail']
        elif f_opt == "No Website": disp = disp[disp['Website'] == 'No Website Found']
        edit = st.data_editor(disp[[c for c in disp.columns if c != 'Drafted Email']], use_container_width=True, hide_index=True)
        conn = sqlite3.connect(DB_FILE)
        for _, row in edit.iterrows():
            st.session_state.master_dataframe.loc[st.session_state.master_dataframe['Name'] == row['Name'], edit.columns] = row.values
            conn.execute("UPDATE leads SET Pitch_SSL=?, Pitch_Mobile=?, Pitch_Pixels=? WHERE campaign_name=? AND Name=?", (int(row['Pitch SSL']), int(row['Pitch Mobile']), int(row['Pitch Pixels']), st.session_state.current_campaign, row['Name']))
        conn.commit(); conn.close()
    else: st.info("👈 Run the scraper in Step 1.")

# --- TAB 3: PITCH & SEND ---
with tab3:
    if st.session_state.master_dataframe is not None:
        with st.container(border=True):
            col_a, col_b = st.columns(2)
            u_prof = col_a.text_input("Profession:")
            y_name = col_a.text_input("Your Name:")
            s_proof = col_b.text_input("Past Work:")
            cta = col_b.text_input("CTA:", value="Chat?")
            offer = st.text_area("Offer:")
        
        target = st.selectbox("Select Target:", st.session_state.master_dataframe['Name'].tolist())
        idx = st.session_state.master_dataframe.index[st.session_state.master_dataframe['Name'] == target].tolist()[0]
        info = st.session_state.master_dataframe.iloc[idx]; draft = info['Drafted Email']

        c_g, c_s = st.columns(2)
        if c_g.button("🤖 Generate Pitch", use_container_width=True):
            if not u_prof or not y_name: st.warning("⚠️ Setup Persona.")
            else:
                with st.spinner("AI Writing..."):
                    d = draft_dynamic_email(info['Name'], info['Rating'], {"SSL": info['SSL'], "Mobile": info['Mobile'], "Pixels": info['Pixels']}, info['Pitch SSL'], info['Pitch Mobile'], info['Pitch Pixels'], u_prof, offer, s_proof, cta, y_name, gemini_key)
                    update_lead_draft(st.session_state.current_campaign, info['Email'], d); st.session_state.master_dataframe.at[idx, 'Drafted Email'] = d; st.rerun()
        if c_s.button("🚀 Send Now", type="primary", use_container_width=True):
            if not draft or draft in ["✅ SENT", "🔥 REPLIED"]: st.error("⚠️ Need fresh pitch.")
            else:
                success, msg = send_email(sender_email, app_password, info['Email'], f"Question: {info['Name']}", draft, smtp_server, smtp_port)
                if success: update_lead_draft(st.session_state.current_campaign, info['Email'], "✅ SENT"); st.rerun()
                else: st.error(msg)
        if draft and draft not in ["✅ SENT", "🔥 REPLIED"]:
            ed = st.text_area("Edit:", value=draft, height=200)
            if ed != draft: update_lead_draft(st.session_state.current_campaign, info['Email'], ed)
        
        st.divider(); st.markdown("### ⚡ Bulk Sending")
        bg = check_background_status()
        if bg["is_running"]: st.info(f"⚙️ Sending: {bg['sent']} / {bg['total']}..."); st.progress(bg['sent']/bg['total'])
        delay = st.slider("Delay (s):", 1, 30, 3)
        b1, b2 = st.columns(2)
        if b1.button("🤖 Bulk Generate", use_container_width=True, disabled=bg["is_running"]):
            for idx, row in st.session_state.master_dataframe.iterrows():
                if not row['Drafted Email'] or row['Drafted Email'] not in ["✅ SENT", "🔥 REPLIED"]:
                    d = draft_dynamic_email(row['Name'], row['Rating'], {"SSL": row['SSL'], "Mobile": row['Mobile'], "Pixels": row['Pixels']}, row['Pitch SSL'], row['Pitch Mobile'], row['Pitch Pixels'], u_prof, offer, s_proof, cta, y_name, gemini_key)
                    update_lead_draft(st.session_state.current_campaign, row['Email'], d); st.session_state.master_dataframe.at[idx, 'Drafted Email'] = d
            st.rerun()
        if b2.button("🚀 Mass Send", type="primary", use_container_width=True, disabled=bg["is_running"]):
            v = st.session_state.master_dataframe[(st.session_state.master_dataframe['Drafted Email'] != "") & (~st.session_state.master_dataframe['Drafted Email'].isin(["✅ SENT", "🔥 REPLIED"])) & (st.session_state.master_dataframe['Email'] != "N/A")]
            if v.empty: st.error("⚠️ No emails ready.")
            else:
                q = [{"Name": r['Name'], "Email": r['Email'], "Subject": f"Question: {r['Name']}", "Body": r['Drafted_Email']} for _, r in v.iterrows()]
                threading.Thread(target=background_email_worker, args=(q, sender_email, app_password, smtp_server, smtp_port, delay, st.session_state.current_campaign), daemon=True).start()
                st.rerun()

# --- TAB 4: LOGS & REPLIES ---
with tab4:
    l_c, r_c = st.columns([2, 1])
    with l_c:
        st.markdown("### 📜 Logs")
        conn = sqlite3.connect(DB_FILE); logs = pd.read_sql("SELECT * FROM logs", conn); conn.close()
        if not logs.empty: st.dataframe(logs, use_container_width=True, hide_index=True)
    with r_c:
        st.markdown("### 📥 Replies")
        if st.button("🔥 Scan for Replies", use_container_width=True):
            try:
                m = imaplib.IMAP4_SSL(imap_server); m.login(sender_email, app_password); m.select('inbox')
                conn = sqlite3.connect(DB_FILE); sent = [r[0] for r in conn.execute("SELECT email_sent_to FROM logs").fetchall()]
                found = 0
                for e in set(sent):
                    s, d = m.search(None, f'FROM "{e}"')
                    if s == 'OK' and d[0]: conn.execute("UPDATE leads SET Drafted_Email='🔥 REPLIED' WHERE Email=?", (e,)); found += 1
                conn.commit(); conn.close(); m.logout(); st.session_state.master_dataframe = load_campaign_leads(st.session_state.current_campaign); st.success(f"Found {found} replies!")
            except Exception as ex: st.error(ex)
