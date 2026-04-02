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

# --- 0. PAGE CONFIGURATION & CUSTOM CSS ---
st.set_page_config(page_title="Outbound AI | Enterprise", page_icon="🏢", layout="wide")

st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
        color: white; border-radius: 8px; border: none; font-weight: bold; padding: 0.5rem 1rem; transition: all 0.3s ease;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(56, 239, 125, 0.4); }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; padding-top: 10px; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. MEMORY, LOGGING & CORE FUNCTIONS ---
CONFIG_FILE = "user_settings.json"
LOG_FILE = "campaign_logs.csv"

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"google_key": "", "gemini_key": "", "sender_email": "", "smtp_pass": "", "smtp_server": "smtp.gmail.com", "smtp_port": 587}

def save_settings(google_key, gemini_key, sender_email, smtp_pass, smtp_server, smtp_port):
    with open(CONFIG_FILE, 'w') as f: 
        json.dump({"google_key": google_key, "gemini_key": gemini_key, "sender_email": sender_email, "smtp_pass": smtp_pass, "smtp_server": smtp_server, "smtp_port": smtp_port}, f)

def log_campaign(business_name, email_address):
    """Appends successful sends to a permanent local CSV log."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    new_record = pd.DataFrame([{"Date Sent": timestamp, "Business Name": business_name, "Email Sent To": email_address}])
    
    if os.path.exists(LOG_FILE):
        new_record.to_csv(LOG_FILE, mode='a', header=False, index=False)
    else:
        new_record.to_csv(LOG_FILE, mode='w', header=True, index=False)

@st.cache_data(ttl=86400, show_spinner=False)
def extract_and_audit(url):
    if not url or url == 'No Website Found': 
        return {"Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "N/A", "Mobile": "N/A", "Pixels": "N/A"}
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
            "Email": list(emails)[0] if emails else "N/A",
            "Instagram": list(ig_links)[0] if ig_links else "N/A",
            "Facebook": list(fb_links)[0] if fb_links else "N/A",
            "Twitter": list(tw_links)[0] if tw_links else "N/A",
            "SSL": has_ssl, "Mobile": has_mobile, "Pixels": has_pixels
        }
    except: 
        return {"Email": "N/A", "Instagram": "N/A", "Facebook": "N/A", "Twitter": "N/A", "SSL": "Error", "Mobile": "Error", "Pixels": "Error"}

def draft_dynamic_email(business_name, rating, audit_data, pitch_ssl, pitch_mobile, pitch_pixels, profession, offer, proof, cta, name, ai_api_key):
    if not ai_api_key: return "⚠️ Missing API Key."
    try:
        genai.configure(api_key=ai_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"""
        You are a professional {profession}. Write a short, friendly cold email to the owner of {business_name}. Rating: {rating}.
        Audit findings: SSL Secure: {audit_data['SSL']}, Mobile Optimized: {audit_data['Mobile']}, Pixels: {audit_data['Pixels']}.
        Instructions: Pitch SSL Issue: {pitch_ssl}, Pitch Mobile: {pitch_mobile}, Pitch Pixels: {pitch_pixels}.
        If an instruction is 'True', gently mention it as a problem. If all 'False', just pivot to your offer.
        Pitch: {offer}. Trust: {proof}. CTA: {cta}. Keep it under 150 words. Sign off as {name}.
        """
        return model.generate_content(prompt).text
    except Exception as e: return f"⚠️ AI Error: {e}"

def send_email(sender, password, recipient, subject, body, smtp_server, smtp_port):
    if not sender or not password: return False, "Missing Credentials."
    if not recipient or recipient == "N/A": return False, "No valid recipient email."
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return True, "Success"
    except Exception as e:
        return False, f"SMTP Error: {e}"

if 'master_dataframe' not in st.session_state: st.session_state.master_dataframe = None

# --- 2. SIDEBAR (Engine Room) ---
saved_keys = load_settings()

with st.sidebar:
    st.title("⚙️ Enterprise Engine")
    
    st.subheader("1. Scraper & AI")
    api_key = st.text_input("Google Places Key:", type="password", value=saved_keys.get("google_key", ""))
    gemini_key = st.text_input("Gemini Key:", type="password", value=saved_keys.get("gemini_key", ""))
    
    st.subheader("2. Mass SMTP Provider")
    st.caption("Use SendGrid or Mailgun for Enterprise scale.")
    smtp_server = st.text_input("SMTP Server:", value=saved_keys.get("smtp_server", "smtp.gmail.com"))
    smtp_port = st.text_input("SMTP Port:", value=str(saved_keys.get("smtp_port", 587)))
    sender_email = st.text_input("Auth Email:", value=saved_keys.get("sender_email", ""))
    smtp_pass = st.text_input("Auth Password:", type="password", value=saved_keys.get("smtp_pass", ""))
    
    if st.button("💾 Save Config"):
        save_settings(api_key, gemini_key, sender_email, smtp_pass, smtp_server, smtp_port)
        st.toast("✅ Infrastructure Saved!")

# --- 3. MAIN HEADER ---
st.markdown("<h1 style='text-align: center;'>🏢 Outbound AI | Enterprise</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray; font-size: 1.2rem; margin-bottom: 2rem;'>Scalable B2B Lead Gen & Bulk Outbound Tool</p>", unsafe_allow_html=True)

# --- 4. TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🔍 1. Mass Hunt", "📊 2. Filter & Setup", "🚀 3. Bulk Execution", "📜 4. Delivery Logs"])

# --- TAB 1: HUNT ---
with tab1:
    colA, colB = st.columns([3, 1])
    search_query = colA.text_input("Search Query", placeholder="e.g., HVAC in Chicago, IL")
    max_results = colB.number_input("Target Volume", min_value=1, max_value=500, value=50)
        
    if st.button("🚀 Launch Scraper Fleet", use_container_width=True):
        if not api_key: st.error("⚠️ Missing Google API Key.")
        else:
            with st.status("🚀 Mining Google Maps Data...", expanded=True) as status:
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
                    
                    st.write(f"Scraping batch... running technical audits...")
                    for place in data.get('places', []):
                        if place.get('businessStatus') == 'OPERATIONAL':
                            name = place.get('displayName', {}).get('text', 'N/A')
                            website = place.get('websiteUri', 'No Website Found')
                            audit = extract_and_audit(website) 
                            
                            all_leads.append({
                                "Name": name, "Rating": place.get('rating', 'N/A'), "Website": website,
                                "Email": audit["Email"], "SSL": audit["SSL"], "Mobile": audit["Mobile"], "Pixels": audit["Pixels"],
                                "Pitch SSL": False, "Pitch Mobile": False, "Pitch Pixels": False, "Drafted Email": ""
                            })
                            if len(all_leads) >= max_results: break
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                    time.sleep(1)
                
                if all_leads:
                    st.session_state.master_dataframe = pd.DataFrame(all_leads)
                    status.update(label=f"✅ Acquired {len(all_leads)} leads.", state="complete")
                else: status.update(label="⚠️ No leads found.", state="error")

# --- TAB 2: ANALYZE ---
with tab2:
    if st.session_state.master_dataframe is not None:
        df = st.session_state.master_dataframe
        filter_opt = st.radio("Isolate Targets:", ["All Leads", "Missing SSL", "Missing Pixels", "No Website"], horizontal=True)
        display_df = df.copy()
        if filter_opt == "Missing SSL": display_df = display_df[display_df['SSL'] == 'Fail']
        elif filter_opt == "Missing Pixels": display_df = display_df[display_df['Pixels'] == 'Fail']
        elif filter_opt == "No Website": display_df = display_df[display_df['Website'] == 'No Website Found']

        cols = [c for c in display_df.columns if c != 'Drafted Email']
        edited_df = st.data_editor(display_df[cols], use_container_width=True, hide_index=True)
        
        for index, row in edited_df.iterrows():
            st.session_state.master_dataframe.loc[st.session_state.master_dataframe['Name'] == row['Name'], edited_df.columns] = row.values
    else: st.info("👈 Run the scraper in Step 1.")

# --- TAB 3: BULK EXECUTION ---
with tab3:
    if st.session_state.master_dataframe is not None:
        st.markdown("### 🤖 Mass Persona Setup")
        with st.container(border=True):
            cA, cB = st.columns(2)
            user_profession = cA.text_input("Your Profession:")
            your_name = cA.text_input("Your Name:")
            social_proof = cB.text_input("Past Work:")
            call_to_action = cB.text_input("CTA:", value="Open to a 5-min chat?")
            core_offer = st.text_area("Core Offer:")
        
        st.divider()
        st.markdown("### ⚡ Bulk Operations")
        
        col1, col2 = st.columns(2)
        
        # BULK GENERATE
        with col1:
            if st.button("🤖 1. Bulk Generate All Pitches", use_container_width=True):
                if not user_profession or not your_name or not core_offer:
                    st.warning("⚠️ Fill out your Persona fields.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total = len(st.session_state.master_dataframe)
                    
                    for idx, row in st.session_state.master_dataframe.iterrows():
                        status_text.text(f"Writing email for {row['Name']} ({idx+1}/{total})...")
                        if not row['Drafted Email'] or row['Drafted Email'] != "✅ SENT":
                            audit_dict = {"SSL": row['SSL'], "Mobile": row['Mobile'], "Pixels": row['Pixels']}
                            draft = draft_dynamic_email(row['Name'], row['Rating'], audit_dict, row['Pitch SSL'], row['Pitch Mobile'], row['Pitch Pixels'], user_profession, core_offer, social_proof, call_to_action, your_name, gemini_key)
                            st.session_state.master_dataframe.at[idx, 'Drafted Email'] = draft
                        progress_bar.progress((idx + 1) / total)
                    
                    status_text.text("✅ All emails generated successfully!")
                    st.rerun()
                    
        # MASS SEND
        with col2:
            if st.button("🚀 2. Send Mass Email", type="primary", use_container_width=True):
                valid_targets = st.session_state.master_dataframe[
                    (st.session_state.master_dataframe['Drafted Email'] != "") & 
                    (st.session_state.master_dataframe['Drafted Email'] != "✅ SENT") & 
                    (st.session_state.master_dataframe['Email'] != "N/A")
                ]
                
                if valid_targets.empty:
                    st.error("⚠️ No pending emails to send. Generate pitches or ensure leads have valid email addresses.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total = len(valid_targets)
                    sent_count = 0
                    
                    for i, (idx, row) in enumerate(valid_targets.iterrows()):
                        status_text.text(f"Dispatching to {row['Email']} ({i+1}/{total})...")
                        subj = f"Quick question regarding {row['Name']}'s website"
                        success, msg = send_email(sender_email, smtp_pass, row['Email'], subj, row['Drafted Email'], smtp_server, smtp_port)
                        
                        if success:
                            st.session_state.master_dataframe.at[idx, 'Drafted Email'] = "✅ SENT"
                            log_campaign(row['Name'], row['Email'])
                            sent_count += 1
                        progress_bar.progress((i + 1) / total)
                        time.sleep(1) # Prevent rate limiting
                    
                    st.success(f"✅ Mass Send Complete: {sent_count} emails dispatched.")
                    st.rerun()

        st.caption("Note: You can view drafted emails by expanding the dashboard in Tab 2, or export them to CSV.")
    else: st.info("👈 Run the scraper in Step 1.")

# --- TAB 4: CAMPAIGN LOGS ---
with tab4:
    if os.path.exists(LOG_FILE):
        logs_df = pd.read_csv(LOG_FILE)
        st.metric("Total Successful Deliveries", len(logs_df))
        st.dataframe(logs_df, use_container_width=True, hide_index=True)
    else: st.info("No delivery history yet.")
