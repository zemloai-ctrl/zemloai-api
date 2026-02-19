from flask import Flask, request, jsonify
import time, os
from flask_cors import CORS
from supabase import create_client, Client

# Tuodaan Oraakkeli (Gemini-äly)
try:
    from intelligence.oracle import get_logistics_advice
except Exception as e:
    def get_logistics_advice(origin, destination, cargo):
        return {
            "risk_assessment": "Oracle offline - using standard safety protocols.",
            "action_plan": ["Verify all documents manually", "Check local customs website"]
        }

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Alustetaan Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# --- APUFUNKTIOT ---
def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'bot', 'curl', 'gemini', 'gpt', 'claude']
    return any(ind in ua.lower() for ind in indicators)

def log_to_supabase(origin, destination, price_range, caller, is_ai, cargo):
    if not supabase: 
        print("!!! SUPABASE ERROR: Client not initialized (URL/KEY missing?)")
        return
    try:
        # TÄMÄ ON SE RATKAISEVA TALLENNUS
        print(f"Attempting to log to Supabase: {origin} -> {destination}")
        supabase.table("signals").insert({
            "origin": origin,
            "destination": destination,
            "cargo": cargo,
            "bot_name": caller,
            "price_estimate": price_range
        }).execute()
        print("!!! SUPABASE SUCCESS: Data saved to table 'signals'")
    except Exception as e:
        print(f"!!! SUPABASE ERROR: {str(e)}")

# --- PÄÄ-ENDPOINT ---
@app.route('/signal', methods=['GET', 'POST'])
@app.route('/api/v1/quote', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')
    cargo = data.get('cargo', 'General goods')
    current_is_bot = is_bot(ua) or "bot_name" in data
    caller = data.get('bot_name', 'Human' if not current_is_bot else 'AI Agent')

    # Lasketaan hinta-arvio
    base_price = 450
    price_min = int(base_price * 0.9)
    price_max = int(base_price * 1.3)
    price_range_str = f"{price_min}-{price_max}"

    # AI-Oraakkeli
    ai_insight = get_logistics_advice(origin, destination, cargo)
    
    # TALLENNETAAN (Suoraan ilman threadia, jotta virhe näkyy logissa)
    log_to_supabase(origin, destination, price_range_str, caller, current_is_bot, cargo)

    signal_response = {
        "zemlo_signal": {
            "status": "Reliable",
            "estimate": {
                "range": price_range_str,
                "currency": "EUR",
                "confidence": "88%"
            },
            "logistics_intel": {
                "est_delivery": "4-6 days",
                "risk_assessment": ai_insight.get("risk_assessment", "Standard route.")
            }
        },
        "action_plan": ai_insight.get("action_plan", ["Ensure documentation is correct."]),
        "meta": {
            "is_ai_optimized": True,
            "provider": "Zemlo 1.0 Lite",
            "disclaimer": "Better situational awareness than a guess.",
            "duration_ms": int((time.time()-start_time)*1000)
        }
    }

    return jsonify(signal_response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
