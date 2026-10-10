import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# URL directe de l'API BESS ou du tableau de bord
BESS_URL = "http://frp-ger.hhdzcesc.com:34470"

@app.route("/sms", methods=['POST'])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            # Tente de récupérer les données via endpoint JSON ou la page brute
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(f"{BESS_URL}/#/dashboard", headers=headers, timeout=10)
            
            # Si le backend répond avec du texte ou du JSON
            content = response.text
            
            # Nettoyage rapide pour afficher un résumé exploitable
            clean_text = " ".join(content.split())
            msg.body(f"BESS Data: {clean_text[:150]}")
        except Exception as e:
            msg.body(f"Erreur BESS: {str(e)}")
    else:
        msg.body("Envoyez 'kw' pour recevoir le statut BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
