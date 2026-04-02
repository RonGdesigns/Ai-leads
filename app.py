import streamlit as st
import requests
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import os

# --- 0. PAGE CONFIGURATION & CUSTOM CSS ---
st.set_page_config(page_title="Outbound AI", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(75, 108, 183, 0.4);
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. MEMORY & CORE FUNCTIONS ---
CONFIG_FILE = "user_settings.json"

def load_settings():
    """Loads saved keys from the user's computer if the file exists."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"google_key": "", "gemini_key": ""}

def save_settings(google_key, gemini_key):
    """Saves the keys to a local file on the user's computer."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"google_key": google_key, "gemini_key": gemini_key}, f)

def extract_and_audit(url):
    """Scrapes contact info AND runs the SEO/Tech Audit."""
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

def draft_dynamic_email(business_name, rating, audit_data, pitch_ssl, pitch_mobile, pitch_pixels, profession, offer, proof, cta, name, ai_api_key):
    if not ai_api_key: return "⚠️ Please enter your Gemini API Key in the settings sidebar."
    try:
        genai.configure(api_key=ai_api_key)
        # Upgraded to the live Flash model to prevent 404 crashes
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        prompt = f"""
        You are a professional {profession}. Write a short, friendly cold email to the owner of {business_name}.
        Their Google rating is {rating}.
        
        I just audited their website and found this:
        - SSL Secure: {audit_data['SSL']}
        - Mobile Optimized: {audit_data['Mobile']}
        - Tracking Pixels Installed: {audit_data['Pixels']}
        
        Important Instructions for this email:
        - Pitch SSL Issue: {pitch_ssl}
        - Pitch Mobile Issue: {pitch_mobile}
        - Pitch Tracking Pixels Issue: {pitch_pixels}
        
        If an instruction above is 'True', gently mention it as a problem hurting their traffic or security. 
        If they are all 'False', just congratulate them on a solid business and pivot straight to your main offer.
        
        Pitch: {offer}. Build trust by mentioning your past work with: {proof}. Call to action: {cta}. Keep it under 150 words. Sign off as {name}.
        """
        return model.generate_content(prompt).text
    except Exception as e: return f"⚠️ AI Error: {e}"

if 'master_dataframe' not in st.session_state:
    st.session_state.master_dataframe = None

# --- 2. SIDEBAR (The Engine Room) ---
saved_keys = load_settings()

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
    st.title("⚙️ Engine Room")
    st.write("Configure your API keys to power the software.")
    
    st.subheader("1. Data Engine")
    api_key = st.text_input("Google Places API Key:", type="password", value=saved_keys.get("google_key", ""))
    
    st.subheader("2. AI Engine")
    gemini_key = st.text_input("Gemini API Key:", type="password", value=saved_keys.get("gemini_key", ""))
    
    st.write("")
    if st.button("💾 Save my keys"):
        if api_key and gemini_key:
            save_settings(api_key, gemini_key)
            st.success("Keys securely saved for your next session!")
        else:
            st.warning("Please enter both keys before saving.")
            
    st.markdown("---")
    st.caption("🔒 Keys are stored securely in a local file on this computer. They are never sent to our servers.")

# --- 3. MAIN HEADER ---
st.markdown("<h1 style='text-align: center;'>🚀 Outbound AI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray; font-size: 1.2rem; margin-bottom: 2rem;'>The Ultimate Local B2B Lead Generator & Sales Machine</p>", unsafe_allow_html=True)

# --- 4. THE 3-STEP WORKFLOW (TABS) ---
tab1, tab2, tab3 = st.tabs(["🔍 1. Hunt (Scraper)", "📊 2. Analyze (Dashboard)", "🤖 3. Pitch (AI Agent)"])

# --- TAB 1: HUNT ---
with tab1:
    st.markdown("### Target Your Ideal Clients")
    
    colA, colB = st.columns([3, 1])
    with colA:
        search_query = st.text_input("Search Query", placeholder="e.g., HVAC companies in Dallas, TX")
    with colB:
        max_results = st.number_input("Max Leads", min_value=1, max_value=100, value=20)
        
    st.write("")
    
    if st.button("🚀 Launch Scraper", use_container_width=True):
        if not api_key or not search_query:
            st.error("⚠️ Please enter your Google Places API Key in the sidebar and a search query.")
        else:
            with st.spinner(f"Scanning the web for '{search_query}' and running SEO audits..."):
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
                            # Now pulls contact info AND tech audit data simultaneously
                            audit_data = extract_and_audit(website) 
                            
                            all_leads.append({
                                "Name": place.get('displayName', {}).get('text', 'N/A'),
                                "Rating": place.get('rating', 'N/A'),
                                "Reviews": place.get('userRatingCount', 0),
                                "Website": website,
                                "Email": audit_data["Email"],
                                "Instagram": audit_data["Instagram"],
                                "Phone": place.get('nationalPhoneNumber', 'N/A'),
                                "Address": place.get('formattedAddress', 'N/A'),
                                "Maps Link": place.get('googleMapsUri', 'N/A'),
                                "SSL": audit_data["SSL"],
                                "Mobile": audit_data["Mobile"],
                                "Pixels": audit_data["Pixels"],
                                "Pitch SSL": False,     # Default toggle state
                                "Pitch Mobile": False,  # Default toggle state
                                "Pitch Pixels": False   # Default toggle state
                            })
                            if len(all_leads) >= max_results: break
                    
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                    time.sleep(1)
                
                if all_leads:
                    df = pd.DataFrame(all_leads)
                    df['Temp_Rating'] = pd.to_numeric(df['Rating'], errors='coerce').fillna(0)
                    df = df.sort_values(by=['Temp_Rating', 'Name'], ascending=[False, True]).drop(columns=['Temp_Rating'])
                    st.session_state.master_dataframe = df
                    st.success(f"✅ Success! Found and audited {len(all_leads)} leads. Go to Step 2 to view them.")
                else:
                    st.warning("No operational leads found.")

# --- TAB 2: ANALYZE ---
with tab2:
    if st.session_state.master_dataframe is not None:
        df = st.session_state.master_dataframe
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Targets", len(df))
        m2.metric("No Website Found", len(df[df['Website'] == 'No Website Found']))
        m3.metric("Emails Scraped", len(df[df['Email'] != 'N/A']))
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            sort_by = st.selectbox("Sort Order:", ["Rating (High to Low)", "Name (A to Z)"])
        with col2:
            st.write("")
            st.write("")
            show_priority_only = st.checkbox("🎯 Priority Targets Only (No Website)")
        
        filtered_df = df.copy()
        if show_priority_only: filtered_df = filtered_df[filtered_df['Website'] == 'No Website Found']
        if sort_by == "Name (A to Z)": filtered_df = filtered_df.sort_values(by='Name', ascending=True)

        st.caption("Check the 'Pitch' boxes on the right side of the table to instruct the AI on which website errors to mention.")
        
        # Upgraded to st.data_editor to allow checking/unchecking the Pitch boxes
        edited_df = st.data_editor(
            filtered_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Maps Link": st.column_config.LinkColumn(), 
                "Website": st.column_config.LinkColumn(), 
                "Instagram": st.column_config.LinkColumn(),
                "Pitch SSL": st.column_config.CheckboxColumn("Pitch SSL?", default=False),
                "Pitch Mobile": st.column_config.CheckboxColumn("Pitch Mobile?", default=False),
                "Pitch Pixels": st.column_config.CheckboxColumn("Pitch Pixels?", default=False)
            }
        )
        
        # Save user toggle changes back to the master dataframe so Tab 3 can read them
        st.session_state.master_dataframe.update(edited_df)
        
        csv_data = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Export to CSV", data=csv_data, file_name="outbound_leads.csv", mime="text/csv")
    else:
        st.info("👈 Run the scraper in Step 1 to populate your dashboard.")

