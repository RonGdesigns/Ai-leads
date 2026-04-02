import streamlit as st
import requests
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

# --- 0. PAGE CONFIGURATION & CUSTOM CSS ---
st.set_page_config(page_title="Outbound AI | Pro", page_icon="🚀", layout="wide")

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

# --- 1. MEMORY, LOGGING & CORE FUNCTIONS ---
CONFIG_FILE = "user_settings.json"
LOG_FILE = "campaign_logs.csv"
STATUS_FILE = "batch_status.json"

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"google_key": "", "gemini_key": "", "smtp_server": "smtp.gmail.com", "smtp_port": "587", "sender_email": "", "app_password": ""}

def save_settings(google_key, gemini_key, smtp_server, smtp_port, sender_email, app_password):
    with open(CONFIG_FILE, 'w') as f: 
        json.dump({"google_key": google_key, "gemini_key": gemini_key, "smtp_server": smtp_server, "smtp_port": smtp_port, "sender_email": sender_email, "app_password": app_password}, f)

def log_campaign(business_name, email_address):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    new_record = pd.DataFrame([{"Date Sent": timestamp, "Business Name": business_name, "Email Sent To": email_address}])
    if os.path.exists(LOG_FILE): new_record.to_csv(LOG_FILE, mode='a', header=False, index=False)
    else: new_record.to_csv(LOG_FILE, mode='w', header=True, index=False)

def background_email_worker(targets, sender, password, smtp_server, smtp_port, delay):
    """Runs in a separate CPU thread so the Streamlit UI does not freeze."""
    status = {"is_running": True, "total": len(targets), "sent": 0, "errors": 0}
    with open(STATUS_FILE, "w") as f: json.dump(status, f)
    
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
            
            log_campaign(target['Name'], target['Email'])
            status['sent'] += 1
        except Exception as e:
            status['errors'] += 1
            
        with open(STATUS_FILE, "w") as f: json.dump(status, f)
        time.sleep(delay)
        
    status["is_running"] = False
    with open(STATUS_FILE, "w") as f: json.dump(status, f)

