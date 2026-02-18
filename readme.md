# 🚀 Zemlo AI: The Logistics Signal Node (Beta)

> **Zemlo is a "clarification machine" for global logistics.**
> Providing a dynamic price-range signal optimized for AI agents and autonomous systems.

Zemlo AI operates as the primary development node for the **Zemlo Quote Protocol (ZQP)**. We are currently in an active **Beta Phase**, mapping the first global logistics signals.

---

## 🛰️ Zemlo Quote Protocol (ZQP) v1.0 [BETA]

ZQP is a proposed open specification for agent-to-agent logistics communication. During this stage, the protocol is in **Active Evolution**. We are learning from bot interactions to build the most efficient standard possible.

### 🔗 Current Endpoint
`POST https://zemlo-engine.onrender.com/v1/zemlo-ghost1`

### 📥 Request Format (ZQP/1.0 Beta)
```json
{
  "from": "City/Port",
  "to": "City/Port",
  "bot_name": "agent-identifier"
}
📤 Response Format (Current Snapshot)
JSON
{
  "protocol": "ZQP/1.0-beta",
  "estimate": {
    "min": 420,
    "max": 610,
    "currency": "EUR"
  }
}
🛠️ Beta Phase Principles
Active Evolution: During the beta, the response shape and logic are subject to change based on real-world performance and agent feedback.

Situational Awareness: Our goal is to provide a signal that is "better than a guess" while we refine our data sources.

Agent-First: Even in beta, our focus remains on deterministic, parseable JSON for LLMs and autonomous bots.

Transparent Testing: We are currently simulating and routing real-time signals to build the "Logistics PageRank."

🤖 Why Zemlo?
Logistics is a "jungle of friction." Zemlo removes that friction by providing a single, clear signal instead of endless lists of links. We process the confusion so the agents can make decisions.

📊 Status
Node: 🟢 Active Beta

Phase: Signal Mapping & Protocol Design

Latency: Optimized for speed

📬 Contact
Web: zemloai.com

Making sending packages to Serbia as easy as sending them to Sweden. Zemlo AI — Built for the Future of Logistics (2026)
