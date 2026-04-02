import streamlit as st
import requests
import pandas as pd
import time
import json
import os
import uuid
import re
import google.generativeai as genai

# --- 0. PAGE CONFIGURATION & CUSTOM CSS ---
st.set_page_config(page_title="Outbound AI | Enterprise", page_icon="🏢", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%); color: white; border-radius: 8px; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding-top: 10px; padding-bottom: 10px; font-weight: bold;}
    </style>
    """, unsafe_allow_html=True)

# --- 1. SECURITY & LICENSING MODULE ---
GUMROAD_PRODUCT_PERMALINK = "your_gumroad_permalink_here" # Change this to your Gumroad product link later
LICENSE_FILE = "license.json"

def get_hardware_id():
    """Gets a unique ID for the user's specific computer to prevent sharing."""
    return str(uuid.getnode())

def verify_gumroad_license(license_key):
    """Pings Gumroad's server to verify the purchase."""
    url = "https://api.gumroad.com/v2/licenses/verify"
    data = {
        "product_permalink": GUMROAD_PRODUCT_PERMALINK,
        "license_key": license_key,
        "increment_uses_count": "true" # Deducts 1 seat from their 5-10 seat limit
    }
    try:
        response = requests.post(url, data=data)
        result = response.json()
        if result.get("success") == True and result.get("purchase", {}).get("refunded") == False:
            return True
        return False
    except:
        return False

def check_local_license():
    """Checks if this computer is already unlocked."""
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r') as f:
                data = json.load(f)
                if data.get("hardware_id") == get_hardware_id() and data.get("is_active") == True:
                    return True
        except:
            pass
    return False

# --- 2. THE LOCK SCREEN ---
if not check_local_license():
    st.markdown("<h1 style='text-align: center;'>🔒 Activation Required</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Please enter your Gumroad License Key to unlock this device.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_key = st.text_input("License Key:", type="password", placeholder="XXXX-XXXX-XXXX-XXXX")
        if st.button("Activate Device", use_container_width=True):
            if not user_key:
                st.warning("Please enter a key.")
            else:
                with st.spinner("Verifying with Gumroad servers..."):
                    if verify_gumroad_license(user_key):
                        with open(LICENSE_FILE, 'w') as f:
                            json.dump({
                                "license_key": user_key,
                                "hardware_id": get_hardware_id(),
                                "is_active": True
                            }, f)
                        st.success("✅ Device Activated! Loading Enterprise Dashboard...")
                        time.sleep(2)
                        st.rerun() 
                    else:
                        st.error("❌ Invalid, refunded, or expired key. Or maximum seats reached.")
    st.stop() # Stops the rest of the app from loading if not activated

# =====================================================================
# --- THE MAIN ENTERPRISE APPLICATION STARTS HERE (IF UNLOCKED) ---
# =====================================================================

# --- 3. ENTERPRISE CORE FUNCTIONS ---
CONFIG_FILE = "enterprise_settings.json"

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"google_key": "", "gemini_key": "", "webhook": ""}

def save_settings(g_key, gem_key, hook):
    with open(CONFIG_FILE, 'w') as f: json.dump({"google_key": g_key, "gemini_key": gem_key, "webhook": hook}, f)

