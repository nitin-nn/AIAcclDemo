# TELUS Enterprise Co-Pilot (Interview PoC)

This repository contains the Proof of Concept (PoC) for the TELUS AI Accelerator interview. 

## Architecture Overview
This solution demonstrates a **Dual-Persona, Multi-Agent Architecture** built for the GCP ecosystem:
1. **Operator View (Streamlit):** A Supervisor Agent (Gemini 3.5 Flash) that routes natural language queries to specialized tools (Field-Ops, Comms, TELUS Health).
2. **Data Layer (GCP BigQuery & FAISS):** The agent performs live SQL reads/writes to BigQuery and semantic searches against an in-memory LangChain FAISS vector store.
3. **Executive View (Google Apps Script):** A serverless dashboard that reads the BigQuery dispatch tickets to calculate live OpEx savings and MTTR reduction.

## Future State (Fuel iX Scaling)
While this PoC uses native tool-calling, the production roadmap includes:
* **Model Context Protocol (MCP):** Decoupling BigQuery and Vector Search into standardized MCP servers.
* **LangGraph:** Upgrading to stateful, cyclical workflows.
* **Human-in-the-Loop (HITL):** Enforcing financial guardrails prior to BigQuery execution.

*Note: API keys and GCP credentials have been excluded from this repository for security.*
