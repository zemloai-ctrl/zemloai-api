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

# --- APUFUNKTIOT: MAANTIEDE & LOGIIKKA ---
def is_eu(city_name):
    eu_cities = ["helsinki", "tampere", "oulu", "pietarsaari", "kokkola", "tallinn", "stockholm", "berlin", "hamburg", "rotterdam", "antwerp", "budapest", "warsaw", "gdansk", "barcelona", "madrid", "paris", "le havre"]
    return any(city in city_name.lower() for city in eu_cities)

def is_island(city_name):
    # Tunnistetaan saaret, joihin tarvitaan laiva/lento (esim. Tokio, Lontoo, Singapore)
    islands = ["tokyo", "london", "singapore", "manila", "jakarta", "reykjavik"]
    return any(island in city_name.lower() for island in islands)

# --- ZEMLO TRUST SCORE ALGORITMI (v1.1) ---
def calculate_trust_score(reliability=0.9, speed=0.95, price_quality=0.85):
    # Kaava: (0.4 x Reliability) + (0.3 x Speed) + (0.3 x Price-quality ratio)
    score = (0.4 * reliability) + (0.3 * speed) + (0.3 * price_quality)
    return int(score * 100)

# --- ÄLYKÄS TUNNISTUS ---
def identify_caller(ua, provided_name):
    if provided_name: return provided_name
    ua = ua.lower()
    if "gpt" in ua or "openai" in ua: return "ChatGPT"
    if "claude" in ua or "anthropic" in ua: return "Claude"
    if "googlebot" in ua or "gemini" in ua: return "Gemini"
    if "mozilla" in ua: return "Human (Browser)"
    return "Unknown AI Agent"

# --- THE SIGNAL ENGINE v1.1 ---
def get_the_signal(origin, destination, cargo):
    # 1. Reittityypin ja tullitarpeen määritys
    origin_is_eu = is_eu(origin)
    dest_is_eu = is_eu(destination)
    needs_customs = not (origin_is_eu and dest_is_eu)
    
    # Suomen sisäinen vs. Kansainvälinen
    is_domestic = ("finland" in origin.lower() or is_eu(origin)) and ("finland" in destination.lower() or is_eu(destination)) and ("kokkola" in origin.lower() or "pietarsaari" in origin.lower())

    # 2. Hintalogiikka (Korjattu Kokkola-Pietarsaari ja Tokio-Budapest)
    seed = len(origin) + len(destination) + len(cargo)
    
    if is_domestic and not needs_customs:
        # Lyhyen matkan paikallislogiikka (esim. 40km)
        base_price = 45 + (seed * 2) 
        mode = "Road (Local Van)"
    elif is_island(origin) or is_island(destination):
        base_price = 550 + (seed * 15)
        mode = "Air Freight / Sea Link"
    else:
        base_price = 420 + (seed * 8)
        mode = "Road / Intermodal"

    if "elec" in cargo.lower(): base_price *= 1.2
    
    price_range = f"{int(base_price * 0.9)} - {int(base_price * 1.2)} EUR"

    # 3. Checklist & Toiminnot (Placeholder affiliate-linkeille)
    if needs_customs:
        actions = [
            "1. Prepare Commercial Invoice & EORI number.",
            "2. Verify HS-codes for international shipping.",
            "3. Action: [Get Customs Assistance] (zemlo.ai/customs-coming-soon)"
        ]
        risk = "High (Customs Inspection Risk)"
    else:
        actions = [
            "1. Pack securely for domestic transit.",
            "2. Check loading window (4h notice).",
            "3. Action: [Book Local Carrier] (zemlo.ai/book-coming-soon)"
        ]
        risk = "Low"

    return {
        "price_estimate": price_range,
        "
