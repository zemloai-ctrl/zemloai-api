from flask import Flask, request, jsonify
import time
import uuid
import os
import requests
import threading
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SHIPPO_API_KEY = os.environ.get("SHIPPO_API_KEY")
PACKLINK_API_KEY = os.environ.get("PACKLINK_API_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per second"],
    storage_uri="memory://"
)

stats = {"total_queries": 0, "bot_queries": 0}

# --- APUFUNKTIOT ---
def is_bot(ua, url_params=None):
    if not ua: ua = ""
    indicators = ['python', 'openai', 'claude', 'gpt', 'bot', 'curl', 'langchain', 'postman', 'gemini', 'test-bot']
    ua_match = any(ind in ua.lower() for ind in indicators)
    param_match = False
    if url_params and url_params.get('ua'):
        param_match = any(ind in str(url_params.get('ua')).lower() for ind in indicators)
    return ua_match or param_match

def log_signal_to_supabase(origin, destination, price_min, price_max, bot_name="System"):
    """Tallentaa varsinaisen logistiikkasignaalin julkiseen lokiin."""
    if not supabase: return
    try:
        data = {
            "origin": origin,
            "destination": destination,
            "cargo": "General Cargo",
            "type": "AI_SIGNAL",
            "bot_name": bot_name,
            "price_estimate": f"{price_min}-{price_max} EUR"
        }
        supabase.table("signals").insert(data).execute()
    except Exception as e:
        print(f"Signal logging error: {e}")

# --- REITIT ---
@app.route('/')
def home():
    return jsonify({
        "message": "Zemlo AI 1.1 - Reidar Engine is Live",
        "status": "Operational",
        "apis_connected": {
            "shippo": bool(SHIPPO_API_KEY),
            "packlink": bool(PACKLINK_API_KEY)
        },
        "owner": "Sakke"
    })

@app.route('/api/v1/quote', methods=['GET', 'POST'])
@app.route('/v1/zemlo-ghost1', methods=['POST']) # Botit herättävät tämän
def get_quote():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    ip = request.headers.get('x-forwarded-for', request.remote_addr).split(',')[0]
    
    data = request.get_json(silent=True) or {}
    bot_caller = data.get('bot_name', 'Unknown Bot')
    
    # 1. Määritetään reitti (Zemlo Lite -logiikka)
    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')

    # 2. Simuloidaan/Haetaan hintoja (MVP-vaiheessa hinta-arvio perustuu lähteisiin)
    # Tässä kohtaa Reidar tekee "Totuus ja vaihtoehdot" -päätöksen
    base_price = 450 # Oletushinta jos apit ei vastaa
    price_min = base_price - 50
    price_max = base_price + 150

    # 3. Tallennetaan signaali tauluun (Tämä näkyy sun etusivulla)
    log_signal_to_supabase(origin, destination, price_min, price_max, bot_caller)

    duration = int((time.time() - start_time) * 1000)
    
    return jsonify({
        "zemlo_status": "Success",
        "route": f"{origin} -> {destination}",
        "estimate": {
            "min_price": price_min,
            "max_price": price_max,
            "currency": "EUR",
            "confidence": "Better than a guess" # Zemlon lupaus
        },
        "metadata": {
            "bot_triggered": bot_caller,
            "response_time_ms": duration
        }
    })

@app.route('/api/v1/stats')
def get_stats():
    return jsonify(stats)

if __name__ == "__main__":
    app.run()
