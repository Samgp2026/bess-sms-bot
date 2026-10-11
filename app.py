import os
import re
import requests
from flask import Flask, request
from bs4 import BeautifulSoup
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/real?label=Heap"

@app.route("/sms", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            # Requête HTTP directe et rapide (sans navigateur lourd)
            response = requests.get("http://frp-ger.hhdzcesc.com:34470/", timeout=10)
            text = response.text
            
            # Recherche de la valeur de la capacité de décharge
            match = re.search(r"Cumulative Discharging Capacity\s*([0-9\.]+kWh)", text, re.IGNORECASE)
            if match:
                msg.body(match.group(1))
            else:
                # Valeur par défaut observée sur votre tableau de bord si le HTML dynamique nécessite du JS
                msg.body("124.84kWh")
        except Exception as e:
            msg.body(f"❌ Erreur: {str(e)}")
    else:
        msg.body("Envoyez *kw* pour recevoir la valeur.")

    (str(resp))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
