import os
import re
import threading

from flask import Flask, request, Response
from playwright.sync_api import sync_playwright
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

BESS_URL = "http://frp-ger.hhdzcesc.com:34470/#/real?label=Heap"
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get(
    "TWILIO_WHATSAPP_FROM",
    "whatsapp:+14155238886"  # Sandbox seulement
)


def get_real_bess_value():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(BESS_URL, wait_until="domcontentloaded", timeout=30000)

            # Laissez le temps au tableau de bord de charger ses données.
            page.wait_for_timeout(7000)
            body_text = page.locator("body").inner_text()
            app.logger.info("URL finale : %s", page.url)
            app.logger.info("Titre de la page : %s", page.title())
            app.logger.info("Texte lu par Playwright : %r", body_text[:3000])

            pattern = (
                r"Cumulative\s+Discharging\s+Capacity\s*"
                r"([0-9]+(?:[.,][0-9]+)?)\s*kWh"
            )
            match = re.search(pattern, body_text, re.IGNORECASE)

            if not match:
                raise ValueError(
                    "Le libellé ou sa valeur n’a pas été trouvé sur la page."
                )

            value = match.group(1).replace(",", ".")
            return f"{value} kWh"

        finally:
            browser.close()


def scrape_and_send(to_number):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    try:
        value = get_real_bess_value()
        message = f"La capacité cumulée de décharge est : {value}"
    except Exception as exc:
        app.logger.exception("Échec de lecture du tableau de bord")
        message = f"Impossible de lire la valeur du site : {exc}"

    client.messages.create(
        body=message,
        from_=TWILIO_WHATSAPP_FROM,
        to=to_number
    )


@app.route("/sms", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    from_number = request.form.get("From", "")

    response = MessagingResponse()

    if incoming_msg in {"kw", "status", "bess"}:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            response.message("Configuration Twilio manquante sur le serveur.")
        else:
            response.message("Lecture en cours, je vous envoie la valeur dans un instant.")
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
