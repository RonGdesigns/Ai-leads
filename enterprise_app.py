import streamlit as st
import requests
import pandas as pd
import time
import json
import os
import google.generativeai as genai

st.set_page_config(page_title="Outbound AI | Enterprise", page_icon="🏢", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%); color: white; border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

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
    """
    Simulates a SERP lookup. Queries DuckDuckGo for the business name + 'Owner LinkedIn'.
    In a real $2,500 software, you would replace this with an official API like Apollo.io or Hunter.io.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://html.duckduckgo.com/html/?q={business_name}+owner+founder+linkedin"
        res = requests.get(url, headers=headers, timeout=4)
        
        # Look for typical LinkedIn title formats like "John Doe - Owner - Business Name"
        import re
        match = re.search(r'>([^<]+) - (?:Owner|Founder)', res.text, re.I)
        if match:
            name = match.group(1).strip()
            # Clean up the name if it's too long
            return name if len(name) < 20 else "Owner"
        return "Owner"
    except:
        return "Owner"

def generate_pitch(business, name, profession, offer, proof, cta, signature, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"You are a {profession}. Write a cold email to {name}, the owner of {business}. Pitch: {offer}. Proof: {proof}. CTA: {cta}. Sign off as {signature}. Keep it under 100 words."
    try: return model.generate_content(prompt).text
    except: return "AI Error"

if 'ent_dataframe' not in st.session_state: st.session_state.ent_dataframe = None

settings = load_settings()
with st.sidebar:
    st.title("⚙️ Enterprise Engine")
    g_key = st.text_input("Google Places API Key:", type="password", value=settings.get("google_key", ""))
    gem_key = st.text_input("Gemini API Key:", type="password", value=settings.get("gemini_key", ""))
    webhook_url = st.text_input("CRM Webhook URL (Zapier/GHL):", value=settings.get("webhook", ""))
    if st.button("💾 Save Settings"): save_settings(g_key, gem_key, webhook_url); st.success("Saved!")

st.markdown("<h1 style='text-align: center;'>🏢 Outbound AI | Enterprise Edition</h1>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 1. Data Mining", "🤖 2. Bulk AI Engine", "⚡ 3. CRM Routing"])

with tab1:
    search_query = st.text_input("Target Market", placeholder="e.g., Dentists in Troy, MI")
    if st.button("Mine Data"):
        with st.spinner("Extracting leads and hunting decision makers..."):
            url = 'https://places.googleapis.com/v1/places:searchText'
            headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': g_key, 'X-Goog-FieldMask': 'places.displayName,places.websiteUri'}
            payload = {'textQuery': search_query, 'pageSize': 10} # Kept low for testing speed
            res = requests.post(url, headers=headers, json=payload).json()
            
            leads = []
            for place in res.get('places', []):
                b_name = place.get('displayName', {}).get('text', 'N/A')
                owner = find_decision_maker(b_name)
                leads.append({
                    "Business": b_name,
                    "Website": place.get('websiteUri', 'N/A'),
                    "Decision Maker": owner,
                    "AI Pitch": "" # Placeholder for Tab 2
                })
            
            st.session_state.ent_dataframe = pd.DataFrame(leads)
            st.success("Mining Complete!")

with tab2:
    if st.session_state.ent_dataframe is not None:
        st.write("Configure your bulk email rules:")
        col1, col2 = st.columns(2)
        prof = col1.text_input("Profession", "Web Developer")
        offer = col2.text_input("Offer", "Modernizing your web presence.")
        proof = col1.text_input("Proof", "Decent Detroit")
        cta = col2.text_input("CTA", "Open to a 5 min chat?")
        sig = st.text_input("Signature", "Ronald")
        
        if st.button("Generate Pitches for ALL Leads"):
            df = st.session_state.ent_dataframe
            progress_bar = st.progress(0)
            status = st.empty()
            
            for index, row in df.iterrows():
                status.write(f"Writing email for {row['Business']}...")
                pitch = generate_pitch(row['Business'], row['Decision Maker'], prof, offer, proof, cta, sig, gem_key)
                df.at[index, 'AI Pitch'] = pitch
                progress_bar.progress((index + 1) / len(df))
                time.sleep(1) # Prevent AI rate limiting
                
            st.session_state.ent_dataframe = df
            status.success("Bulk Generation Complete!")
            st.dataframe(df)

with tab3:
    if st.session_state.ent_dataframe is not None:
        st.write("Push your enriched leads and AI emails directly into your CRM (GoHighLevel, HubSpot, Salesforce) via Webhook.")
        st.dataframe(st.session_state.ent_dataframe)
        
        if st.button("⚡ Push to CRM"):
            if not webhook_url:
                st.error("Please enter your CRM Webhook URL in the sidebar.")
            else:
                with st.spinner("Transmitting data..."):
                    # Convert dataframe to JSON and send it to the CRM
                    payload = st.session_state.ent_dataframe.to_dict(orient='records')
                    try:
                        resp = requests.post(webhook_url, json=payload)
                        if resp.ok:
                            st.success("Successfully pushed to CRM pipeline!")
                        else:
                            st.error(f"CRM rejected the payload. Status code: {resp.status_code}")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
