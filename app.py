from flask import Flask, request, jsonify, send_from_directory
import time, os
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# --- APUFUNKTIOT ---
def is_eu(city_name):
    eu_cities = ["helsinki", "tampere", "oulu", "pietarsaari", "kokkola", "tallinn", "stockholm", "berlin", "hamburg", "rotterdam", "antwerp", "budapest", "warsaw", "gdansk", "barcelona", "madrid", "paris", "le havre"]
    return any(city in city_name.lower() for city in eu_cities)

def is_island(city_name):
    islands = ["tokyo", "london", "singapore", "manila", "jakarta", "reykjavik"]
    return any(island in city_name.lower() for island in islands)

def calculate_trust_score(reliability=0.9, speed=0.95, price_quality=0.85):
    score = (0.4 * reliability) + (0.3 * speed) + (0.3 * price_quality)
    return int(score * 100)

def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    ua = ua.lower()
    if "gpt" in ua or "openai" in ua: return "ChatGPT"
    if "claude" in ua or "anthropic" in ua: return "Claude"
    if "googlebot" in ua or "gemini" in ua: return "Gemini"
    if "mozilla" in ua: return "Human (Browser)"
    return "Unknown AI Agent"

# --- THE SIGNAL ENGINE v1.1 ---
def get_the_signal(origin, destination, cargo):
    origin_is_eu = is_eu(origin)
    dest_is_eu = is_eu(destination)
    needs_customs = not (origin_is_eu and dest_is_eu)
    
    is_domestic = ("finland" in origin.lower() or is_eu(origin)) and \
                  ("finland" in destination.lower() or is_eu(destination)) and \
                  ("kokkola" in origin.lower() or "pietarsaari" in origin.lower())

    seed = len(origin) + len(destination) + len(cargo)
    
    if is_domestic and not needs_customs:
        base_price = 45 + (seed * 2) 
        mode = "Road (Local Van)"
    elif is_island(origin) or is_island(destination):
        base_price = 550 + (seed * 15)
        mode = "Air Freight / Sea Link"
    else:
        base_price = 420 + (seed * 8)
        mode = "Road / Intermodal"

    if "elec" in cargo.lower(): base_price *= 1.2
    price_range = f"{int(base_price * 0.9)} - {int(base_price * 1.2)} EUR"

    if needs_customs:
        actions = ["1. Prepare Commercial Invoice.", "2. Verify HS-codes.", "3. Action: [Customs] (https://zemlo.ai/customs)"]
        risk = "High (Customs)"
    else:
        actions = ["1. Pack securely.", "2. Check loading window.", "3. Action: [Book] (https://zemlo.ai/book)"]
        risk = "Low"

    return {
        "price_estimate": price_range,
        "mode": mode,
        "trust_score": calculate_trust_score(),
        "customs": "Required" if needs_customs else "Not Required",
        "actions": actions,
        "risk": risk
    }

# --- REITIT BOTEILLE ---
@app.route('/.well-known/ai-plugin.json')
def serve_ai_plugin():
    return send_from_directory(os.path.join(app.root_path, '.well-known'), 'ai-plugin.json')

@app.route('/openapi.yaml')
def serve_openapi():
    return send_from_directory(app.root_path, 'openapi.yaml')

# --- PÄÄ-ENDPOINT ---
@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    data = request.get_json(silent=True) if request.method == 'POST' else request.args
    if not data: data = {}

    origin = data.get('from', 'Unknown')
    destination = data.get('to', 'Unknown')
    cargo = data.get('cargo', 'General Cargo')
    caller = identify_caller(ua, data.get('bot_name'))
    
    s = get_the_signal(origin, destination, cargo)

    if origin != 'Unknown' and supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin, "destination": destination, "cargo": cargo,
                "bot_name": caller, "price_estimate": s["price_estimate"],
                "type": "AI_AGENT" if "Human" not in caller else "HUMAN"
            }).execute()
        except Exception as e: print(f"DB Error: {e}")

    return jsonify({
        "signal": {
            "price_estimate": s["price_estimate"],
            "transport_mode": s["mode"],
            "trust_score": s["trust_score"],
            "risk_analysis": s["risk"]
        },
        "clarification": {"checklist": s["actions"]},
        "metadata": {"engine": "Zemlo v1.1 Action Engine", "request_by": caller}
    })

@app.route('/')
def health():
    return "Zemlo v1.1 Operational", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
