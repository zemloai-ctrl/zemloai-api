import os, json, requests, hashlib, uuid, re, logging, concurrent.futures, time
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

# --- SETUP & LOGGING ---
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v1.1")

# --- CONFIGURATION ---
REDIS_URL    = os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN  = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY")
NEWS_KEY     = os.environ.get("NEWS_API_KEY")
SHIPPO_KEY      = os.environ.get("SHIPPO_API_KEY")
FREIGHTOS_KEY   = os.environ.get("FREIGHTOS_API_KEY")
EASYSHIP_KEY    = os.environ.get("EASYSHIP_API_KEY")

redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)
supabase     = create_client(SUPABASE_URL, SUPABASE_KEY)
limiter      = Limiter(key_func=get_remote_address, app=app, default_limits=["100 per minute"], storage_uri="memory://")

DEFAULT_EUR_TO_USD = 1.09

# --- FX RATE ---

def get_live_fx_rate():
    """Fetches live EUR/USD rate with 24h Redis cache."""
    cache_key = "fx_rate:EUR_USD"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return float(cached)
    except Exception:
        pass
    try:
        resp = requests.get("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD", timeout=5)
        rate = resp.json()['rates']['USD']
        try:
            redis_client.set(cache_key, rate, ex=86400)
        except Exception:
            pass
        return float(rate)
    except Exception as e:
        logger.warning(f"FX unavailable: {e}. Fallback: {DEFAULT_EUR_TO_USD}")
        return DEFAULT_EUR_TO_USD

# --- AGENT IDENTIFICATION ---

def identify_agent(ua):
    """Identifies whether the caller is a human, ghost bot, or an AI agent."""
    ua = ua.lower()
    if 'ghostbot' in ua:
        return 'GHOST'
    agents = {
        'gptbot': 'OPENAI', 'chatgpt': 'OPENAI',
        'claude': 'ANTHROPIC', 'anthropic': 'ANTHROPIC',
        'googlebot': 'GOOGLE', 'gemini': 'GOOGLE',
        'perplexity': 'PERPLEXITY',
        'bingbot': 'MICROSOFT', 'copilot': 'MICROSOFT'
    }
    for key, val in agents.items():
        if key in ua:
            return val
    return "HUMAN"

# --- TRUST SCORE ---

def compute_trust(ai_data, news, alerts, cache_hit):
    """
    Trust score = signal confidence, not route difficulty.
    Answers: "How much should a bot trust this data right now?"
    - Base: route risk level (proxy for how well we know this route)
    - Penalties: stale cache, active alerts, disruption news
    """
    risk_map = {"Low": 95, "Med": 75, "High": 45}
    score = risk_map.get(ai_data.get("risk", "Med"), 50)
    if ai_data.get("dist_km", 0) == 0:
        score -= 15  # route unknown to AI
    if cache_hit:
        score -= 5   # data not freshest possible
    if alerts:
        score -= 10  # active disaster alert on this corridor
    if news:
        score -= 5   # disruption news in circulation
    return max(min(score, 100), 10)

# --- CO2 ---

def get_co2_impact(mode, dist_km, weight_kg):
    factors = {"Air": 0.5, "Road": 0.1, "Rail": 0.03, "Sea": 0.015}
    return round(float(dist_km or 0) * (float(weight_kg) / 1000) * factors.get(mode, 0.1), 2)

def get_weight_bucket(weight_kg):
    if weight_kg <= 50:  return "Light"
    if weight_kg <= 500: return "Medium"
    return "Heavy"

# --- LIVE NEWS & ALERTS (1h cache) ---

def fetch_live_signals():
    cache_key = "global_logistics_context"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return data["news"], data["alerts"]
    except Exception:
        pass

    def get_news():
        try:
            q = "port+strike+OR+logistics+disruption+OR+border+delay+OR+shipping+war+risk"
            url = f"https://newsapi.org/v2/everything?q={q}&pageSize=3&apiKey={NEWS_KEY}"
            r = requests.get(url, timeout=3).json()
            return [a['title'] for a in r.get('articles', [])]
        except Exception:
            return []

    def get_disasters():
        try:
            r = requests.get("https://www.gdacs.org/xml/rss.xml", timeout=3)
            return "RED ALERT: Severe global disaster detected." if re.search(r'\bRed\b', r.text) else None
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        news   = executor.submit(get_news).result()
        alerts = executor.submit(get_disasters).result()

    try:
        redis_client.set(cache_key, json.dumps({"news": news, "alerts": alerts}), ex=3600)
    except Exception:
        pass

    return news, alerts

