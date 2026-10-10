import os
import re
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from playwright.sync_api import sync_playwright

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/dashboard"

def scrape_bess_data():
    with sync_playwright() as p:
        # Lancement du navigateur léger
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigation vers le tableau de bord BESS
        page.goto(BESS_URL, timeout=30000)
        
        # Attente de 5 secondes pour laisser le temps au JavaScript de charger les valeurs
        page.wait_for_timeout(5000)
        
        # Extraction de tout le texte visible à l'écran
        body_text = page.inner_text("body")
        browser.close()
        
        # Nettoyage des retours à la ligne
        clean_text = " ".join(body_text.split())
        return clean_text

@app.route("/sms", methods=['POST'])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            full_text = scrape_bess_data()
            
            # Recherche de motifs fréquents (kW, kWh, %, SOC)
            # On envoie les 150 premiers caractères du contenu capturé
            msg.body(f"BESS Scan: {full_text[:150]}")
            
        except Exception as e:
            msg.body(f"Erreur lors du scan BESS: {str(e)}")
    else:
        msg.body("Envoyez 'kw' pour recevoir le statut BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
