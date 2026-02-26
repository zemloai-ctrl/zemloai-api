from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # Tehdään ohjeesta niin selkeä, ettei AI voi sekoilla
    prompt = f"Return ONLY JSON for a shipment from {origin} to {destination} ({cargo}). Format: {{\"price_min\": 100, \"price_max\": 200, \"lead_time\": \"days\", \"risk\": \"text\", \"actions\": [\"a\", \"b\", \"c\"], \"mode\": \"text\", \"customs_needed\": true}}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        # Suora haku ilman monimutkaista siivoamista
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        
        # Poistetaan mahdolliset markdown-koodiblokit
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Error: {e}")
        return None

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    
    # Haetaan parametrit
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args
    
    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Tallinn')
    cargo = data.get('cargo', 'General Cargo')

    ai_data = get_ai_signal(origin, destination, cargo)

    # Jos AI vastaa, käytetään sen lukuja. Jos ei, näytetään nollat (jotta tiedät että se failasi).
    if ai_data:
        p_min = ai_data.get('price_min', 0)
        p_max = ai_data.get('price_max', 0)
        customs_needed = ai_data.get('customs_needed', False)
        risk = ai_data.get('risk', "Standard")
        mode = ai_data.get('mode', "Freight")
        actions = ai_data.get('actions', [])
    else:
        p_min, p_max, customs_needed, risk, mode, actions = 0, 0, False, "AI Timeout", "Unknown", ["Try again"]

    # Pakotettu tullilogiikka Serbialle
    customs_str = "Required" if customs_needed or "serbia" in origin.lower() or "belgrade" in origin.lower() else "Not Required"

    response_data = {
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR" if p_min > 0 else "Estimate unavailable",
            "transport_mode": mode,
            "trust_score": 90 if ai_data else 10,
            "risk_analysis": risk,
            "customs": customs_str
        },
        "clarification": {
            "checklist": actions
        },
        "metadata": {
            "engine": "Zemlo v1.2 Brain",
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    }

    return jsonify(response_data)

@app.route('/')
def health(): return "Zemlo Operational", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
