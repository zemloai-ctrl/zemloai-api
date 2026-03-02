import os, time, json, requests, random, logging, hashlib, uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from upstash_redis import Redis
from datetime import datetime, timezone

# ==============================
# 1. INITIALIZATION
# ==============================
redis_client = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"), 
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v2.0.6-Paid")

# ==============================
# 2. LOGISTICS DATA & BLACKLISTS
# ==============================
EU_COUNTRIES = ["austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia", "denmark", "estonia", "finland", "france", "germany", "greece", "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg", "malta", "netherlands", "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden"]

RAMADAN_COUNTRIES = ["saudi", "uae", "dubai", "qatar", "kuwait", "egypt", "indonesia", "malaysia", "turkey", "pakistan", "jordan", "oman", "riyadh", "jeddah", "abu dhabi", "cairo", "jakarta", "kuala lumpur", "istanbul", "karachi"]

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
    (["cannabis", "marijuana", "weed", "hashish"],
     ["singapore", "dubai", "uae", "saudi", "china", "malaysia", "indonesia",
      "japan", "tokyo", "osaka", "south korea", "seoul", "busan",
      "vietnam", "hanoi", "ho chi minh", "philippines", "manila",
      "thailand", "bangkok"],
     "Drug trafficking carries capital punishment or life imprisonment in this region."),
    (["ivory", "rhino horn"], [], "CITES-prohibited wildlife products. Illegal globally.")
]

# ==============================
# 3. LOGIC FUNCTIONS
# ==============================
def redis_safe(func, *args, **kwargs):
    try: return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Upstash Error: {e}")
        return None

def get_ramadan_warning(origin, dest):
    now = datetime.now(timezone.utc)
    ramadan_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    ramadan_end   = datetime(2026, 3, 31, tzinfo=timezone.utc)
    is_ramadan = ramadan_start <= now <= ramadan_end

    if not is_ramadan: return None
        
    combined = (origin + " " + dest).lower()
    if any(country in combined for country in RAMADAN_COUNTRIES):
        return "⚠️ RAMADAN 2026 (1–31 Mar): Port and customs operations in this region may experience significant delays."
    return None

def compute_trust(ai_data):
    base = 100
    p_min, p_max = ai_data.get('p_min', 0), ai_data.get('p_max', 0)
    risk = ai_data.get('risk', 'Low').lower()
    if p_max > p_min * 2: base -= 15
    if risk == 'high': base -= 30
    if risk == 'med': base -= 10
    return max(10, base)

def check_customs(origin, dest):
    o, d = origin.lower(), dest.lower()
    o_is_eu = any(country in o for country in EU_COUNTRIES)
    d_is_eu = any(country in d for country in EU_COUNTRIES)
    return not (o_is_eu and d_is_eu) if o != d else False

# ==============================
# 4. AI AGENT (v2.0.6 - NO TIMEOUTS)
# ==============================
def get_ai_signal(origin, dest, cargo):
    api_key = os.environ.get("GEMINI_API_KEY")
    prompt = (
        f"Zemlo v2.0 Logistics AI. Current: March 2026. "
        f"Return ONLY raw JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"string\", \"risk\":\"Low|Med|High\", \"actions\":[\"str\"]}}. "
        f"Route: {origin}-{dest}, Cargo: {cargo}. "
        f"Include ADR/UN-numbers for batteries."
    )
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    try:
        logger.info(f"AI Fetch for: {origin}-{dest}")
        # NOSTETTU 8 -> 30 jotta maksettu tila toimii varmasti
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        json_str = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return {"error": "AI_OFFLINE", "details": str(e)}

# ==============================
# 5. ENDPOINTS
# ==============================
@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    data = request.get_json(silent=True) if request.method == "POST" else request.args
    origin, dest = data.get("from", "").strip(), data.get("to", "").strip()
    cargo = data.get("cargo", "General Cargo").strip()

    if not origin or not dest: return jsonify({"error": "Missing route"}), 400

    # Safety
    for keywords, reason in SANCTIONED_ROUTES:
        if any(kw in origin.lower() or kw in dest.lower() for kw in keywords):
            return jsonify({"hard_stop": True, "reason": reason}), 451
            
    # Cache
    cache_key = f"z2:cache:{hashlib.md5(f'{origin}{dest}{cargo}'.encode()).hexdigest()}"
    cached = redis_safe(redis_client.get, cache_key)
    
    if cached:
        res = json.loads(cached)
        res["metadata"]["cache_hit"] = True
        return jsonify(res)

    # AI & Business Logic
    ai = get_ai_signal(origin, dest, cargo)
    if "error" in ai: return jsonify(ai), 503

    ramadan = get_ramadan_warning(origin, dest)
    
    response = {
        "signal": {
            "price_estimate": f"{ai.get('p_min')} - {ai.get('p_max')} EUR",
            "transport_mode": ai.get("mode"),
            "trust_score": compute_trust(ai),
            "customs_clearance_required": check_customs(origin, dest),
            "risk_level": ai.get("risk")
        },
        "do_these_3_things": ai.get("actions", [])[:3],
        "context_warnings": [ramadan] if ramadan else [],
        "metadata": {
            "engine": "Zemlo v2.0.6-Paid", 
            "id": str(uuid.uuid4())[:8], 
            "cache_hit": False
        }
    }
    
    redis_safe(redis_client.set, cache_key, json.dumps(response), ex=300)
    return jsonify(response)

@app.route("/")
def health():
    return jsonify({"status": "Zemlo 2.0 Operational", "version": "2.0.6-Paid"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
