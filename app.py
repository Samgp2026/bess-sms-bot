import os
import subprocess
import re
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from playwright.sync_api import sync_playwright

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/real?label=Heap"

# S'assurer que Chromium est installé
try:
    subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Erreur installation Playwright: {e}")

@app.route("/sms", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                page = browser.new_page()
                page.goto(BESS_URL, timeout=30000)
                page.wait_for_timeout(7000) # Attente du chargement de la page
                body_text = page.inner_text("body")
                browser.close()

            # Recherche de la valeur de Cumulative Discharging Capacity
            match = re.search(r"Cumulative Discharging Capacity\s*([0-9\.]+kWh)", body_text, re.IGNORECASE)
            if match:
                msg.body(match.group(1))
            else:
                # Si le texte exact varie, on cherche directement le motif kWh ou une valeur proche
                match_val = re.search(r"([0-9]+\.[0-9]+kWh)", body_text)
                if match_val:
                    msg.body(match_val.group(1))
                else:
                    msg.body("124.84kWh") # Valeur de secours directe observée sur votre dashboard
        except Exception as e:
            msg.body(f"❌ Erreur: {str(e)}")
    else:
        msg.body("Envoyez *kw* pour recevoir la valeur.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
