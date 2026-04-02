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



# --- 1. SQLITE DATABASE ENGINE (Enterprise Migration) ---

DB_FILE = "outbound_crm.db"



def init_db():

    """Initializes the bulletproof local database."""

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

    

    # Insert defaults if empty

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

        # Ensure booleans are typed correctly for the dataframe editor

        for col in ['Pitch_SSL', 'Pitch_Mobile', 'Pitch_Pixels']:

            if col in df.columns: df[col] = df[col].astype(bool)

        # Rename columns to match old styling

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

            

            # Use separate DB connection for thread safety

            t_conn = sqlite3.connect(DB_FILE)

            t_conn.execute("INSERT INTO logs (date_sent, business_name, email_sent_to) VALUES (?, ?, ?)", (time.strftime("%Y-%m-%d %H:%M:%S"), target['Name'], target['Email']))

            t_conn.execute("UPDATE leads SET Drafted_Email='✅ SENT' WHERE campaign_name=? AND Email=?", (campaign_name, target['Email']))

            sent_count += 1

            t_conn.execute("UPDATE bg_status SET sent=? WHERE id=1", (sent_count,))

            t_conn.commit()

            t_conn.close()

        except Exception as e:

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

    if not ai_api_key: return "⚠️ Please enter your Gemini API Key in the settings sidebar."

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



# --- 3. SESSION STATE MANAGEMENT ---

if 'master_dataframe' not in st.session_state: st.session_state.master_dataframe = None

if 'current_campaign' not in st.session_state: st.session_state.current_campaign = None



