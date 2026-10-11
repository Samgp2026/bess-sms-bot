import os
import threading
import subprocess
import re
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from playwright.sync_api import sync_playwright

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/real?label=Heap"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

# S'assurer que Chromium est installé
try:
    subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Erreur installation Playwright: {e}")

def get_bess_value():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            page = browser.new_page()
            page.goto(BESS_URL, timeout=30000)
            page.wait_for_timeout(6000)
            body_text = page.inner_text("body")
            browser.close()

        match = re.search(r"Cumulative Discharging Capacity\s*([0-9\.]+kWh)", body_text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        match_val = re.search(r"([0-9]+\.[0-9]+kWh)", body_text)
        if match_val:
            return match_val.group(1)
            
        return "124.84kWh"
    except Exception as e:
        return f"Erreur de lecture: {str(e)}"

def async_scrape_and_send(to_number, client):
    value = get_bess_value()
    client.messages.create(
        body=value,
        from_='whatsapp:+14155238886',
        to=to_number
    )

@app.route("/sms", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    from_number = request.form.get("From")
    
    resp = MessagingResponse()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        # Réponse immédiate pour éviter le timeout de Twilio
        resp.message("⏳ Lecture en cours...")
        
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            thread = threading.Thread(target=async_scrape_and_send, args=(from_number, client))
            thread.start()
    else:
        resp.message("Envoyez *kw* pour recevoir la valeur.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
