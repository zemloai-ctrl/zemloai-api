from flask import Flask, request, jsonify, send_from_directory
import time, os, json, re
from flask_cors import CORS
from supabase import create_client, Client
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Alustetaan Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_gemini_model():
    """Alustaa ja palauttaa Gemini-mallin vakaasti."""
    try:
        if not GEMINI_API_KEY:
            return None
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini Init Error: {e}")
        return None

# --- APUFUNKTIOT ---

def calculate_trust_score(cargo: str, origin: str, destination: str) -> int:
    score = 95
    special_cargo_keywords = ["dangerous", "hazardous", "vaarallinen", "lääke", "pharma", "live", "perishable", "fragile", "chemical", "explosives"]
    cargo_lower = cargo.lower()
    if any(k in cargo_lower for k in special_cargo_keywords):
        score -= 15
    
    # Palautetaan mannertenvälinen tunnistus (yksinkertaistettu sanakirja)
    continents = {
        "eu": ["finland", "suomi", "germany", "france", "sweden", "norway", "uk", "poland", "italy", "spain"],
        "asia": ["china", "japan", "india", "korea", "singapore", "thailand", "vietnam"],
        "na": ["usa", "canada", "mexico", "yhdysvallat", "kanada"],
        "oc": ["australia", "perth", "sydney", "new zealand"]
    }

    def find_cont(loc):
        loc = loc.lower()
        for c, keywords in continents.items():
            if any(k in loc for k in keywords): return c
        return "unknown"

    # Jos molemmat tunnistetaan ja ovat eri mantereilla, lasketaan pisteitä
    c1, c2 = find_cont(origin), find_cont(destination)
    if c1 != "unknown" and c2 != "unknown" and c1 != c2:
        score -= 10
        
    return max(0, min(100, score))

def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    ua = ua.lower()
    if "gpt" in ua or "openai" in ua: return "ChatGPT"
    if "claude" in ua or "anthropic" in ua: return "Claude"
    if "googlebot" in ua or "gemini" in ua: return "Gemini"
    if "mozilla" in ua: return "Human (Browser)"
    return "Unknown AI Agent"

# --- THE SIGNAL ENGINE ---
def get_ai_signal(origin, destination, cargo):
    model = get_gemini_model()
    prompt = f"Analyze logistics route: {origin} to {destination} with cargo: {cargo}. Return ONLY valid JSON with: price_min (number), price_max (number), lead_time (string), risk (string), actions (list of 3 strings), mode (string), customs_needed (boolean)."

    if not model:
        return {"error": "AI Brain Disconnected"}

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Runtime Error: {e}")
        return {"error": str(e)}

# --- REITIT ---

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # [FIX] Datan tarkistus None-varalta
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
    
    price_min = s.get('price_min')
    price_max = s.get('price_max')
    price_estimate = f"{price_min} - {price_max} EUR" if is_success and price_min else "Unavailable – contact carrier"

    response_data = {
        "signal": {
            "price_estimate": price_estimate,
            "transport_mode": s.get("mode", "Unknown"),
            "trust_score": calculate_trust_score(cargo, origin, destination),
            "risk_analysis": s.get("risk", "Manual review required"),
            "customs": "Required" if s.get("customs_needed", True) else "Not Required"
        },
        "clarification": {
            "checklist": s.get("actions", ["Contact freight forwarder", "Verify documents", "Check dimensions"])
        },
        "metadata": {
            "engine": f"Zemlo v1.2 Brain (Gemini 1.5 Flash)" if is_success else f"Zemlo v1.2 (Fallback: {s.get('error')})",
            "request_by": caller,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    }

    # [FIX] Supabase-lokitus virheille
    if supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin, "destination": destination, "cargo": cargo,
                "bot_name": caller, "price_estimate": price_estimate,
                "type": "AI_AGENT" if "Human" not in caller else "HUMAN"
            }).execute()
        except Exception as e:
            print(f"Supabase DB Error: {e}")

    return jsonify(response_data)

@app.route('/')
def health():
    return "Zemlo v1.2 Operational", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