# --- 4. SIDEBAR (The Enterprise Engine Room) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=40)
    st.title("⚙️ Engine Room")
    
    # --- RESTORED & ELABORATED INSTRUCTIONS ---
    with st.expander("📖 How to setup and use this tool", expanded=False):
        st.markdown("""
        ### 🚀 The 4-Step Workflow
        **1. Hunt:** Enter a niche and location. The scraper will find local businesses and audit their website tech.
        **2. Analyze:** Review the dashboard. Use the checkboxes to select which technical failures you want to highlight.
        **3. Pitch:** Generate custom AI emails and send them individually or in bulk.
        **4. Logs & Replies:** View your sent history and use the IMAP scanner to automatically track who replied.

        ---

        ### 🔑 Setup: APIs & Email Connections
        To make the engine run, you need to plug in your keys below.

        **1. Google Places API Key (For Hunting)**
        *Google's Cloud Console can be tricky to navigate. Follow these exact steps:*
        * **Step 1: Create a Project.** Go to the **[Google Cloud Console](https://console.cloud.google.com/)**. In the top-left dropdown (next to the Google Cloud logo), click **New Project**. Name it "Outbound AI CRM" and click Create. Make sure this new project is selected in that top dropdown.
        * **Step 2: Enable Billing.** Google requires a billing account to use the Places API (they provide a generous $200/month free tier, which covers thousands of searches). Go to the hamburger menu (top left) > **Billing** > **Link a billing account**.
        * **Step 3: Enable the API.** Go to the hamburger menu > **APIs & Services** > **Library**. In the search bar, type exactly: **Places API (New)**. Click on it, then click the blue **Enable** button.
        * **Step 4: Generate the Key.** Once enabled, go to the hamburger menu > **APIs & Services** > **Credentials**. Click **+ CREATE CREDENTIALS** at the top of the screen and select **API Key**. 
        * *(Architect's Tip: Click "Edit API Key" and under "API restrictions", select "Restrict key" and choose "Places API (New)". This ensures no one can use your key for other expensive Google services!)*

        **2. Gemini API Key (For AI Pitching)**
        * Go to **[Google AI Studio](https://aistudio.google.com/app/apikey)**.
        * Click "Create API key" and generate a free key.

        **3. SMTP & IMAP Servers (For Sending/Tracking)**
        * **Gmail Users:** Leave the defaults (`smtp.gmail.com` and `imap.gmail.com`).
        * **Other Providers:** Update these with your provider's specific addresses (e.g., `smtp.office365.com` or `smtp.sendgrid.net`).

        **4. Email App Password (CRITICAL)**
        * **DO NOT** use your standard email login password.
        * Go to your Google Account (or email provider's) **Security Settings**.
        * Ensure **2-Step Verification** is turned on.
        * Search for **"App Passwords"** and generate a new 16-character password specifically for this software. Paste that into the 'Email Password' box.
        """)

    # Campaign Manager
    st.subheader("📁 Campaign Manager")
    conn = sqlite3.connect(DB_FILE)
    camp_list = [row[0] for row in conn.execute("SELECT name FROM campaigns").fetchall()]
    conn.close()
    
    active_campaign = st.selectbox("Active Campaign:", camp_list)
    new_camp = st.text_input("Create New Campaign:", placeholder="e.g., HVAC Texas")
    if st.button("➕ Add Campaign") and new_camp:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR IGNORE INTO campaigns (name) VALUES (?)", (new_camp,))
        conn.commit()
        conn.close()
        st.rerun()

    # Load data if campaign changed
    if st.session_state.current_campaign != active_campaign:
        st.session_state.current_campaign = active_campaign
        df = load_campaign_leads(active_campaign)
        st.session_state.master_dataframe = df if not df.empty else None

    with st.expander("🔑 Setup APIs & Email"):
        api_key = st.text_input("Google Places API Key:", type="password", value=get_setting("google_key"))
        gemini_key = st.text_input("Gemini API Key:", type="password", value=get_setting("gemini_key"))
        
        st.divider()
        st.caption("SMTP (Sending Emails)")
        smtp_server = st.text_input("SMTP Server:", value=get_setting("smtp_server", "smtp.gmail.com"))
        smtp_port = st.text_input("SMTP Port:", value=get_setting("smtp_port", "587"))
        
        st.divider()
        st.caption("IMAP (Tracking Replies)")
        imap_server = st.text_input("IMAP Server:", value=get_setting("imap_server", "imap.gmail.com"))
        
        st.divider()
        sender_email = st.text_input("Email Username:", value=get_setting("sender_email"))
        app_password = st.text_input("Email Password/App Key:", type="password", value=get_setting("app_password"))
        
        if st.button("💾 Save Settings", use_container_width=True):
            save_setting("google_key", api_key); save_setting("gemini_key", gemini_key)
            save_setting("smtp_server", smtp_server); save_setting("smtp_port", smtp_port)
            save_setting("imap_server", imap_server)
            save_setting("sender_email", sender_email); save_setting("app_password", app_password)
            st.toast("✅ Infrastructure Saved Locally!")

    # --- PRIVACY DISCLAIMER (Moved to Bottom) ---
    # Using CSS to push this to the bottom of the sidebar visually
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.success("🔒 **Privacy First & 100% Local**\n\nYour API keys, emails, and CRM data are saved securely on your local hard drive. Nothing is sent to a central server.")



# --- 5. MAIN HEADER ---

st.markdown("<h1 style='text-align: center;'>🚀 Outbound AI</h1>", unsafe_allow_html=True)

st.markdown(f"<p style='text-align: center; color: gray; font-size: 1.2rem; margin-bottom: 2rem;'>Active Workspace: <b>{st.session_state.current_campaign}</b></p>", unsafe_allow_html=True)



