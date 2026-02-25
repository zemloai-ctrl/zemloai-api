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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # Luetaan aina ympäristömuuttujasta

# Alustetaan Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Alustetaan Gemini
try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY ei ole asetettu ympäristömuuttujissa")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-8b')  # [FIX 1] Oikea malli
except Exception as e:
    print(f"Init Error: {e}")
    model = None

# --- APUFUNKTIOT ---

# [FIX 2] Dynaaminen Trust Score
def calculate_trust_score(cargo: str, origin: str, destination: str) -> int:
    score = 95  # Aloituspisteet

    # Vähennetään pisteitä erikoistavaroista
    special_cargo_keywords = ["dangerous", "hazardous", "vaarallinen", "lääke", "pharma",
                               "live", "perishable", "pilaantuva", "fragile", "hauraat",
                               "chemical", "kemikaali", "explosives", "räjähde"]
    cargo_lower = cargo.lower()
    for keyword in special_cargo_keywords:
        if keyword in cargo_lower:
            score -= 15
            break

    # Vähennetään pisteitä mannertenvälisistä reiteistä
    continents = {
        "europe": ["finland", "germany", "france", "sweden", "norway", "uk", "poland",
                   "suomi", "saksa", "ruotsi", "italia", "espanja"],
        "asia": ["china", "japan", "india", "korea", "kiina", "japani", "intia"],
        "america": ["usa", "canada", "brazil", "mexico", "yhdysvallat", "kanada"],
        "africa": ["nigeria", "kenya", "egypt", "south africa", "egypti"],
        "oceania": ["australia", "new zealand", "australi"],
    }

    def get_continent(location: str) -> str:
        loc = location.lower()
        for continent, countries in continents.items():
            if any(c in loc for c in countries):
                return continent
        return "unknown"

    origin_continent = get_continent(origin)
    dest_continent = get_continent(destination)

    if origin_continent != "unknown" and dest_continent != "unknown":
        if origin_continent != dest_continent:
            score -= 10  # Mannertenvälinen reitti

    return max(0, min(100, score))  # Pidetään arvo välillä 0–100


def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    ua = ua.lower()
    if "gpt" in ua or "openai" in ua: return "ChatGPT"
    if "claude" in ua or "anthropic" in ua: return "Claude"
    if "googlebot" in ua or "gemini" in ua: return "Gemini"
    if "mozilla" in ua: return "Human (Browser)"
    return "Unknown AI Agent"


# --- THE SIGNAL ENGINE v1.2 (GEMINI POWERED) ---
def get_ai_signal(origin, destination, cargo):
    prompt = f"""
    Analyze logistics route: {origin} to {destination} with cargo: {cargo}.
    As a logistics expert, provide realistic estimates.
    Return ONLY a valid JSON object with these exact keys:
    - price_min: (number, EUR)
    - price_max: (number, EUR)
    - lead_time: (string, e.g. "3-5 business days")
    - risk: (string, short risk assessment)
    - actions: (list of exactly 3 specific actionable instructions as strings)
    - mode: (string, e.g. "Air Freight", "Sea Freight", "Road Transport")
    - customs_needed: (boolean)
    """

    if not model:
        return {"error": "AI Brain not initialized"}

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Error: {e}")
        # Fallback – ei kovakoodattuja hintoja, mutta pakollinen rakenne säilyy
        return {
            "price_min": None, "price_max": None,
            "lead_time": "Unavailable – contact carrier",
            "risk": "AI analysis failed, manual review required",
            "actions": [
                "Contact a local freight forwarder",
                "Verify customs documentation requirements",
                "Confirm cargo weight and dimensions with carrier"
            ],
            "mode": "Unknown – manual check needed",
            "customs_needed": True
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
    if not data:
        data = {}

    origin = data.get('from', '').strip()
    destination = data.get('to', '').strip()
    cargo = data.get('cargo', 'General Cargo').strip()
    caller = identify_caller(ua, data.get('bot_name'))

    # [FIX 3] Validointi – palautetaan 400 jos origin tai destination puuttuu
    if not origin or not destination:
        return jsonify({
            "error": "Missing required parameters",
            "details": "'from' (origin) and 'to' (destination) are required fields."
        }), 400

    # Haetaan älykäs signaali Geminiltä
    s = get_ai_signal(origin, destination, cargo)

    # [FIX 5] Hinta-arvio ja checklist tulevat suoraan Geminin vastauksesta
    price_min = s.get('price_min')
    price_max = s.get('price_max')

    if price_min is not None and price_max is not None:
        price_estimate = f"{price_min} - {price_max} EUR"
    else:
        price_estimate = "Unavailable – contact carrier"

    checklist = s.get("actions", ["Contact support for manual assessment"])

    # Tallennetaan haku Supabaseen
    if supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin,
                "destination": destination,
                "cargo": cargo,
                "bot_name": caller,
                "price_estimate": price_estimate,
                "type": "AI_AGENT" if "Human" not in caller else "HUMAN"
            }).execute()
        except Exception as e:
            print(f"DB Error: {e}")

    return jsonify({
        "signal": {
            "price_estimate": price_estimate,
            "transport_mode": s.get("mode", "Unknown"),
            "trust_score": calculate_trust_score(cargo, origin, destination),  # [FIX 2] Dynaaminen
            "risk_analysis": s.get("risk", "Analysis pending"),
            "customs": "Required" if s.get("customs_needed") else "Not Required"
        },
        "clarification": {
            "checklist": checklist  # [FIX 5] Suoraan Geminiltä
        },
        "metadata": {
            "engine": "Zemlo v1.2 Brain (Gemini 1.5 Flash)",
            "request_by": caller,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    })


@app.route('/')
def health():
    return "Zemlo v1.2 Operational (Brain Active)", 200


if __name__ == "__main__":
    # Render vaatii portin ja hostin määrittelyn näin:
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