# --- GEMINI: RESOLVE CITY NAME TO STRUCTURED ADDRESS ---

def resolve_location(place_name):
    """
    Converts a city/country name into structured address for Shippo.
    Returns dict with city, state, zip, country (ISO2).
    """
    prompt = (
        f"Return ONLY JSON, no explanation: "
        f"{{\"city\": \"str\", \"state\": \"str\", \"zip\": \"str\", \"country\": \"ISO2\"}}. "
        f"For this place: '{place_name}'. Use main city zip. State = empty string if not applicable."
    )
    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
        resp = requests.post(api_url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 200, "temperature": 0.0, "thinkingConfig": {"thinkingBudget": 0}}
        }, timeout=8)
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        raw_clean = re.sub(r"```(?:json)?\s*", "", raw).strip()
        return json.loads(re.search(r"\{.*\}", raw_clean, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"Location resolve failed for '{place_name}': {e}")
        return None

# --- GEMINI: RESOLVE CITY TO LOCODE ---

def resolve_locode(place_name):
    """
    Converts a city name to UN/LOCODE or IATA code for Freightos.
    Returns e.g. "HEL" for Helsinki, "MNL" for Manila.
    """
    prompt = (
        f"Return ONLY the 3-letter IATA airport code or UN/LOCODE for: '{place_name}'. "
        f"No explanation, just the code. Examples: Helsinki=HEL, Manila=MNL, Rotterdam=RTM, Shanghai=SHA."
    )
    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
        resp = requests.post(api_url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 10, "temperature": 0.0, "thinkingConfig": {"thinkingBudget": 0}}
        }, timeout=6)
        code = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip().upper()
        if re.match(r'^[A-Z]{3}$', code):
            return code
        return None
    except Exception as e:
        logger.warning(f"Locode resolve failed for '{place_name}': {e}")
        return None

# --- FREIGHTOS: REAL FREIGHT RATES ---

def get_freightos_rates(origin, destination, weight_kg):
    """
    Fetches real international freight rates from Freightos.
    Covers Air, Sea, Road globally. Best for >10kg shipments.
    Returns list of rate options sorted by price, or empty list on failure.
    """
    if not FREIGHTOS_KEY:
        return []

    origin_code = resolve_locode(origin)
    dest_code   = resolve_locode(destination)

    if not origin_code or not dest_code:
        logger.warning(f"Could not resolve locodes for Freightos: {origin} -> {destination}")
        return []

    try:
        params = {
            "origin":      origin_code,
            "destination": dest_code,
            "weight":      weight_kg,
            "loadtype":    "boxes",
            "quantity":    1,
            "apiKey":      FREIGHTOS_KEY
        }
        resp = requests.get(
            "https://ship.freightos.com/api/shippingCalculator",
            params=params,
            timeout=15
        )
        data = resp.json()

        rates = []
        for quote in data.get("quotes", []):
            price = quote.get("totalPrice") or quote.get("price")
            if price:
                rates.append({
                    "carrier":  quote.get("provider", "Freight Forwarder"),
                    "service":  quote.get("serviceType", ""),
                    "price":    float(price),
                    "currency": quote.get("currency", "USD"),
                    "days":     quote.get("transitDays"),
                    "mode":     quote.get("mode", "")
                })

        rates.sort(key=lambda x: x["price"])
        logger.info(f"Freightos: {len(rates)} rates for {origin_code} -> {dest_code}")
        return rates[:5]

    except Exception as e:
        logger.warning(f"Freightos API error: {e}")
        return []

# --- EASYSHIP: REAL CARRIER RATES (EU-FIRST) ---

