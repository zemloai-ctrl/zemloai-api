from flask import Flask, request, jsonify
import time
from datetime import datetime
import uuid

app = Flask(__name__)

# Metriikat Slush-demoa varten
stats = {"total_queries": 0, "bot_queries": 0}

def is_bot(ua):
    if not ua: return False
    indicators = ['python', 'openai', 'claude', 'gpt', 'bot', 'curl', 'langchain']
    return any(ind in ua.lower() for ind in indicators)

@app.route('/api/v1/quote', methods=['POST'])
def get_quote():
    start_time = time.time()
    ua = request.headers.get('User-Agent', '')
    stats["total_queries"] += 1
    if is_bot(ua): stats["bot_queries"] += 1

    data = request.get_json(silent=True) or {}
    origin = data.get('from', 'Unknown')
    destination = data.get('to', 'Unknown')
    gen_at = datetime.utcnow().isoformat() + "Z"

    # Final Spec v1.0 mukainen vastaus
    response = {
        "options": [
            {
                "option_id": f"zemlo_cheapest_{uuid.uuid4().hex[:8]}",
                "type": "cheapest",
                "price": 550,
                "currency": "EUR",
                "delivery_days": "10-14",
                "delivery_days_min": 10,
                "delivery_days_max": 14,
                "carrier": "LKW Walter",
                "mode": "ROAD",
                "route": f"{origin} -> Terminal -> {destination}"
            },
            {
                "option_id": f"zemlo_fastest_{uuid.uuid4().hex[:8]}",
                "type": "fastest",
                "price": 1450,
                "currency": "EUR",
                "delivery_days": "2-4",
                "delivery_days_min": 2,
                "delivery_days_max": 4,
                "carrier": "DHL Air",
                "mode": "AIR",
                "route": f"{origin} -> Airport -> {destination}"
            },
            {
                "option_id": f"zemlo_balanced_{uuid.uuid4().hex[:8]}",
                "type": "balanced",
                "price": 920,
                "currency": "EUR",
                "delivery_days": "5-7",
                "delivery_days_min": 5,
                "delivery_days_max": 7,
                "carrier": "DSV / Schenker",
                "mode": "ROAD",
                "route": f"{origin} -> Direct -> {destination}"
            }
        ],
        "metadata": {
            "data_source": "estimated",
            "generated_at": gen_at,
            "response_time_ms": int((time.time() - start_time) * 1000)
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
        "api_version": "v1.0-lite"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
