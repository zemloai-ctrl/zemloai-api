import os, time, json, requests, random, logging, hashlib, uuid, re
from flask import Flask, request, jsonify
from flask_cors import CORS
from upstash_redis import Redis
from datetime import datetime, timezone
from supabase import create_client, Client

# ==============================
# 1. ALUSTUS
# ==============================
redis_client = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"), 
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url else None

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zemlo-v1.6.6")

# Konfiguraatio
RATE_LIMIT_CALLS = 10
RATE_LIMIT_WINDOW = 60

RAMADAN_COUNTRIES = ["saudi", "uae", "dubai", "qatar", "kuwait", "egypt", "indonesia", "malaysia", "turkey", "pakistan", "jordan", "oman"]

SANCTIONED_ROUTES = [
    (["iran", "tehran"], "US OFAC + EU sanctions. No price quoting permitted."),
    (["russia", "moscow", "st. petersburg"], "Active EU/US trade sanctions."),
    (["north korea", "pyongyang"], "UN total embargo.")
]

# ==============================
# 2. APUFUNKTIOT
# ==============================

def check_rate_limit(ip):
    key = f"limit:{ip}"
    try:
        current = redis_client.get(key)
        if current and int(current) >= RATE_LIMIT_CALLS:
            return False
        redis_client.incr(key)
        redis_client.expire(key, RATE_LIMIT_WINDOW)
        return True
    except: return True

def log_to_supabase(origin, dest, cargo, response_data, status="success"):
    if not supabase: return
    try:
        user_agent = request.headers.get('User-Agent', '').lower()
        is_bot = any(bot in user_agent for bot in ['bot', 'crawler', 'spider', 'agent', 'perplexity', 'claude'])
        
        payload = {
            "origin": origin,
            "destination": dest,
            "cargo": cargo,
            "status": status,
            "price_estimate": response_data.get("signal", {}).get("price_estimate"),
            "trust_score": response_data.get("signal", {}).get("trust_score"),
            "mode": response_data.get("signal", {}).get("transport_mode"),
            "co2_kg": response_data.get("environmental_impact", {}).get("estimated_co2_kg"),
            "request_id": response_data.get("metadata", {}).get("id"),
            "type": "BOT" if is_bot else "HUMAN",
            "bot_name": user_agent[:50] if is_bot else "Human (Browser)"
        }
        supabase.table("signals").insert(payload).execute()
    except Exception as e:
        logger.warning(f"Supabase logging failed: {e}")

def get_context_warnings(origin, dest):
    warnings = []
    now = datetime.now(timezone.utc)
    combined = (origin + " " + dest).lower()
    
    if now.month == 3 and now.year == 2026:
        if any(country in combined for country in RAMADAN_COUNTRIES):
            warnings.append("⚠️ RAMADAN 2026: Expect regional logistics delays.")
            
    if any(k in combined for k in ["riyadh", "jeddah", "dubai", "red sea", "suez"]):
        warnings.append("🌍 RED SEA SITUATION: Potential carrier diversions via Cape of Good Hope.")
        
    return warnings

# ==============================
# 3. AI-MOOTTORI (GEMINI)
# ==============================

def get_ai_signal(origin, dest, cargo, weight):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return {"error": "API_KEY_MISSING"}

    # Prompt päivitetty v1.6.6: Lisätty "customs_needed" päätöksenteko tekoälylle
    prompt = (
        f"You are Zemlo v1.6.6 Logistics Agent. Return ONLY JSON: "
        f"{{\"p_min\":int, \"p_max\":int, \"mode\":\"Road|Sea|Air|Rail\", \"risk\":\"Low|Med|High\", "
        f"\"actions\":[\"str\"], \"dist_km\":int, \"customs_needed\":bool}}. "
        f"Context: Route {origin} to {dest}, Cargo {cargo}, Weight {weight}kg. Date March 2, 2026. "
        f"Determine if customs clearance is needed based on geography (e.g., intra-EU is false)."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12)
        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        # Siivotaan markdown-koodiblokit pois jos tekoäly niitä tarjoaa
        clean_json = re.sub(r'```json\s*|\s*```', '', raw_text).strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": "AI_UNAVAILABLE", "details": str(e)}

# ==============================
# 4. ENDPOINTIT
# ==============================

@app.route("/signal", methods=["GET", "POST"])
def get_signal():
    client_ip = request.remote_addr
    if not check_rate_limit(client_ip):
        return jsonify({"error": "Rate limit exceeded."}), 429

    data = request.get_json(silent=True) if request.method == "POST" else request.args
    origin = data.get("from", "").strip()
    dest = data.get("to", "").strip()
    cargo = data.get("cargo", "General Cargo").strip()
    weight = data.get("weight", 500)

    if not origin or not dest:
        return jsonify({"error": "Missing 'from' or 'to' parameters."}), 400

    # Pakotelista
    for keywords, reason in SANCTIONED_ROUTES:
        if any(kw in origin.lower() or kw in dest.lower() for kw in keywords):
            res = {"hard_stop": True, "reason": reason}
            log_to_supabase(origin, dest, cargo, {"metadata":{"id":"blocked"}}, status="blocked")
            return jsonify(res), 451

    # Välimuisti (5 min)
    cache_key = f"z1.6.6:{hashlib.md5(f'{origin}{dest}{cargo}{weight}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached: return jsonify(json.loads(cached))
    except: pass

    # Haku AI:lta
    ai = get_ai_signal(origin, dest, cargo, weight)
    if "error" in ai:
        return jsonify(ai), 503

    response = {
        "signal": {
            "price_estimate": f"{ai.get('p_min')} - {ai.get('p_max')} EUR",
            "transport_mode": ai.get("mode"),
            "trust_score": 90 if ai.get("risk") == "Low" else 65,
            # Käytetään AI:n tekemää maantieteellistä päätelmää
            "customs_clearance_required": ai.get("customs_needed", False)
        },
        "environmental_impact": {
            "estimated_co2_kg": round(ai.get("dist_km", 1000) * (float(weight)/1000) * 0.1, 1)
        },
        "context_warnings": get_context_warnings(origin, dest),
        "do_these_3_things": ai.get("actions", [])[:3],
        "metadata": {
            "engine": "Zemlo v1.6.6",
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    try:
        redis_client.set(cache_key, json.dumps(response), ex=300)
        log_to_supabase(origin, dest, cargo, response, status="success")
    except: pass

    return jsonify(response)

@app.route("/")
def health():
    return jsonify({"status": "Operational", "version": "1.6.6"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