def get_easyship_rates(origin, destination, weight_kg):
    """
    Fetches real rates from Easyship — 550+ couriers, strong EU coverage.
    Best for parcels from Europe to anywhere globally.
    Returns top 5 options sorted by price, or empty list on failure.
    """
    if not EASYSHIP_KEY:
        return []

    origin_addr = resolve_location(origin)
    dest_addr   = resolve_location(destination)

    if not origin_addr or not dest_addr:
        logger.warning("Could not resolve addresses for Easyship")
        return []

    # Easyship uses grams
    weight_g = weight_kg * 1000

    payload = {
        "origin_country_alpha2":      origin_addr.get("country", "FI"),
        "origin_postal_code":         origin_addr.get("zip", ""),
        "destination_country_alpha2": dest_addr.get("country", "PH"),
        "destination_postal_code":    dest_addr.get("zip", ""),
        "parcels": [{
            "total_actual_weight": weight_kg,
            "height": 15,
            "width":  20,
            "length": 30
        }],
        "output_currency": "USD"
    }

    try:
        resp = requests.post(
            "https://public-api-sandbox.easyship.com/rates/v2",
            headers={
                "Authorization": f"Bearer {EASYSHIP_KEY}",
                "Content-Type":  "application/json"
            },
            json=payload,
            timeout=15
        )
        data = resp.json()

        rates = []
        for rate in data.get("rates", []):
            total = rate.get("total_charge") or rate.get("shipment_charge")
            if total:
                rates.append({
                    "carrier":  rate.get("courier_name", "Courier"),
                    "service":  rate.get("service_name", ""),
                    "price":    float(total),
                    "currency": rate.get("currency", "USD"),
                    "days":     rate.get("estimated_days"),
                    "mode":     "Air"
                })

        rates.sort(key=lambda x: x["price"])
        logger.info(f"Easyship: {len(rates)} rates for {origin} -> {destination}")
        return rates[:5]

    except Exception as e:
        logger.warning(f"Easyship API error: {e}")
        return []

# --- SHIPPO: REAL CARRIER RATES ---

def get_shippo_rates(origin, destination, weight_kg):
    """
    Fetches real rates from Shippo for parcel shipments (under 70kg).
    Returns top 5 options sorted by price, or empty list on failure.
    """
    if not SHIPPO_KEY:
        return []

    origin_addr = resolve_location(origin)
    dest_addr   = resolve_location(destination)

    if not origin_addr or not dest_addr:
        logger.warning("Could not resolve addresses for Shippo")
        return []

    weight_lbs = round(weight_kg * 2.20462, 2)

    shipment_payload = {
        "address_from": {
            "city":    origin_addr.get("city", origin),
            "state":   origin_addr.get("state", ""),
            "zip":     origin_addr.get("zip", ""),
            "country": origin_addr.get("country", "FI"),
        },
        "address_to": {
            "city":    dest_addr.get("city", destination),
            "state":   dest_addr.get("state", ""),
            "zip":     dest_addr.get("zip", ""),
            "country": dest_addr.get("country", "PH"),
        },
        "parcels": [{
            "length": "30",
            "width":  "20",
            "height": "15",
            "distance_unit": "cm",
            "weight": str(weight_lbs),
            "mass_unit": "lb"
        }],
        "async": False
    }

    try:
        resp = requests.post(
            "https://api.goshippo.com/shipments/",
            headers={
                "Authorization": f"ShippoToken {SHIPPO_KEY}",
                "Content-Type": "application/json"
            },
            json=shipment_payload,
            timeout=15
        )
        data = resp.json()

        rates = []
        for rate in data.get("rates", []):
            if rate.get("amount") and rate.get("provider"):
                rates.append({
                    "carrier":        rate["provider"],
                    "service":        rate.get("servicelevel", {}).get("name", ""),
                    "price":          float(rate["amount"]),
                    "currency":       rate.get("currency", "USD"),
                    "days":           rate.get("estimated_days"),
                    "rate_object_id": rate.get("object_id")
                })

        rates.sort(key=lambda x: x["price"])
        logger.info(f"Shippo: {len(rates)} rates for {origin} -> {destination}")
        return rates[:5]

    except Exception as e:
        logger.warning(f"Shippo API error: {e}")
        return []

# --- GEMINI: ROUTE INTELLIGENCE ---

