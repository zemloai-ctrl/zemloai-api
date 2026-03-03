import os, json, requests, hashlib, uuid, re, logging, concurrent.futures
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v1.9.2")

# --- KONFIGURAATIO ---
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["100 per minute"], storage_uri="memory://")
redis_client = Redis(url=os.environ.get("UPSTASH_REDIS_REST_URL"), token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"))
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# --- APUFUNKTIOT ---

def compute_trust(ai_data):
    risk_map = {"Low": 95, "Med": 75, "High": 45}
    score = risk_map.get(ai_data.get("risk", "Med"), 50)
    if ai_data.get("dist_km", 0) == 0: score -= 10
    return max(min(score, 100), 10)

def compute_co2(mode, dist_km, weight_kg):
    factors = {"Air": 0.5, "Road": 0.1, "Rail": 0.03, "Sea": 0.015}
    return round(float(dist_km or 0) * (float(weight_kg) / 1000) * factors.get(mode, 0.1), 1)

# --- LIVE CONTEXT (Rinnakkaisajona) ---

def fetch_news():
    try:
        url = f"https://newsapi.org/v2/everything?q=logistics+strike+delay+port&pageSize=2&apiKey={os.environ.get('NEWS_API_KEY')}"
        r = requests.get(url, timeout=3).json()
        return [a['title'] for a in r.get('articles', [])]
    except Exception: return []

def fetch_weather():
    try:
        r = requests.get("https://www.gdacs.org/xml/rss.xml", timeout=3)
        return "RED ALERT: Severe global disaster detected." if re.search(r'\bRed\b', r.text) else None
    except Exception: return None

# --- PÄÄLOGIIKKA ---

@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args
    origin = str(data.get("from", ""))[:80]
    dest = str(data.get("to", ""))[:80]
    cargo = str(data.get("cargo", "General"))[:80]
    
    try:
        weight_val = data.get("weight", 500)
        weight = float(weight_val)
        if weight <= 0: raise ValueError
    except (ValueError, TypeError): 
        return jsonify({"error": "Invalid weight. Must be positive number."}), 400

    if not origin or not dest: 
        return jsonify({"error": "Missing params: 'from' and 'to' required."}), 400

    # 1. BLACKLIST (Sanctions 2026)
    o_c, d_c, c_c = origin.lower(), dest.lower(), cargo.lower()
    sanctions = ["russia", "venäjä", "belarus", "iran", "syria", "north korea", "moscow", "st petersburg"]
    if any(s in o_c for s in sanctions) or any(s in d_c for s in sanctions):
        return jsonify({"hard_stop": True, "reason": "Sanctions: Route blocked."}), 451

    # 2. CACHE CHECK (TTL 300s / 5 min)
    cache_key = f"z1.9.2:{hashlib.md5(f'{o_c}{d_c}{c_c}{int(weight)}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            res = json.loads(cached)
            res["metadata"]["cache_hit"] = True
            return jsonify(res)
    except Exception: pass

    # 3. RINNAKKAISET HAUT (Uutiset, Sää)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f_news = executor.submit(fetch_news)
        f_weather = executor.submit(fetch_weather)
        news_list = f_news.result()
        weather_alert = f_weather.result()

    # 4. AI CALL (Gemini 2.5 Flash)
    # Käytetään json.dumpsia estämään uutisten erikoismerkkien JSON-rikkoontuminen
    news_escaped = json.dumps(news_list)
    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool, \"note\":\"str\"}}. "
        f"Route: {origin} to {dest}, Cargo: {cargo}, {weight}kg. Context: {news_escaped}, {weather_alert}."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ.get('GEMINI_API_KEY')}"
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12)
        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        ai = json.loads(json_match.group())
        required = ["p_min", "p_max", "mode", "risk"]
        if not all(k in ai for k in required): raise ValueError("Missing AI fields")
    except Exception as e:
        logger.error(f"AI Sync Error: {e}")
        return jsonify({"error": "Engine synchronization error"}), 503

    # 5. RESPONSE CONSTRUCTION
    is_hazardous = any(w in c_c for w in ["battery", "lithium", "chemical", "hazardous"])
    co2_val = compute_co2(ai['mode'], ai.get("dist_km", 0), weight)
    full_uuid = str(uuid.uuid4())
    
    response = {
        "signal": {
            "price_estimate": f"{ai['p_min']} - {ai['p_max']} EUR",
            "transport_mode": ai['mode'],
            "trust_score": compute_trust(ai),
            "risk_level": ai.get("risk", "Med"),
            "hazardous_flag": is_hazardous,
            "customs_clearance_required": ai.get("customs", True),
            "note": ai.get("note", "")
        },
        "live_context": {
            "news": news_list,
            "disaster_alert": weather_alert
        },
        "do_these_3_things": (ai.get("actions", []) + ["Check documents", "Verify route"])[:3],
        "environmental_impact": {"co2_kg": co2_val},
        "metadata": {
            "engine": "Zemlo v1.9.2 (The Final Polish)",
            "id": full_uuid[:8],
            "cache_hit": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    # 6. CACHE (5 min) & DB
    try:
        redis_client.set(cache_key, json.dumps(response), ex=300) 
        ua = request.headers.get('User-Agent', '').lower()
        user_type = next((a.upper() for a in ['gptbot', 'chatgpt', 'claude', 'gemini', 'perplexity', 'copilot', 'anthropic'] if a in ua), "HUMAN")
        supabase.table("signals").insert({
            "id": full_uuid,
            "origin": origin, "destination": dest, "cargo": cargo, 
            "price_estimate": response["signal"]["price_estimate"],
            "mode": ai['mode'], "co2_kg": co2_val,
            "type": user_type, "bot_name": ua[:100],
            "trust_score": response["signal"]["trust_score"]
        }).execute()
    except Exception as e:
        logger.warning(f"Storage error: {e}")

    return jsonify(response)

@app.route("/")
def health(): return jsonify({"status": "Operational", "version": "1.9.2", "motto": "Logistics made easy."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