# --- TAB 3: PITCH ---
with tab3:
    if st.session_state.master_dataframe is not None:
        st.markdown("### 🤖 Setup Your AI Sales Persona")
        
        with st.container(border=True):
            col_a, col_b = st.columns(2)
            with col_a:
                user_profession = st.text_input("Your Profession/Industry:", value="Web Developer & SEO Specialist")
                your_name = st.text_input("Your Name:", value="Ronald")
            with col_b:
                social_proof = st.text_input("Social Proof/Past Clients:", value="Barber Station Detroit, From Scratch Bakery")
                call_to_action = st.text_input("Call to Action:", value="Are you open to a quick 5-minute chat this week?")
            
            core_offer = st.text_area("What is your core offer?", value="Building modern, SEO-optimized websites to drive local foot traffic and sales.")
        
        st.divider()
        
        st.markdown("### ✉️ Generate Draft")
        selected_business = st.selectbox("Select target to pitch:", st.session_state.master_dataframe['Name'].tolist())
        
        if st.button("Generate Cold Email"):
            lead_info = st.session_state.master_dataframe[st.session_state.master_dataframe['Name'] == selected_business].iloc[0]
            
            # Package the audit data for the AI prompt
            audit_dict = {"SSL": lead_info['SSL'], "Mobile": lead_info['Mobile'], "Pixels": lead_info['Pixels']}
            
            with st.spinner("AI is analyzing the business, reading your toggles, and writing your email..."):
                draft = draft_dynamic_email(
                    lead_info['Name'], 
                    lead_info['Rating'], 
                    audit_dict, 
                    lead_info['Pitch SSL'], 
                    lead_info['Pitch Mobile'], 
                    lead_info['Pitch Pixels'], 
                    user_profession, core_offer, social_proof, call_to_action, your_name, gemini_key
                )
                st.success("Draft Complete!")
                st.text_area("Copy your pitch:", value=draft, height=250)
                st.caption(f"**Found Email:** {lead_info['Email']}")
    else:
        st.info("👈 Run the scraper in Step 1 before drafting emails.")
