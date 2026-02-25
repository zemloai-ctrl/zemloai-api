from flask import Flask, request, jsonify
import time, os, json
from flask_cors import CORS
from supabase import create_client, Client
import google.generativeai as genai
from google.generativeai.types import RequestOptions

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_gemini_model():
    try:
        if not GEMINI_API_KEY: return None
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini Init Error: {e}")
        return None

def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    ua = ua.lower()
    if any(bot in ua for bot in ["gpt", "openai", "claude", "anthropic", "googlebot", "gemini"]):
        return "AI Agent"
    return "Human (Browser)"

def get_ai_signal(origin, destination, cargo):
    model = get_gemini_model()
    # Pyydetään AI:lta kaikki tarvittava data kerralla, mukaan lukien Trust Score -arvio
    prompt = f"""
    Analyze logistics route: {origin} to {destination} with cargo: {cargo}.
    Return ONLY valid JSON with:
    - price_min: (number, EUR)
    - price_max: (number, EUR)
    - lead_time: (string)
    - risk: (string)
    - actions: (list of 3 strings)
    - mode: (string)
    - customs_needed: (boolean)
    - is_intercontinental: (boolean)
    """

    if not model: return {"error": "AI Brain Disconnected"}

    try:
        # Pakotetaan v1-versio poistamaan 404-virheet
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
            request_options=RequestOptions(api_version='v1')
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Runtime Error: {e}")
        return {"error": str(e)}

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    data = request.get_json(silent=True) if request.method == 'POST' else request.args
    if data is None: data = {}
    
    origin = data.get('from', '').strip()
    destination = data.get('to', '').strip()
    cargo = data.get('cargo', 'General Cargo').strip()
    caller = identify_caller(ua, data.get('bot_name'))

    if not origin or not destination:
        return jsonify({"error": "Missing 'from' or 'to' parameters"}), 400

    s = get_ai_signal(origin, destination, cargo)
    is_success = "error" not in s
    
    # Lasketaan Trust Score dynaamisesti AI:n havaintojen perusteella
    trust_score = 95
    if is_success:
        if s.get("is_intercontinental"): trust_score -= 10
        if any(k in cargo.lower() for k in ["dangerous", "pharma", "fragile"]): trust_score -= 15

    price_min = s.get('price_min')
    price_max = s.get('price_max')
    price_estimate = f"{price_min} - {price_max} EUR" if is_success and price_min else "Unavailable – contact carrier"

    response_data = {
        "signal": {
            "price_estimate": price_estimate,
            "transport_mode": s.get("mode", "Unknown"),
            "trust_score": max(0, min(100, trust_score)),
            "risk_analysis": s.get("risk", "Manual review required"),
            "customs": "Required" if s.get("customs_needed", True) else "Not Required"
        },
        "clarification": {
            "checklist": s.get("actions", ["Contact freight forwarder", "Verify documents", "Check dimensions"])
        },
        "metadata": {
            "engine": f"Zemlo v1.2 Brain" if is_success else f"Zemlo v1.2 (Fallback: {s.get('error')})",
            "request_by": caller,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    }

    if supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin, "destination": destination, "cargo": cargo,
                "bot_name": caller, "price_estimate": price_estimate,
                "type": "AI_AGENT" if "Human" not in caller else "HUMAN"
            }).execute()
        except Exception as e: print(f"DB Error: {e}")

    return jsonify(response_data)

@app.route('/')
def health(): return "Zemlo v1.2 Operational", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
