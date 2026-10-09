import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
from bs4 import BeautifulSoup
import anthropic

app = Flask(__name__)

TARGET_URL = "http://frp-ger.hhdzcesc.com:34470/#/dashboard"

@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            response = requests.get(TARGET_URL, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text(separator=' ', strip=True)

            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"Voici les données extraites du système BESS : {page_text[:4000]}. Fais un résumé ultra-court et direct des données clés (puissance en kW, état de charge SoC, statuts) en maximum 3 lignes pour un affichage sur SMS."
                }]
            )
            summary = message.content[0].text
            msg.body(summary)
        except Exception as e:
            msg.body(f"Erreur lors de la récupération des données BESS: {str(e)}")
    else:
        msg.body("Envoyez 'kw' pour recevoir le statut de votre système BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
