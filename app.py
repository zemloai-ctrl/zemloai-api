from flask import Flask, request, jsonify
import time, os
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'bot', 'curl', 'gemini', 'gpt', 'claude']
    return any(ind in ua.lower() for ind in indicators)

def log_to_supabase(origin, destination, price_range, caller, is_ai, cargo_val):
    if not supabase: return
    # ESTETÄÄN RENDER-ROBOTIN TALLENNUS (Siivotaan kanta)
    if "Render" in caller or "Render/1.0" in caller:
        return 
        
    try:
        supabase.table("signals").insert({
            "origin": origin,
            "destination": destination,
            "cargo": cargo_val, # Nyt se ottaa tämän muuttujan
            "bot_name": caller,
            "price_estimate": price_range
        }).execute()
        print(f"!!! SUCCESS: Saved {origin} -> {destination} ({cargo_val})")
    except Exception as e:
        print(f"!!! ERROR: {str(e)}")

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    # HAETAAN TIEDOT TAI KÄYTETÄÄN OLETUKSIA
    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')
    cargo_item = data.get('cargo', 'General goods') # Tämä muuttuja talteen
    
    current_is_bot = is_bot(ua) or "bot_name" in data
    
    # Tunnistetaan onko kyseessä Renderin tarkistus
    if "Render" in ua:
        caller = "Render Health Check"
    else:
        caller = data.get('bot_name', 'Human' if not current_is_bot else 'AI Agent')

    price_range_str = "405-585"

    # TALLENNUS
    log_to_supabase(origin, destination, price_range_str, caller, current_is_bot, cargo_item)

    return jsonify({
        "zemlo_signal": {
            "status": "Reliable",
            "estimate": {"range": price_range_str, "currency": "EUR"},
            "route": f"{origin} to {destination}",
            "item": cargo_item
        },
        "meta": {"provider": "Zemlo 1.0 Lite", "caller": caller}
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
