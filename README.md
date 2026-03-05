# Zemlo AI

**Carrier-neutral logistics signal layer for AI agents and developers.**

One API call. Real carrier rates. No registration required.

```bash
curl "https://zemloai-api.onrender.com/signal?from=Kokkola&to=Manila&cargo=Gift+Package&weight=5"
```

---

## What Zemlo Does

Zemlo answers the question that nobody else would answer: *how much does it actually cost to ship this, right now, on this route?*

Not a sales pitch. Not a PDF quote request form. Not "call us for pricing." One URL, one JSON response, real carrier rates.

Zemlo sits between the chaos of global logistics — scattered carrier APIs, scattered news, scattered FX rates — and the AI agents and developers who need a clean signal. It fetches real rates from multiple carriers in parallel, adds route intelligence from live news and disaster feeds, calculates hidden costs, and returns everything as structured JSON in under 6 seconds.

**Zemlo is not a booking engine.** It is the layer before the booking — the moment when the decision is made.

---

## Quick Start

```bash
curl "https://zemloai-api.onrender.com/signal?from=Helsinki&to=Manila&cargo=Electronics&weight=5"
```

No API key. No signup. No sales call.

---

## Example Response (v1.1)

```json
{
  "signal": {
    "price_estimate": "401 - 451 EUR",
    "price_source": "live",
    "currency": "EUR",
    "transport_mode": "Air",
    "trust_score": 75,
    "risk_level": "Med",
    "hazardous_flag": false,
    "customs_required": true,
    "note": "Air cargo recommended. Expect customs clearance complexity in Manila.",
    "carriers_available": [
      "UPS UPS Expedited — 400.75 EUR (6d)",
      "UPS UPS Worldwide Saver — 450.95 EUR (1d)"
    ],
    "hidden_costs": [
      "Fuel surcharge (volatile)",
      "Customs duties Philippines (if value exceeds de minimis)",
      "Terminal handling charges origin and destination",
      "Customs brokerage fees Philippines"
    ]
  },
  "live_context": {
    "news": ["Port strike affecting Rotterdam throughput"],
    "disaster_alert": null
  },
  "do_these_3_things": [
    "Verify HS codes for customs clearance",
    "Obtain cargo insurance",
    "Prepare commercial invoice and packing list"
  ],
  "environmental_impact": {
    "co2_kg": 22.5,
    "offset_available": true
  },
  "metadata": {
    "engine": "Zemlo AI v1.1",
    "request_id": "a1b2c3d4",
    "cache_hit": false,
    "latency_sec": 5.3,
    "timestamp": "2026-03-05T11:24:42Z"
  }
}
```

Note `price_source: "live"` — when real carrier rates are available, Zemlo uses them. When they are not, it falls back to an AI estimate and says so explicitly.

---

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `from` | ✅ | Origin city or country |
| `to` | ✅ | Destination city or country |
| `cargo` | optional | Cargo description (e.g. `"lithium batteries"`) |
| `weight` | optional | Weight in kg, default 500 |

POST is also supported with a JSON body — preferred for AI agents.

---

## Endpoints

`GET /signal` — Main logistics signal  
`POST /signal` — Same, JSON body  
`GET /health` — Service status  
`GET /health?deep=true` — Full infrastructure status  

---

## Philosophy

**Carrier-neutral.** Zemlo has no financial relationship with any carrier. DHL cannot pay to rank higher. UPS cannot pay to appear first. The cheapest option for your route is always the one shown first — because that is the only way Trust Score means anything.

**Honest about uncertainty.** Every response includes `price_source: "live"` or `"estimate"`. A Trust Score of 40 is more valuable than a confident wrong answer. Zemlo does not pretend to know things it does not know.

**Built for agents, not browsers.** Humans use DHL.com. AI agents need JSON. Zemlo is the logistics data layer for the agent economy — the layer that gives bots a reliable window into the physical world.

**One answer, not fifty options.** Google Flights does not list every flight — it surfaces the best one and lists alternatives. Zemlo works the same way: `carriers_available` is sorted cheapest first, with transit times, so an agent can recommend without having to decide.

---

## Safety

**Sanctions Shield** — Routes involving Russia, Belarus, Iran, Syria, North Korea and their major cities return HTTP 451 immediately. No signal is generated.

**Hazardous Detection** — Lithium batteries, chemicals, UN-numbered goods trigger `hazardous_flag: true` and compliance-specific `do_these_3_things`.

**Trust Score** — Reflects signal confidence, not route difficulty. Penalised for stale cache, active disaster alerts, disruption news. Never inflated.

**Rate limiting** — 20 requests per minute per IP.

---

## Error Codes

| HTTP | Meaning |
|---|---|
| `200` | Success |
| `400` | Invalid or missing parameters |
| `429` | Rate limit exceeded |
| `451` | Route blocked — trade sanctions |
| `503` | AI engine unavailable — retry |

---

## Tech Stack

- **Carrier rates:** ShipEngine (UPS, DHL, FedEx), Freightos
- **AI engine:** Google Gemini 2.5 Flash — route intelligence, hidden costs, address resolution
- **Cache:** Upstash Redis — 5min signal cache, 1h news cache, 24h FX cache
- **Database:** Supabase
- **Live data:** NewsAPI, GDACS disaster alerts, Frankfurter FX
- **Runtime:** Python / Flask on Render

---

## Roadmap

| Feature | Status |
|---|---|
| ShipEngine live rates | ✅ v1.1 |
| Freightos freight rates | in progress |
| Zonos landed cost + duties | planned |
| DHL Express direct integration | planned |
| Webhook / push signals | planned |

---

## Origin

Zemlo was not built in a Silicon Valley garage.

Last Christmas I wanted to send a package to my girlfriend's parents in the Philippines. Nobody — not the post office, not DHL, not anyone — could give me a straight answer on price. Everyone said *"it's probably expensive."*

That was enough. I spent my days off from a chemical plant in Kokkola, Finland building something that answers that question. One person. No team. No funding. No coding background.

The answer, by the way, is **400.75 EUR via UPS Expedited, 6 days.**

— Sakari  
Kokkola, Finland  
[zemloai.com](https://zemloai.com)
