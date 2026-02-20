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

# --- ÄLYKÄS TUNNISTUS: Kuka kysyy? ---
def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    
    ua = ua.lower()
    if "gpt" in ua or "openai" in ua: return "ChatGPT"
    if "claude" in ua or "anthropic" in ua: return "Claude"
    if "googlebot" in ua or "gemini" in ua: return "Gemini"
    if "bing" in ua or "edg/" in ua: return "Copilot"
    if "python" in ua or "curl" in ua or "postman" in ua: return "Developer Script"
    if "mozilla" in ua: return "Human (Browser)"
    
    return "Unknown AI Agent"

# --- DYNAAMINEN HINTA ---
def calculate_estimate(origin, destination, cargo):
    seed = len(origin) + len(destination) + len(cargo)
    base = 400 + (seed * 7)
    c_lower = cargo.lower()
    if "elec" in c_lower: base += 200
    if "food" in c_lower or "poro" in c_lower: base += 120
    
    low = int(base * 0.92)
    high = int(base * 1.18)
    return f"{low}-{high}"

# --- ENDPOINTIT ---

@app.route('/health')
@app.route('/')
def health_check():
    return "Zemlo Engine Operational", 200

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')

    if "Render" in ua:
        return jsonify({"status": "standby"}), 200

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Unknown')
    destination = data.get('to', 'Unknown')
    cargo = data.get('cargo', 'General Cargo')
    
    # TUNNISTUS
    caller = identify_caller(ua, data.get('bot_name'))
    is_ai = "Human" not in caller

    price_range = calculate_estimate(origin, destination, cargo)

    # TALLENNUS SUPABASEEN
    if origin != 'Unknown' and supabase:
        try:
            # Varmista että Supabasen taulussa on sarake 'type' ja 'bot_name'
            supabase.table("signals").insert({
                "origin": origin,
                "destination": destination,
                "cargo": cargo,
                "bot_name": caller, # Esim: "ChatGPT", "Gemini"...
                "price_estimate": price_range,
                "type": "AI_AGENT" if is_ai else "HUMAN"
            }).execute()
            print(f"!!! SIGNAL: {caller} | {origin} -> {destination}")
        except Exception as e:
            print(f"!!! DB ERROR: {str(e)}")

    return jsonify({
        "zemlo_signal": {
            "status": "Reliable",
            "estimate": {"range": price_range, "currency": "EUR"},
            "logistics_intel": {"origin": origin, "destination": destination, "cargo": cargo}
        },
        "meta": {
            "provider": "Zemlo 1.0 Lite",
            "caller_identity": caller,
            "is_ai_optimized": is_ai,
            "duration_ms": int((time.time()-start_time)*1000)
        }
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
