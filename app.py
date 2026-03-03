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
logger = logging.getLogger("Zemlo-v1.9.6")

# --- KONFIGURAATIO ---
REDIS_URL    = os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN  = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY")
NEWS_KEY     = os.environ.get("NEWS_API_KEY")

redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)
supabase     = create_client(SUPABASE_URL, SUPABASE_KEY)
limiter      = Limiter(key_func=get_remote_address, app=app, default_limits=["100 per minute"], storage_uri="memory://")

# --- VALUUTTA-LOGIIKKA (v1.9.6) ---

# EUR-vyöhyke: EU-maat + lähialueet joissa EUR on standardi
EUR_ZONE = [
    "finland", "helsinki", "sweden", "stockholm", "norway", "oslo",
    "denmark", "copenhagen", "germany", "berlin", "hamburg", "frankfurt",
    "france", "paris", "spain", "madrid", "barcelona", "italy", "rome", "milan",
    "netherlands", "amsterdam", "rotterdam", "belgium", "brussels",
    "austria", "vienna", "poland", "warsaw", "czech", "prague",
    "hungary", "budapest", "romania", "bucharest", "bulgaria", "sofia",
    "croatia", "zagreb", "slovakia", "bratislava", "slovenia", "ljubljana",
    "estonia", "tallinn", "latvia", "riga", "lithuania", "vilnius",
    "portugal", "lisbon", "greece", "athens", "ireland", "dublin",
    "luxembourg", "malta", "cyprus", "nicosia",
    "switzerland", "zurich", "bern", "iceland",
    "serbia", "belgrade", "balkans", "ukraine", "kyiv"
]

# USD-vyöhyke: kaikki muut globaalit markkinat
USD_ZONE = [
    "usa", "united states", "new york", "los angeles", "chicago", "houston",
    "canada", "toronto", "vancouver", "montreal",
    "china", "beijing", "shanghai", "shenzhen", "guangzhou",
    "japan", "tokyo", "osaka",
    "south korea", "seoul",
    "singapore", "hong kong",
    "australia", "sydney", "melbourne",
    "india", "mumbai", "delhi", "bangalore",
    "brazil", "sao paulo", "rio",
    "mexico", "mexico city",
    "uae", "dubai", "abu dhabi",
    "saudi", "riyadh", "jeddah",
    "turkey", "istanbul", "ankara",
    "egypt", "cairo",
    "south africa", "johannesburg", "cape town",
    "indonesia", "jakarta",
    "malaysia", "kuala lumpur",
    "thailand", "bangkok",
    "vietnam", "ho chi minh",
    "philippines", "manila",
    "taiwan", "taipei",
    "new zealand", "auckland",
    "argentina", "buenos aires",
    "chile", "santiago",
    "colombia", "bogota",
    "peru", "lima",
    "nigeria", "lagos",
    "kenya", "nairobi",
    "morocco", "casablanca"
]

# Kiinteä EUR→USD konversiokerroin (v1.9.6: staattinen, v2.0: live FX API)
EUR_TO_USD = 1.09

def determine_currency(origin_clean, dest_clean):
    """
    Älykäs valuutan valinta reitin perusteella.
    - Molemmat EUR-vyöhykkeessä → EUR
    - Toinen tai molemmat USD-vyöhykkeessä → USD
    - Tuntematon reitti → USD (kansainvälinen standardi)
    """
    is_eur_origin = any(z in origin_clean for z in EUR_ZONE)
    is_eur_dest   = any(z in dest_clean   for z in EUR_ZONE)
    is_usd_origin = any(z in origin_clean for z in USD_ZONE)
    is_usd_dest   = any(z in dest_clean   for z in USD_ZONE)

    # Intra-EUR reitti
    if is_eur_origin and is_eur_dest and not is_usd_origin and not is_usd_dest:
        return "EUR"

    # Yksikin pää on globaali → USD
    if is_usd_origin or is_usd_dest:
        return "USD"

    # Molemmat tuntemattomat → USD (kansainvälinen default)
    return "USD"

def convert_price(p_min, p_max, currency):
    """Muuntaa EUR-pohjaisen AI-hinnan oikeaan valuuttaan."""
    if currency == "USD":
        return round(p_min * EUR_TO_USD), round(p_max * EUR_TO_USD)
    return p_min, p_max

# --- BUSINESS LOGIC HELPERS ---

def identify_agent(ua):
    """Tunnistaa onko kysyjä ihminen vai AI-botti (ZBI-logiikka)."""
    ua = ua.lower()
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

def compute_trust(ai_data):
    """Trust score heijastaa datan varmuutta, ei rahdin helppoutta."""
    risk_map = {"Low": 95, "Med": 75, "High": 45}
    score = risk_map.get(ai_data.get("risk", "Med"), 50)
    if ai_data.get("dist_km", 0) == 0:
        score -= 10
    return max(min(score, 100), 10)

