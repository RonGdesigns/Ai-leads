import streamlit as st
import requests
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import os

st.set_page_config(page_title="Outbound AI | Pro", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%); color: white; border-radius: 8px; border: none; font-weight: bold; padding: 0.5rem 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding-top: 10px; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "user_settings.json"

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"google_key": "", "gemini_key": ""}

def save_settings(google_key, gemini_key):
    with open(CONFIG_FILE, 'w') as f: json.dump({"google_key": google_key, "gemini_key": gemini_key}, f)

def extract_and_audit(url):
    """Scrapes contact info AND runs a technical SEO/Marketing audit."""
    if not url or url == 'No Website Found': 
        return {"Email": "N/A", "Instagram": "N/A", "SSL": "N/A", "Mobile": "N/A", "Pixels": "N/A"}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        html_text = response.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # 1. Contact Info
        emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html_text))
        ig_links = set([a['href'] for a in soup.find_all('a', href=True) if 'instagram.com' in a['href']])
        
        # 2. Tech Audit
        has_ssl = "Pass" if url.startswith("https") else "Fail"
        has_mobile = "Pass" if soup.find("meta", attrs={"name": "viewport"}) else "Fail"
        has_pixels = "Pass" if re.search(r'gtm\.js|analytics\.js|gtag|fbevents\.js', html_text, re.I) else "Fail"
        
        return {
            "Email": list(emails)[0] if emails else "N/A",
            "Instagram": list(ig_links)[0] if ig_links else "N/A",
            "SSL": has_ssl,
            "Mobile": has_mobile,
            "Pixels": has_pixels
        }
    except: 
        return {"Email": "N/A", "Instagram": "N/A", "SSL": "Error", "Mobile": "Error", "Pixels": "Error"}

def draft_audit_email(business_name, rating, audit_data, profession, offer, proof, cta, name, ai_api_key):
    if not ai_api_key: return "⚠️ Please enter your Gemini API Key."
    try:
        genai.configure(api_key=ai_api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        # The prompt now includes the tech audit!
        prompt = f"""
        You are a professional {profession}. Write a short, friendly cold email to the owner of {business_name}.
        Their Google rating is {rating}.
        
        I just audited their website and found this:
        - SSL Secure: {audit_data['SSL']}
        - Mobile Optimized: {audit_data['Mobile']}
        - Tracking Pixels Installed: {audit_data['Pixels']}
        
        If they failed any of those checks, gently mention it as a problem hurting their traffic or security. 
        Pitch: {offer}. Build trust: {proof}. Call to action: {cta}. Keep it under 150 words. Sign off as {name}.
        """
        return model.generate_content(prompt).text
    except Exception as e: return f"⚠️ AI Error: {e}"

if 'master_dataframe' not in st.session_state: st.session_state.master_dataframe = None

saved_keys = load_settings()
with st.sidebar:
    st.title("⚙️ Engine Room")
    api_key = st.text_input("Google Places API Key:", type="password", value=saved_keys.get("google_key", ""))
    gemini_key = st.text_input("Gemini API Key:", type="password", value=saved_keys.get("gemini_key", ""))
    if st.button("💾 Save Keys"): save_settings(api_key, gemini_key); st.success("Saved!")

st.markdown("<h1 style='text-align: center;'>🚀 Outbound AI | Pro Auditor</h1>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 1. Hunt", "📊 2. Audit Dashboard", "🤖 3. Pitch"])

with tab1:
    colA, colB = st.columns([3, 1])
    search_query = colA.text_input("Search Query", placeholder="e.g., Roofers in Detroit")
    max_results = colB.number_input("Max Leads", min_value=1, value=20)
    
    if st.button("🚀 Run Scraper & Auditor", use_container_width=True):
        if not api_key: st.error("⚠️ Missing Google API Key")
        else:
            with st.spinner("Scraping and auditing websites..."):
                url = 'https://places.googleapis.com/v1/places:searchText'
                headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': 'places.displayName,places.websiteUri,places.rating,places.businessStatus'}
                all_leads = []
                
                payload = {'textQuery': search_query, 'pageSize': max_results}
                res = requests.post(url, headers=headers, json=payload).json()
                
                for place in res.get('places', []):
                    if place.get('businessStatus') == 'OPERATIONAL':
                        website = place.get('websiteUri', 'No Website Found')
                        audit = extract_and_audit(website)
                        
                        all_leads.append({
                            "Name": place.get('displayName', {}).get('text', 'N/A'),
                            "Rating": place.get('rating', 'N/A'),
                            "Website": website,
                            "Email": audit["Email"],
                            "SSL Cert": audit["SSL"],
                            "Mobile Ready": audit["Mobile"],
                            "Pixels": audit["Pixels"]
                        })
                        if len(all_leads) >= max_results: break
                
                st.session_state.master_dataframe = pd.DataFrame(all_leads)
                st.success("✅ Extraction and Audit Complete!")

with tab2:
    if st.session_state.master_dataframe is not None:
        df = st.session_state.master_dataframe
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇️ Export to CSV", data=df.to_csv(index=False).encode('utf-8'), file_name="audited_leads.csv", mime="text/csv")

with tab3:
    if st.session_state.master_dataframe is not None:
        user_profession = st.text_input("Profession:", value="Web Developer & SEO Specialist")
        core_offer = st.text_input("Offer:", value="Fixing technical website errors to increase local ranking.")
        social_proof = st.text_input("Proof:", value="Barber Station Detroit, Decent Detroit")
        call_to_action = st.text_input("CTA:", value="Can I send you a quick video showing how to fix this?")
        your_name = st.text_input("Name:", value="Ronald")
        
        target = st.selectbox("Select Target:", st.session_state.master_dataframe['Name'].tolist())
        
        if st.button("Generate Audit Pitch"):
            row = st.session_state.master_dataframe[st.session_state.master_dataframe['Name'] == target].iloc[0]
            audit_dict = {"SSL": row['SSL Cert'], "Mobile": row['Mobile Ready'], "Pixels": row['Pixels']}
            
            with st.spinner("AI is analyzing the audit..."):
                draft = draft_audit_email(row['Name'], row['Rating'], audit_dict, user_profession, core_offer, social_proof, call_to_action, your_name, gemini_key)
                st.text_area("Pitch:", value=draft, height=250)
