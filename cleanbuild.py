import os
import uuid
import hashlib
import json
import time
import re
import random
import threading
import smtplib
import imaplib
import sqlite3
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import requests
import pandas as pd
import aiohttp
from bs4 import BeautifulSoup
import google.generativeai as genai

# --- 0. PAGE CONFIGURATION & CUSTOM CSS ---
st.set_page_config(page_title="sortingsource | Enterprise Intelligence", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    /* 1. Global App Background & Typography */
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    h1, h2, h3, h4 {
        letter-spacing: -0.5px;
        font-weight: 700 !important;
    }
    
    /* 2. Frosted Glass Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(14, 17, 23, 0.6) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* 3. Premium Gradient Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #4b6cb7 0%, #182848 100%);
        color: white; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);
        font-weight: 600; padding: 0.6rem 1.2rem; 
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stButton>button:hover { 
        transform: translateY(-2px); 
        box-shadow: 0 6px 15px rgba(75, 108, 183, 0.5); 
        border: 1px solid rgba(255,255,255,0.3);
        color: white; 
    }
    
    /* 4. Glassmorphism Metric Cards */
    div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.02); 
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 20px; 
        border-radius: 12px; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(10px); 
        -webkit-backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px); 
        border: 1px solid rgba(75, 108, 183, 0.5);
        box-shadow: 0 10px 30px rgba(75, 108, 183, 0.15);
    }
    
    /* 5. Input Fields & Dropdowns (Glow Effects) */
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div, 
    div[data-baseweb="textarea"] > div {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    div[data-baseweb="input"] > div:focus-within, 
    div[data-baseweb="select"] > div:focus-within, 
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: #4b6cb7 !important;
        box-shadow: 0 0 10px rgba(75, 108, 183, 0.4) !important;
        background-color: rgba(255, 255, 255, 0.05) !important;
    }

    /* 6. Rounded Data Tables */
    [data-testid="stDataFrame"] > div {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* 7. Tab Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; white-space: pre-wrap; background-color: transparent; 
        border-radius: 4px 4px 0px 0px; padding-top: 10px; padding-bottom: 10px; 
        transition: color 0.3s ease;
    }
    .stTabs [aria-selected="true"] { 
        border-bottom-color: #4b6cb7 !important; 
        color: #4b6cb7 !important;
    }
    
    /* 8. Custom Native Scrollbars */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #4b6cb7; }
    
    /* 9. Clean Inputs (Hide Arrows) & Expander Polish */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    
    .streamlit-expanderHeader {
        background-color: rgba(255,255,255,0.02); 
        border-radius: 8px; 
        border: 1px solid rgba(255,255,255,0.05);
        transition: all 0.3s ease;
    }
    .streamlit-expanderHeader:hover {
        background-color: rgba(255,255,255,0.05);
    }
    </style>
    """, unsafe_allow_html=True)


# --- 0.5 ENTERPRISE LICENSING ENGINE ---
PRODUCT_ID = "OrrFSc94F9HJITilrZZcIg==" 
LICENSE_FILE = "license.dat"
SECRET_SALT = "OutboundAI_Enterprise_2024"

def get_hardware_id():
    """Grabs a unique identifier from the user's computer hardware."""
    return str(uuid.getnode())

def generate_license_hash(license_key, hw_id):
    """Creates an unbreakable hash binding the key to the hardware."""
    raw_string = f"{license_key}-{hw_id}-{SECRET_SALT}"
    return hashlib.sha256(raw_string.encode()).hexdigest()

def check_activation():
    """Checks if the software is activated. If not, halts the app and shows the login screen."""
    hw_id = get_hardware_id()
    
    # 1. Check if they already activated it previously
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            saved_data = json.load(f)
            
        saved_hash = saved_data.get("hash")
        saved_key = saved_data.get("key")
        
        # Verify the hardware hasn't changed (prevents copying the app to another PC)
        if saved_hash == generate_license_hash(saved_key, hw_id):
            return True # Let them into the CRM!
            
    # 2. If not activated, build the Activation Wall
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Enterprise Activation</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Please enter your Gumroad License Key to unlock your software.</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            input_key = st.text_input("License Key:", placeholder="XXXX-XXXX-XXXX-XXXX")
            
            if st.button("Unlock Software", use_container_width=True, type="primary"):
                if not input_key:
                    st.error("Please enter a key.")
                else:
                    with st.spinner("Verifying with Gumroad..."):
                        url = "https://api.gumroad.com/v2/licenses/verify"
                      # --- USE PRODUCT ID EXACTLY AS GUMROAD REQUESTED ---
                        payload = {"product_id": PRODUCT_ID, "license_key": input_key}
                        # -----------------------------------
                        
                        try:
                            res = requests.post(url, data=payload)
                            data = res.json()
                            
                           if data.get("success") == True:
                                
                                # --- 10-SEAT ENTERPRISE LIMIT CHECK ---
                                uses = data.get("uses", 0)
                                if uses > 10:
                                    st.error("❌ Maximum enterprise seats (10) reached for this License Key.")
                                    st.stop()
                                # --------------------------------------
                                
                                # Gumroad says it's real! Lock it to the hardware.
                                final_hash = generate_license_hash(input_key, hw_id)
                                
                                with open(LICENSE_FILE, "w") as f:
                                    json.dump({"key": input_key, "hash": final_hash}, f)
                                    
                                st.success(f"✅ Activation Successful! (Seat {uses} of 10)")
                                time.sleep(2)
                                st.rerun()
                                
                                with open(LICENSE_FILE, "w") as f:
                                    json.dump({"key": input_key, "hash": final_hash}, f)
                                    
                                st.success("✅ Activation Successful! Rebooting engine...")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ Gumroad Error: {data.get('message', 'Unknown Error')} | Full Response: {data}")
                        except Exception as e:
                            st.error("⚠️ Could not connect to the licensing server. Check your internet connection.")
                            
        st.stop() # CRITICAL: This stops the rest of the CRM from loading if they aren't activated!

