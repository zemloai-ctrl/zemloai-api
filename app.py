from flask import Flask, request, jsonify
import time, os, threading
from flask_cors import CORS
from supabase import create_client, Client

# Tuodaan Oraakkeli (Gemini-äly)
try:
    from intelligence.oracle import get_logistics_advice
except ImportError:
    # Fallback jos tiedostoa ei vielä löydy tai polku on väärä
    def get_logistics_advice(origin, destination, cargo):
        return {"risk_assessment": "Standard logistics conditions apply.", "action_plan": ["Ensure documentation is correct."]}

app = Flask(__name__)
CORS(app)

# --- KONFIGURAATIO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SHIPPO_API_KEY = os.environ.get("SHIPPO_API_KEY")
PACKLINK_API_KEY = os.environ.get("PACKLINK_API_KEY")

# Alustetaan Supabase vain jos avaimet löytyvät
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# --- APUFUNKTIOT ---
def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'bot', 'curl', 'gemini', 'gpt', 'claude']
    return any(ind in ua.lower() for ind in indicators)

def log_to_supabase(origin, destination, price_range, caller, is_ai):
    if not supabase: return
    try:
        # TÄMÄ ON KORJAUS: Try-block suojaa, jos kanta ei vastaa skeemaa
        supabase.table("signals").insert({
            "origin": origin,
            "destination": destination,
            "type": "AI_SIGNAL" if is_ai else "HUMAN_QUERY",
            "bot_name": caller, # Jos tämä sarake puuttuu, siirrytään except-kohtaan
            "price_estimate": price_range
        }).execute()
    except Exception as e:
        # Tulostetaan virhe lokiin, mutta ei kaadeta sovellusta
        print(f"Supabase logging skipped or failed: {e}")

# --- PÄÄ-ENDPOINT: THE SIGNAL ---
@app.route('/signal', methods=['GET', 'POST'])
@app.route('/api/v1/quote', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # Haetaan data
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')
    cargo = data.get('cargo', 'General goods')
    current_is_bot = is_bot(ua) or "bot_name" in data
    caller = data.get('bot_name', 'Human' if not current_is_bot else 'AI Agent')

    # --- ZEMLO LOGIC (The Signal) ---
    # Kutsutaan AI-Oraakkelia (Gemini 1.5 Flash)
    ai_insight = get_logistics_advice(origin, destination, cargo)

    base_price = 450 # Tähän pultataan myöhemmin dynaaminen hinta
    price_min = int(base_price * 0.9)
    price_max = int(base_price * 1.3)
    
    # Rakennetaan neutraali vastausrakenne
    signal_response = {
        "zemlo_signal": {
            "status":
