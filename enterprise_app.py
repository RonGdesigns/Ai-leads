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
