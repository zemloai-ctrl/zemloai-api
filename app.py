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

redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)
supabase     = create_client(SUPABASE_URL, SUPABASE_KEY)
limiter      = Limiter(key_func=get_remote_address, app=app, default_limits=["100 per minute"], storage_uri="memory://")

# --- CONSTANTS ---
SANCTIONED_COUNTRIES = ["russia", "venäjä", "belarus", "valko-venäjä", "iran", "syria", "north korea", "dprk"]

EUR_ZONE = ["finland", "helsinki", "sweden", "stockholm", "norway", "oslo", "germany", "france", "spain", "italy", "serbia", "ukraine"]
USD_ZONE = ["usa", "china", "japan", "brazil", "uae", "india", "canada", "mexico", "australia"]

# --- HELPERS ---

def get_live_fx_rate():
    cache_key = "fx_rate:EUR_USD"
    try:
        cached = redis_client.get(cache_key)
        if cached: return float(cached)
        resp = requests.get("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD", timeout=5)
        rate = resp.json()['rates']['USD']
        redis_client.set(cache_key, rate, ex=86400)
        return float(rate)
    except: return 1.09

def determine_currency(origin, dest):
    o_c, d_c = origin.lower(), dest.lower()
    if any(z in o_c for z in EUR_ZONE) and any(z in d_c for z in EUR_ZONE):
        return "EUR"
    return "USD"

def compute_trust(ai_data):
    risk_map = {"Low": 95, "Med": 75, "High": 45}
    score = risk_map.get(ai_data.get("risk", "Med"), 50)
    return max(min(score, 100), 10)

def fetch_live_signals():
    cache_key = "global_logistics_context"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            d = json.loads(cached)
            return d["news"], d["alerts"]
    except: pass

    def get_news():
        try:
            url = f"https://newsapi.org/v2/everything?q=logistics+disruption+OR+port+strike&pageSize=3&apiKey={NEWS_KEY}"
            r = requests.get(url, timeout=3).json()
            return [a['title'] for a in r.get('articles', [])]
        except: return []

    def get_disasters():
        try:
            r = requests.get("https://www.gdacs.org/xml/rss.xml", timeout=3)
            return "RED ALERT: Severe global disaster detected." if "Red" in r.text else None
        except: return None

    with concurrent.futures.ThreadPoolExecutor() as ex:
        news, alerts = ex.submit(get_news).result(), ex.submit(get_disasters).result()

    try: 
        redis_client.set(cache_key, json.dumps({"news": news, "alerts": alerts}), ex=3600)
        logger.info("Live signals cached for 1h")
    except: pass
    return news, alerts

# --- MAIN ENDPOINT ---

@app.route("/signal", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def get_signal():
    start_time = time.time()
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args

    origin = str(data.get("from", ""))[:80]
    dest   = str(data.get("to", ""))[:80]
    cargo  = str(data.get("cargo", "General Goods"))[:80]
    weight = data.get("weight", 500)

    if not origin or not dest:
        return jsonify({"error": "Missing 'from' or 'to' parameters."}), 400

    # 1. FAST SANCTIONS CHECK (Countries)
    o_c, d_c = origin.lower(), dest.lower()
    if any(s in o_c for s in SANCTIONED_COUNTRIES) or any(s in d_c for s in SANCTIONED_COUNTRIES):
        return jsonify({"hard_stop": True, "reason": "Trade sanctions apply to this route."}), 451

    # 2. CACHE & CURRENCY
    currency = determine_currency(o_c, d_c)
    cache_key = f"z1.1:{hashlib.md5(f'{o_c}{d_c}{cargo}{weight}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            res = json.loads(cached)
            res["metadata"]["cache_hit"] = True
            return jsonify(res)
    except: pass

    # 3. LIVE INTEL
    news, alerts = fetch_live_signals()

    # 4. AI ENGINE (Hybrid Sanctions Detection)
    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool, \"sanctioned\":bool, \"note\":\"str\"}}. "
        f"Route: {origin} to {dest}. Cargo: {cargo}, {weight}kg. "
        f"IMPORTANT: If route involves sanctioned territories (Russia, Belarus, Iran, Syria, North Korea) set 'sanctioned': true."
    )

    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
        resp = requests.post(api_url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 400, "temperature": 0.1}
        }, timeout=12)
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        ai = json.loads(re.search(r'\{.*\}', raw, re.DOTALL).group())
    except Exception as e:
        logger.error(f"AI Failure: {e}")
        return jsonify({"error": "Signal loss. Try again."}), 503

    # AI-level sanctions block (kaupunkitunnistus)
    if ai.get("sanctioned"):
        logger.warning(f"AI Blocked sanctioned route: {origin} -> {dest}")
        return jsonify({"hard_stop": True, "reason": "Route involves sanctioned regions identified by AI."}), 451

    # 5. CALCULATIONS
    fx_rate = get_live_fx_rate() if currency == "USD" else 1.0
    req_id = str(uuid.uuid4())
    is_haz = bool(re.search(r'(batter|lithium|chemic|hazard|hazmat|\bun\d{4}\b)', cargo.lower()))

    # 6. RESPONSE
    response = {
        "signal": {
            "price_estimate": f"{round(ai['p_min']*fx_rate)} - {round(ai['p_max']*fx_rate)} {currency}",
            "transport_mode": ai['mode'],
            "trust_score": compute_trust(ai),
            "hazardous_flag": is_haz,
            "note": ai.get("note", "")
        },
        "live_context": {"news": news, "disasters": alerts},
        "do_these_3_things": (ai.get("actions", []) + ["Verify docs", "Check route"])[:3],
        "metadata": {
            "engine": "Zemlo AI v1.1",
            "request_id": req_id[:8],
            "latency_sec": round(time.time() - start_time, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    try: redis_client.set(cache_key, json.dumps(response), ex=300)
    except: pass
    
    return jsonify(response)

@app.route("/health")
def health():
    return jsonify({"status": "Operational", "version": "1.1"})

@app.route("/")
def index():
    return "Zemlo AI v1.1 — The Global Logistics Signal. Use /signal."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
