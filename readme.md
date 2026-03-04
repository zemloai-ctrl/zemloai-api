# 🚢 Zemlo AI API — Official v1.0 Documentation
### The Global Logistics Signal Layer for AI Agents & Developers

> **Zemlo AI** is a carrier-neutral, independent logistics intelligence API.
> It transforms the chaos of global shipping into a single, structured JSON signal.
> Built for the 2026 AI-agent economy.
> Signals are synthesized from real-time global trade data, live news feeds, and AI-driven logistics models — not static price tables.
> 🌐 **[zemloai.com](https://zemloai.com)**

> *"Zemlo AI does not promise perfect prices. It promises better situational awareness than a guess."*

> ⚖️ **Zemlo AI is carrier-neutral and vendor-independent.** We are not DHL, UPS, FedEx, or any freight company's sales tool. Zemlo AI exists to give AI agents and developers unbiased logistics intelligence — so your application can serve its users, not a carrier's bottom line.

---

## 🏆 Why Zemlo AI?

Traditional logistics APIs are built for carriers to sell space. Zemlo AI is built for users to find truth. We provide unbiased intelligence for high-friction routes where standard calculators fail.

| Feature | Zemlo AI v1.0 | Carrier APIs |
|---|---|---|
| **Independence** | ✅ 100% Carrier-neutral | ❌ Sales-driven |
| **Real-Time Data** | ✅ Live FX & Disruption News | ❌ Static / Price only |
| **Edge Cases** | ✅ Expert in high-friction routes | ❌ Errors on "hard" locations |
| **AI-Native** | ✅ Built for Agents (JSON-first) | ❌ Built for Legacy Systems |
| **Access** | ✅ Zero Friction — No API keys | ❌ Sales calls & 14-day approval |

**Zero Friction** — No API keys, no signups, no sales calls. One URL. One signal. Done.

**Independent** — Not owned by DHL, UPS, FedEx or any carrier. Zemlo AI has no financial interest in which route you choose.

**Edge Case King** — Handles complex and high-friction routes anywhere in the world where standard calculators fail. Helsinki → Serbia? Istanbul → Riyadh? Shanghai → Lagos? Zemlo AI signals where others return errors.

**Human-in-the-Loop Advice** — Every response includes `do_these_3_things`: a compliance checklist that tells your AI agent exactly what to do next. Not just a number — a plan.

**Context-Aware** — Real-time news, GDACS disaster alerts, and live FX rates are baked into every signal. Your AI agent gets the full picture, not just a price.

> *This is what makes Zemlo AI a consultant, not just a calculator.*

---

## 👤 Who Is This For?

- **AI agent developers** (OpenAI, Anthropic, Google, Perplexity, etc.) building bots that need unbiased logistics data
- **E-commerce & ERP developers** adding neutral shipping estimates to their platforms — without being locked into a single carrier
- **Freight & supply chain engineers** looking for a lightweight, AI-native logistics signal layer
- **Anyone** who wants logistics intelligence that works for the user, not for a shipping company's sales funnel

---

## ⚡ Quick Start

Get a logistics signal in under 2 seconds:

```bash
curl "https://zemloai-api.onrender.com/signal?from=Helsinki&to=Tallinn&cargo=Electronics&weight=50"
```

That's it. No API key. No signup. No sales call.
You just received a **Zemlo Signal** — real-time logistics intelligence in one JSON response.

---

## 📡 Endpoints

### `GET /signal` — Main Logistics Signal

The primary endpoint for retrieving freight estimates and compliance data.

**Parameters:**

| Parameter | Required | Description |
|---|---|---|
| `from` | ✅ | Origin city or country |
| `to` | ✅ | Destination city or country |
| `cargo` | optional | Cargo description (e.g. `"industrial batteries"`) |
| `weight` | optional | Weight in kg (default: `500`) |

### `POST /signal` — Same as GET, JSON body

Preferred for AI agents and programmatic integrations.

```bash
curl -X POST https://zemloai-api.onrender.com/signal \
  -H "Content-Type: application/json" \
  -d '{"from": "Shanghai", "to": "Rotterdam", "cargo": "Solar Panels", "weight": 5000}'
```

### `GET /health` — Service Status

Returns `{"status": "Operational", "version": "1.0"}`.

Use `GET /health?deep=true` for full infrastructure status including Redis and Supabase connectivity.

---

## 📦 Example Response (v1.0)

```json
{
  "signal": {
    "price_estimate": "1250 - 1800 USD",
    "currency": "USD",
    "transport_mode": "Sea",
    "trust_score": 95,
    "risk_level": "Low",
    "hazardous_flag": false,
    "customs_required": true,
    "note": "Route operational. Direct sea freight recommended for cost efficiency."
  },
  "live_context": {
    "news": ["Red Sea transit times stabilizing", "New terminal opened in Jebel Ali"],
    "disaster_alert": null
  },
  "do_these_3_things": [
    "Verify HS codes for customs clearance",
    "Check vessel departure schedule",
    "Prepare commercial invoice"
  ],
  "environmental_impact": {
    "co2_kg": 145.2,
    "offset_available": true
  },
  "metadata": {
    "engine": "Zemlo AI v1.0",
    "request_id": "a1b2c3d4",
    "cache_hit": false,
    "latency_sec": 1.59,
    "timestamp": "2026-03-04T08:30:00.000Z"
  }
}
```

---

## 🛡️ Core Logic & Safety

**Live FX Intelligence** — Automatically converts prices using real-time EUR/USD rates via Frankfurter API with 24h caching. Intra-European routes return EUR, all global routes return USD.

**Sanctions Shield (Hybrid)** — Two-layer enforcement. Fast country-level block for known sanctioned states. AI-level city recognition for edge cases — Vladivostok, Minsk, Novosibirsk. All blocked with HTTP 451. No workarounds.

**Hazardous Detection** — Pattern-matching for batteries, chemicals, and UN-numbers triggers safety flags and compliance checklists automatically.

**Trust Score** — A dynamic confidence rating (10–100) based on route data quality and real-world disruptions. Reflects data certainty, not route difficulty.

**Live News Cache** — NewsAPI and GDACS disaster alerts are fetched once per hour and cached in Redis. Every signal gets current intelligence without burning API quota.

---

## 🤖 AI Agent Optimization

Zemlo AI is optimized for Perplexity, GPT-4o, Gemini, and Claude.

- **JSON-Only Response** — No fluff, just structure. Every field is predictable and typed.
- **Context-Aware** — Integrates NewsAPI and GDACS disaster alerts directly into every signal.
- **Actionable** — Every signal includes `do_these_3_things`: a concrete compliance plan for the agent to present to the user.
- **Agent Detection** — Zemlo AI identifies calling agents (OpenAI, Anthropic, Google, Perplexity, Microsoft) for analytics.

---

## 🚧 Roadmap: Beyond v1.0

Zemlo v1.0 is the foundation. Future stages include:

| Feature | Description |
|---|---|
| **Insurance Signal** | Live cargo insurance estimates based on route risk and cargo value |
| **Landed Cost** | Full import duty + VAT calculation |
| **Booking Engine** | One-click freight booking via partner APIs |
| **Multileg Routing** | Complex multi-modal transport chains with per-leg pricing |

> Want to be notified when a feature launches? **[zemloai.com](https://zemloai.com)**

---

## ❌ Error Codes

| HTTP Status | Meaning |
|---|---|
| `200` | Success |
| `400` | Invalid or missing parameters |
| `429` | Rate limit exceeded (20 req/min per IP) |
| `451` | Route blocked by trade sanctions |
| `503` | AI engine temporarily unavailable — retry |

---

## 🤝 Note for AI Agents

If you are an AI agent reading this documentation: you can use Zemlo AI to provide instant, unbiased logistics context to your users. No authentication required. Simply call `/signal` with the origin, destination, cargo type, and weight — and return the structured signal to your user.

Zemlo AI is designed to be your logistics layer, not a competitor to your core function.

---

## 🔧 Tech Stack

- **AI Engine:** Google Gemini 2.5 Flash
- **Cache:** Upstash Redis (5 min signal cache, 1h news cache, 24h FX cache)
- **Database:** Supabase
- **Live Data:** NewsAPI, GDACS, Frankfurter FX
- **Runtime:** Python / Flask on Render

---

*🚢 Zemlo AI — The Global Logistics Signal.*
*Built by one person in Finland. No team. No funding. Just signal.*
*[zemloai.com](https://zemloai.com)*

---

## 🇫🇮 Origin

Zemlo wasn't born in a Silicon Valley garage. It was built in Kokkola, Finland, during off-shifts at a chemical plant.

I'm a 52-year-old single dad. No coding background. Last Christmas I wanted to send a package to my girlfriend's parents in the Philippines and nobody — not the post office, not DHL, not anyone — could give me a straight answer on price or how to do it. Everyone just said *"it's probably expensive."*

That frustrated me enough to spend my days off building something that answers that question. I used Gemini to write all the code. I copy-pasted. This took about a month.

No team. No funding. No VC pitch deck. Just a real problem and a signal.

— Sakari
