import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

TARGET_URL = "http://frp-ger.hhdzcesc.com:34470/#/dashboard"

@app.route("/sms", methods=['POST'])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            # Récupération des données du BESS
            response = requests.get(TARGET_URL, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text(separator=' ', strip=True)

            # Envoi direct des données extraites par SMS (limité à 160 caractères)
            msg.body(f"Statut BESS: {page_text[:140]}")
        except Exception as e:
            msg.body(f"Erreur BESS: {str(e)}")
    else:
        msg.body("Envoyez 'kw' pour recevoir le statut BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
