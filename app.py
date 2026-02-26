from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return {"error": "API Key Missing"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # TIUKKA PROMPT: Pakotetaan vastaus oikeaan muotoon
    prompt = f"""
    Return ONLY JSON for logistics route {origin} to {destination} ({cargo}).
    JSON structure:
    {{
      "price_min": number,
      "price_max": number,
      "lead_time": "string",
      "risk": "string",
      "actions": ["string", "string", "string"],
      "mode": "string",
      "customs_needed": boolean
    }}
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        # Siivous jos AI laittaa markdownia
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except:
        return None

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    data = request.get_json(silent=True) if request.method == 'POST' else request.args
    
    origin = data.get('from', 'Unknown')
    destination = data.get('to', 'Unknown')
    cargo = data.get('cargo', 'General Cargo')

    ai_data = get_ai_signal(origin, destination, cargo)

    # JOS AI ONNISTUI, KÄYTETÄÄN SEN DATAA. JOS EI, KÄYTETÄÄN VARALUULOA.
    if ai_data and isinstance(ai_data, dict):
        p_min = ai_data.get('price_min', 200)
        p_max = ai_data.get('price_max', 600)
        customs = "Required" if ai_data.get('customs_needed') else "Not Required"
        risk = ai_data.get('risk', "Standard route")
        mode = ai_data.get('mode', "Road Freight")
        actions = ai_data.get('actions', ["Check docs", "Verify weight", "Book space"])
    else:
        # TÄMÄ ON SE FALLBACK JOKA SULLA NYT NÄKYY - POISTETAAN SE AI-DATAN TIESTÄ
        p_min, p_max = 0, 0
        customs, risk, mode, actions = "Unknown", "Analysis failed", "Unknown", []

    # Pakotetaan tulli Belgradille jos AI epäröi
    if "belgrade" in origin.lower() or "serbia" in origin.lower():
        customs = "Required"

    response_data = {
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR" if p_min > 0 else "Estimate unavailable",
            "transport_mode": mode,
            "trust_score": 85 if ai_data else 50,
            "risk_analysis": risk,
            "customs": customs
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
