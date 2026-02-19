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

@app.route('/signal', methods=['GET', 'POST'])
def get_signal():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # 1. Haetaan parametrit
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Berlin')
    cargo = data.get('cargo', 'General goods')
    caller = data.get('bot_name', 'Human')

    # 2. ROBOTTI-FILTTERI (Kirurginen)
    # Tallennetaan VAIN jos se EI ole Renderin tarkistus tai jos se on sun oma Oulu-testi
    is_render = "Render" in ua or "Render/1.0" in ua
    
    if not is_render and supabase:
        try:
            supabase.table("signals").insert({
                "origin": origin,
                "destination": destination,
                "cargo": cargo,
                "bot_name": caller,
                "price_estimate": "405-585"
            }).execute()
            print(f"!!! TALLENNETTU KANTAAN: {origin} -> {destination}")
        except Exception as e:
            print(f"!!! KANTA-VIRHE: {str(e)}")
    else:
        print(f"!!! OHITETTU (Robotti tai ei kantaa): {ua}")

    # 3. VASTAUS SELAIMEEN
    return jsonify({
        "zemlo_signal": {
            "route": {"from": origin, "to": destination},
            "cargo": cargo,
            "estimate": "405-585 EUR"
        },
        "meta": {"status": "Live", "ua": ua}
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