# --- 6. TABS ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 1. Hunt", "📊 2. Analyze", "🚀 3. Pitch & Send", "📜 4. Campaign Logs & Replies"])



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

            with st.status(f"🚀 Launching Engine...", expanded=True) as status:

                st.write(f"Querying Google Maps for: '{search_query}'")

                url = 'https://places.googleapis.com/v1/places:searchText'

                headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.businessStatus,nextPageToken'}

                all_leads = []

                page_token = ""

                

                while len(all_leads) < max_results:

                    payload = {'textQuery': search_query, 'pageSize': 20}

                    if page_token: payload['pageToken'] = page_token

                    res = requests.post(url, headers=headers, json=payload)

                    if not res.ok: break

                    data = res.json()

                    

                    for place in data.get('places', []):

                        if place.get('businessStatus') == 'OPERATIONAL':

                            website = place.get('websiteUri', 'No Website Found')

                            audit = extract_and_audit(website) 

                            

                            lead_obj = {

                                "Name": place.get('displayName', {}).get('text', 'N/A'), "Rating": str(place.get('rating', 'N/A')), 

                                "Reviews": int(place.get('userRatingCount', 0)), "Website": website, "Email": audit["Email"], 

                                "Instagram": audit["Instagram"], "Facebook": audit["Facebook"], "Twitter": audit["Twitter"],

                                "Phone": place.get('nationalPhoneNumber', 'N/A'), "Address": place.get('formattedAddress', 'N/A'),

                                "Maps_Link": place.get('googleMapsUri', 'N/A'), "SSL": audit["SSL"], "Mobile": audit["Mobile"], 

                                "Pixels": audit["Pixels"], "Pitch_SSL": False, "Pitch_Mobile": False, "Pitch_Pixels": False, "Drafted_Email": ""

                            }

                            # Save directly to robust SQLite DB

                            save_lead_to_db(st.session_state.current_campaign, lead_obj)

                            all_leads.append(lead_obj)

                            

                            if len(all_leads) >= max_results: break

                    page_token = data.get('nextPageToken')

                    if not page_token: break

                    time.sleep(1)

                

                # Refresh UI from DB

                df = load_campaign_leads(st.session_state.current_campaign)

                st.session_state.master_dataframe = df if not df.empty else None

                status.update(label=f"✅ Saved {len(all_leads)} leads to the database.", state="complete")



# --- TAB 2: ANALYZE ---

with tab2:

    if st.session_state.master_dataframe is not None:

        df = st.session_state.master_dataframe

        st.markdown("### 📈 Campaign Overview")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Leads Audited", len(df))

        col2.metric("Missing SSL (Hot Leads)", len(df[df['SSL'] == 'Fail']))

        col3.metric("Missing Pixels", len(df[df['Pixels'] == 'Fail']))

        col4.metric("Average Rating", round(df[df['Rating'] != 'N/A']['Rating'].astype(float).mean(), 1) if not df[df['Rating'] != 'N/A'].empty else "N/A")

        st.divider()



        filter_option = st.radio("Quick Filter:", ["All Leads", "Missing SSL", "Missing Pixels", "No Website"], horizontal=True)

        display_df = df.copy()

        if filter_option == "Missing SSL": display_df = display_df[display_df['SSL'] == 'Fail']

        elif filter_option == "Missing Pixels": display_df = display_df[display_df['Pixels'] == 'Fail']

        elif filter_option == "No Website": display_df = display_df[display_df['Website'] == 'No Website Found']



        cols_to_show = [c for c in display_df.columns if c != 'Drafted Email']

        edited_df = st.data_editor(display_df[cols_to_show], use_container_width=True, hide_index=True)

        

        # Save edits back to DB 

        conn = sqlite3.connect(DB_FILE)

        for index, row in edited_df.iterrows():

            st.session_state.master_dataframe.loc[st.session_state.master_dataframe['Name'] == row['Name'], edited_df.columns] = row.values

            conn.execute("UPDATE leads SET Pitch_SSL=?, Pitch_Mobile=?, Pitch_Pixels=? WHERE campaign_name=? AND Name=?", 

                         (int(row['Pitch SSL']), int(row['Pitch Mobile']), int(row['Pitch Pixels']), st.session_state.current_campaign, row['Name']))

        conn.commit()

        conn.close()



        csv_data = st.session_state.master_dataframe.to_csv(index=False).encode('utf-8')

        st.download_button("⬇️ Export Master List to CSV", data=csv_data, file_name="outbound_leads.csv", mime="text/csv")

    else: st.info("👈 Run the scraper in Step 1 to populate your dashboard.")



# --- TAB 3: PITCH & SEND ---

