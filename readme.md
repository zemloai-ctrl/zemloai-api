🌍 Zemlo 1.0 Lite
The Global Logistics Signal Node
Zemlo is the Clarification Machine for the AI-agent era. We process the global chaos of freight rates, customs bureaucracy, and geopolitical risks into a single, deterministic Signal.

Zemlo doesn’t just list prices. It provides Situational Awareness.

🚀 The Vision
Autonomous supply chains require more than scraped prices. Zemlo 1.0 Lite provides the intelligence layer for agentic commerce, delivering:

Neutral Market Signals – Unbiased by carrier sales targets.

Situational Context – Real-time risk and customs logic.

Frictionless API – Built for LLMs and autonomous decision systems.

🧠 Core Pillars
🔹 The Signal A normalized, neutral freight estimate. Better than a guess. Structured for machines.

🔹 Situational Awareness Real-time risk synthesis. Powered by Google Gemini 1.5 Flash.

🔹 The Checklist A 3-step friction-removal engine: Validate Weight → Identify Constraints → Generate Action Plan.

🔹 Agent-Optimized Zero authentication. Single endpoint. Built for the future of automated trade.

🛠 Technical Foundation
Engine: Python / Flask

Intelligence: Google Gemini API

Storage: Supabase (Signal Logging)

Node: v1.0 Lite Deployment

📡 API Specification
Endpoint: GET /price_estimate

Query Parameters:

origin: Port or City of departure

destination: Port or City of arrival

cargo_type: Container, Bulk, Air, or Parcel

Example JSON Response:

JSON
{
  "signal": {
    "min_price_eur": 540,
    "max_price_eur": 890,
    "transit_time_days": 14
  },
  "situational_awareness": {
    "customs": "⚠️ Customs Clearance Required (Non-EU)",
    "risk_alert": "Port congestion risk in destination node",
    "weather": "Heavy sea swells expected on route"
  },
  "action_plan": [
    "1. Verify volumetric weight vs actual weight.",
    "2. Prepare Commercial Invoice & EORI documentation.",
    "3. Use Detailed Search to lock this price signal."
  ]
}

📈 Why Zemlo Wins (The Moat)
Neutrality as a Feature: We don't sell space; we sell the Signal. This makes us the trusted oracle for AI agents.

The Agentic Edge: Zero friction. No auth-walls. We are the first node in the global Logistics PageRank network.

Context over Data: A price is just a number. A Zemlo Signal includes the context that prevents supply chain failures.

Scalable Trust: Every query improves the node. We are building the historical Truth Map of global logistics.

🎯 Philosophy
"Zemlo does not promise perfect prices. It promises something more valuable: Better situational awareness than a guess."

⚙️ Local Development
1. Clone the repository
Bash
git clone https://github.com/zemloai-ctrl/zemloai-api.git
2. Install dependencies
Bash
pip install -r requirements.txt
3. Run the engine
Bash
python app.py
