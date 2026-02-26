from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return {"error": "API_KEY_MISSING"}

    # VUODEN 2026 TUOREIN: Gemini 2.5 Flash
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"Return ONLY JSON for logistics {origin} to {destination} ({cargo}). Format: {{\"p_min\": 100, \"p_max\": 200, \"mode\": \"text\", \"customs\": true, \"risk\": \"text\", \"actions\": [\"a\", \"b\"]}}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=12)
        
        if response.status_code != 200:
            return {"error": f"HTTP_{response.status_code}", "msg": response.text}
            
        data = response.json()
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        # Siivotaan markdown-koodiblokit pois jos AI niitä tarjoaa
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": "CONNECTION_ERROR", "msg": str(e)}

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args
    
    origin = data.get('from', 'Unknown')
    dest = data.get('to', 'Unknown')
    cargo = data.get('cargo', 'General Cargo')

    ai = get_ai_signal(origin, dest, cargo)

    if ai and "p_min" in ai:
        p_min, p_max = ai.get('p_min'), ai.get('p_max')
        mode = ai.get('mode', "Freight")
        risk = ai.get('risk', "AI Analysis Success")
        actions = ai.get('actions', ["Check docs"])
        customs_needed = ai.get('customs', False)
        trust = 100
    else:
        p_min, p_max = "ERR", "ERR"
        mode = "ERROR"
        risk = f"FAIL: {ai.get('error') if ai else 'Unknown'}"
        actions = ["Check Google AI Studio for Gemini 2.5 status"]
        customs_needed = False
        trust = 0

    # Serbia-pakotus
    is_serbia = any(x in origin.lower() or x in dest.lower() for x in ["serbia", "belgrade"])
    customs_str = "Required" if customs_needed or is_serbia else "Not Required"

    return jsonify({
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR" if p_min != "ERR" else "Service Unavailable",
            "transport_mode": mode,
            "trust_score": trust,
            "risk_analysis": risk,
            "customs": customs_str
        },
        "clarification": { "checklist": actions },
        "metadata": {
            "engine": "Zemlo v1.2 (Gemini 2.5 Flash)",
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    })

@app.route('/')
def health():
    return "Zemlo Operational", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