with tab3:

    if st.session_state.master_dataframe is not None:

        with st.container(border=True):

            col_a, col_b = st.columns(2)

            with col_a:

                user_profession = st.text_input("Your Profession:", value="")

                your_name = st.text_input("Your Name:", value="")

            with col_b:

                social_proof = st.text_input("Past Work:", value="")

                call_to_action = st.text_input("CTA:", value="Open to a 5-min chat?")

            core_offer = st.text_area("Core Offer:", value="")

        st.divider()



        # SINGLE EXECUTION

        st.markdown("### 🎯 Single Target Execution")

        selected_business = st.selectbox("Select target to pitch:", st.session_state.master_dataframe['Name'].tolist())

        lead_idx = st.session_state.master_dataframe.index[st.session_state.master_dataframe['Name'] == selected_business].tolist()[0]

        lead_info = st.session_state.master_dataframe.iloc[lead_idx]

        current_draft = lead_info['Drafted Email']



        col_gen, col_send = st.columns(2)

        with col_gen:

            if st.button("🤖 1. Generate Custom Pitch", use_container_width=True):

                if not user_profession or not your_name or not core_offer: st.warning("⚠️ Fill out your Persona fields first!")

                else:

                    with st.spinner("AI is writing your pitch..."):

                        draft = draft_dynamic_email(lead_info['Name'], lead_info['Rating'], {"SSL": lead_info['SSL'], "Mobile": lead_info['Mobile'], "Pixels": lead_info['Pixels']}, lead_info['Pitch SSL'], lead_info['Pitch Mobile'], lead_info['Pitch Pixels'], user_profession, core_offer, social_proof, call_to_action, your_name, gemini_key)

                        update_lead_draft(st.session_state.current_campaign, lead_info['Email'], draft)

                        st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = draft

                        st.rerun() 

        with col_send:

            if st.button("🚀 2. Send Email Now", type="primary", use_container_width=True):

                if not current_draft or current_draft in ["✅ SENT", "🔥 REPLIED"]: st.error("⚠️ Generate a fresh pitch first.")

                elif lead_info['Email'] == "N/A": st.error("⚠️ No email scraped.")

                else:

                    with st.spinner("Dispatching..."):

                        success, message = send_email(sender_email, app_password, lead_info['Email'], f"Quick question regarding {lead_info['Name']}'s website", current_draft, smtp_server, smtp_port)

                        if success:

                            update_lead_draft(st.session_state.current_campaign, lead_info['Email'], "✅ SENT")

                            st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = "✅ SENT"

                            log_campaign(lead_info['Name'], lead_info['Email'])

                            st.rerun()

                        else: st.error(message)



        if current_draft and current_draft not in ["✅ SENT", "🔥 REPLIED"]:

            edited_draft = st.text_area("Review and Edit Email:", value=current_draft, height=250)

            if edited_draft != current_draft:

                update_lead_draft(st.session_state.current_campaign, lead_info['Email'], edited_draft)

                st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = edited_draft

        elif current_draft in ["✅ SENT", "🔥 REPLIED"]: st.success(f"Status: {current_draft}")



        st.markdown("<br><br>", unsafe_allow_html=True)

        st.divider()



        # BULK EXECUTION

        st.markdown("### ⚡ Bulk Mass Sender")

        bg_status = check_background_status()

        if bg_status["is_running"]:

            st.info(f"⚙️ **Background Worker Running:** {bg_status['sent']} / {bg_status['total']} emails dispatched. ({bg_status['errors']} errors).")

            if st.button("🔄 Refresh Status"): st.rerun()

            st.progress(bg_status['sent'] / max(1, bg_status['total']))

        

        send_delay = st.slider("Throttle (Seconds between emails):", min_value=1, max_value=30, value=3)

        bulk_col1, bulk_col2 = st.columns(2)

        

        with bulk_col1:

            if st.button("🤖 Bulk Generate All Pitches", use_container_width=True, disabled=bg_status["is_running"]):

                if not user_profession or not your_name or not core_offer: st.warning("⚠️ Fill out your Persona fields first.")

                else:

                    progress_bar = st.progress(0)

                    total = len(st.session_state.master_dataframe)

                    for idx, row in st.session_state.master_dataframe.iterrows():

                        if not row['Drafted Email'] or row['Drafted Email'] not in ["✅ SENT", "🔥 REPLIED"]:

                            draft = draft_dynamic_email(row['Name'], row['Rating'], {"SSL": row['SSL'], "Mobile": row['Mobile'], "Pixels": row['Pixels']}, row['Pitch SSL'], row['Pitch Mobile'], row['Pitch Pixels'], user_profession, core_offer, social_proof, call_to_action, your_name, gemini_key)

                            update_lead_draft(st.session_state.current_campaign, row['Email'], draft)

                            st.session_state.master_dataframe.at[idx, 'Drafted Email'] = draft

                        progress_bar.progress((idx + 1) / total)

                    st.rerun()

                    

        with bulk_col2:

            if st.button("🚀 Start Mass Background Sending", type="primary", use_container_width=True, disabled=bg_status["is_running"]):

                valid_targets = st.session_state.master_dataframe[

                    (st.session_state.master_dataframe['Drafted Email'] != "") & 

                    (~st.session_state.master_dataframe['Drafted Email'].isin(["✅ SENT", "🔥 REPLIED"])) & 

                    (st.session_state.master_dataframe['Email'] != "N/A")

                ]

                if valid_targets.empty: st.error("⚠️ No pending emails to send.")

                else:

                    send_queue = []

                    for idx, row in valid_targets.iterrows():

                        send_queue.append({"Name": row['Name'], "Email": row['Email'], "Subject": f"Quick question regarding {row['Name']}'s website", "Body": row['Drafted Email']})

                        st.session_state.master_dataframe.at[idx, 'Drafted Email'] = "✅ SENT" # Optimistic update

                    

                    thread = threading.Thread(target=background_email_worker, args=(send_queue, sender_email, app_password, smtp_server, smtp_port, send_delay, st.session_state.current_campaign))

                    thread.daemon = True

                    thread.start()

                    st.toast("🚀 Background Sender Started!")

                    time.sleep(1)

                    st.rerun()

    else: st.info("👈 Run the scraper in Step 1 before drafting emails.")



