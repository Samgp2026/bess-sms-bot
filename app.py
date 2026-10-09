import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import anthropic

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
URL_EMS = "http://er.hhdzcesc.com:34470"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

@app.route("/sms", methods=['POST'])
def sms_reply():
    body = request.form.get('Body', '').strip().lower()
    
    if 'kw' in body or 'status' in body:
        try:
            res = requests.get(URL_EMS, timeout=10)
            html_data = res.text[:4000]

            prompt = f"""
            Voici le code source de supervision de ma batterie (BESS).
            Extrais et résume les données clés (Puissance PV, Puissance Réseau, SOC Batterie %, Puissance Batterie).
            Réponds uniquement sous la forme d'un SMS très court et lisible en français.
            HTML:
            {html_data}
            """

            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )
            reply_text = response.content[0].text

        except Exception as e:
            reply_text = "Erreur de connexion au système BESS."
    else:
        reply_text = "Envoyez 'kw' pour obtenir l'état de la batterie."

    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
