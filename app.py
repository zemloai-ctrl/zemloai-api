from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return {"error": "API_KEY_MISSING"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Return ONLY JSON for logistics {origin} to {destination} ({cargo}). Format: {{\"p_min\": 100, \"p_max\": 200, \"mode\": \"text\", \"customs\": true}}"

    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"HTTP_{response.status_code}", "msg": response.text}
            
        res_data = response.json()
        raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": "EXCEPTION", "msg": str(e)}

# TÄMÄ PUUTTUI - Render vaatii tämän, jotta se ei anna 404-virhettä
@app.route('/')
def health():
    return "Zemlo Operational", 200

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    
    # Haetaan data joko JSON-bodystä tai URL-parametreista
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args
    
    origin = data.get('from', 'Helsinki')
    dest = data.get('to', 'Tallinn')
    cargo = data.get('cargo', 'General')

    ai = get_ai_signal(origin, dest, cargo)

    if ai and "error" not in ai:
        p_min = ai.get('p_min', 0)
        p_max = ai.get('p_max', 0)
        customs_needed = ai.get('customs', False)
        risk = "AI Analysis OK"
        mode = ai.get('mode', "Freight")
        trust = 100
    else:
        p_min, p_max = "ERR", "ERR"
        risk = f"FAIL: {ai.get('error') if ai else 'TIMEOUT'}"
        customs_needed = False
        mode = "ERROR"
        trust = 0

    # Zemlo Special: Serbia-pakotus
    is_serbia = "serbia" in origin.lower() or "belgrade" in origin.lower() or "serbia" in dest.lower()
    customs_str = "Required" if customs_needed or is_serbia else "Not Required"

    return jsonify({
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR",
            "transport_mode": mode,
            "trust_score": trust,
            "risk_analysis": risk,
            "customs": customs_str
        },
        "metadata": { 
            "duration_ms": int((time.time() - start_time) * 1000),
            "engine": "Zemlo v1.2 Brain"
        }
    })

if __name__ == "__main__":
    # Render käyttää PORT-ympäristömuuttujaa
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
