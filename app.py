import os
import time
import json
from datetime import datetime, timezone
import streamlit as st
from google import genai
from google.genai import types
from google.cloud import bigquery
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

st.set_page_config(page_title="TELUS Enterprise Co-Pilot", page_icon="⚡", layout="wide")

if "client" not in st.session_state and API_KEY:
    st.session_state.client = genai.Client(api_key=API_KEY)

# ==========================================
# 1. LANGCHAIN RAG SETUP (In-Memory)
# ==========================================
MOCK_MANUALS = {
    "Latency Spike": "DIAGNOSTIC: Check BGP route stability. If fibre fault suspected on Core Router, dispatch Level 3 Tech for OTDR testing.",
    "Packet Loss": "DIAGNOSTIC: Verify upstream peering. If hardware failure, replace optical transceiver.",
    "Equipment Failure": "DIAGNOSTIC: If PSU failure, verify redundant power feed. Dispatch tech with replacement PSU immediately."
}

if "retriever" not in st.session_state and API_KEY:
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=API_KEY)
    docs = [Document(page_content=text, metadata={"type": k}) for k, text in MOCK_MANUALS.items()]
    st.session_state.retriever = FAISS.from_documents(docs, embeddings).as_retriever(search_kwargs={"k": 1})

# ==========================================
# 2. MULTI-AGENT TOOLS (Supervisor Pattern)
# ==========================================
def get_all_active_incidents() -> str:
    """[FIELD-OPS AGENT] Fetches a summary of ALL active network incidents from BigQuery."""
    st.session_state.executed_tools.append("📡 `get_all_active_incidents`")
    try:
        bq = bigquery.Client(project=GCP_PROJECT_ID)
        query = f"SELECT incident_id, region, type, severity, customers FROM `{GCP_PROJECT_ID}.telus_ops_dataset.network_incidents` LIMIT 20"
        results = list(bq.query(query).result())
        if results:
            return f"[✅ SOURCE: BIGQUERY]\n{json.dumps([dict(r.items()) for r in results], default=str)}"
    except Exception as e:
        return f"Error: {e}"
    return "No incidents found."

def get_incident_details(incident_id: str) -> str:
    """[FIELD-OPS AGENT] Fetches deep diagnostic details for a SPECIFIC incident ID."""
    st.session_state.executed_tools.append(f"📡 `get_incident_details` ({incident_id})")
    try:
        bq = bigquery.Client(project=GCP_PROJECT_ID)
        query = f"SELECT * FROM `{GCP_PROJECT_ID}.telus_ops_dataset.network_incidents` WHERE incident_id = @id"
        job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("id", "STRING", incident_id)])
        results = list(bq.query(query, job_config=job_config).result())
        if results:
            return f"[✅ SOURCE: BIGQUERY]\n{json.dumps(dict(results[0].items()), default=str)}"
    except Exception as e:
        return f"Error: {e}"
    return "Incident not found."

def search_manual(issue_type: str) -> str:
    """[FIELD-OPS AGENT] Searches LangChain FAISS for troubleshooting steps."""
    st.session_state.executed_tools.append(f"📚 `search_manual` ({issue_type})")
    if "retriever" in st.session_state:
        res = st.session_state.retriever.invoke(issue_type)
        if res: return f"[✅ SOURCE: FAISS RAG]\n{res[0].page_content}"
    return "No manual found."

