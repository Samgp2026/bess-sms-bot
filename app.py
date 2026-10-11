import os
import subprocess
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from playwright.sync_api import sync_playwright

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/dashboard"

# S'assurer que le navigateur Chromium est bien installé
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
        page.wait_for_timeout(5000)
        body_text = page.inner_text("body")
        browser.close()
        return " ".join(body_text.split())

@app.route("/sms", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "kw" in incoming_msg or "status" in incoming_msg or "bess" in incoming_msg:
        try:
            full_text = scrape_bess_data()
            msg.body(f"📊 *Statut BESS* :\n\n{full_text[:500]}")
        except Exception as e:
            msg.body(f"❌ Erreur lors du scan BESS: {str(e)}")
    else:
        msg.body("Envoyez *kw* pour recevoir le statut du BESS.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
