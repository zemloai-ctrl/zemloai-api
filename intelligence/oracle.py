import os
import google.generativeai as genai

# Määritetään tekoäly-yhteys (API-avain Renderin Secretseistä)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_risk_analysis(origin, destination, cargo="General Cargo"):
    """
    Kysyy tekoälyltä logistiikkariskit ja tilannekuvan valitulle reitille.
    """
    prompt = f"""
    Toimi globaalina logistiikka-analyytikkona. 
    Analysoi reitti: {origin} -> {destination}.
    Tavara: {cargo}.
    
    Anna lyhyt (max 2 lausetta) analyysi mahdollisista viiveistä, tulliriskeistä tai geopoliittisista häiriöistä.
    Ole neutraali ja rehellinen. Jos reitti on helppo, sano se.
    
    Vastaa muodossa: "Analyysi: [tekstisi tässä]"
    """

    try:
        response = model.generate_content(prompt)
        # Puhdistetaan vastaus varmuuden vuoksi
        text = response.text.replace("Analyysi:", "").strip()
        return text
    except Exception as e:
        print(f"Oracle error: {e}")
        return "Standard logistics conditions apply. No major disruptions reported."

def get_action_steps(origin, destination, cargo="General Cargo"):
    """
    Luo "Tee nämä 3 asiaa" -listan dynaamisesti reitin perusteella.
    """
    prompt = f"Luo 3 lyhyttä ja konkreettista ohjetta (ranskalaisilla viivoilla) lähettäjälle välille {origin}-{destination} tavaralle {cargo}. Keskity tulliin ja pakkaamiseen."
    
    try:
        response = model.generate_content(prompt)
        steps = response.text.strip().split("\n")
        # Otetaan vain 3 ensimmäistä viivaa
        return [s.strip("- ").strip() for s in steps if s.strip()][:3]
    except:
        return ["Check commercial invoice", "Verify HS-codes", "Pack securely"]
