from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return {"error": "API Key Missing"}

    # Varmistettu v1beta endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Return ONLY a JSON object for a logistics route from {origin} to {destination} with cargo {cargo}.
    Format:
    {{
      "price_min": number,
      "price_max": number,
      "lead_time": "string",
      "risk": "string",
      "actions": ["string", "string", "string"],
      "mode": "string",
      "customs_needed": boolean
    }}
    Do not include any other text or markdown.
    """

    # Korjattu payload: Lisätty role: user
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=12)
        if response.status_code != 200:
            return None
            
        data = response.json()
        # Varmistettu polku vastaukseen
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        
        # Puhdistetaan mahdolliset markdown-roskat
        clean_json = raw_text.replace("```json", "").replace("```", "").replace("\n", " ").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Zemlo Brain Error: {e}")
        return None

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    
    # Käsitellään parametrit joustavasti (GET tai POST)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args
    
    origin = data.get('from', '').strip() or "Unknown"
    destination = data.get('to', '').strip() or "Unknown"
    cargo = data.get('cargo', 'General Cargo').strip()

    ai_data = get_ai_signal(origin, destination, cargo)

    # Jos AI antaa dataa, käytetään sitä. Jos ei, täytetään Zemlo-standardi-arvot.
    if ai_data and isinstance(ai_data, dict):
        p_min = ai_data.get('price_min', 150)
        p_max = ai_data.get('price_max', 450)
        customs_needed = ai_data.get('customs_needed', False)
        risk = ai_data.get('risk', "Standard route")
        mode = ai_data.get('mode', "Road Freight")
        actions = ai_data.get('actions', ["Check documentation", "Verify weight", "Contact carrier"])
    else:
        # Fallback jos Gemini on hiljaa, mutta pidetään Zemlo-tyyli
        p_min, p_max = 0, 0
        customs_needed = False
        risk = "AI analysis temporary unavailable"
        mode = "Standard Freight"
        actions = ["Contact forwarder", "Verify route", "Check customs manual"]

    # --- ZEMLO SPECIAL LOGIC: SERBIA/BELGRADE ---
    customs_str = "Required" if customs_needed else "Not Required"
    if "belgrade" in origin.lower() or "serbia" in origin.lower() or "belgrade" in destination.lower():
        customs_str = "Required (Non-EU)"

    # Lasketaan Trust Score (Zemlo Trust Algorithm v1.1)
    trust_score = 90 if ai_data else 45
    if "serbia" in origin.lower(): trust_score -= 5 # Haastavampi reitti laskee pistettä hieman

    response_data = {
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR" if p_min > 0 else "Consulting market data...",
            "transport_mode": mode,
            "trust_score": trust_score,
            "risk_analysis": risk,
            "customs": customs_str
        },
        "clarification": {
            "checklist": actions
        },
        "metadata": {
            "engine": "Zemlo v1.2 Brain (Gemini 1.5 Flash)",
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    }

    return jsonify(response_data)

@app.route('/')
def health():
    return "Zemlo Operational", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