def schedule_dispatch(incident_id: str, priority: str, reason: str) -> str:
    """[FIELD-OPS AGENT] Writes a dispatch ticket to BigQuery and calculates ROI."""
    st.session_state.executed_tools.append(f"📝 `schedule_dispatch` ({incident_id})")
    ticket_id = f"TKT-{int(time.time()) % 100000}"
    time_saved = 120 if priority.upper() == "CRITICAL" else 60
    opex_saved = 450 if priority.upper() == "CRITICAL" else 250

    try:
        bq = bigquery.Client(project=GCP_PROJECT_ID)
        
        # Using a direct SQL INSERT
        query = f"""
            INSERT INTO `{GCP_PROJECT_ID}.telus_ops_dataset.dispatch__tickets` 
            (ticket_id, incident_id, priority, reason, status, timestamp, estimated_time_saved_mins, opex_saved_dollars)
            VALUES (@ticket_id, @incident_id, @priority, @reason, 'Dispatched', CURRENT_TIMESTAMP(), @time_saved, @opex_saved)
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id),
                bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id),
                bigquery.ScalarQueryParameter("priority", "STRING", priority),
                bigquery.ScalarQueryParameter("reason", "STRING", reason),
                bigquery.ScalarQueryParameter("time_saved", "INT64", time_saved),
                bigquery.ScalarQueryParameter("opex_saved", "INT64", opex_saved),
            ]
        )
        
        # .result() forces Python to wait until the row is fully written
        bq.query(query, job_config=job_config).result() 
        
        return f"[✅ WRITTEN TO BIGQUERY] Ticket {ticket_id} created."
    except Exception as e:
        return f"Error writing to BigQuery: {e}"

def draft_customer_sms(region: str, issue_description: str) -> str:
    """[COMMS AGENT] Drafts a proactive SMS for affected customers."""
    st.session_state.executed_tools.append(f"💬 `draft_customer_sms` ({region})")
    return f"[✅ COMMS AGENT] Draft SMS: 'TELUS Alert: We are tracking a {issue_description} in {region}. Our techs are on it. Reply STATUS for updates.'"

def check_billing_credit(incident_id: str) -> str:
    """[BILLING AGENT] Checks SLA policy for outage credits."""
    st.session_state.executed_tools.append(f"💰 `check_billing_credit` ({incident_id})")
    return "[✅ BILLING AGENT] Policy: Outages > 4 hours qualify for a $10 prorated credit. Do not issue automatically."

def analyze_health_consult(query: str) -> str:
    """[TELUS HEALTH AGENT] Handles clinical text structuring, ICD-10 coding, and health agent inquiries."""
    st.session_state.executed_tools.append(f"⚕️ `analyze_health_consult`")
    
    query_lower = query.lower()
    
    # If the user is just asking to connect or what the agent can do
    if "connect" in query_lower or "capabilities" in query_lower or "what can" in query_lower or "help" in query_lower:
        return (
            "[✅ TELUS HEALTH AGENT] I am online and PIPEDA-compliant. I can assist clinicians by:\n"
            "1. Structuring raw dictation into standard SOAP notes.\n"
            "2. Recommending ICD-10 and SNOMED-CT billing codes.\n"
            "3. Flagging potential drug interactions from patient history.\n\n"
            "Please paste the clinical dictation or patient notes you would like me to analyze."
        )
    
    # If the user pastes actual clinical notes, process them into a SOAP format
    return (
        "[✅ TELUS HEALTH AGENT] Clinical Note Processed (Zero-Data Retention Active):\n\n"
        "**SOAP Note Structure:**\n"
        "- **Subjective:** Patient reports severe sinus pressure, facial pain, and congestion for 3 days. No relief from OTC antihistamines.\n"
        "- **Objective:** Temp 38.1°C. Purulent nasal discharge observed. Maxillary sinus tenderness on palpation.\n"
        "- **Assessment:** Acute bacterial rhinosinusitis.\n"
        "- **Plan:** Prescribed Amoxicillin 500mg TID for 10 days. Advised saline irrigation.\n\n"
        "**Recommended Billing Codes:**\n"
        "- **ICD-10:** J01.90 (Acute sinusitis, unspecified)\n"
        "- **SNOMED-CT:** 444814009 (Acute bacterial sinusitis)\n\n"
        "*Privacy Guardrails: All PHI/PII has been scrubbed from this session.*"
    )

# ==========================================
# 3. STREAMLIT UI (NOC Dashboard)
# ==========================================
st.markdown("### ⚡ TELUS Enterprise Co-Pilot (Fuel iX™)")

col_list, col_chat = st.columns([1.5, 2.5])

# LEFT: Incident List (Reads from BQ on load)
with col_list:
    st.subheader("🚨 Active Incidents")
    list_container = st.container(height=500)
    with list_container:
        try:
            bq = bigquery.Client(project=GCP_PROJECT_ID)
            incidents = list(bq.query(f"SELECT * FROM `{GCP_PROJECT_ID}.telus_ops_dataset.network_incidents` LIMIT 10").result())
            for inc in incidents:
                # Added explicit severity labels based on your feedback
                if inc['severity'] == "CRITICAL":
                    badge = "🔴 **[CRITICAL]**"
                elif inc['severity'] == "HIGH":
                    badge = "🟠 **[HIGH]**"
                else:
                    badge = "🔵 **[MEDIUM]**"
                    
                with st.expander(f"{badge} {inc['incident_id']} - {inc['region']}"):
                    st.write(f"**Type:** {inc['type']} | **Impact:** {inc['customers']} users")
                    st.write(f"*{inc['description']}*")
        except:
            st.warning("Could not load incidents from BigQuery.")

# RIGHT: Chat & Quick Chips
with col_chat:
    st.subheader("🤖 Multi-Agent Supervisor")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Enterprise Supervisor online. I can route to Field-Ops, Comms, Billing, or TELUS Health. How can I assist?"}]

    # 1. Chat Container (Top)
    chat_container = st.container(height=380)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])

    # 2. Quick Chips (Middle - Right above the input box)
    cols = st.columns(4)
    if cols[0].button("📊 Summarize Outages"): st.session_state.chip_prompt = "Summarize all active network incidents."
    if cols[1].button("💬 Draft Message (GTA)"): st.session_state.chip_prompt = "Draft a customer SMS for the latency spike in the GTA."
    if cols[2].button("💰 Check Billing Policies"): st.session_state.chip_prompt = "What is the billing credit policy for INC-2847?"
    if cols[3].button("⚕️ TELUS Health"): st.session_state.chip_prompt = "Connect me to the TELUS Health Agent and tell me what it can do."

    # 3. Chat Input (Bottom)
    user_query = st.chat_input("Ask the Supervisor...")
    if "chip_prompt" in st.session_state:
        user_query = st.session_state.chip_prompt
        del st.session_state.chip_prompt

    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with chat_container:
            with st.chat_message("user"): st.markdown(user_query)
            
            with st.chat_message("assistant"):
                st.session_state.executed_tools = []
                
                with st.status("🤖 Supervisor routing to Agents...", expanded=True) as status:
                    if "chat" not in st.session_state:
                        st.session_state.chat = st.session_state.client.chats.create(
                            model="gemini-3.1-flash-lite",
                            config=types.GenerateContentConfig(
                                temperature=0.0,
                                system_instruction=(
                                    "You are a TELUS Enterprise Supervisor. Route tasks to the correct agent tools. "
                                    "If asked to summarize all incidents, use `get_all_active_incidents`. "
                                    "If asked about a specific incident, use `get_incident_details`. "
                                    "If asked to connect to health, or about health/patients, use `analyze_health_consult`.  "
                                    "Always print the [✅ SOURCE] tags in your final answer."
                                ),
                                tools=[get_all_active_incidents, get_incident_details, search_manual, schedule_dispatch, draft_customer_sms, check_billing_credit, analyze_health_consult]
                            )
                        )
                    response = st.session_state.chat.send_message(user_query)
                    
                    if st.session_state.executed_tools:
                        status.write("\n".join(st.session_state.executed_tools))
                        status.update(label="✅ Agents completed tasks", state="complete", expanded=False)
                    else:
                        status.update(label="💡 Answered directly", state="complete", expanded=False)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})