def get_gemini_signal(origin, dest, cargo, weight, news, alerts):
    """
    Gemini provides route context: mode, risk, customs, actions, hidden costs.
    Used for intelligence layer — price comes from Shippo when available.
    """
    prompt = (
        f"Return ONLY JSON: {{\"mode\":\"Road|Sea|Air|Rail\", "
        f"\"currency\":\"EUR|USD\", \"risk\":\"Low|Med|High\", \"actions\":[\"str\"], "
        f"\"p_min\":int, \"p_max\":int, "
        f"\"dist_km\":int, \"customs\":bool, \"note\":\"str\", "
        f"\"hidden_costs\":[\"str\"]}}. "
        f"Use EUR for intra-European routes, USD for all global routes. "
        f"Route: {origin} to {dest}. Cargo: {cargo}, {weight}kg. "
        f"Context News: {json.dumps(news)}. Alerts: {alerts}. "
        f"CRITICAL: Evaluate risk ONLY for THIS SPECIFIC ROUTE. "
        f"In hidden_costs: list realistic extra costs specific to this route — "
        f"fuel surcharges, customs duties, handling fees, insurance estimates."
    )
    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
        resp = requests.post(api_url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 1000,
                "temperature": 0.1,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }, timeout=12)
        raw       = resp.json()['candidates'][0]['content']['parts'][0]['text']
        raw_clean = re.sub(r"```(?:json)?\s*", "", raw).strip()
        ai        = json.loads(re.search(r"\{.*\}", raw_clean, re.DOTALL).group())
        if not all(k in ai for k in ["mode", "risk", "actions"]):
            raise ValueError("Missing required fields")
        return ai
    except Exception as e:
        logger.error(f"Gemini failure: {e}")
        return None

# --- SIGNAL ENDPOINT ---

