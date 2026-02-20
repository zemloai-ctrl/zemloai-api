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

# --- ÄLYKÄS TUNNISTUS ---
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

# --- THE SIGNAL ENGINE (Dynaaminen analyysi) ---
def get_the_signal(origin, destination, cargo):
    # 1. Price Estimate
    seed = len(origin) + len(destination) + len(cargo)
    base = 420 + (seed * 8)
    if "elec" in cargo.lower(): base += 210
    low = int(base * 0.94)
    high = int(base * 1.15)
    price_range = f"{low} - {high} EUR"

    # 2. Lead Time & Risks
    is_non_eu = any(country in destination.lower() for country in ["serbia", "belgrade", "turkey", "istanbul", "uk", "london", "usa", "america"])
    
    lead_time = "4-7 days (Realistic)" if not is_non_eu else "6-10 days (Customs delay risk)"
    risk_level = "Medium" if is_non_eu else "Low"
    hidden_costs = "Fuel + Export documentation fees" if is_non_eu else "Standard fuel surcharges"

    # 3. Action List (Ne 3 asiaa)
    if is_non_eu:
        actions = [
            "1. Prepare Export Accompanying Document (EAD).",
            "2. Verify HS-codes for non-EU customs clearance.",
            "3. Ensure Incoterms (DAP/CPT) are clearly defined."
        ]
    else:
        actions = [
            "1. Confirm CMR consignment note details.",
            "2. Verify loading window availability.",
            "3. Digital freight document (e-CMR) recommended."
        ]

    return {
        "price_estimate": price_range,
        "hidden_costs": hidden_costs,
        "lead_time": lead_time,
        "risk_analysis": f"{risk_level} (Source: Zemlo Engine)",
        "actions": actions
    }

# --- ENDPOINTIT ---

@app.route('/health')
@app.route('/')
def health_check():
    return "Zemlo Engine Operational", 200

# Tukee nyt molempia: vanhaa /api/v1/quote ja uutta /signal
@app.route('/api/v1/quote', methods=['GET', 'POST'])
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
    
    caller = identify_caller(ua, data.get('bot_name'))
    is_ai = "Human" not in caller

    # Generoidaan Signaali
    signal_data = get_the_signal(origin, destination, cargo)

    # TALLENNUS SUPABASEEN
    if origin != 'Unknown' and supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin,
                "destination": destination,
                "cargo": cargo,
                "bot_name": caller,
                "price_estimate": signal_data["price_estimate"],
                "type": "AI_AGENT" if is_ai else "HUMAN"
            }).execute()
        except Exception as e:
            print(f"!!! DB ERROR: {str(e)}")

    # PALAUTUS (The Signal Format)
    return jsonify({
        "signal": {
            "price_estimate": signal_data["price_estimate"],
            "hidden_costs": signal_data["hidden_costs"],
            "lead_time": signal_data["lead_time"],
            "risk_analysis": signal_data["risk_analysis"]
        },
        "the_action_list": signal_data["actions"],
        "metadata": {
            "engine": "Zemlo Clarification v1.0",
            "request_by": caller,
            "duration_ms": int((time.time()-start_time)*1000)
        }
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
