import os, json, requests, hashlib, uuid, re, logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

# 1. Alustus
app = Flask(__name__)
CORS(app)
logger = logging.getLogger("Zemlo-v1.6.9")

redis_client = Redis(url=os.environ.get("UPSTASH_REDIS_REST_URL"), token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"))
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

SANCTIONED_ROUTES = [
    (["iran", "tehran"], "US OFAC + EU sanctions. No price quoting permitted."),
    (["russia", "moscow", "st. petersburg"], "Active EU/US trade sanctions."),
    (["north korea", "pyongyang"], "UN total embargo.")
]

# 2. Apufunktiot
def log_to_supabase(origin, dest, cargo, response_data, status="success"):
    try:
        ua = request.headers.get('User-Agent', '').lower()
        is_bot = any(b in ua for b in ['bot', 'crawler', 'agent', 'perplexity', 'claude'])
        
        # Jätetään 'id' pois, jotta Supabase generoi sen itse
        payload = {
            "origin": origin,
            "destination": dest,
            "cargo": cargo,
            "status": status,
            "price_estimate": response_data.get("signal", {}).get("price_estimate"),
            "trust_score": response_data.get("signal", {}).get("trust_score"),
            "mode": response_data.get("signal", {}).get("transport_mode"),
            "co2_kg": response_data.get("environmental_impact", {}).get("estimated_co2_kg"),
            "type": "BOT" if is_bot else "HUMAN",
            "bot_name": ua[:50]
        }
        supabase.table("signals").insert(payload).execute()
    except Exception as e:
        logger.warning(f"Supabase logging failed: {e}")

# 3. Ydin: Gemini 2.5 Flash
def get_ai_signal(origin, dest, cargo, weight):
    prompt = (
        f"Return ONLY JSON: {{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", "
        f"\"risk\":\"Low|Med|High\", \"actions\":[\"str\"], \"dist_km\":int, \"customs\":bool}}. "
        f"Route: {origin} to {dest}, Cargo: {cargo}, {weight}kg. Zemlo 1.6.9 Logic. "
        f"Strict: 'customs':false if intra-EU (e.g. Finland to Finland)."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ.get('GEMINI_API_KEY')}"
    
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        json_str = re.search(r'\{.*\}', raw_text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"AI error: {e}")
        return None

# 4. Reitit
@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    data = request.get_json(silent=True) if request.method == "POST" else request.args
    origin = data.get("from", "").strip()
    dest = data.get("to", "").strip()
    cargo = data.get("cargo", "General").strip()
    weight = data.get("weight", 500)

    if not origin or not dest: return jsonify({"error": "Missing params"}), 400

    # Blacklist check
    for keywords, reason in SANCTIONED_ROUTES:
        if any(k in origin.lower() or k in dest.lower() for k in keywords):
            log_to_supabase(origin, dest, cargo, {"signal":{}}, status="blocked")
            return jsonify({"hard_stop": True, "reason": reason}), 451

    # Cache key v1.6.9
    cache_key = f"z1.6.9:{hashlib.md5(f'{origin}{dest}{cargo}{weight}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached: return jsonify(json.loads(cached))
    except: pass

    ai = get_ai_signal(origin, dest, cargo, weight)
    if not ai: return jsonify({"error": "AI side failure"}), 503

    response = {
        "signal": {
            "price_estimate": f"{ai['p_min']} - {ai['p_max']} EUR",
            "transport_mode": ai['mode'],
            "trust_score": 90 if ai['risk'] == "Low" else 65,
            "customs_clearance_required": ai['customs']
        },
        "environmental_impact": {"estimated_co2_kg": round(ai['dist_km'] * (float(weight)/1000) * 0.1, 1)},
        "do_these_3_things": ai['actions'][:3],
        "metadata": {
            "engine": "Zemlo v1.6.9 (2.5 Flash)",
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    try:
        redis_client.set(cache_key, json.dumps(response), ex=300)
        log_to_supabase(origin, dest, cargo, response)
    except: pass

    return jsonify(response)

@app.route("/")
def health(): return jsonify({"status": "Operational", "version": "1.6.9"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