# Run the security check immediately
check_activation()


# --- 1. SQLITE DATABASE ENGINE (Enterprise WAL Migration) ---
DB_FILE = "outbound_crm.db"

def get_db_conn():
    """Returns a DB connection with WAL enabled for high-concurrency."""
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_name TEXT, Name TEXT, Rating TEXT, Reviews INTEGER, 
                 Website TEXT, Email TEXT, Instagram TEXT, Facebook TEXT, Twitter TEXT, Phone TEXT, Address TEXT, 
                 Maps_Link TEXT, SSL TEXT, Mobile TEXT, Pixels TEXT, Pitch_SSL BOOLEAN, Pitch_Mobile BOOLEAN, 
                 Pitch_Pixels BOOLEAN, Drafted_Email TEXT, step_number INTEGER DEFAULT 1, last_contacted TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (date_sent TEXT, business_name TEXT, email_sent_to TEXT, email_body TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bg_status (id INTEGER PRIMARY KEY, is_running BOOLEAN, total INTEGER, sent INTEGER, errors INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # --- ENTERPRISE AUTO-MIGRATION ---
    c.execute("PRAGMA table_info(leads)")
    columns = [col[1] for col in c.fetchall()]
    if "step_number" not in columns:
        c.execute("ALTER TABLE leads ADD COLUMN step_number INTEGER DEFAULT 1")
    if "last_contacted" not in columns:
        c.execute("ALTER TABLE leads ADD COLUMN last_contacted TEXT")
        
    c.execute("PRAGMA table_info(logs)")
    log_columns = [col[1] for col in c.fetchall()]
    if "email_body" not in log_columns:
        c.execute("ALTER TABLE logs ADD COLUMN email_body TEXT")
    
    # Ensure campaigns table exists safely
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (name TEXT PRIMARY KEY)''')
    c.execute("INSERT OR IGNORE INTO campaigns (name) VALUES ('Default Campaign')")
    c.execute("INSERT OR IGNORE INTO bg_status (id, is_running, total, sent, errors) VALUES (1, 0, 0, 0, 0)")
    
    conn.commit()
    conn.close()

init_db()


# --- 1.5 EXTERNAL AI MODEL CONFIGURATOR ---
MODEL_CONFIG_FILE = "model_config.json"

def get_ai_model_name():
    """Reads the AI model name from an external file so users can update it without a patch."""
    default_model = "gemini-2.5-flash-lite"
    
    if not os.path.exists(MODEL_CONFIG_FILE):
        try:
            with open(MODEL_CONFIG_FILE, "w") as f:
                json.dump({
                    "_instruction": "Change 'gemini_model' below if Google releases a new model.",
                    "gemini_model": default_model
                }, f, indent=4)
        except Exception:
            pass
        return default_model
    else:
        try:
            with open(MODEL_CONFIG_FILE, "r") as f:
                data = json.load(f)
                return data.get("gemini_model", default_model)
        except Exception:
            return default_model


def get_setting(key, default=""):
    conn = get_db_conn()
    res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return res[0] if res else default

def save_setting(key, value):
    conn = get_db_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def load_campaign_leads(campaign_name):
    conn = get_db_conn()
    df = pd.read_sql("SELECT * FROM leads WHERE campaign_name=?", conn, params=(campaign_name,))
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id', 'campaign_name'])
        for col in ['Pitch_SSL', 'Pitch_Mobile', 'Pitch_Pixels']:
            if col in df.columns: df[col] = df[col].astype(bool)
        df.columns = df.columns.str.replace('_', ' ')
    return df


# --- 2. ASYNC SCRAPER & API LOGIC ---
async def async_extract_and_audit(session, url):
    if not url or url == 'No Website Found': 
        return {"Website": url, "Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "N/A", "Mobile": "N/A", "Pixels": "N/A"}
    try:
        async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7) as response:
            html_text = await response.text()
            soup = BeautifulSoup(html_text, 'html.parser')
            
            emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html_text))
            ig_links = set([a['href'] for a in soup.find_all('a', href=True) if 'instagram.com' in a['href']])
            fb_links = set([a['href'] for a in soup.find_all('a', href=True) if 'facebook.com' in a['href']])
            tw_links = set([a['href'] for a in soup.find_all('a', href=True) if 'twitter.com' in a['href'] or 'x.com' in a['href']])
            has_ssl = "Pass" if url.startswith("https") else "Fail"
            has_mobile = "Pass" if soup.find("meta", attrs={"name": "viewport"}) else "Fail"
            has_pixels = "Pass" if re.search(r'gtm\.js|analytics\.js|gtag|fbevents\.js', html_text, re.I) else "Fail"
            
            return {"Website": url, "Email": list(emails)[0] if emails else "N/A", "Instagram": list(ig_links)[0] if ig_links else "N/A", "Facebook": list(fb_links)[0] if fb_links else "N/A", "Twitter": list(tw_links)[0] if tw_links else "N/A", "SSL": has_ssl, "Mobile": has_mobile, "Pixels": has_pixels}
    except: return {"Website": url, "Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "Error", "Mobile": "Error", "Pixels": "Error"}

async def process_audits_concurrently(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [async_extract_and_audit(session, url) for url in urls]
        return await asyncio.gather(*tasks)


# --- 3. BACKGROUND WORKER (With Anti-Spam Jitter) ---
def background_email_worker(targets, sender, password, smtp_server, smtp_port, base_delay, campaign_name):
    conn = get_db_conn()
    conn.execute("UPDATE bg_status SET is_running=1, total=?, sent=0, errors=0 WHERE id=1", (len(targets),))
    conn.commit()
    
    sent_count = 0; err_count = 0
    for target in targets:
        try:
            msg = MIMEMultipart()
            msg['From'] = sender; msg['To'] = target['Email']; msg['Subject'] = target['Subject']
            msg.attach(MIMEText(target['Body'], 'plain'))
            
            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            
            t_conn = get_db_conn()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            t_conn.execute("INSERT INTO logs (date_sent, business_name, email_sent_to, email_body) VALUES (?, ?, ?, ?)", (timestamp, target['Name'], target['Email'], target['Body']))
            t_conn.execute("UPDATE leads SET Drafted_Email='✅ SENT', last_contacted=? WHERE campaign_name=? AND Email=?", (timestamp, campaign_name, target['Email']))
            sent_count += 1
            t_conn.execute("UPDATE bg_status SET sent=? WHERE id=1", (sent_count,))
            t_conn.commit(); t_conn.close()
        except Exception as e:
            err_count += 1
            t_conn = get_db_conn()
            t_conn.execute("UPDATE bg_status SET errors=? WHERE id=1", (err_count,))
            t_conn.commit(); t_conn.close()
        
        time.sleep(random.uniform(base_delay, base_delay * 1.5))
        
    conn = get_db_conn()
    conn.execute("UPDATE bg_status SET is_running=0 WHERE id=1")
    conn.commit(); conn.close()

def check_background_status():
    conn = get_db_conn()
    res = conn.execute("SELECT is_running, total, sent, errors FROM bg_status WHERE id=1").fetchone()
    conn.close()
    return {"is_running": bool(res[0]), "total": res[1], "sent": res[2], "errors": res[3]}

def draft_dynamic_email(business_name, rating, audit_data, pitch_ssl, pitch_mobile, pitch_pixels, profession, offer, proof, cta, name, tone, ai_api_key):
    if not ai_api_key: return "⚠️ Please enter your Gemini API Key in the settings sidebar."
    try:
        genai.configure(api_key=ai_api_key)
        
        active_model = get_ai_model_name()
        model = genai.GenerativeModel(active_model) 
        
        prompt = f"You are a professional {profession} writing a cold email to {business_name}. Tone: {tone}. CRITICAL GREETING RULES: You do NOT have a contact name. NEVER use placeholders like '[Name]' or '[Head of Operations]'. NEVER say 'Dear Owner' or 'Dear Head of Operations'. Start the email naturally with 'Hi there,' or 'Hi {business_name} team,' or just jump right into the first sentence without a greeting. Rating: {rating}. Audit: SSL Secure: {audit_data['SSL']}, Mobile Optimized: {audit_data['Mobile']}, Pixels: {audit_data['Pixels']}. Pitch SSL: {pitch_ssl}, Pitch Mobile: {pitch_mobile}, Pitch Pixels: {pitch_pixels}. If True, gently mention it as a problem. If all False, congratulate them on a solid business and pivot to offer. Pitch: {offer}. Trust: {proof}. CTA: {cta}. Keep it strictly under 150 words. Sign off as {name}."
        
        return model.generate_content(prompt).text
    except Exception as e: 
        return f"⚠️ AI Error: {e}"


# --- 4. SESSION STATE MANAGEMENT ---
if 'active_tab_index' not in st.session_state: 
    st.session_state.active_tab_index = 0
if 'master_dataframe' not in st.session_state: st.session_state.master_dataframe = None
if 'current_campaign' not in st.session_state: st.session_state.current_campaign = None


# --- 5. SIDEBAR (The Engine Room) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=40)
    st.title("⚙️ Engine Room")
    
    with st.expander("📖 How to setup and use this tool", expanded=False):
        st.markdown("""
        ### 🚀 The 4-Step Workflow
        **1. Hunt:** Enter a niche and location. The scraper will find local businesses and audit their website tech.
        **2. Analyze:** Review the dashboard. Use the checkboxes to select which technical failures you want to highlight.
        **3. Pitch:** Generate custom AI emails and send them individually or in bulk.
        **4. Logs & Replies:** View your sent history and use the IMAP scanner to automatically track who replied.

        ---

        ### 🔑 Setup: APIs & Email Connections
        To make the engine run, you need to plug in your keys below:

        **1. Google Places API Key (For Hunting)**
        * Go to the **[Google Cloud Console](https://console.cloud.google.com/)**.
        * Create a project, set up billing, and enable the **Places API (New)**.
        * Go to "APIs & Services" > "Credentials" and generate an API key.

        **2. Gemini API Key (For AI Pitching)**
        * Go to **[Google AI Studio](https://aistudio.google.com/app/apikey)**.
        * Click "Create API key" and generate a free key.

        **3. SMTP & IMAP Servers (For Sending/Tracking)**
        * **Gmail Users:** Leave the defaults (`smtp.gmail.com` and `imap.gmail.com`).
        * **Other Providers:** Update these with your provider's specific addresses (e.g., `smtp.office365.com` or `smtp.sendgrid.net`).

        **4. Email App Password (CRITICAL)**
        * **DO NOT** use your standard email login password.
        * Ensure **2-Step Verification** is turned on for your account.
        * Go directly to the **[Google App Passwords page](https://myaccount.google.com/apppasswords)** (this menu is often hidden without the direct link).
        * Create a new password named "Outbound AI" and paste that 16-character code into the 'Email Password/App Key' box below.
        """)

    # Campaign Manager
    st.subheader("📁 Campaign Manager")
    conn = get_db_conn()
    try:
        camp_list = [row[0] for row in conn.execute("SELECT name FROM campaigns").fetchall()]
    except sqlite3.OperationalError:
        init_db()
        camp_list = ["Default Campaign"]
    finally:
        conn.close()
    
    active_campaign = st.selectbox("Active Campaign:", camp_list)
    new_camp = st.text_input("Create New Campaign:", placeholder="e.g., HVAC Texas")
    if st.button("➕ Add Campaign") and new_camp:
        conn = get_db_conn()
        conn.execute("INSERT OR IGNORE INTO campaigns (name) VALUES (?)", (new_camp,))
        conn.commit(); conn.close()
        st.rerun()

    # SELF-HEALING LOGIC
    if st.session_state.current_campaign != active_campaign or st.session_state.master_dataframe is None:
        st.session_state.current_campaign = active_campaign
        df = load_campaign_leads(active_campaign)
        st.session_state.master_dataframe = df if not df.empty else None

    with st.expander("🔑 Setup APIs & Email"):
        api_key = st.text_input("Google Places API Key:", type="password", value=get_setting("google_key"))
        gemini_key = st.text_input("Gemini API Key:", type="password", value=get_setting("gemini_key"))
        st.divider()
        smtp_server = st.text_input("SMTP Server:", value=get_setting("smtp_server", "smtp.gmail.com"))
        smtp_port = st.text_input("SMTP Port:", value=get_setting("smtp_port", "587"))
        imap_server = st.text_input("IMAP Server:", value=get_setting("imap_server", "imap.gmail.com"))
        st.divider()
        sender_email = st.text_input("Email Username:", value=get_setting("sender_email"))
        app_password = st.text_input("Email Password/App Key:", type="password", value=get_setting("app_password"))
        
        if st.button("💾 Save Settings", use_container_width=True):
            save_setting("google_key", api_key); save_setting("gemini_key", gemini_key)
            save_setting("smtp_server", smtp_server); save_setting("smtp_port", smtp_port)
            save_setting("imap_server", imap_server); save_setting("sender_email", sender_email); save_setting("app_password", app_password)
            st.toast("✅ Infrastructure Saved Locally!")
            
    st.divider()
    # --- THE DIAGNOSTIC TOGGLE ---
    diagnostic_mode = st.toggle("🛠️ Diagnostic Mode (Debug API)")
    if diagnostic_mode:
        st.caption("⚠️ Diagnostic Mode will halt the app mid-hunt to display raw API data.")

    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.success("🔒 **Privacy First & 100% Local**\n\nYour data is saved securely on your local DB.")


# --- 6. MAIN HEADER ---
st.markdown("<h1 style='text-align: center; color: #4b6cb7;'>💠 SortingSource</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: gray; font-size: 1.1rem; margin-top: -15px;'>Enterprise Intelligence Platform | <a href='https://sortingsource.com' style='text-decoration: none; color: #4b6cb7;'>sortingsource.com</a></p>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #888;'>Active Workspace: <b>{st.session_state.current_campaign}</b></p>", unsafe_allow_html=True)


# --- 7. TABS ---
tab_names = ["🔍 1. Hunt", "📊 2. Analyze", "🚀 3. Pitch & Send", "📜 4. Campaign Logs"]
tab1, tab2, tab3, tab4 = st.tabs(tab_names)

# --- TAB 1: HUNT ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1: niche = st.text_input("Niche / Industry", placeholder="e.g., Roofers, HVAC, Software")
    with col2:
        lead_dropdown = st.selectbox("Max Leads", ["5", "10", "20", "50", "100", "250", "Type custom amount..."], index=2)
        if lead_dropdown == "Type custom amount...": max_results = st.number_input("Enter exact number:", min_value=1, value=15, step=1)
        else: max_results = int(lead_dropdown)
            
    col3, col4, col5 = st.columns([2, 2, 1])
    with col5:
        st.markdown("<br>", unsafe_allow_html=True) 
        is_international = st.checkbox("🌍 International")
    with col3: city = st.text_input("City (Optional)", placeholder="e.g., Detroit")
    with col4: region = st.text_input("Country" if is_international else "State", placeholder="e.g., MI")
        
    if st.button("🚀 Launch Scraper", use_container_width=True):
        if not api_key: st.error("⚠️ Please enter your Google Places API Key.")
        elif not niche or not region: st.warning("⚠️ Please fill out Niche and State/Country.")
        else:
            search_query = f"{niche} in {city}, {region}" if city else f"{niche} in {region}"
            with st.status(f"🚀 Launching Async Engine for '{search_query}'...", expanded=True) as status:
                
                # --- STEP 1: FETCH FROM GOOGLE ---
                st.write("1️⃣ Fetching Leads from Google Maps...")
                url = 'https://places.googleapis.com/v1/places:searchText'
                headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.businessStatus,nextPageToken'}
                
                raw_places = []
                page_token = ""
                
                while len(raw_places) < max_results:
                    payload = {'textQuery': search_query, 'pageSize': 20}
                    if page_token: payload['pageToken'] = page_token
                    res = requests.post(url, headers=headers, json=payload)
                    if not res.ok: break
                    data = res.json()
                    
                    places_batch = [p for p in data.get('places', []) if p.get('businessStatus') == 'OPERATIONAL']
                    raw_places.extend(places_batch)
                    
                    if len(raw_places) >= max_results:
                        raw_places = raw_places[:max_results]
                        break
                        
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                    time.sleep(1)

                if 'raw_places' in locals() and raw_places:
                    # --- STEP 2: ASYNC AUDITS ---
                    st.write(f"2️⃣ Found {len(raw_places)} leads. Running high-speed async audits...")
                    urls_to_audit = [p.get('websiteUri', 'No Website Found') for p in raw_places]
                    
                    audit_results = asyncio.run(process_audits_concurrently(urls_to_audit))

                    # --- STEP 3: DUPLICATE SHIELD & SAVE ---
                    st.write("3️⃣ Filtering Duplicates and Saving to Database...")
                    conn = get_db_conn()
                    
                    existing_df = load_campaign_leads(st.session_state.current_campaign)
                    existing_names = set(existing_df['Name'].tolist()) if existing_df is not None else set()
                    
                    sample_keys = [
                        "campaign_name", "Name", "Rating", "Reviews", "Website", "Email", 
                        "Instagram", "Facebook", "Twitter", "Phone", "Address", "Maps_Link", 
                        "SSL", "Mobile", "Pixels", "Pitch_SSL", "Pitch_Mobile", "Pitch_Pixels", 
                        "Drafted_Email", "step_number", "last_contacted"
                    ]
                    cols = ", ".join(sample_keys)
                    places = ", ".join(["?"] * len(sample_keys))
                    sql = f"INSERT INTO leads ({cols}) VALUES ({places})"
                    
                    batch_data = []
                    duplicates_skipped = 0
                    
                    for i, place in enumerate(raw_places):
                        try:
                            display_name = place.get('displayName')
                            if isinstance(display_name, dict):
                                biz_name = display_name.get('text', 'N/A')
                            else:
                                biz_name = str(display_name) if display_name else 'N/A'
                                
                            if biz_name in existing_names:
                                duplicates_skipped += 1
                                continue
                                
                            audit = audit_results[i] if i < len(audit_results) else {}
                            
                            lead_row = (
                                str(st.session_state.current_campaign), 
                                str(biz_name), 
                                str(place.get('rating') or 'N/A'),
                                int(place.get('userRatingCount') or 0), 
                                str(audit.get("Website") or "N/A"), 
                                str(audit.get("Email") or "N/A"),
                                str(audit.get("Instagram") or "N/A"), 
                                str(audit.get("Facebook") or "N/A"), 
                                str(audit.get("Twitter") or "N/A"),
                                str(place.get('nationalPhoneNumber') or 'N/A'), 
                                str(place.get('formattedAddress') or 'N/A'),
                                str(place.get('googleMapsUri') or 'N/A'), 
                                str(audit.get("SSL") or "N/A"), 
                                str(audit.get("Mobile") or "N/A"),
                                str(audit.get("Pixels") or "N/A"), 
                                False, False, False, "", 1, ""
                            )
                            batch_data.append(lead_row)
                        except Exception as e:
                            st.warning(f"⚠️ Skipping record due to format error: {e}")
                    
                    try:
                        if batch_data:
                            conn.executemany(sql, batch_data)
                            conn.commit()
                    except Exception as e:
                        st.error(f"🛑 Database Write Error: {e}")
                    finally:
                        conn.close()
                    
                    df = load_campaign_leads(st.session_state.current_campaign)
                    st.session_state.master_dataframe = df
                    
                    status.update(label=f"✅ Complete. Saved {len(batch_data)} new leads (Skipped {duplicates_skipped} duplicates).", state="complete")
                    
                    st.toast("🎉 Hunt Complete! Moving to Analyze...")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    status.update(label="⚠️ Search yielded no results to process.", state="error")


# --- TAB 2: ANALYZE ---
with tab2:
    if st.session_state.master_dataframe is not None:
        df = st.session_state.master_dataframe
        
        st.markdown("### 🎛️ Command Center")
        
        m1, m2, m3, m4 = st.columns(4)
        total_leads = len(df)
        emails_found = len(df[df['Email'] != 'N/A'])
        m1.metric("Total Prospects", total_leads)
        
        match_percentage = int((emails_found / total_leads) * 100) if total_leads > 0 else 0
        m2.metric("Valid Emails Found", emails_found, f"{match_percentage}% Match")
        
        m3.metric("Missing SSL (Hot)", len(df[df['SSL'] == 'Fail']))
        m4.metric("Missing Pixels", len(df[df['Pixels'] == 'Fail']))
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        filter_option = st.radio("Quick Filter:", ["All Leads", "Missing SSL", "Missing Pixels", "Valid Emails Only"], horizontal=True)
        display_df = df.copy()
        if filter_option == "Missing SSL": display_df = display_df[display_df['SSL'] == 'Fail']
        elif filter_option == "Missing Pixels": display_df = display_df[display_df['Pixels'] == 'Fail']
        elif filter_option == "Valid Emails Only": display_df = display_df[display_df['Email'] != 'N/A']

        url_cols = ["Website", "Instagram", "Facebook", "Twitter", "Maps Link"]
        for col in url_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].replace(["N/A", "No Website Found"], None)

        display_df['Name'] = display_df.apply(lambda r: f"✅ {r['Name']}" if r['Drafted Email'] in ['✅ SENT', '🔥 REPLIED'] else r['Name'], axis=1)

        cols_to_show = [c for c in display_df.columns if c not in ['Drafted Email', 'step number', 'last contacted']]
        
        edited_df = st.data_editor(
            display_df[cols_to_show], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Website": st.column_config.LinkColumn("Website"),
                "Instagram": st.column_config.LinkColumn("Instagram"),
                "Facebook": st.column_config.LinkColumn("Facebook"),
                "Twitter": st.column_config.LinkColumn("Twitter"),
                "Maps Link": st.column_config.LinkColumn("Maps Link"),
                "Pitch SSL": st.column_config.CheckboxColumn("Pitch SSL?"),
                "Pitch Mobile": st.column_config.CheckboxColumn("Pitch Mobile?"),
                "Pitch Pixels": st.column_config.CheckboxColumn("Pitch Pixels?")
            }
        )
        
        conn = get_db_conn()
        for index, row in edited_df.iterrows():
            clean_row = row.fillna("N/A")
            original_name = clean_row['Name'].replace("✅ ", "")
            
            st.session_state.master_dataframe.loc[st.session_state.master_dataframe['Name'] == original_name, ['Pitch SSL', 'Pitch Mobile', 'Pitch Pixels']] = [clean_row['Pitch SSL'], clean_row['Pitch Mobile'], clean_row['Pitch Pixels']]
            
            conn.execute("UPDATE leads SET Pitch_SSL=?, Pitch_Mobile=?, Pitch_Pixels=? WHERE campaign_name=? AND Name=?", 
                         (int(clean_row['Pitch SSL']), int(clean_row['Pitch Mobile']), int(clean_row['Pitch Pixels']), st.session_state.current_campaign, original_name))
        conn.commit()
        conn.close()

        csv_data = st.session_state.master_dataframe.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Export Master List to CSV", data=csv_data, file_name="outbound_leads.csv", mime="text/csv")
    else: 
        st.info("👈 Run the scraper in Step 1 to populate your Command Center.")


# --- TAB 3: PITCH & SEND ---
with tab3:
    if st.session_state.master_dataframe is not None:
        with st.expander("👤 1. Persona & Offer Setup (Configure Once)", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                user_profession = st.text_input("Your Profession:", value=get_setting("user_profession", ""))
                your_name = st.text_input("Your Name:", value=get_setting("your_name", ""))
                
                tone_dropdown = st.selectbox("AI Tone / Persona:", ["Friendly & Conversational", "Direct & Professional", "Consultative & Helpful", "Witty & Humorous", "Type custom tone..."])
                if tone_dropdown == "Type custom tone...":
                    email_tone = st.text_input("Enter exact tone:", placeholder="e.g., Aggressive Wolf of Wall Street")
                else:
                    email_tone = tone_dropdown
                    
            with col_b:
                social_proof = st.text_input("Past Work:", value=get_setting("social_proof", ""))
                call_to_action = st.text_input("CTA:", value=get_setting("cta", "Open to a 5-min chat?"))
            core_offer = st.text_area("Core Offer:", value=get_setting("core_offer", ""))
            
            if st.button("💾 Save Persona Defaults"):
                save_setting("user_profession", user_profession); save_setting("your_name", your_name)
                save_setting("social_proof", social_proof); save_setting("cta", call_to_action)
                save_setting("core_offer", core_offer)
                st.toast("✅ Persona & Offer saved globally!")

        st.markdown("### 🎯 2. Single Target Execution")
        
        sort_by = st.radio("Sort List By:", ["Name (A-Z)", "Highest Rating", "Most Reviews"], horizontal=True)
        
        sort_df = st.session_state.master_dataframe[st.session_state.master_dataframe['Email'] != 'N/A'].copy()
        
        if sort_df.empty:
            st.warning("⚠️ No leads with valid emails found in this campaign. Go back to Tab 1 to hunt for more!")
            st.stop()
            
        if sort_by == "Name (A-Z)":
            sort_df['sort_key'] = sort_df['Name'].astype(str).str.lower()
            sort_df = sort_df.sort_values(by='sort_key', ascending=True)
            
        name_list = sort_df['Name'].tolist()
        
        def format_target_name(name):
            row = st.session_state.master_dataframe[st.session_state.master_dataframe['Name'] == name].iloc[0]
            status = row['Drafted Email']
            rating = row['Rating']
            reviews = row['Reviews']
            phone = row['Phone']
            
            prefix = "✅ " if status in ["✅ SENT", "🔥 REPLIED"] else ""
            rating_str = f"⭐ {rating} ({reviews})" if str(rating) != "N/A" else "⭐ N/A"
            phone_str = f"📞 {phone}" if str(phone) != "N/A" else "📞 N/A"
            return f"{prefix}{name}  |  {rating_str}  |  {phone_str}"
            
        selected_business = st.selectbox("Select target to pitch:", name_list, format_func=format_target_name)
        
        matching_rows = st.session_state.master_dataframe.index[st.session_state.master_dataframe['Name'] == selected_business].tolist()
        if not matching_rows:
            st.warning("⚠️ Loading lead data... please select a business.")
            st.stop()
            
        lead_idx = matching_rows[0]
        lead_info = st.session_state.master_dataframe.iloc[lead_idx]
        current_draft = lead_info['Drafted Email']

        if current_draft and current_draft not in ["✅ SENT", "🔥 REPLIED"]:
            edited_draft = st.text_area("Review and Edit Email:", value=current_draft, height=250)
            if edited_draft != current_draft:
                conn = get_db_conn()
                conn.execute("UPDATE leads SET Drafted_Email=? WHERE campaign_name=? AND Email=?", (edited_draft, st.session_state.current_campaign, lead_info['Email']))
                conn.commit(); conn.close()
                st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = edited_draft
                current_draft = edited_draft  
        elif current_draft in ["✅ SENT", "🔥 REPLIED"]: 
            st.success(f"Status: {current_draft}")

        col_gen, col_send = st.columns(2)
        with col_gen:
            if st.button("🤖 Generate Custom Pitch", use_container_width=True):
                if not user_profession or not core_offer: st.warning("⚠️ Fill out your Persona fields above!")
                else:
                    with st.spinner("AI is analyzing data and writing..."):
                        draft = draft_dynamic_email(lead_info['Name'], lead_info['Rating'], {"SSL": lead_info['SSL'], "Mobile": lead_info['Mobile'], "Pixels": lead_info['Pixels']}, lead_info['Pitch SSL'], lead_info['Pitch Mobile'], lead_info['Pitch Pixels'], user_profession, core_offer, social_proof, call_to_action, your_name, email_tone, gemini_key)
                        conn = get_db_conn()
                        conn.execute("UPDATE leads SET Drafted_Email=? WHERE campaign_name=? AND Email=?", (draft, st.session_state.current_campaign, lead_info['Email']))
                        conn.commit(); conn.close()
                        st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = draft
                        st.toast("✅ Pitch Generated!")
                        st.rerun() 
        with col_send:
            if st.button("🚀 Send Email Now", type="primary", use_container_width=True):
                if not current_draft or current_draft in ["✅ SENT", "🔥 REPLIED"]: st.error("⚠️ Generate a fresh pitch first.")
                elif lead_info['Email'] == "N/A": st.error("⚠️ No email scraped.")
                else:
                    with st.spinner("Dispatching through SMTP..."):
                        try:
                            msg = MIMEMultipart(); msg['From'] = sender_email; msg['To'] = lead_info['Email']; msg['Subject'] = f"Quick question regarding {lead_info['Name']}'s website"
                            msg.attach(MIMEText(current_draft, 'plain'))
                            
                            server = smtplib.SMTP(smtp_server, int(smtp_port)); server.starttls(); server.login(sender_email, app_password); server.send_message(msg); server.quit()
                            
                            conn = get_db_conn()
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            conn.execute("INSERT INTO logs (date_sent, business_name, email_sent_to, email_body) VALUES (?, ?, ?, ?)", (timestamp, lead_info['Name'], lead_info['Email'], current_draft))
                            conn.execute("UPDATE leads SET Drafted_Email='✅ SENT', last_contacted=? WHERE campaign_name=? AND Email=?", (timestamp, st.session_state.current_campaign, lead_info['Email']))
                            conn.commit(); conn.close()
                            
                            st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = "✅ SENT"
                            st.toast("🚀 Sent Successfully!")
                            st.balloons()
                            st.rerun()
                        except Exception as e: st.error(f"SMTP Error: {e}")

        st.divider()

        st.markdown("### ⚡ 3. Background Mass Sender")
        bg_status = check_background_status()
        if bg_status["is_running"]:
            st.info(f"⚙️ **Engine Running:** {bg_status['sent']} / {bg_status['total']} dispatched. ({bg_status['errors']} errors).")
            if st.button("🔄 Refresh Status"): st.rerun()
            st.progress(bg_status['sent'] / max(1, bg_status['total']))
        
        col_gen_settings, col_send_settings = st.columns(2)
        with col_gen_settings:
            gen_limit = st.number_input("Batch Size (AI Generation):", min_value=1, value=10, step=1, help="Limit how many pitches the AI writes at once so you don't have to wait for the whole list.")
        with col_send_settings:
            send_delay = st.slider("Anti-Spam Base Delay (Seconds):", min_value=10, max_value=120, value=45, help="To prevent domain blacklisting, the system will wait a random amount of time between this base delay and 1.5x this delay.")
            
        bulk_col1, bulk_col2 = st.columns(2)
        
        with bulk_col1:
            if st.button(f"🤖 Bulk Generate {gen_limit} Pitches", use_container_width=True, disabled=bg_status["is_running"]):
                if not user_profession or not core_offer: st.warning("⚠️ Fill out your Persona fields.")
                else:
                    progress_bar = st.progress(0)
                    generated_count = 0
                    conn = get_db_conn()
                    
                    for idx, row in st.session_state.master_dataframe.iterrows():
                        if not row['Drafted Email'] or row['Drafted Email'] not in ["✅ SENT", "🔥 REPLIED"]:
                            draft = draft_dynamic_email(row['Name'], row['Rating'], {"SSL": row['SSL'], "Mobile": row['Mobile'], "Pixels": row['Pixels']}, row['Pitch SSL'], row['Pitch Mobile'], row['Pitch Pixels'], user_profession, core_offer, social_proof, call_to_action, your_name, email_tone, gemini_key)
                            
                            conn.execute("UPDATE leads SET Drafted_Email=? WHERE campaign_name=? AND Email=?", (draft, st.session_state.current_campaign, row['Email']))
                            st.session_state.master_dataframe.at[idx, 'Drafted Email'] = draft
                            
                            generated_count += 1
                            progress_bar.progress(generated_count / gen_limit)
                            
                            if generated_count >= gen_limit:
                                break
                                
                            time.sleep(4)
                            
                    conn.commit(); conn.close()
                    st.toast(f"✅ Successfully generated {generated_count} pitches!")
                    time.sleep(1)
                    st.rerun()
                    
        with bulk_col2:
            if st.button("🚀 Start Mass Dispatch Sequence", type="primary", use_container_width=True, disabled=bg_status["is_running"]):
                valid_targets = st.session_state.master_dataframe[
                    (st.session_state.master_dataframe['Drafted Email'] != "") & 
                    (~st.session_state.master_dataframe['Drafted Email'].isin(["✅ SENT", "🔥 REPLIED"])) & 
                    (st.session_state.master_dataframe['Email'] != "N/A")
                ]
                if valid_targets.empty: st.error("⚠️ No pending emails to send.")
                else:
                    send_queue = [{"Name": r['Name'], "Email": r['Email'], "Subject": f"Quick question regarding {r['Name']}'s website", "Body": r['Drafted Email']} for i, r in valid_targets.iterrows()]
                    thread = threading.Thread(target=background_email_worker, args=(send_queue, sender_email, app_password, smtp_server, smtp_port, send_delay, st.session_state.current_campaign))
                    thread.daemon = True
                    thread.start()
                    st.toast("🚀 Background Sender Started!")
                    time.sleep(1)
                    st.rerun()
    else: st.info("👈 Run the scraper in Step 1 before drafting emails.")


# --- TAB 4: CAMPAIGN LOGS & IMAP ---
with tab4:
    col_log, col_imap = st.columns([2, 1])
    with col_log:
        st.markdown("### 📜 Dispatch Logs")
        conn = get_db_conn()
        try:
            logs_df = pd.read_sql("SELECT * FROM logs ORDER BY date_sent DESC", conn)
        except sqlite3.OperationalError:
            logs_df = pd.DataFrame()
        conn.close()
        
        st.metric("Total Emails Sent", len(logs_df))
        if not logs_df.empty: 
            st.dataframe(
                logs_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "email_body": st.column_config.TextColumn("Email Content", width="large", help="Double-click any cell to read the full email.")
                }
            )
        else: 
            st.info("No emails have been sent yet.")
        
    with col_imap:
        st.markdown("### 📥 Reply Scanner")
        st.caption("Logs into IMAP and flags prospects who replied.")
        if st.button("🔥 Scan Inbox for Replies", use_container_width=True):
            if not imap_server or not sender_email or not app_password: st.error("⚠️ Check IMAP settings in Engine Room.")
            else:
                with st.spinner(f"Connecting to {imap_server}..."):
                    try:
                        mail = imaplib.IMAP4_SSL(imap_server); mail.login(sender_email, app_password); mail.select('inbox')
                        conn = get_db_conn()
                        sent_emails = pd.read_sql("SELECT email_sent_to FROM logs", conn)['email_sent_to'].tolist()
                        
                        replied_count = 0
                        for e in set(sent_emails):
                            if e == "N/A": continue
                            status, data = mail.search(None, f'FROM "{e}"')
                            if status == 'OK' and data[0]:
                                conn.execute("UPDATE leads SET Drafted_Email='🔥 REPLIED' WHERE Email=?", (e,))
                                replied_count += 1
                        
                        conn.commit(); conn.close(); mail.logout()
                        st.session_state.master_dataframe = load_campaign_leads(st.session_state.current_campaign)
                        
                        if replied_count > 0: 
                            st.success(f"✅ Found {replied_count} replies! Dashboard updated.")
                            st.balloons()
                        else: st.info("No new replies found.")
                    except Exception as e: st.error(f"IMAP Error: {e}")
