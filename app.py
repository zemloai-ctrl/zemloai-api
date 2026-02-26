from flask import Flask, request, jsonify
import time, os, json, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Haetaan se avain - varmista että Renderissä nimi on täsmälleen tämä
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_ai_signal(origin, destination, cargo):
    if not GEMINI_API_KEY:
        return None

    # Käytetään varminta mahdollista endpointia
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # Primitivinen ja raaka prompti - ei selityksiä AI:lle
    prompt = f"Provide logistics estimate for {origin} to {destination}, cargo {cargo}. Return ONLY JSON: {{\"price_min\": 100, \"price_max\": 200, \"lead_time\": \"text\", \"risk\": \"text\", \"actions\": [\"a\", \"b\", \"c\"], \"mode\": \"text\", \"customs_needed\": true}}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        # Pidennetty timeout varmuuden vuoksi
        response = requests.post(url, json=payload, timeout=20)
        data = response.json()
        
        # Haetaan raakateksti
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        
        # Pakotettu siivous koodiblokkien varalta
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1].replace("json", "").strip()
        
        return json.loads(raw_text)
    except Exception as e:
        # Jos tämä failaa, se palauttaa virheen suoraan vastaukseen, jotta tiedät miksi
        return {"debug_error": str(e)}

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    
    # Parametrit sisään
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args
    
    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Tallinn')
    cargo = data.get('cargo', 'General Cargo')

    # Aivojen kutsu
    ai_data = get_ai_signal(origin, destination, cargo)

    # Jos AI vastaa, käytetään lukuja. Jos ei, näytetään virhe.
    if ai_data and "price_min" in ai_data:
        p_min = ai_data.get('price_min')
        p_max = ai_data.get('price_max')
        customs_needed = ai_data.get('customs_needed', False)
        risk = ai_data.get('risk', "Standard")
        mode = ai_data.get('mode', "Freight")
        actions = ai_data.get('actions', [])
        trust = 100
    else:
        # JOS TÄMÄ TULEE RUUTUUN, AI-YHTEYS ON POIKKI TAI AVAIN VÄÄRÄ
        p_min, p_max = "ERR", "ERR"
        customs_needed = False
        risk = f"FAILED: {ai_data.get('debug_error') if ai_data else 'Timeout'}"
        mode = "ERROR"
        actions = ["CHECK API KEY", "CHECK LOGS"]
        trust = 0

    # Zemlo-logiikka: Serbia vaatii aina tullin
    customs_status = "Required" if customs_needed or "serbia" in origin.lower() or "belgrade" in origin.lower() else "Not Required"

    return jsonify({
        "signal": {
            "price_estimate": f"{p_min} - {p_max} EUR",
            "transport_mode": mode,
            "trust_score": trust,
            "risk_analysis": risk,
            "customs": customs_status
        },
        "clarification": { "checklist": actions },
        "metadata": {
            "engine": "Zemlo v1.2 Brain",
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    })

@app.route('/')
def health(): return "Zemlo UP", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
