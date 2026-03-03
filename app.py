import os, json, requests, hashlib, uuid, re, logging
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

# 1. Alustus ja konfiguraatio
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v1.8.6")

# Rate limiting (Memory-storage Render-yhteensopivuuteen)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://"
)

# Yhteydet
redis_client = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)
supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# 2. Apuohjelmat
def compute_trust(ai_data):
    risk_map = {"Low": 95, "Med": 70, "High": 40}
    base_score = risk_map.get(ai_data.get("risk", "Med"), 50)
    if ai_data.get("dist_km", 0) == 0:
        base_score -= 10
    return max(min(base_score, 100), 10)

def compute_co2(mode, dist_km, weight_kg):
    try:
        factors = {"Air": 0.5, "Road": 0.1, "Rail": 0.03, "Sea": 0.015}
        factor = factors.get(mode, 0.1)
        return round(float(dist_km) * (float(weight_kg) / 1000) * factor, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0

def get_context_warnings(origin_clean, dest_clean, cargo_clean):
    warnings = []
    text = origin_clean + " " + dest_clean
    now = datetime.now(timezone.utc)

    if now.year == 2026 and ((now.month == 2 and now.day >= 15) or (now.month == 3 and now.day <= 25)):
        ram_countries = ["saudi", "uae", "dubai", "qatar", "egypt", "turkey", "indonesia", "malaysia"]
        if any(c in text for c in ram_countries):
            warnings.append("Ramadan 2026: Expect local delivery delays and altered hours.")

    if any(p in text for p in ["suez", "red sea", "aden", "yemen", "djibouti"]):
        warnings.append("Red Sea Transit: Ongoing risk. Expect insurance surcharges.")

    if any(word in cargo_clean for word in ["battery", "batteries", "hazardous", "chemical", "acid"]):
        warnings.append("Hazardous Cargo: ADR/IMDG documentation and UN-rated packaging mandatory.")

    return warnings

# 3. Gemini Integrointi
def get_ai_signal(origin, dest, cargo, weight):
    s_origin, s_dest, s_cargo = origin[:80], dest[:80], cargo[:80]

    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool}}. "
        f"Route: {s_origin} to {s_dest}, Cargo: {s_cargo}, {weight}kg. Date: March 2026."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ.get('GEMINI_API_KEY')}"
    
    try:
        # FIX: Timeout nostettu 20 sekuntiin monimutkaisia hakuja varten
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        resp.raise_for_status()
        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match: return None
        return json.loads(json_match.group())
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return None

# 4. Reitit
@app.route("/robots.txt")
def robots_txt():
    # BOT STRATEGY: Toivotetaan AI-agentit tervetulleeksi
    content = "User-agent: *\nAllow: /\nDisallow: /admin\n\n# Zemlo AI - The Global Logistics Signal Hub 2026"
    return Response(content, mimetype="text/plain")

@app.route("/signal", methods=["GET", "POST"])
@limiter.limit("60 per minute")
def get_signal():
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args

    origin = data.get("from", "").strip()
    dest = data.get("to", "").strip()
    cargo = data.get("cargo", "General").strip()

    try:
        weight = float(data.get("weight", 500))
        if weight <= 0: return jsonify({"error": "Weight must be positive."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid weight format."}), 400

    if not origin or not dest:
        return jsonify({"error": "Missing parameters."}), 400

    origin_clean, dest_clean, cargo_clean = origin.lower().replace("_", " "), dest.lower().replace("_", " "), cargo.lower().replace("_", " ")

    # THE SHIELD: Sanctions
    sanctions = ["russia", "petersburg", "moscow", "iran", "tehran", "north korea", "belarus", "syria", "venäjä"]
    if any(s in origin_clean for s in sanctions) or any(s in dest_clean for s in sanctions):
        return jsonify({"hard_stop": True, "reason": "Sanctions: Automated quoting disabled.", "metadata": {"engine": "Zemlo OS 1.8.6 (The Shield)"}}), 451

    # Cache
    cache_key = f"z1.8.6:{hashlib.md5(f'{origin_clean}{dest_clean}{cargo_clean}{int(weight)}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            res = json.loads(cached)
            res["metadata"]["cache_hit"] = True
            return jsonify(res)
    except: pass

    ai = get_ai_signal(origin, dest, cargo, weight)
    if not ai or not all(k in ai for k in ["p_min", "p_max", "mode", "actions"]):
        return jsonify({"error": "Logistics engine busy. Please retry."}), 503

    trust = compute_trust(ai)
    co2 = compute_co2(ai.get("mode"), ai.get("dist_km", 0), weight)
    warnings = get_context_warnings(origin_clean, dest_clean, cargo_clean)
    is_hazardous = any(word in cargo_clean for word in ["battery", "batteries", "hazardous", "chemical", "acid"])

    response = {
        "signal": {
            "price_estimate": f"{ai['p_min']} - {ai['p_max']} EUR",
            "transport_mode": ai['mode'],
            "trust_score": trust,
            "risk_level": ai.get("risk", "Med"),
            "customs_clearance_required": ai.get("customs", True),
            "hazardous_flag": is_hazardous
        },
        "environmental_impact": {"estimated_co2_kg": co2},
        "context_warnings": warnings,
        "do_these_3_things": (ai['actions'] + ["Verify documents", "Confirm insurance", "Check hours"])[:3],
        "metadata": {
            "engine": "Zemlo v1.8.6 (2.5 Flash)",
            "cache_hit": False,
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    try:
        redis_client.set(cache_key, json.dumps(response), ex=300)
        ua = request.headers.get('User-Agent', '').lower()
        user_type = next((a.upper() for a in ['gptbot', 'chatgpt', 'claude', 'anthropic', 'perplexity', 'gemini', 'copilot'] if a in ua), "HUMAN")
        supabase.table("signals").insert({
            "origin": origin, "destination": dest, "cargo": cargo, "status": "success",
            "price_estimate": response["signal"]["price_estimate"],
            "trust_score": trust, "mode": ai['mode'], "type": user_type,
            "co2_kg": co2, "bot_name": ua[:100]
        }).execute()
    except Exception as e: logger.warning(f"Log fail: {e}")

    return jsonify(response)

@app.route("/")
def health():
    return jsonify({"status": "Operational", "version": "1.8.6", "shield": "Active", "agents": "Welcome"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
