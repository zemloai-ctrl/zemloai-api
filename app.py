from flask import Flask, request, jsonify
import time
from datetime import datetime
import uuid

app = Flask(__name__)

# Metriikat Slush-demoa varten - Pysyvät muistissa 7e paketin ansiosta
stats = {"total_queries": 0, "bot_queries": 0}

def is_bot(ua):
    if not ua: return False
    # Laajennettu tunnistus, jotta saadaan "Bot Percentage" nousemaan
    indicators = ['python', 'openai', 'claude', 'gpt', 'bot', 'curl', 'langchain', 'postman', 'gemini']
    return any(ind in ua.lower() for ind in indicators)

@app.route('/')
def home():
    return jsonify({
        "message": "Zemlo AI 1.1 is Live",
        "status": "Operational",
        "owner": "Sakke",
        "endpoints": {
            "quote": "/api/v1/quote",
            "stats": "/api/v1/stats"
        }
    })

@app.route('/api/v1/quote', methods=['GET', 'POST'])
def get_quote():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    
    # Päivitetään statsit
    stats["total_queries"] += 1
    if is_bot(ua): 
        stats["bot_queries"] += 1

    # Haetaan tiedot joko URL-parametreista (selain) tai JSON-bodystä (botti)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    origin = data.get('from', 'Helsinki')
    destination = data.get('to', 'Belgrade')
    gen_at = datetime.utcnow().isoformat() + "Z"

    # Zemlo 1.1 Vastausrakenne
    response = {
        "options": [
            {
                "option_id": f"zemlo_cheapest_{uuid.uuid4().hex[:8]}",
                "type": "cheapest",
                "price": 550,
                "currency": "EUR",
                "delivery_days": "10-14",
                "carrier": "LKW Walter",
                "mode": "ROAD",
                "route": f"{origin} -> Central Hub -> {destination}"
            },
            {
                "option_id": f"zemlo_fastest_{uuid.uuid4().hex[:8]}",
                "type": "fastest",
                "price": 1450,
                "currency": "EUR",
                "delivery_days": "2-4",
                "carrier": "DHL Air",
                "mode": "AIR",
                "route": f"{origin} -> Airport -> {destination}"
            }
        ],
        "metadata": {
            "data_source": "Zemlo Global Signal",
            "generated_at": gen_at,
            "response_time_ms": int((time.time() - start_time) * 1000),
            "request_by": "Bot" if is_bot(ua) else "Human"
        }
    }
    return jsonify(response)

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    total = stats["total_queries"]
    bot_percent = (stats["bot_queries"] / total * 100) if total > 0 else 0
    return jsonify({
        "total_requests": total,
        "bot_percentage": f"{bot_percent:.1f}%",
        "status": "online",
        "api_version": "v1.1-sakke-mode",
        "server_type": "Starter-7EUR"
    })

if __name__ == "__main__":
    # Render käyttää porttia 10000 oletuksena
    app.run(host="0.0.0.0", port=10000)
