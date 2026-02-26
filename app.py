from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return {"error": "API_KEY_MISSING"}

    # Tämä on se toimiva endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"Return ONLY JSON for logistics {origin} to {destination} ({cargo}). Format: {{\"p_min\": 100, \"p_max\": 200, \"mode\": \"text\", \"customs\": true}}"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        # TÄMÄ ON SE HETKI: Jos virhe, näytetään se raakana
        if response.status_code != 200:
            return {"error": f"HTTP_{response.status_code}", "raw": response.text}
            
        data = response.json()
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": "EXCEPTION", "msg": str(e)}

@app.route('/')
def health():
    return "Zemlo is Live", 200

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    
    # Haetaan parametrit
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args
    
    origin = data.get('from', 'Unknown')
    dest = data.get('to', 'Unknown')
    cargo = data.get('cargo', 'General')

    ai = get_ai_signal(origin, dest, cargo)

    # EI FALLBACKEJA. Jos ei toimi, näytetään virhe.
    if ai and "p_min" in ai:
        p_min, p_max = ai.get('p_min'), ai.get('p_max')
        customs_needed = ai.get('customs', False)
        mode = ai.get('mode', "Road")
        risk = "AI Success"
    else:
        # TÄSTÄ TIEDETÄÄN MIKÄ MÄTTÄÄ
        p_min, p_max = "ERR", "ERR"
        mode = "ERROR"
        risk = str(ai.get('error') if ai else "Unknown Error")
        if ai and "raw" in ai:
            risk += f" - {ai['raw']}"

    # Zemlo-tunnistus Belgradille
    is_serbia = "serbia" in origin.lower() or "belgrade" in origin.lower()
    customs_str = "Required" if customs_needed or is_serbia else "Not Required"

    return jsonify({
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR",
            "transport_mode": mode,
            "risk_analysis": risk,
            "customs": customs_str
        },
        "metadata": {
            "duration_ms": int((time.time() - start_time) * 1000),
            "engine": "Zemlo v1.2 Brain"
        }
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