@app.route("/signal", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def get_signal():
    start_time = time.time()
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args

    origin = str(data.get("from", ""))[:80]
    dest   = str(data.get("to",   ""))[:80]
    cargo  = str(data.get("cargo", "General Goods"))[:80]

    try:
        weight = float(data.get("weight", 500))
        if weight <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Weight must be a positive number."}), 400

    if not origin or not dest:
        return jsonify({"error": "Missing 'from' or 'to' parameters."}), 400

    # 1. SANCTIONS SHIELD
    o_c, d_c, c_c = origin.lower(), dest.lower(), cargo.lower()
    SANCTIONED_COUNTRIES = [
        "russia", "venäjä", "belarus", "valko-venäjä",
        "iran", "syria", "north korea", "dprk"
    ]
    if any(s in o_c for s in SANCTIONED_COUNTRIES) or any(s in d_c for s in SANCTIONED_COUNTRIES):
        return jsonify({"hard_stop": True, "reason": "Trade sanctions apply to this route."}), 451

    # 2. CACHE CHECK
    cache_key = f"z1.1:{hashlib.md5(f'{o_c}{d_c}{c_c}{int(weight)}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            res = json.loads(cached)
            res["metadata"]["cache_hit"] = True
            return jsonify(res)
    except Exception:
        pass

    # 3. LIVE INTELLIGENCE
    news, alerts = fetch_live_signals()

    # 4. FX RATE
    fx_rate = get_live_fx_rate()

    # 5. PARALLEL: Easyship + Shippo (≤70kg) + Freightos + Gemini
    with concurrent.futures.ThreadPoolExecutor() as executor:
        easyship_future  = executor.submit(get_easyship_rates, origin, dest, weight)
        shippo_future    = executor.submit(get_shippo_rates, origin, dest, weight) if weight <= 70 else None
        freightos_future = executor.submit(get_freightos_rates, origin, dest, weight)
        gemini_future    = executor.submit(get_gemini_signal, origin, dest, cargo, weight, news, alerts)

        easyship_rates  = easyship_future.result()
        shippo_rates    = shippo_future.result() if shippo_future else []
        freightos_rates = freightos_future.result()
        ai              = gemini_future.result()

    if not ai:
        return jsonify({"error": "Signal loss. Try again."}), 503

    # 6. PRICE: merge all live rates, sort by price, fallback to Gemini
    all_live_rates = sorted(easyship_rates + shippo_rates + freightos_rates, key=lambda x: x["price"])

    if all_live_rates:
        currency     = all_live_rates[0]["currency"]
        price_min    = all_live_rates[0]["price"]
        price_max    = all_live_rates[-1]["price"] if len(all_live_rates) > 1 else price_min * 1.5
        price_source = "live"
        carriers_available = [
            f"{r['carrier']} {r['service']} — {r['price']} {r['currency']}"
            + (f" ({r['days']}d)" if r.get("days") else "")
            for r in all_live_rates[:5]
        ]
    else:
        currency  = ai.get("currency", "USD")
        p_min_raw = ai.get("p_min", 500)
        p_max_raw = ai.get("p_max", 1000)
        if currency == "USD":
            price_min = round(p_min_raw * fx_rate)
            price_max = round(p_max_raw * fx_rate)
        else:
            price_min = p_min_raw
            price_max = p_max_raw
        price_source       = "estimate"
        carriers_available = []

    # 7. MISC CALCULATIONS
    is_haz = bool(re.search(r'(batter|lithium|chemic|hazard|hazmat|\bun\d{4}\b)', c_c))
    bucket = get_weight_bucket(weight)
    co2    = get_co2_impact(ai['mode'], ai.get("dist_km", 0), weight)
    req_id = str(uuid.uuid4())
    ua     = request.headers.get('User-Agent', '')
    trust  = compute_trust(ai, news, alerts, False)

    # 8. RESPONSE
    response = {
        "signal": {
            "price_estimate":     f"{round(price_min)} - {round(price_max)} {currency}",
            "price_source":       price_source,
            "currency":           currency,
            "transport_mode":     ai['mode'],
            "trust_score":        trust,
            "risk_level":         ai.get("risk", "Med"),
            "hazardous_flag":     is_haz,
            "customs_required":   ai.get("customs", True),
            "note":               ai.get("note", ""),
            "carriers_available": carriers_available,
            "hidden_costs":       ai.get("hidden_costs", [])
        },
        "live_context": {
            "news":           news,
            "disaster_alert": alerts
        },
        "do_these_3_things": (ai.get("actions", []) + ["Verify docs", "Check route"])[:3],
        "environmental_impact": {
            "co2_kg":           co2,
            "offset_available": True
        },
        "metadata": {
            "engine":      "Zemlo AI v1.1",
            "request_id":  req_id[:8],
            "cache_hit":   False,
            "latency_sec": round(time.time() - start_time, 2),
            "timestamp":   datetime.now(timezone.utc).isoformat()
        }
    }

    # 9. STORAGE
    try:
        redis_client.set(cache_key, json.dumps(response), ex=300)
        supabase.table("signals").insert({
            "request_id":     req_id,
            "origin":         origin,
            "destination":    dest,
            "cargo":          cargo,
            "mode":           ai['mode'],
            "type":           identify_agent(ua),
            "bot_name":       ua[:100],
            "co2_kg":         co2,
            "price_estimate": response["signal"]["price_estimate"],
            "trust_score":    trust,
            "currency":       currency,
            "weight_bucket":  bucket
        }).execute()
    except Exception as e:
        logger.warning(f"Storage error: {e}")

    return jsonify(response)

# --- HEALTH CHECK ---

@app.route("/health")
def health():
    if request.args.get("deep") == "true":
        status = {"status": "Operational", "version": "1.1", "services": {}}
        try:
            redis_client.get("health-check")
            status["services"]["redis"] = "Connected"
        except Exception:
            status["services"]["redis"] = "Disconnected"
        try:
            supabase.table("signals").select("id").limit(1).execute()
            status["services"]["supabase"] = "Connected"
        except Exception:
            status["services"]["supabase"] = "Disconnected"
        status["services"]["shippo"]    = "Configured" if SHIPPO_KEY else "Missing"
        status["services"]["freightos"] = "Configured" if FREIGHTOS_KEY else "Missing"
        status["services"]["easyship"]  = "Configured" if EASYSHIP_KEY else "Missing"
        return jsonify(status)
    return jsonify({"status": "Operational", "version": "1.1"})

@app.route("/")
def index():
    return jsonify({
        "name":        "Zemlo AI",
        "version":     "1.1",
        "description": "Carrier-neutral logistics signal layer for AI agents and developers.",
        "status":      "Operational",
        "usage":       "GET /signal?from=Helsinki&to=Manila&cargo=Electronics&weight=20",
        "docs":        "https://github.com/zemloai-ctrl/zemloai-api",
        "auth":        "None required",
        "contact":     "info@zemloai.com"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
