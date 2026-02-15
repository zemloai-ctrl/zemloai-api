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

# Supabase-yhteys
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

# Rajoitetaan kutsuja (Rate limiting)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per second"],
    storage_uri="memory://"
)

# Sisäinen laskuri MVP-vaiheeseen
stats = {"total_queries": 0, "bot_queries": 0}

def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'claude', 'gpt', 'bot', 'curl', 'langchain', 'postman', 'gemini']
    return any(ind in ua.lower() for ind in indicators)

def log_to_supabase_bg(ua, ip, params, duration):
    if not supabase: return
    try:
        # Haetaan sijaintitiedot IP-osoitteen perusteella
        geo = requests.get(f"http://ip-api.com/json/{ip}").json()
        
        data = {
            "caller_type": "AI/Bot" if is_bot(ua) else "Human",
            "user_agent": ua,
            "country": geo.get("country", "Unknown"),
            "city": geo.get("city", "Unknown"),
            "query_params": params, 
            "response_time_ms": duration,  # Täsmää Supabaseen
            "status_code": 200
        }
        supabase.table("api_logs").insert(data).execute()
    except Exception as e:
        print(f"Logging error: {e}")

@app.route('/')
def home():
    return jsonify({
        "message": "Zemlo AI 1.1 is Live",
        "status": "Operational",
        "owner": "Sakke"
    })

@app.route('/api/v1/quote', methods=['GET', 'POST'])
def get_quote():
    start_time = time.time()
    
    ua = request.headers.get('User-Agent', '')
    ip = request.headers.get('x-forwarded-for', request.remote_addr).split(',')[0]
    
    stats["total_queries"] += 1
    if is_bot(ua): stats["bot_queries"] += 1

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Belgrade')
    
    # Lasketaan kesto millisekunneissa
    duration = int((time.time() - start_time) * 1000)
    if duration == 0: duration = 1 

    # Tallennus taustalla (daemon=True varmistaa ettei pyyntö jää odottamaan)
    log_thread = threading.Thread(
        target=log_to_supabase_bg, 
        args=(ua, ip, dict(data), duration),
        daemon=True
    )
    log_thread.start()

    return jsonify({
        "options": [
            {
                "option_id": f"zemlo_cheapest_{uuid.uuid4().hex[:8]}",
                "type": "cheapest",
                "price": 550,
                "currency": "EUR",
                "carrier": "LKW Walter",
                "route": f"{origin} -> {destination}"
            }
        ],
        "metadata": {
            "response_time_ms": duration, # YHTENÄISTETTY NIMI
            "request_by": "Bot" if is_bot(ua) else "Human"
        }
    })

@app.route('/api/v1/stats')
def get_stats():
    return jsonify(stats)

if __name__ == "__main__":
    app.run()