def get_co2_impact(mode, dist_km, weight_kg):
    """Laskee hiilijalanjäljen (Zemlo Care+ valmius)."""
    factors = {"Air": 0.5, "Road": 0.1, "Rail": 0.03, "Sea": 0.015}
    return round(float(dist_km or 0) * (float(weight_kg) / 1000) * factors.get(mode, 0.1), 2)

# --- ASYNCHRONOUS DATA FETCHING ---

def fetch_live_signals():
    """Hakee uutiset ja globaalit hälytykset rinnakkain."""
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
        f_news     = executor.submit(get_news)
        f_disaster = executor.submit(get_disasters)
        return f_news.result(), f_disaster.result()

# --- THE SIGNAL ENDPOINT ---

@app.route("/signal", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def get_signal():
    start_time = time.time()
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args

    # Input sanitointi
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

    # 1. BLACKLIST & SAFETY (Sanctions 2026)
    o_c, d_c, c_c = origin.lower(), dest.lower(), cargo.lower()
    sanctions = ["russia", "venäjä", "belarus", "iran", "syria", "north korea"]
    if any(s in o_c for s in sanctions) or any(s in d_c for s in sanctions):
        return jsonify({"hard_stop": True, "reason": "Trade sanctions apply to this route."}), 451

    # 2. VALUUTAN MÄÄRITYS (v1.9.6: älykäs reittipohjainen logiikka)
    currency = determine_currency(o_c, d_c)

    # 3. CACHE LAYER (5 min TTL — cache_key sisältää valuutan)
    cache_key = f"z1.9.6:{hashlib.md5(f'{o_c}{d_c}{c_c}{int(weight)}{currency}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            res = json.loads(cached)
            res["metadata"]["cache_hit"] = True
            return jsonify(res)
    except Exception:
        pass

    # 4. LIVE INTELLIGENCE (Rinnakkain)
    news, alerts = fetch_live_signals()

    # 5. AI ENGINE (Gemini 2.5 Flash)
    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool, \"note\":\"str\"}}. "
        f"Route: {origin} to {dest}, Cargo: {cargo}, {weight}kg. "
        f"Context: {json.dumps(news)}, {alerts}."
    )

    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
        resp    = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12)
        raw     = resp.json()['candidates'][0]['content']['parts'][0]['text']
        ai      = json.loads(re.search(r'\{.*\}', raw, re.DOTALL).group())
        if not all(k in ai for k in ["p_min", "p_max", "mode", "risk", "actions"]):
            raise ValueError("Missing required AI fields")
    except Exception as e:
        logger.error(f"AI Failure: {e}")
        return jsonify({"error": "Signal loss. Try again."}), 503

    # 6. BUSINESS LOGIC & COMPLIANCE
    is_haz = bool(re.search(r'(batter|lithium|chemic|hazard|hazmat|\bun\d{4}\b)', c_c))
    co2    = get_co2_impact(ai['mode'], ai.get("dist_km", 0), weight)
    req_id = str(uuid.uuid4())
    ua     = request.headers.get('User-Agent', '')

    # v1.9.6: Konvertoidaan hinta oikeaan valuuttaan
    final_min, final_max = convert_price(ai['p_min'], ai['p_max'], currency)

    # 7. RESPONSE OBJECT
    response = {
        "signal": {
            "price_estimate":   f"{final_min} - {final_max} {currency}",
            "currency":         currency,
            "transport_mode":   ai['mode'],
            "trust_score":      compute_trust(ai),
            "risk_level":       ai.get("risk", "Med"),
            "hazardous_flag":   is_haz,
            "customs_required": ai.get("customs", True),
            "note":             ai.get("note", "")
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
            "engine":      "Zemlo AI v1.9.6",
            "request_id":  req_id[:8],
            "cache_hit":   False,
            "latency_sec": round(time.time() - start_time, 2),
            "timestamp":   datetime.now(timezone.utc).isoformat()
        }
    }

    # 8. STORAGE (Redis 5 min + Supabase)
    try:
        redis_client.set(cache_key, json.dumps(response), ex=300)
        supabase.table("signals").insert({
            "id":             req_id,
            "origin":         origin,
            "destination":    dest,
            "cargo":          cargo,
            "mode":           ai['mode'],
            "type":           identify_agent(ua),
            "bot_name":       ua[:100],
            "co2_kg":         co2,
            "price_estimate": response["signal"]["price_estimate"],
            "trust_score":    response["signal"]["trust_score"],
            "currency":       currency
        }).execute()
    except Exception as e:
        logger.warning(f"Storage error: {e}")

    return jsonify(response)

# --- HEALTH CHECK ---

@app.route("/health")
def health():
    """Tarkistaa infrastruktuurin tilan (Redis + Supabase)."""
    status = {
        "status":   "Operational",
        "version":  "1.9.6",
        "services": {}
    }
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

    return jsonify(status)

@app.route("/")
def index():
    return "Zemlo AI API v1.9.6 - Logistics Made Easy. Use /signal for queries."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
