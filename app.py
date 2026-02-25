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

# Alustetaan Gemini "Aivot"
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    print(f"Init Error: {e}")
    model = None

# --- APUFUNKTIOT ---
def calculate_trust_score(reliability=0.9, speed=0.95, price_quality=0.85):
    # Zemlo Trust Score -kaava
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

# --- THE SIGNAL ENGINE v1.1 (GEMINI POWERED) ---
def get_ai_signal(origin, destination, cargo):
    prompt = f"""
    Analyze logistics route: {origin} to {destination} with cargo {cargo}.
    As a logistics expert, provide realistic estimates.
    Return ONLY a JSON object with these keys:
    - price_min: (number in EUR)
    - price_max: (number in EUR)
    - lead_time: (string, e.g. '3-5 days')
    - risk: (string, brief, e.g. 'Low' or 'Customs Delay Risk')
    - actions: (list of 3 specific instructions)
    - mode: (string, e.g. 'Road Freight' or 'Air Freight')
    - customs_needed: (boolean)
    """
    
    try:
        response = model.generate_content(prompt)
        # Siivotaan vastaus koodiblokkien varalta
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception as e:
        print(f"Gemini Error: {e}")
        # Fallback-vastaus jos tekoäly sakkaa
        return {
            "price_min": 100, "price_max": 1000, "lead_time": "Unknown",
            "risk": "Technical Error", "actions": ["Contact support"],
            "mode": "Unknown", "customs_needed": False
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
    
    # Haetaan älykäs signaali Geminiltä
    s = get_ai_signal(origin, destination, cargo)

    # Tallennetaan haku Supabaseen
    if origin != 'Unknown' and supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin, 
                "destination": destination, 
                "cargo": cargo,
                "bot_name": caller, 
                "price_estimate": f"{s['price_min']}-{s['price_max']} EUR",
                "type": "AI_AGENT" if "Human" not in caller else "HUMAN"
            }).execute()
        except Exception as e: 
            print(f"DB Error: {e}")

    return jsonify({
        "signal": {
            "price_estimate": f"{s['price_min']} - {s['price_max']} EUR",
            "transport_mode": s["mode"],
            "trust_score": calculate_trust_score(),
            "risk_analysis": s["risk"],
            "customs": "Required" if s["customs_needed"] else "Not Required"
        },
        "clarification": {
            "checklist": s["actions"]
        },
        "metadata": {
            "engine": "Zemlo v1.1 Brain (Gemini)", 
            "request_by": caller,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    })

@app.route('/')
def health():
    return "Zemlo v1.1 Operational (Brain Active)", 200

if __name__ == "__main__":
    # Render vaatii joustavan portin
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
