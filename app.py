import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# URL de base du serveur BESS
BASE_URL = "http://frp-ger.hhdzcesc.com:34470"

@app.route("/sms", methods=['POST'])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            # Endpoints d'API courants pour les dashboards EMS / BESS
            endpoints = [
                f"{BASE_URL}/api/getdata",
                f"{BASE_URL}/api/dashboard",
                f"{BASE_URL}/api/status",
                f"{BASE_URL}/api/v1/bess/status",
                f"{BASE_URL}/data"
            ]
            
            data_found = None
            headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

            for url in endpoints:
                try:
                    res = requests.get(url, headers=headers, timeout=3)
                    if res.status_code == 200 and "json" in res.headers.get("Content-Type", ""):
                        data_found = res.json()
                        break
                except Exception:
                    continue

            if data_found:
                # Extrait et formate les données sous forme lisible
                info_str = str(data_found)[:140]
                msg.body(f"BESS Statut: {info_str}")
            else:
                msg.body("BESS accessible, mais requête API à affiner. Envoyez 'kw' à nouveau.")

        except Exception as e:
            msg.body(f"Erreur connexion BESS: {str(e)}")
    else:
        msg.body("Envoyez 'kw' pour recevoir le statut du BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
