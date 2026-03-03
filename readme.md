# 🚢 Zemlo AI API — Developer Documentation
### v1.9.5 · Logistics Intelligence for AI Agents & Developers

> **Zemlo AI** is a logistics signal API built for developers, AI agents, and bot integrations.  
> It returns real-time freight price estimates, transport recommendations, sanctions checks, hazardous cargo flags, and live disruption alerts — all in a single JSON call.  
> 🌐 **[zemloai.com](https://zemloai.com)**

> *"Zemlo AI does not promise perfect prices. It promises something more valuable: Better situational awareness than a guess."*

---

## 👤 Who Is This For?

- **AI agent developers** (OpenAI, Anthropic, Google, Perplexity, etc.) building bots that need logistics data
- **E-commerce & ERP developers** adding shipping estimates to their platforms
- **Freight & supply chain engineers** looking for a lightweight, AI-native logistics signal layer

---

## ⚡ Quick Start

```bash
curl "https://zemloai-api.onrender.com/signal?from=Helsinki&to=Tallinn&cargo=Electronics&weight=50"
```

That's it. You'll get a full logistics signal back in under 2 seconds.

---

## 🔗 Base URL

```
https://zemloai-api.onrender.com
```

---

## 📡 Endpoints

### `GET /signal` — Main Logistics Signal

Returns a freight price estimate, transport mode, risk assessment, live disruptions, and compliance flags.

**Parameters**

| Parameter | Type   | Required | Description                          | Example              |
|-----------|--------|----------|--------------------------------------|----------------------|
| `from`    | string | ✅        | Origin city or country               | `Helsinki`           |
| `to`      | string | ✅        | Destination city or country          | `New York`           |
| `cargo`   | string | ❌        | Cargo description (default: General) | `industrial batteries` |
| `weight`  | number | ❌        | Weight in kg (default: 500)          | `1200`               |

**GET example**
```
GET /signal?from=Stockholm&to=Belgrade&cargo=industrial+batteries&weight=200
```

**POST example**
```bash
curl -X POST https://zemloai-api.onrender.com/signal \
  -H "Content-Type: application/json" \
  -d '{"from": "Stockholm", "to": "Belgrade", "cargo": "industrial batteries", "weight": 200}'
```

---

### `GET /health` — Infrastructure Status

Returns the operational status of Redis and Supabase connections.

```bash
curl "https://zemloai-api.onrender.com/health"
```

```json
{
  "status": "Operational",
  "version": "1.9.5",
  "services": {
    "redis": "Connected",
    "supabase": "Connected"
  }
}
```

---

## 📦 Example Response

```json
{
  "signal": {
    "price_estimate": "650 - 1200 EUR",
    "currency": "EUR",
    "transport_mode": "Road",
    "trust_score": 75,
    "risk_level": "Med",
    "hazardous_flag": true,
    "customs_required": true,
    "note": "Industrial batteries are classified as dangerous goods (UN3090, UN3480). ADR compliance required."
  },
  "live_context": {
    "news": [
      "Port strike causes delays at Hamburg terminal"
    ],
    "disaster_alert": null
  },
  "do_these_3_things": [
    "Ensure UN-approved packaging and labeling (ADR)",
    "Prepare MSDS and dangerous goods declaration",
    "Book LTL road freight with ADR-certified carrier"
  ],
  "environmental_impact": {
    "co2_kg": 42.0,
    "offset_available": true
  },
  "metadata": {
    "engine": "Zemlo AI v1.9.5",
    "request_id": "43e955e5",
    "cache_hit": false,
    "latency_sec": 1.84,
    "timestamp": "2026-03-03T20:05:14.104223+00:00"
  }
}
```

---

## 🗂️ Response Fields Explained

### `signal`

| Field | Type | Description |
|-------|------|-------------|
| `price_estimate` | string | Freight cost range in EUR |
| `currency` | string | `EUR` for intra-European routes, `USD` for all other routes (auto-detected) |
| `transport_mode` | string | `Road`, `Sea`, `Air`, or `Rail` |
| `trust_score` | int | Data confidence score 10–95. Based on risk level and route data quality — not cargo difficulty |
| `risk_level` | string | `Low`, `Med`, or `High` |
| `hazardous_flag` | bool | `true` if cargo matches ADR/IMDG dangerous goods patterns (batteries, lithium, chemicals, UN numbers) |
| `customs_required` | bool | `false` for intra-EU routes, `true` otherwise |
| `note` | string | AI-generated human-readable summary of the route logic |

### `live_context`

| Field | Type | Description |
|-------|------|-------------|
| `news` | array | Real-time logistics disruption headlines from NewsAPI |
| `disaster_alert` | string / null | GDACS Red Alert if a severe global disaster is active |

### `environmental_impact`

| Field | Type | Description |
|-------|------|-------------|
| `co2_kg` | float | Estimated CO2 emissions in kg. Mode factors: Air 0.5 · Road 0.1 · Rail 0.03 · Sea 0.015 |
| `offset_available` | bool | `true` when CO2 offset purchasing is enabled (see Roadmap) |

### `metadata`

| Field | Type | Description |
|-------|------|-------------|
| `engine` | string | API version string |
| `request_id` | string | Unique 8-char request identifier for debugging |
| `cache_hit` | bool | `true` if response served from Redis cache |
| `latency_sec` | float | Total server-side processing time in seconds |
| `timestamp` | string | UTC ISO 8601 timestamp |

---

## 🛡️ Sanctions & Safety (The Shield)

Zemlo AI enforces hard stops on sanctioned routes. These calls return **HTTP 451** with no price estimate.

**Blocked zones (2026 policy):**
- Russia / Venäjä
- Belarus / Valko-Venäjä
- Iran
- Syria
- North Korea

**Example blocked response:**
```json
{
  "hard_stop": true,
  "reason": "Trade sanctions apply to this route."
}
```

> ⚠️ Do not attempt to work around sanctions blocks in your integration. These are enforced per international trade law (EU, OFAC, UN).

---

## ☣️ Hazardous Cargo Detection

The API automatically detects dangerous goods from the `cargo` parameter using pattern matching:

| Pattern matched | Examples |
|-----------------|---------|
| `batter` / `batteries` | industrial batteries, battery packs |
| `lithium` | lithium-ion, lithium polymer |
| `chemic` | chemicals, chemical compound |
| `hazard` / `hazmat` | hazardous materials |
| `UN` + 4 digits | UN3480, UN3090, UN2794 |

When `hazardous_flag: true`, the `do_these_3_things` array will include ADR/IMDG compliance steps.

---

## ⚙️ Caching & Rate Limiting

**Caching:** Responses are cached in Redis for **5 minutes** per unique route+cargo+weight combination.  
The `metadata.cache_hit` field tells you whether the response was served from cache.  
Cache key is based on: `origin + destination + cargo + weight (int)`.

**Rate Limits:**

| Limit | Value |
|-------|-------|
| `/signal` | 20 requests / minute per IP |
| Global | 100 requests / minute per IP |

Exceeding limits returns HTTP **429 Too Many Requests**.

---

## 🤖 AI Agent Integration Notes

Zemlo AI tracks the `User-Agent` header to identify AI callers for analytics. Recognized agents:

| Agent string | Identified as |
|---|---|
| `gptbot`, `chatgpt` | OPENAI |
| `claude`, `anthropic` | ANTHROPIC |
| `googlebot`, `gemini` | GOOGLE |
| `perplexity` | PERPLEXITY |
| `bingbot`, `copilot` | MICROSOFT |
| anything else | HUMAN |

No behavior changes based on agent type — this is analytics only.

---

## 🚧 Roadmap — Coming Soon

The following features are under active development. Integrate now and they will be available as additional fields in the same `/signal` response — **no breaking changes planned**.

| Feature | Field (planned) | Description |
|---------|----------------|-------------|
| **Insurance Signal** | `signal.insurance_estimate` | Live cargo insurance price estimate based on route risk and cargo value |
| **Customs & Duties** | `signal.landed_cost` | Accurate import duties and VAT via partner integration |
| **CO2 Offset Purchase** | `environmental_impact.offset_url` | Direct link to purchase carbon offset for the shipment via partner |
| **Freight Booking** | `signal.booking_url` | One-click freight booking via partner integration |
| **Multileg Routing** | `signal.legs` | Combined route breakdown e.g. Road → Sea → Road with per-leg pricing |
| **Webhook Support** | — | Push notifications to your endpoint when route risk changes or disruptions detected |
| **Freight Forwarding** | `signal.forwarder` | Recommended licensed freight forwarder for complex routes |
| **HS Code Lookup** | `signal.hs_code` | Harmonized System code suggestion based on cargo description |
| **Live FX Rates** | `signal.fx_rate` | Real-time EUR/USD conversion via FX API (v1.9.6 uses fixed rate 1.09) |

> Want to be notified when a feature launches? Contact the Zemlo AI team at **[zemloai.com](https://zemloai.com)**.

---

## ❌ Error Codes

| HTTP Status | Meaning |
|-------------|---------|
| `200` | Success |
| `400` | Invalid or missing parameters |
| `429` | Rate limit exceeded |
| `451` | Route blocked by trade sanctions |
| `503` | AI engine temporarily unavailable — retry |

---

## 🔧 Powered By

- **AI Engine:** Google Gemini 2.5 Flash
- **Cache:** Upstash Redis
- **Database:** Supabase
- **Live Data:** NewsAPI, GDACS
- **Partners:** Selected via Zemlo AI partner network
- **Runtime:** Python / Flask on Render

---

*🚢 Zemlo AI — Logistics Made Easy. It's time.*  
*[zemloai.com](https://zemloai.com)*
