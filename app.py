import os
import threading
import subprocess
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from playwright.sync_api import sync_playwright

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/dashboard"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

# S'assurer que Chromium est installé
try:
    subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Erreur installation Playwright: {e}")

def scrape_bess_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = browser.new_page()
        page.goto(BESS_URL, timeout=30000)
        page.wait_for_timeout(8000) # Temps de chargement de la page
        body_text = page.inner_text("body")
        print("TEXTE EXTRAIT :", body_text[:300]) # Visible dans les logs de Render
        browser.close()
        return " ".join(body_text.split())

def async_scrape_and_send(to_number, client):
    try:
        full_text = scrape_bess_data()
        message_body = f"📊 *Statut BESS* :\n\n{full_text[:500]}"
    except Exception as e:
        message_body = f"❌ Erreur lors du scan BESS: {str(e)}"

    client.messages.create(
        body=message_body,
        from_='whatsapp:+14155238886',
        to=to_number
    )

@app.route("/sms", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    from_number = request.form.get("From")
    
    resp = MessagingResponse()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        resp.message("⏳ *Analyse du BESS en cours...* Veuillez patienter quelques secondes.")
        
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            thread = threading.Thread(target=async_scrape_and_send, args=(from_number, client))
            thread.start()
    else:
        resp.message("Envoyez *kw* pour recevoir le statut du BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
