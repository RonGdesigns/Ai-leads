"use client";

import React, { useState, useEffect } from "react";
import { Settings2, ShieldAlert, Mail, CheckSquare, Cpu, Send, Loader2 } from "lucide-react";

const TONE_OPTIONS = [
  "Direct & Professional",
  "Consultative & Helpful",
  "Witty & Humorous",
  "Relaxed & Conversational",
  "Aggressive & Sales-Driven",
  "Academic & Data-Driven",
  "Storyteller / Narrative",
  "Urgency & Scarcity",
  "Hyper-Personalized & Warm",
  "Polished Enterprise"
];

export default function PitchDashboard() {
  // --- STATE: PERSONA & CREDENTIALS ---
  const [yourName, setYourName] = useState("");
  const [profession, setProfession] = useState("");
  const [offer, setOffer] = useState("");
  const [tone, setTone] = useState(TONE_OPTIONS[0]);
  
  const [geminiKey, setGeminiKey] = useState("");
  const [senderEmail, setSenderEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");

  // --- STATE: LEADS & SELECTION ---
  const [leads, setLeads] = useState<any[]>([]);
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set());
  
  // --- STATE: TERMINAL & LOADING ---
  const [isProcessing, setIsProcessing] = useState(false);
  const [terminalLogs, setTerminalLogs] = useState<string[]>(["System initialized. Awaiting orders..."]);

  const addLog = (msg: string) => {
    setTerminalLogs((prev) => [...prev, `> ${msg}`]);
  };

  // Fetch leads on load
  const fetchLeads = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/leads/Default%20Campaign");
      if (response.ok) {
        const data = await response.json();
        setLeads(data.leads);
      }
    } catch (error) {
      addLog("ERROR: Could not connect to Python Engine.");
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const toggleLeadSelection = (email: string) => {
    const newSet = new Set(selectedEmails);
    if (newSet.has(email)) newSet.delete(email);
    else newSet.add(email);
    setSelectedEmails(newSet);
  };

  const toggleAll = () => {
    if (selectedEmails.size === leads.filter(l => l.Email !== "N/A").length) {
      setSelectedEmails(newSet => new Set());
    } else {
      const allValidEmails = leads.filter(l => l.Email !== "N/A").map(l => l.Email);
      setSelectedEmails(new Set(allValidEmails));
    }
  };

  // --- ACTIONS ---

  const handleBulkGenerate = async () => {
    if (!geminiKey || !profession || !offer || !yourName) {
      alert("Please fill out your Persona and Gemini Key.");
      return;
    }
    if (selectedEmails.size === 0) {
      alert("Select at least one lead.");
      return;
    }

    setIsProcessing(true);
    addLog(`INITIATING BULK GENERATION FOR ${selectedEmails.size} TARGETS...`);

    const targets = leads.filter(l => selectedEmails.has(l.Email));

    for (const lead of targets) {
      addLog(`Synthesizing pitch for ${lead.Name}...`);
      try {
        const response = await fetch("http://localhost:8000/api/generate-pitch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            business_name: lead.Name,
            rating: lead.Rating,
            audit_data: { SSL: lead.SSL, Mobile: lead.Mobile, Pixels: lead.Pixels },
            profession: profession,
            offer: offer,
            proof: "We have helped dozens of local businesses.", // Hardcoded default for now
            cta: "Open to a quick 5-min chat?",
            your_name: yourName,
            tone: tone,
            gemini_key: geminiKey,
            campaign_name: "Default Campaign",
            lead_email: lead.Email
          }),
        });

        if (response.ok) {
          addLog(`SUCCESS: Draft saved for ${lead.Name}.`);
        } else {
          addLog(`FAILED: Could not generate for ${lead.Name}.`);
        }
      } catch (e) {
        addLog(`ERROR connecting to AI engine for ${lead.Name}.`);
      }
    }
    
    addLog("BULK GENERATION COMPLETE.");
    fetchLeads(); // Refresh to show the drafts
    setIsProcessing(false);
  };

  const handleBulkDispatch = async () => {
    if (!senderEmail || !appPassword) {
      alert("Please enter your Sender Email and App Password.");
      return;
    }
    if (selectedEmails.size === 0) {
      alert("Select at least one lead.");
      return;
    }

    setIsProcessing(true);
    addLog(`INITIATING SMTP DISPATCH FOR ${selectedEmails.size} TARGETS...`);

    const targets = leads.filter(l => selectedEmails.has(l.Email));

    for (const lead of targets) {
      if (!lead.Drafted_Email || lead.Drafted_Email === "✅ SENT") {
        addLog(`SKIPPED: ${lead.Name} (No draft or already sent).`);
        continue;
      }

      addLog(`Deploying payload to ${lead.Email}...`);
      try {
        const response = await fetch("http://localhost:8000/api/send-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_email: lead.Email,
            target_name: lead.Name,
            subject: `Quick question regarding ${lead.Name}'s website`,
            body: lead.Drafted_Email,
            sender_email: senderEmail,
            app_password: appPassword,
            smtp_server: "smtp.gmail.com",
            smtp_port: 587,
            campaign_name: "Default Campaign"
          }),
        });

        if (response.ok) {
          addLog(`SUCCESS: Sent to ${lead.Name}.`);
        } else {
          addLog(`FAILED SMTP for ${lead.Name}.`);
        }
      } catch (e) {
        addLog(`ERROR connecting to SMTP for ${lead.Name}.`);
      }
      
      // Artificial "Anti-Spam Jitter" delay for the UI demonstration
      await new Promise(r => setTimeout(r, 2000)); 
    }

    addLog("DISPATCH SEQUENCE COMPLETE.");
    fetchLeads();
    setIsProcessing(false);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-neutral-300 font-sans p-8 selection:bg-purple-500/30">
      <header className="mb-10">
        <h1 className="text-3xl font-bold text-white">💠 SortingSource Pitch Engine</h1>
        <p className="text-neutral-500 font-mono text-sm mt-1">Active Workspace: DEFAULT_CAMPAIGN</p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        
        {/* --- LEFT COLUMN: ENGINE CONFIG --- */}
        <div className="xl:col-span-1 space-y-6">
          
          {/* Persona Card */}
          <div className="p-6 border bg-[#0F0F0F] border-neutral-800 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent"></div>
            <div className="flex items-center gap-3 mb-6">
              <Settings2 className="text-purple-400" />
              <h2 className="text-lg font-bold text-white">Persona Configuration</h2>
            </div>
            <div className="space-y-4">
              <div className="flex gap-4">
                <div className="w-1/2">
                  <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">Your Name</label>
                  <input type="text" value={yourName} onChange={(e) => setYourName(e.target.value)} placeholder="e.g., John" className="w-full p-3 text-white border rounded-lg bg-black/50 border-neutral-800 focus:border-purple-500 focus:outline-none text-sm" />
                </div>
                <div className="w-1/2">
                  <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">Profession</label>
                  <input type="text" value={profession} onChange={(e) => setProfession(e.target.value)} placeholder="e.g., SEO Pro" className="w-full p-3 text-white border rounded-lg bg-black/50 border-neutral-800 focus:border-purple-500 focus:outline-none text-sm" />
                </div>
              </div>
              <div>
                <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">Core Offer</label>
                <textarea rows={2} value={offer} onChange={(e) => setOffer(e.target.value)} placeholder="I can fix your mobile site." className="w-full p-3 text-white border rounded-lg bg-black/50 border-neutral-800 focus:border-purple-500 focus:outline-none text-sm resize-none" />
              </div>
              <div>
                <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">AI Personality Tone</label>
                <select value={tone} onChange={(e) => setTone(e.target.value)} className="w-full p-3 text-white border rounded-lg bg-black/50 border-neutral-800 focus:border-purple-500 focus:outline-none text-sm appearance-none">
                  {TONE_OPTIONS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Credentials Card */}
          <div className="p-6 border bg-[#0F0F0F] border-neutral-800 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-yellow-500/50 to-transparent"></div>
            <div className="flex items-center gap-3 mb-6">
              <ShieldAlert className="text-yellow-400" />
              <h2 className="text-lg font-bold text-white">Security & Keys (BYOK)</h2>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">Gemini AI Key</label>
                <input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder="AIzaSy..." className="w-full p-3 text-neutral-400 border rounded-lg bg-black/50 border-neutral-800 focus:border-yellow-500 focus:outline-none font-mono text-xs" />
              </div>
              <div>
                <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">SMTP Email Address</label>
                <input type="email" value={senderEmail} onChange={(e) => setSenderEmail(e.target.value)} placeholder="you@domain.com" className="w-full p-3 text-neutral-400 border rounded-lg bg-black/50 border-neutral-800 focus:border-yellow-500 focus:outline-none font-mono text-xs" />
              </div>
              <div>
                <label className="block mb-1 text-xs font-mono text-neutral-500 uppercase">App Password</label>
                <input type="password" value={appPassword} onChange={(e) => setAppPassword(e.target.value)} placeholder="xxxx xxxx xxxx xxxx" className="w-full p-3 text-neutral-400 border rounded-lg bg-black/50 border-neutral-800 focus:border-yellow-500 focus:outline-none font-mono text-xs" />
              </div>
            </div>
          </div>

        </div>

        {/* --- RIGHT COLUMN: THE TERMINAL --- */}
        <div className="xl:col-span-2 space-y-6">
          
          {/* Target List Table */}
          <div className="p-6 border bg-[#0F0F0F] border-neutral-800 rounded-2xl shadow-2xl flex flex-col h-[600px]">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <CheckSquare className="text-cyan-400" /> Target Selection
              </h2>
              <div className="flex gap-2">
                <button onClick={handleBulkGenerate} disabled={isProcessing} className="px-4 py-2 text-xs font-bold text-white bg-purple-600 rounded hover:bg-purple-500 disabled:opacity-50 flex items-center gap-2">
                  <Cpu size={14} /> Bulk Generate
                </button>
                <button onClick={handleBulkDispatch} disabled={isProcessing} className="px-4 py-2 text-xs font-bold text-white bg-green-600 rounded hover:bg-green-500 disabled:opacity-50 flex items-center gap-2">
                  <Send size={14} /> Dispatch Selected
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto border border-neutral-800 rounded-lg bg-[#0A0A0A]">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-[#151515] text-neutral-400 font-mono text-xs uppercase sticky top-0">
                  <tr>
                    <th className="px-4 py-3 border-b border-neutral-800 w-10">
                      <input type="checkbox" onChange={toggleAll} className="accent-purple-500" />
                    </th>
                    <th className="px-4 py-3 border-b border-neutral-800">Business</th>
                    <th className="px-4 py-3 border-b border-neutral-800">Email</th>
                    <th className="px-4 py-3 border-b border-neutral-800">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/50">
                  {leads.map((lead, idx) => {
                    const isMissingEmail = lead.Email === "N/A" || !lead.Email;
                    return (
                      <tr key={idx} className={`hover:bg-white/[0.02] ${isMissingEmail ? "opacity-50" : ""}`}>
                        <td className="px-4 py-3">
                          <input 
                            type="checkbox" 
                            checked={selectedEmails.has(lead.Email)}
                            onChange={() => toggleLeadSelection(lead.Email)}
                            disabled={isMissingEmail}
                            className="accent-purple-500"
                          />
                        </td>
                        <td className="px-4 py-3 text-white">{lead.Name}</td>
                        <td className="px-4 py-3 text-neutral-400">{lead.Email}</td>
                        <td className="px-4 py-3 font-mono text-xs">
                          {lead.Drafted_Email === "✅ SENT" ? (
                             <span className="text-green-400">✅ DISPATCHED</span>
                          ) : lead.Drafted_Email ? (
                             <span className="text-purple-400">🤖 DRAFT READY</span>
                          ) : (
                             <span className="text-neutral-500">PENDING</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {leads.length === 0 && (
                    <tr><td colSpan={4} className="px-4 py-8 text-center text-neutral-600">No leads found in database.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Execution Terminal */}
          <div className="p-4 border rounded-xl bg-[#050505] border-neutral-800 font-mono text-xs leading-relaxed h-[200px] overflow-auto flex flex-col-reverse shadow-inner">
            <div>
               {terminalLogs.map((log, i) => (
                 <p key={i} className={log.includes("ERROR") || log.includes("FAILED") ? "text-red-400" : log.includes("SUCCESS") || log.includes("COMPLETE") ? "text-green-400" : "text-neutral-400"}>
                   {log}
                 </p>
               ))}
               {isProcessing && <p className="text-purple-400 animate-pulse">{`> Processing...`}</p>}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
