import os, json, requests, hashlib, uuid, re, logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

# 1. Alustus
app = Flask(__name__)
CORS(app)
logger = logging.getLogger("Zemlo-v1.7.4")

# Yhteydet
redis_client = Redis(url=os.environ.get("UPSTASH_REDIS_REST_URL"), token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"))
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# 2. Älykäs logiikka
def compute_trust(ai_data):
    risk_map = {"Low": 95, "Med": 70, "High": 40}
    base_score = risk_map.get(ai_data.get("risk"), 50)
    if ai_data.get("dist_km", 0) == 0: base_score -= 10
    return max(min(base_score, 100), 10)

def compute_co2(mode, dist_km, weight_kg):
    factors = {"Air": 0.5, "Road": 0.1, "Rail": 0.03, "Sea": 0.015}
    factor = factors.get(mode, 0.1)
    return round(dist_km * (float(weight_kg)/1000) * factor, 1)

def get_context_warnings(origin, dest):
    warnings = []
    text = (origin + " " + dest).lower()
    now = datetime.now(timezone.utc)
    
    # Korjattu Ramadan-logiikka (v1.7.4)
    is_ramadan_window = (now.month == 2 and now.day >= 15) or (now.month == 3 and now.day <= 25)
    if now.year == 2026 and is_ramadan_window:
        ramadan_countries = ["saudi", "uae", "dubai", "qatar", "egypt", "turkey", "indonesia", "malaysia", "jordan", "oman", "kuwait"]
        if any(c in text for c in ramadan_countries):
            warnings.append("Ramadan 2026 active: Expect local delivery delays and altered working hours.")
        
    # Red Sea / Suez tilanne
    red_sea_points = ["suez", "red sea", "aden", "yemen", "djibouti", "jeddah", "aqaba"]
    if any(p in text for p in red_sea_points):
        warnings.append("Red Sea Transit: Ongoing risk. Expect insurance surcharges and potential rerouting.")
        
    return warnings

# 3. AI-Integraatio (Gemini 2.5 Flash)
def get_ai_signal(origin, dest, cargo, weight):
    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool}}. "
        f"Route: {origin} to {dest}, Cargo: {cargo}, {weight}kg. Date: March 2, 2026. "
        f"Rules: 'customs':false if intra-EU."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ.get('GEMINI_API_KEY')}"
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12)
        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        json_str = re.search(r'\{.*\}', raw_text, re.DOTALL).group()
        return json.loads(json_str)
    except: return None

# 4. Endpoints
@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    data = request.get_json(silent=True) if request.method == "POST" else request.args
    origin, dest = data.get("from", "").strip(), data.get("to", "").strip()
    cargo, weight = data.get("cargo", "General").strip(), data.get("weight", 500)

    if not origin or not dest: return jsonify({"error": "Missing params"}), 400

    # Sanctions (v1.7.4)
    sanctions = [
        ("russia", "EU/US Sanctions"), ("iran", "OFAC Sanctions"), 
        ("north korea", "UN Embargo"), ("belarus", "EU Sanctions"), 
        ("syria", "Sanctions/High Risk")
    ]
    for country, reason in sanctions:
        if country in origin.lower() or country in dest.lower():
            return jsonify({"hard_stop": True, "reason": reason}), 451

    cache_key = f"z1.7.4:{hashlib.md5(f'{origin}{dest}{cargo}{weight}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached: return jsonify(json.loads(cached))
    except: pass

    ai = get_ai_signal(origin, dest, cargo, weight)
    if not ai: return jsonify({"error": "AI Engine failure"}), 503

    trust = compute_trust(ai)
    co2 = compute_co2(ai.get("mode"), ai.get("dist_km", 0), weight)
    warnings = get_context_warnings(origin, dest)

    response = {
        "signal": {
            "price_estimate": f"{ai['p_min']} - {ai['p_max']} EUR",
            "transport_mode": ai['mode'],
            "trust_score": trust,
            "risk_level": ai.get("risk"),
            "customs_clearance_required": ai['customs']
        },
        "environmental_impact": {"estimated_co2_kg": co2},
        "context_warnings": warnings,
        "do_these_3_things": ai['actions'][:3],
        "metadata": {
            "engine": "Zemlo v1.7.4 (2.5 Flash)",
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    try:
        redis_client.set(cache_key, json.dumps(response), ex=300)
        ua = request.headers.get('User-Agent', '').lower()
        is_bot = any(b in ua for b in ['bot', 'crawler', 'agent', 'perplexity', 'claude'])
        supabase.table("signals").insert({
            "origin": origin, "destination": dest, "cargo": cargo, "status": "success",
            "price_estimate": response["signal"]["price_estimate"],
            "trust_score": trust, "mode": ai['mode'], "co2_kg": co2,
            "type": "BOT" if is_bot else "HUMAN", "bot_name": ua[:50]
        }).execute()
    except Exception as e:
        logger.warning(f"Logging failed: {e}")

    return jsonify(response)

@app.route("/")
def health(): return jsonify({"status": "Operational", "version": "1.7.4"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