def check_background_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"is_running": False, "total": 0, "sent": 0, "errors": 0}

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
        
        return {
            "Email": list(emails)[0] if emails else "N/A", "Instagram": list(ig_links)[0] if ig_links else "N/A",
            "Facebook": list(fb_links)[0] if fb_links else "N/A", "Twitter": list(tw_links)[0] if tw_links else "N/A",
            "SSL": has_ssl, "Mobile": has_mobile, "Pixels": has_pixels
        }
    except: return {"Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "Error", "Mobile": "Error", "Pixels": "Error"}

def draft_dynamic_email(business_name, rating, audit_data, pitch_ssl, pitch_mobile, pitch_pixels, profession, offer, proof, cta, name, ai_api_key):
    if not ai_api_key: return "⚠️ Please enter your Gemini API Key in the settings sidebar."
    try:
        genai.configure(api_key=ai_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"""
        You are a professional {profession}. Write a short, friendly cold email to the owner of {business_name}. Rating: {rating}.
        Audit: SSL Secure: {audit_data['SSL']}, Mobile Optimized: {audit_data['Mobile']}, Pixels: {audit_data['Pixels']}
        Instructions - Pitch SSL: {pitch_ssl}, Pitch Mobile: {pitch_mobile}, Pitch Pixels: {pitch_pixels}.
        If True, gently mention it as a problem. If all False, congratulate them on a solid business and pivot to offer.
        Pitch: {offer}. Trust: {proof}. CTA: {cta}. Keep it under 150 words. Sign off as {name}.
        """
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

if 'master_dataframe' not in st.session_state: st.session_state.master_dataframe = None

# --- 2. SIDEBAR ---
saved_keys = load_settings()

with st.sidebar:
    st.title("⚙️ Engine Room")
    st.subheader("1. Data Engine")
    api_key = st.text_input("Google Places API Key:", type="password", value=saved_keys.get("google_key", ""))
    st.subheader("2. AI Engine")
    gemini_key = st.text_input("Gemini API Key:", type="password", value=saved_keys.get("gemini_key", ""))
    st.subheader("3. SMTP Engine")
    smtp_server = st.text_input("SMTP Server:", value=saved_keys.get("smtp_server", "smtp.gmail.com"))
    smtp_port = st.text_input("SMTP Port:", value=saved_keys.get("smtp_port", "587"))
    sender_email = st.text_input("Auth Username / Email:", value=saved_keys.get("sender_email", ""))
    app_password = st.text_input("Auth Password / API Key:", type="password", value=saved_keys.get("app_password", ""))
    
    if st.button("💾 Save Settings"):
        save_settings(api_key, gemini_key, smtp_server, smtp_port, sender_email, app_password)
        st.toast("✅ Settings securely saved!")

# --- 3. MAIN HEADER ---
st.markdown("<h1 style='text-align: center;'>🚀 Outbound AI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray; font-size: 1.2rem; margin-bottom: 2rem;'>Local B2B Lead Generation & Outbound CRM</p>", unsafe_allow_html=True)

# --- 4. TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🔍 1. Hunt", "📊 2. Analyze", "🚀 3. Pitch & Send", "📜 4. Campaign Logs"])

# --- TAB 1: HUNT ---
with tab1:
    st.markdown("### 🎯 Target Your Ideal Clients")
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
        elif not niche or not region: st.warning("⚠️ Please fill out at least the Niche and State/Country fields.")
        else:
            search_query = f"{niche} in {city}, {region}" if city else f"{niche} in {region}"
            with st.status(f"🚀 Launching Scraper Engine...", expanded=True) as status:
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
                            business_name = place.get('displayName', {}).get('text', 'N/A')
                            website = place.get('websiteUri', 'No Website Found')
                            audit_data = extract_and_audit(website) 
                            all_leads.append({
                                "Name": business_name, "Rating": place.get('rating', 'N/A'), "Reviews": place.get('userRatingCount', 0),
                                "Website": website, "Email": audit_data["Email"], "Instagram": audit_data["Instagram"],
                                "Facebook": audit_data["Facebook"], "Twitter": audit_data["Twitter"],
                                "Phone": place.get('nationalPhoneNumber', 'N/A'), "Address": place.get('formattedAddress', 'N/A'),
                                "Maps Link": place.get('googleMapsUri', 'N/A'), "SSL": audit_data["SSL"],
                                "Mobile": audit_data["Mobile"], "Pixels": audit_data["Pixels"],
                                "Pitch SSL": False, "Pitch Mobile": False, "Pitch Pixels": False, "Drafted Email": ""
                            })
                            if len(all_leads) >= max_results: break
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                    time.sleep(1)
                
                if all_leads:
                    st.session_state.master_dataframe = pd.DataFrame(all_leads)
                    status.update(label=f"✅ Acquired {len(all_leads)} leads.", state="complete")
                else: status.update(label="⚠️ No operational leads found.", state="error")

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
        for index, row in edited_df.iterrows():
            st.session_state.master_dataframe.loc[st.session_state.master_dataframe['Name'] == row['Name'], edited_df.columns] = row.values

        csv_data = st.session_state.master_dataframe.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Export Master List to CSV", data=csv_data, file_name="outbound_leads.csv", mime="text/csv")
    else: st.info("👈 Run the scraper in Step 1 to populate your dashboard.")

# --- TAB 3: PITCH & SEND ---
with tab3:
    if st.session_state.master_dataframe is not None:
        st.markdown("### 🤖 AI Sales Persona")
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

        # --- SINGLE EXECUTION ---
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
                        st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = draft
                        st.rerun() 
        with col_send:
            if st.button("🚀 2. Send Email Now", type="primary", use_container_width=True):
                if not current_draft or current_draft == "✅ SENT": st.error("⚠️ Generate a fresh pitch first.")
                elif lead_info['Email'] == "N/A": st.error("⚠️ No email scraped.")
                else:
                    with st.spinner("Dispatching..."):
                        success, message = send_email(sender_email, app_password, lead_info['Email'], f"Quick question regarding {lead_info['Name']}'s website", current_draft, smtp_server, smtp_port)
                        if success:
                            st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = "✅ SENT"
                            log_campaign(lead_info['Name'], lead_info['Email'])
                            st.rerun()
                        else: st.error(message)

        if current_draft and current_draft != "✅ SENT":
            edited_draft = st.text_area("Review and Edit Email:", value=current_draft, height=250)
            if edited_draft != current_draft: st.session_state.master_dataframe.at[lead_idx, 'Drafted Email'] = edited_draft
        elif current_draft == "✅ SENT": st.success("✅ Email sent and logged!")

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()

        # --- BULK EXECUTION (MULTI-THREADED) ---
        st.markdown("### ⚡ Bulk Mass Sender")
        st.caption("Generate and send emails in the background. You can keep using the app while this runs.")
        
        # UI for the Background Process
        bg_status = check_background_status()
        if bg_status["is_running"]:
            st.info(f"⚙️ **Background Worker Running:** {bg_status['sent']} / {bg_status['total']} emails dispatched. ({bg_status['errors']} errors).")
            if st.button("🔄 Refresh Status"): st.rerun()
            st.progress(bg_status['sent'] / max(1, bg_status['total']))
        else:
            if bg_status["total"] > 0:
                st.success(f"✅ Last Batch Finished: {bg_status['sent']} sent, {bg_status['errors']} errors.")
        
        send_delay = st.slider("Throttle (Seconds between emails):", min_value=1, max_value=30, value=3)
        bulk_col1, bulk_col2 = st.columns(2)
        
        with bulk_col1:
            if st.button("🤖 Bulk Generate All Pitches", use_container_width=True, disabled=bg_status["is_running"]):
                if not user_profession or not your_name or not core_offer: st.warning("⚠️ Fill out your Persona fields first.")
                else:
                    progress_bar = st.progress(0)
                    total = len(st.session_state.master_dataframe)
                    for idx, row in st.session_state.master_dataframe.iterrows():
                        if not row['Drafted Email'] or row['Drafted Email'] != "✅ SENT":
                            draft = draft_dynamic_email(row['Name'], row['Rating'], {"SSL": row['SSL'], "Mobile": row['Mobile'], "Pixels": row['Pixels']}, row['Pitch SSL'], row['Pitch Mobile'], row['Pitch Pixels'], user_profession, core_offer, social_proof, call_to_action, your_name, gemini_key)
                            st.session_state.master_dataframe.at[idx, 'Drafted Email'] = draft
                        progress_bar.progress((idx + 1) / total)
                    st.rerun()
                    
        with bulk_col2:
            if st.button("🚀 Start Mass Background Sending", type="primary", use_container_width=True, disabled=bg_status["is_running"]):
                valid_targets = st.session_state.master_dataframe[
                    (st.session_state.master_dataframe['Drafted Email'] != "") & 
                    (st.session_state.master_dataframe['Drafted Email'] != "✅ SENT") & 
                    (st.session_state.master_dataframe['Email'] != "N/A")
                ]
                
                if valid_targets.empty: st.error("⚠️ No pending emails to send.")
                else:
                    # Package the data for the background thread
                    send_queue = []
                    for idx, row in valid_targets.iterrows():
                        send_queue.append({"Name": row['Name'], "Email": row['Email'], "Subject": f"Quick question regarding {row['Name']}'s website", "Body": row['Drafted Email']})
                        st.session_state.master_dataframe.at[idx, 'Drafted Email'] = "✅ SENT" # Mark optimistically in UI
                        
                    # Spin up the daemon thread
                    thread = threading.Thread(target=background_email_worker, args=(send_queue, sender_email, app_password, smtp_server, smtp_port, send_delay))
                    thread.daemon = True # Allows app to close even if thread is running
                    thread.start()
                    
                    st.toast("🚀 Background Sender Started!")
                    time.sleep(1)
                    st.rerun()
    else: st.info("👈 Run the scraper in Step 1 before drafting emails.")

# --- TAB 4: CAMPAIGN LOGS ---
with tab4:
    st.markdown("### 📜 Campaign History")
    if os.path.exists(LOG_FILE):
        logs_df = pd.read_csv(LOG_FILE)
        st.metric("Total Emails Sent", len(logs_df))
        st.dataframe(logs_df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Export Full History", data=logs_df.to_csv(index=False).encode('utf-8'), file_name="campaign_history.csv", mime="text/csv")
    else: st.info("No emails have been sent yet.")
