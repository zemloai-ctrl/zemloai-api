# 🚀 Zemlo AI

> **The First AI-Agent Optimized Logistics Infrastructure.**
> No auth, no rate limits, just situational awareness.

Zemlo AI is a "clarification machine" designed to remove friction from global logistics. It provides a strategic snapshot of shipping options—better than a guess, faster than a forwarder.

---

## 🔗 Live API

**Base Endpoint:** `https://zemloai-api.onrender.com`

**Status:** 🟢 Online (Beta)

---

## 📖 Quick Start

Zemlo AI is designed to be called directly by LLMs (GPT-4, Claude, Gemini) and autonomous agents.

### Get a Quote

```bash
curl -X POST [https://zemloai-api.onrender.com/api/v1/quote](https://zemloai-api.onrender.com/api/v1/quote) \
  -H "Content-Type: application/json" \
  -d '{"from": "Helsinki", "to": "Belgrade", "item": "Industrial Equipment"}'
🤖 Built for AI Agents
No Auth Required: Frictionless access for agents.

Predictable JSON: Strict data types.

Situational Awareness: Not just prices, but reality.

📊 API Endpoints
POST /api/v1/quote -> Get shipping alternatives.

GET /api/v1/stats -> Network health.

🛠️ Tech Stack
Python 3.11 / Flask

Deployed on Render

📬 Contact
Web: zemloai.com

Built with ❤️ on Valentine's Day 2026.