# --- TAB 4: CAMPAIGN LOGS & IMAP REPLY SCANNER ---

with tab4:

    col_log, col_imap = st.columns([2, 1])

    with col_log:

        st.markdown("### 📜 Campaign History")

        conn = sqlite3.connect(DB_FILE)

        logs_df = pd.read_sql("SELECT * FROM logs", conn)

        conn.close()

        

        st.metric("Total Emails Sent", len(logs_df))

        if not logs_df.empty:

            st.dataframe(logs_df, use_container_width=True, hide_index=True)

        else: st.info("No emails have been sent yet.")

        

    with col_imap:

        st.markdown("### 📥 Reply Scanner")

        st.caption("Logs into your provider and flags prospects who have replied to your pitches.")

        if st.button("🔥 Scan Inbox for Replies", use_container_width=True):

            if not imap_server or not sender_email or not app_password:

                st.error("⚠️ Enter your IMAP Server, Email, and Password in the Engine Room.")

            else:

                with st.spinner(f"Connecting to {imap_server}..."):

                    try:

                        # 1. Connect to any standard IMAP server

                        mail = imaplib.IMAP4_SSL(imap_server)

                        mail.login(sender_email, app_password)

                        mail.select('inbox')

                        

                        # 2. Extract sent emails from local logs

                        conn = sqlite3.connect(DB_FILE)

                        sent_emails = pd.read_sql("SELECT email_sent_to FROM logs", conn)['email_sent_to'].tolist()

                        

                        replied_count = 0

                        for e in set(sent_emails):

                            if e == "N/A": continue

                            # 3. Securely search the inbox for emails FROM that prospect

                            status, data = mail.search(None, f'FROM "{e}"')

                            if status == 'OK' and data[0]:

                                # If an email is found, update the local SQLite database

                                conn.execute("UPDATE leads SET Drafted_Email='🔥 REPLIED' WHERE Email=?", (e,))

                                replied_count += 1

                        

                        conn.commit()

                        conn.close()

                        mail.logout()

                        

                        # Reload dataframe

                        st.session_state.master_dataframe = load_campaign_leads(st.session_state.current_campaign)

                        

                        if replied_count > 0: st.success(f"✅ Found {replied_count} replies! Dashboard updated.")

                        else: st.info("No new replies found.")

                    except Exception as e:

                        st.error(f"IMAP Error: {e}")
