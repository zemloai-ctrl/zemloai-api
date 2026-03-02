import os, time, json, requests, random, logging, hashlib, uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from upstash_redis import Redis

# ==============================
# 1. UPSTASH REST INITIALIZATION
# ==============================
redis_client = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"), 
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

app = Flask(__name__)
CORS(app) # Zemlo Connectivity: Sallii AI-agentit ja selaimet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v2.0-Upstash")

# ==============================
# 2. LOGISTICS DATA & SAFETY (v2.0 Full)
# ==============================
EU_COUNTRIES = ["austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia", "denmark", "estonia", "finland", "france", "germany", "greece", "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg", "malta", "netherlands", "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden"]

# Ramadan 2026: 1.3.2026 - 30.3.2026 (Loppuu 31.3. 00:00 UTC)
RAMADAN_2026_START = 1740787200 
RAMADAN_2026_END   = 1743379200 # KORJATTU: Sisältää nyt koko 30. maaliskuuta
RAMADAN_COUNTRIES = ["saudi", "uae", "dubai", "qatar", "kuwait", "egypt", "indonesia", "malaysia", "turkey", "pakistan", "jordan", "oman"]

SANCTIONED_ROUTES = [
    (["iran", "tehran"], "US OFAC + EU sanctions. Western carriers prohibited."),
    (["north korea", "pyongyang"], "UN Security Council total embargo."),
    (["russia", "moscow", "st. petersburg"], "EU/US sanctions active."),
    (["belarus", "minsk"], "EU sanctions active."),
    (["syria", "damascus"], "Comprehensive UN/EU sanctions."),
    (["venezuela", "caracas"], "US/EU financial and trade sanctions."),
    (["cuba", "havana"], "US trade embargo."),
    (["myanmar", "burma"], "EU/US military and trade sanctions."),
    (["sudan", "khartoum"], "UN/EU sanctions on specific sectors."),
    (["mali"], "ECOWAS and international trade restrictions.")
]

ILLEGAL_CARGO_RULES = [
    (["cannabis", "marijuana", "weed", "hashish"], ["singapore", "dubai", "uae", "saudi", "china", "malaysia", "indonesia"], 
     "Drug trafficking carries capital punishment or life imprisonment in this region."),
    (["ivory", "rhino horn"], [], "CITES-prohibited wildlife products. Illegal globally.")
]

# ==============================
# 3. CORE LOGIC FUNCTIONS
# ==============================
def redis_safe(func, *args, **kwargs):
    try: return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Upstash Error: {e}")
        return None

def compute_trust(ai_data):
    base = 100
    p_min = ai_data.get('p_min', 0)
    p_max = ai_data.get('p_max', 0)
    risk = ai_data.get('risk', 'Low').lower()
    
    if p_max > p_min * 2: base -= 15 # Epävarmuus hinta-arviossa
    if risk == 'high': base -= 30
    if risk == 'med': base -= 10
    return max(10, base)

def check_customs(origin, dest):
    """KORJATTU: Tarkistaa sisältääkö syöte EU-maan nimen (esim. 'Helsinki, Finland')."""
    o, d = origin.lower(), dest.lower()
    o_is_eu = any(country in o for country in EU_COUNTRIES)
    d_is_eu = any(country in d for country in EU_COUNTRIES)
    
    if o_is_eu and d_is_eu: return False 
    if o == d: return False
    return True

# ==============================
# 4. AI AGENT (Gemini 2.5 Flash)
# ==============================
def get_ai_signal(origin, dest, cargo):
    api_key = os.environ.get("GEMINI_API_KEY")
    prompt = (
        f"Zemlo v2.0 Logistics AI. Return ONLY raw JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"string\", \"risk\":\"Low|Med|High\", \"actions\":[\"str\"]}}. "
        f"Route: {origin}-{dest}, Cargo: {cargo}"
    )
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=8)
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}")
        return {"error": "AI_OFFLINE", "details": str(e)}

# ==============================
# 5. ENDPOINTS
# ==============================
@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    start_time = time.time()
    data = request.get_json(silent=True) if request.method == "POST" else request.args
    
    origin = data.get("from", "").strip()
    dest = data.get("to", "").strip()
    cargo = data.get("cargo", "General Cargo").strip()

    # --- SAFETY LAYER ---
    if not origin or not dest:
        return jsonify({"error": "Missing 'from' or 'to' fields"}), 400

    for keywords, reason in SANCTIONED_ROUTES:
        if any(kw in origin.lower() or kw in dest.lower() for kw in keywords):
            redis_safe(redis_client.incr, "metrics:hard_stops")
            return jsonify({"hard_stop": True, "reason": reason, "type": "Sanctions"}), 451
    
    for keywords, regions, reason in ILLEGAL_CARGO_RULES:
        if any(kw in cargo.lower() for kw in keywords):
            if not regions or any(reg in dest.lower() for reg in regions):
                redis_safe(redis_client.incr, "metrics:hard_stops")
                return jsonify({"hard_stop": True, "reason": reason, "type": "Illegal Cargo"}), 451

    # --- CACHE (300s / 5 min TTL) ---
    cache_key = f"z2:cache:{hashlib.md5(f'{origin}{dest}{cargo}'.encode()).hexdigest()}"
    cached = redis_safe(redis_client.get, cache_key)
    if cached: 
        redis_safe(redis_client.incr, "metrics:cache_hits")
        return jsonify(json.loads(cached))

    # --- AI SIGNAL ---
    ai = get_ai_signal(origin, dest, cargo)
    if "error" in ai: return jsonify(ai), 503

    # --- LOGIC & METRICS ---
    trust = compute_trust(ai)
    customs_needed = check_customs(origin, dest)
    
    redis_safe(redis_client.incr, "metrics:requests_total")
    redis_safe(redis_client.incrbyfloat, "metrics:trust_sum", float(trust))

    # --- RAMADAN INJECTION ---
    warnings = []
    now = time.time()
    if RAMADAN_2026_START <= now <= RAMADAN_2026_END:
        combined_route = (origin + " " + dest).lower()
        if any(country in combined_route for country in RAMADAN_COUNTRIES):
            warnings.append("⚠️ RAMADAN 2026 Context: Port and customs operations in this region may experience delays.")

    response = {
        "signal": {
            "price_estimate": f"{ai.get('p_min')} - {ai.get('p_max')} EUR",
            "transport_mode": ai.get("mode"),
            "trust_score": trust,
            "customs_clearance_required": customs_needed,
            "risk_level": ai.get("risk")
        },
        "do_these_3_things": ai.get("actions", [])[:3],
        "context_warnings": warnings,
        "metadata": {"engine": "Zemlo v2.0.3-Upstash", "id": str(uuid.uuid4())[:8]}
    }

    # Tallennus
    redis_safe(redis_client.set, cache_key, json.dumps(response), ex=300)
    return jsonify(response)

@app.route('/test-db')
def test_db():
    try:
        redis_client.set('z2_status', 'OK')
        return {"status": "success", "msg": f"Zemlo 2.0 -> Upstash: {redis_client.get('z2_status')}"}
    except Exception as e: return {"status": "error", "msg": str(e)}, 500

@app.route("/")
def health():
    return jsonify({"status": "Zemlo 2.0 Operational", "version": "2.0.3-Upstash", "timestamp": "March 2026"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
