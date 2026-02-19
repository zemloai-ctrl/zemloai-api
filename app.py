from flask import Flask, request, jsonify
import time, os, threading
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
# Nämä odottavat moottoreita
SHIPPO_API_KEY = os.environ.get("SHIPPO_API_KEY")
PACKLINK_API_KEY = os.environ.get("PACKLINK_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- APUFUNKTIOT ---
def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'bot', 'curl', 'gemini', 'gpt', 'claude']
    return any(ind in ua.lower() for ind in indicators)

def log_to_supabase(origin, destination, price_range, caller, is_ai):
    if not supabase: return
    try:
        supabase.table("signals").insert({
            "origin": origin,
            "destination": destination,
            "type": "AI_SIGNAL" if is_ai else "HUMAN_QUERY",
            "bot_name": caller,
            "price_estimate": price_range
        }).execute()
    except Exception as e:
        print(f"Logging error: {e}")

# --- PÄÄ-ENDPOINT: THE SIGNAL ---
@app.route('/signal', methods=['GET', 'POST'])
@app.route('/api/v1/quote', methods=['GET', 'POST']) # Pidetään yhteensopivuus
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # Haetaan data riippumatta onko GET vai POST
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')
    current_is_bot = is_bot(ua) or "bot_name" in data
    caller = data.get('bot_name', 'Human' if not current_is_bot else 'AI Agent')

    # --- ZEMLO LOGIC (The Signal) ---
    # Tähän väliin pultataan myöhemmin packlink.py ja oracle.py
    base_price = 450 # Simuloidaan raakaa dataa
    price_min = int(base_price * 0.9)
    price_max = int(base_price * 1.3) # Lisätään tullivara
    
    # Rakennetaan uusi neutraali vastausrakenne
    signal_response = {
        "zemlo_signal": {
            "status": "Reliable",
            "estimate": {
                "range": f"{price_min}-{price_max}",
                "currency": "EUR",
                "confidence": "88%"
            },
            "logistics_intel": {
                "est_delivery": "4-6 days",
                "risk_assessment": "Standard route. Potential customs delay at border.", # Tämän antaa AI myöhemmin
            }
        },
        "action_plan": [
            "Ensure commercial invoice is attached",
            "Verify HS-codes for cargo",
            "Contact receiver for local delivery access"
        ],
        "meta": {
            "is_ai_optimized": True,
            "provider": "Zemlo 1.0 Lite",
            "disclaimer": "Better situational awareness than a guess.",
            "duration_ms": int((time.time()-start_time)*1000)
        }
    }

    # Taustaloggaus Supabaseen
    threading.Thread(target=log_to_supabase, 
                     args=(origin, destination, f"{price_min}-{price_max}", caller, current_is_bot)).start()

    return jsonify(signal_response)

if __name__ == "__main__":
    # Render antaa portin ympäristömuuttujana, oletus on 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