def find_decision_maker(business_name):
    """Simulates a lookup for the business owner's name."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://html.duckduckgo.com/html/?q={business_name}+owner+founder+linkedin"
        res = requests.get(url, headers=headers, timeout=4)
        match = re.search(r'>([^<]+) - (?:Owner|Founder)', res.text, re.I)
        if match:
            name = match.group(1).strip()
            return name if len(name) < 20 else "Owner"
        return "Owner"
    except:
        return "Owner"

def generate_pitch(business, name, profession, offer, proof, cta, signature, api_key):
    if not api_key: return "Missing Gemini API Key"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"You are a {profession}. Write a cold email to {name}, the owner of {business}. Pitch: {offer}. Proof: {proof}. CTA: {cta}. Sign off as {signature}. Keep it under 100 words. Be natural."
        return model.generate_content(prompt).text
    except: return "AI Error"

if 'ent_dataframe' not in st.session_state: 
    st.session_state.ent_dataframe = None

# --- 4. SIDEBAR (Engine Room) ---
settings = load_settings()
with st.sidebar:
    st.title("⚙️ Enterprise Engine")
    g_key = st.text_input("Google Places API Key:", type="password", value=settings.get("google_key", ""))
    gem_key = st.text_input("Gemini API Key:", type="password", value=settings.get("gemini_key", ""))
    webhook_url = st.text_input("CRM Webhook URL (Zapier/GHL):", value=settings.get("webhook", ""))
    if st.button("💾 Save Settings"): 
        save_settings(g_key, gem_key, webhook_url)
        st.success("Saved locally!")

# --- 5. MAIN UI ---
st.markdown("<h1 style='text-align: center;'>🏢 Outbound AI | Enterprise Edition</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Bulk Data Mining & Automated CRM Pipeline Routing</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 1. Data Mining", "🤖 2. Bulk AI Engine", "⚡ 3. CRM Routing"])

with tab1:
    colA, colB = st.columns([3, 1])
    search_query = colA.text_input("Target Market", placeholder="e.g., Dentists in Troy, MI")
    max_leads = colB.number_input("Max Leads", min_value=1, value=10)
    
    if st.button("🚀 Mine Data & Hunt Decision Makers", use_container_width=True):
        if not g_key:
            st.error("Please enter a Google Places API key in the sidebar.")
        else:
            with st.spinner("Extracting leads and hunting decision makers... This may take a minute."):
                url = 'https://places.googleapis.com/v1/places:searchText'
                headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': g_key, 'X-Goog-FieldMask': 'places.displayName,places.websiteUri,places.nationalPhoneNumber'}
                
                payload = {'textQuery': search_query, 'pageSize': max_leads}
                res = requests.post(url, headers=headers, json=payload).json()
                
                leads = []
                for place in res.get('places', []):
                    b_name = place.get('displayName', {}).get('text', 'N/A')
                    owner = find_decision_maker(b_name)
                    leads.append({
                        "Business": b_name,
                        "Website": place.get('websiteUri', 'No Website Found'),
                        "Phone": place.get('nationalPhoneNumber', 'N/A'),
                        "Decision Maker": owner,
                        "AI Pitch": "" 
                    })
                    if len(leads) >= max_leads: break
                
                st.session_state.ent_dataframe = pd.DataFrame(leads)
                st.success(f"✅ Successfully mined {len(leads)} leads!")

with tab2:
    if st.session_state.ent_dataframe is not None:
        st.markdown("### Configure Bulk Email Rules")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            prof = col1.text_input("Profession", "Web Developer")
            offer = col2.text_input("Offer", "Modernizing your web presence to drive traffic.")
            proof = col1.text_input("Proof", "Decent Detroit")
            cta = col2.text_input("CTA", "Open to a 5 min chat?")
            sig = col1.text_input("Signature", "Ronald")
        
        st.write("")
        if st.button("🤖 Generate Pitches for ALL Leads", use_container_width=True):
            if not gem_key:
                st.error("Please enter your Gemini API key in the sidebar.")
            else:
                df = st.session_state.ent_dataframe
                progress_bar = st.progress(0)
                status = st.empty()
                
                for index, row in df.iterrows():
                    status.info(f"Writing highly-personalized email to {row['Decision Maker']} at {row['Business']}...")
                    pitch = generate_pitch(row['Business'], row['Decision Maker'], prof, offer, proof, cta, sig, gem_key)
                    df.at[index, 'AI Pitch'] = pitch
                    progress_bar.progress((index + 1) / len(df))
                    time.sleep(1) # Prevent AI rate limiting
                    
                st.session_state.ent_dataframe = df
                status.success("✅ Bulk AI Generation Complete! Check the Data Table below.")
                st.dataframe(df)
    else:
        st.info("👈 Run the Data Miner in Step 1 first.")

with tab3:
    if st.session_state.ent_dataframe is not None:
        st.markdown("### Push Pipeline to CRM")
        st.write("Push your enriched leads and AI emails directly into your CRM (GoHighLevel, HubSpot, Salesforce) via Webhook.")
        st.dataframe(st.session_state.ent_dataframe)
        
        col_down, col_push = st.columns(2)
        with col_down:
            csv_data = st.session_state.ent_dataframe.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download CSV Backup", data=csv_data, file_name="enterprise_leads.csv", mime="text/csv", use_container_width=True)
            
        with col_push:
            if st.button("⚡ Push to CRM via Webhook", use_container_width=True):
                if not webhook_url:
                    st.error("⚠️ Please enter your CRM Webhook URL in the sidebar Engine Room.")
                else:
                    with st.spinner("Transmitting data packet..."):
                        payload = st.session_state.ent_dataframe.to_dict(orient='records')
                        try:
                            resp = requests.post(webhook_url, json=payload)
                            if resp.ok:
                                st.success("✅ Successfully pushed to CRM pipeline!")
                            else:
                                st.error(f"CRM rejected the payload. Status code: {resp.status_code}")
                        except Exception as e:
                            st.error(f"Connection failed: {e}")
    else:
        st.info("👈 Run the Data Miner in Step 1 first.")
