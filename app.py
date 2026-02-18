from flask import Flask, request, jsonify
import time, uuid, os, requests, threading
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SHIPPO_API_KEY = os.environ.get("SHIPPO_API_KEY")
PACKLINK_API_KEY = os.environ.get("PACKLINK_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- ÄLYKÄS BOTTI-TUNNISTUS ---
def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'bot', 'curl', 'gemini', 'gpt', 'claude']
    return any(ind in ua.lower() for ind in indicators)

def log_signal_to_supabase(origin, destination, price_min, price_max, bot_name, is_ai):
    if not supabase: return
    try:
        supabase.table("signals").insert({
            "origin": str(origin)[:50],
            "destination": str(destination)[:50],
            "cargo": "General Cargo",
            "type": "AI_SIGNAL" if is_ai else "HUMAN_QUERY",
            "bot_name": bot_name,
            "price_estimate": f"{price_min}-{price_max} EUR"
        }).execute()
    except Exception as e:
        print(f"Logging error: {e}")

@app.route('/v1/zemlo-ghost1', methods=['POST'])
@app.route('/api/v1/quote', methods=['GET', 'POST'])
def get_quote():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    data = request.get_json(silent=True) or {}
    
    # ChatGPT:n huomio: Otetaan bottitunnistus käyttöön
    current_is_bot = is_bot(ua) or "bot_name" in data
    caller = data.get('bot_name', 'Human' if not current_is_bot else 'AI Agent')

    origin = str(data.get('from', 'Helsinki'))[:50]
    destination = str(data.get('to', 'Berlin'))[:50]

    # Zemlo 1.0 logiikka: Totuus ja vaihtoehdot
    # Tähän tulee myöhemmin oikeat haut SHIPPO_API_KEY:llä
    base_price = 450 
    price_min, price_max = base_price - 50, base_price + 150

    # Tausta-ajo signaalille, jotta vastaus on nopea
    threading.Thread(target=log_signal_to_supabase, 
                     args=(origin, destination, price_min, price_max, caller, current_is_bot)).start()

    return jsonify({
        "zemlo_status": "Success",
        "estimate": {"min": price_min, "max": price_max, "currency": "EUR"},
        "disclaimer": "Better than a guess",
        "meta": {"is_ai": current_is_bot, "duration_ms": int((time.time()-start_time)*1000)}
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
