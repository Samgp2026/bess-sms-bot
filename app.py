import os
import re
import threading

from flask import Flask, Response, request
from playwright.sync_api import sync_playwright
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/real?label=Heap"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get(
    "TWILIO_WHATSAPP_FROM",
    "whatsapp:+14155238886"  # Numéro WhatsApp du Sandbox Twilio
)


def get_real_bess_value():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        try:
            chrome_ua = (
                f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"
            )

            page = browser.new_page(user_agent=chrome_ua)
            page.goto(
                BESS_URL,
                wait_until="domcontentloaded",
                timeout=30000
            )

            # Laisser l'application afficher le tableau
            page.wait_for_timeout(7000)

            # Développer la section contenant les capacités 
            
            page.get_by_text(
                 "Detailed parameters",
                 exact=True
            ).click(timeout=15000)

            page.wait_for_function(
                 """() => [...document.querySelectorAll("span")].some(
                 el => el.textContent.trim() === "Cumulative Discharging Capacity"
                 && el.getClientRects().length > 0
                 )""",
                 timeout=15000
            )

            body_text = page.locator("body").inner_text(timeout=15000)

            # Accepte par exemple 128.70kWh ou 128,70 kWh
            pattern = (
                r"Cumulative\s+Discharging\s+Capacity\s*"
                r"([0-9]+(?:[.,][0-9]+)?)\s*kWh"
            )
            match = re.search(pattern, body_text, re.IGNORECASE)

            if not match:
                raise ValueError(
                    "Le libellé ou la valeur de décharge est introuvable."
                )

            value = match.group(1).replace(",", ".")
            return f"{value} kWh"

        finally:
            browser.close()


def scrape_and_send(to_number):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        try:
            value = get_real_bess_value()
            message = f"Die Ausgangsleistung der Batterie beträgt: {value}"
        except Exception as exc:
            app.logger.exception("Échec de lecture du tableau de bord")
            message = f"Der Wert kann nicht gelesen werden : {exc}"

        client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number
        )

    except Exception:
        app.logger.exception("Senden der WhatsApp-Nachricht fehlgeschlagen")


@app.route("/sms", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    from_number = request.form.get("From", "")

    response = MessagingResponse()

    if incoming_msg in {"kw", "status", "bess"}:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            response.message("Configuration Twilio manquante sur le serveur.")
        else:
            response.message(
                "Messung läuft, ich sende Ihnen den Wert in Kürze.."
            )

            threading.Thread(
                target=scrape_and_send,
                args=(from_number,),
                daemon=True
            ).start()
    else:
        response.message("Envoyez « kw » pour recevoir la valeur.")

    return Response(str(response), mimetype="application/xml")


@app.route("/", methods=["GET"])
def health_check():
    return "Application active", 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
