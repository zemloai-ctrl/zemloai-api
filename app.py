from flask import Flask, request, jsonify
import time, os
from flask_cors import CORS
from supabase import create_client, Client

# --- KONFIGURAATIO ---
app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Alustetaan Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'bot', 'curl', 'gemini', 'gpt', 'claude']
    return any(ind in ua.lower() for ind in indicators)

def log_to_supabase(origin, destination, price_range, caller, cargo_val):
    if not supabase: return
    
    # --- KOVA SUODATIN ---
    # 1. Jos User-Agent sisältää "Render", älä tallenna.
    # 2. Jos origin ja destination ovat oletuksia (Helsinki/Berlin), älä tallenna (estää tyhjät robotit).
    if "Render" in caller or (origin == "Helsinki" and destination == "Berlin"):
        return 

    try:
        supabase.table("signals").insert({
            "origin": origin,
            "destination": destination,
            "cargo": cargo_val,
            "bot_name": caller,
            "price_estimate": price_range
        }).execute()
        print(f"!!! REAL SIGNAL CAPTURED: {origin} -> {destination}")
    except Exception as e:
        print(f"!!! SUPABASE ERROR: {str(e)}")

@app.route('/signal', methods=['GET', 'POST'])
@app.route('/api/v1/quote', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # Katsotaan mistä data tulee
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    # Haetaan arvot
    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')
    cargo = data.get('cargo', 'General goods')
    
    # Tunnistetaan kutsuja
    current_is_bot = is_bot(ua)
    if "Render" in ua:
        caller = "Render Health Check"
    else:
        caller = data.get('bot_name', 'Human' if not current_is_bot else 'AI Agent')

    price_range = "405-585"

    # Tallennetaan vain aidot haut
    log_to_supabase(origin, destination, price_range, caller, cargo)

    # Vastaus (Zemlo 1.0 Lite -määritelmä: toimii ihmiselle ja botille)
    return jsonify({
        "zemlo_signal": {
            "status": "Reliable",
            "estimate": {
                "range": price_range,
                "currency": "EUR"
            },
            "route": {"from": origin, "to": destination},
            "cargo": cargo
        },
        "meta": {
            "provider": "Zemlo 1.0 Lite",
            "disclaimer": "Better situational awareness than a guess.",
            "duration_ms": int((time.time()-start_time)*1000)
        }
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
