import os, json, requests, hashlib, uuid, re, logging
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

# 1. Alustus
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v1.8.8")

limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["100 per minute"], storage_uri="memory://")

redis_client = Redis(url=os.environ.get("UPSTASH_REDIS_REST_URL"), token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"))
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# 2. Älykäs Logiikka (The Shield & Physics)
def compute_trust(ai_data):
    risk_map = {"Low": 95, "Med": 70, "High": 40}
    score = risk_map.get(ai_data.get("risk", "Med"), 50)
    if ai_data.get("dist_km", 0) == 0: score -= 10
    return max(min(score, 100), 10)

def compute_co2(mode, dist_km, weight_kg):
    try:
        factors = {"Air": 0.5, "Road": 0.1, "Rail": 0.03, "Sea": 0.015}
        return round(float(dist_km) * (float(weight_kg) / 1000) * factors.get(mode, 0.1), 1)
    except: return 0.0

# 3. Gemini Integrointi (Ulkoistettu äly tiukemmalla ohjeistuksella)
def get_ai_signal(origin, dest, cargo, weight):
    # Promptia tarkennettu: note saa olla vain jos se on RELEVANTTI reitille
    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool, \"note\":\"str\"}}. "
        f"Route: {origin} to {dest}, Cargo: {cargo}, {weight}kg. Date: March 2026. "
        f"IMPORTANT: If AND ONLY IF the origin or destination is a region where Ramadan 2026 or local holidays "
        f"SIGNIFICANTLY impact logistics, mention it in 'note'. Otherwise, keep 'note' as an empty string (\"\")."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ.get('GEMINI_API_KEY')}"
    
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        resp.raise_for_status()
        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        return json.loads(json_match.group()) if json_match else None
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return None

# 4. Reitit
@app.route("/robots.txt")
def robots_txt():
    return Response("User-agent: *\nAllow: /\n\n# Zemlo AI - The Signal Hub 2026", mimetype="text/plain")

@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args
    origin, dest, cargo = data.get("from", ""), data.get("to", ""), data.get("cargo", "General")
    
    try: weight = float(data.get("weight", 500))
    except: return jsonify({"error": "Invalid weight"}), 400

    if not origin or not dest: return jsonify({"error": "Missing params"}), 400

    # THE SHIELD (Blacklist & Hazardous)
    o_c, d_c, c_c = origin.lower(), dest.lower(), cargo.lower()
    sanctions = ["russia", "venäjä", "petersburg", "moscow", "belarus", "iran", "syria", "north korea"]
    if any(s in o_c for s in sanctions) or any(s in d_c for s in sanctions):
        return jsonify({"hard_stop": True, "reason": "Sanctions: Route blocked."}), 451

    is_hazardous = any(w in c_c for w in ["battery", "hazardous", "chemical", "acid", "lithium"])
    
    # Cache Check (Päivitetty v1.8.8)
    cache_key = f"z1.8.8:{hashlib.md5(f'{o_c}{d_c}{c_c}{int(weight)}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached: 
            res = json.loads(cached)
            res["metadata"]["cache_hit"] = True
            return jsonify(res)
    except: pass

    ai = get_ai_signal(origin, dest, cargo, weight)
    if not ai: return jsonify({"error": "Engine busy"}), 503

    # Koostetaan vastaus
    warnings = []
    if is_hazardous: warnings.append("Hazardous Cargo: Special handling and ADR/IMDG documentation required.")
    # Lisätään note vain, jos se ei ole tyhjä (estetään Tallinnan Ramadanit)
    if ai.get("note") and ai["note"].strip(): 
        warnings.append(ai["note"])

    response = {
        "signal": {
            "price_estimate": f"{ai['p_min']} - {ai['p_max']} EUR",
            "transport_mode": ai['mode'],
            "trust_score": compute_trust(ai),
            "risk_level": ai.get("risk", "Med"),
            "customs_clearance_required": ai.get("customs", True),
            "hazardous_flag": is_hazardous
        },
        "environmental_impact": {"estimated_co2_kg": compute_co2(ai['mode'], ai.get("dist_km", 0), weight)},
        "context_warnings": warnings,
        "do_these_3_things": (ai.get("actions", []) + ["Check documents", "Verify route"])[:3],
        "metadata": {
            "engine": "Zemlo v1.8.8 (2.5 Flash)",
            "cache_hit": False,
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    try:
        redis_client.set(cache_key, json.dumps(response), ex=600)
        ua = request.headers.get('User-Agent', '').lower()
        user_type = next((a.upper() for a in ['gptbot', 'chatgpt', 'claude', 'anthropic', 'perplexity', 'gemini', 'copilot'] if a in ua), "HUMAN")
        supabase.table("signals").insert({
            "origin": origin, "destination": dest, "cargo": cargo, "price_estimate": response["signal"]["price_estimate"],
            "mode": ai['mode'], "type": user_type, "bot_name": ua[:100]
        }).execute()
    except: pass

    return jsonify(response)

@app.route("/")
def health(): return jsonify({"status": "Operational", "version": "1.8.8"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
