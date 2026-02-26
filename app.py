from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Alustetaan Supabase vain jos tunnukset löytyvät
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    ua = ua.lower()
    if any(bot in ua for bot in ["gpt", "openai", "claude", "anthropic", "googlebot", "gemini"]):
        return "AI Agent"
    return "Human (Browser)"

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return {"error": "API Key Missing"}

    # Vakaa osoite: v1beta ja Gemini 1.5 Flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Analyze logistics route: {origin} to {destination} with cargo: {cargo}.
    As Zemlo AI, provide a realistic situational awareness estimate.
    Return ONLY valid JSON:
    - price_min: (integer, EUR)
    - price_max: (integer, EUR)
    - lead_time: (string, e.g. '3-5 days')
    - risk: (string, brief analysis)
    - actions: (list of 3 strings)
    - mode: (string, e.g. 'Sea Freight')
    - customs_needed: (boolean)
    - is_intercontinental: (boolean)
    
    If exact data is unavailable, use your logistics knowledge to provide a professional estimate.
    """

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            return {"error": f"Google API Error {response.status_code}: {response.text}"}
            
        data = response.json()
        
        # Kaivetaan teksti ulos
        content = data['candidates'][0]['content']['parts'][0]['text']
        
        # Siivotaan markdown-koodiblokit pois
        content = content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(content)
        
    except Exception as e:
        return {"error": str(e)}

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # Käsitellään parametrit
    data = request.get_json(silent=True) if request.method == 'POST' else request.args
    if data is None: data = {}
    
    origin = data.get('from', '').strip()
    destination = data.get('to', '').strip()
    cargo = data.get('cargo', 'General Cargo').strip()
    caller = identify_caller(ua, data.get('bot_name'))

    if not origin or not destination:
        return jsonify({"error": "Missing 'from' or 'to' parameters"}), 400

    # Haetaan tekoälysignaali
    s = get_ai_signal(origin, destination, cargo)
    is_success = "error" not in s
    
    # Lasketaan Trust Score
    trust_score = 95
    if is_success:
        if s.get("is_intercontinental"): trust_score -= 10
        if any(k in cargo.lower() for k in ["dangerous", "pharma", "fragile"]): trust_score -= 15

    price_min = s.get('price_min')
    price_max = s.get('price_max')
    price_estimate = f"{price_min} - {price_max} EUR" if is_success and price_min else "Unavailable"

    # Rakennetaan vastaus
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
            "engine": "Zemlo v1.2 Brain (Gemini 1.5 Flash)",
            "request_by": caller,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    }

    # Tallennus Supabaseen
    if supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin, "destination": destination, "cargo": cargo,
                "bot_name": caller, "price_estimate": price_estimate,
                "type": "AI_AGENT" if "Human" not in caller else "HUMAN"
            }).execute()
        except: 
            pass

    return jsonify(response_data)

@app.route('/')
def health(): 
    return "Zemlo v1.2 Operational", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
