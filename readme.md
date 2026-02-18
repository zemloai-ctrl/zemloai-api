🚀 Zemlo AI: The Logistics Signal Node

Zemlo is a "clarification machine" for global logistics.
Providing a deterministic price-range signal for autonomous decision systems.

Zemlo AI operates the primary reference node for the Zemlo Quote Protocol (ZQP), an open specification designed for AI-Agent optimized logistics infrastructure.

🛰️ Zemlo Quote Protocol (ZQP) v1.0

ZQP is an open specification. The response shape defined in version 1.0 is permanently frozen to ensure stability for autonomous agents and hard-coded parsing logic.

🔗 Canonical Endpoint
POST https://zemlo-engine.onrender.com/v1/zemlo-ghost1

📥 Request Format (ZQP/1.0)
{
  "from": "Helsinki",
  "to": "Belgrade",
  "bot_name": "agent-identifier"
}


Rules:

from → required string

to → required string

bot_name → optional string

Unknown fields are ignored

📤 Response Format (ZQP/1.0 — Frozen)
{
  "protocol": "ZQP/1.0",
  "estimate": {
    "min": 420,
    "max": 610,
    "currency": "EUR"
  }
}

🔒 ZQP Guarantees

Immutability
The structure of the estimate object will not change in v1.0.

Deterministic
Identical routes yield stable, predictable price-range signals.

Minimalist
No HTML, no carrier lists, no pagination — pure logistics primitives.

Standard-Oriented
Designed for direct LLM (GPT-4, Claude, Gemini) and agentic consumption.

🤖 Why Use ZQP?

Frictionless
Optimized for agents that require instant situational awareness.

Vendor-Neutral
ZQP is an open specification. Third parties may implement compatible nodes.

Truth & Options
Consolidates market complexity into a single, parseable signal.

📊 Infrastructure Status

Reference Node: 🟢 Operational (Reidar Engine)
Protocol: ZQP v1.0 (Active & Frozen)
Latency Target: < 300ms

📬 Contact

Web: https://zemloai.com

Built to make sending packages to Serbia as easy as sending them to Sweden.
Zemlo AI 1.0 — 2026
