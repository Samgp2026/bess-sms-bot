
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
    "whatsapp:+14155238886"
)


def get_real_bess_value():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        try:
            page = browser.new_page()

            page.goto(
                BESS_URL,
                wait_until="domcontentloaded",
                timeout=45000
            )

            # Laisser l'application EMS commencer à charger ses données.
            page.wait_for_timeout(8000)

            # Vérifier si le libellé de la capacité est déjà visible.
            capacity_visible = page.evaluate(r"""() => {
                const normalize = text => text.replace(/\s+/g, " ").trim();
                return [...document.querySelectorAll("span, button, a, div")].some(
                    el =>
                        normalize(el.textContent) ===
                            "Cumulative Discharging Capacity" &&
                        el.getClientRects().length > 0
                );
            }""")

            # Si la capacité n'est pas encore visible, ouvrir les paramètres détaillés.
            if not capacity_visible:
                page.wait_for_function(
                    r"""() => {
                        const normalize = text =>
                            text.replace(/\s+/g, " ").trim();

                        return [...document.querySelectorAll(
                            "span, button, a, div"
                        )].some(
                            el =>
                                normalize(el.textContent) ===
                                    "Detailed parameters" &&
                                el.getClientRects().length > 0
                        );
                    }""",
                    timeout=30000
                )

                clicked = page.evaluate(r"""() => {
                    const normalize = text =>
                        text.replace(/\s+/g, " ").trim();

                    const el = [...document.querySelectorAll(
                        "span, button, a, div"
                    )].find(
                        item =>
                            normalize(item.textContent) ===
                                "Detailed parameters" &&
                            item.getClientRects().length > 0
                    );

                    if (!el) {
                        return false;
                    }

                    el.click();
                    return true;
                }""")

                if not clicked:
                    raise ValueError(
                        "La section « Detailed parameters » "
                        "n'est pas visible."
                    )

            # Attendre que le libellé de capacité soit visible après le clic.
            page.wait_for_function(
                r"""() => {
                    const normalize = text =>
                        text.replace(/\s+/g, " ").trim();

                    return [...document.querySelectorAll(
                        "span, button, a, div"
                    )].some(
                        el =>
                            normalize(el.textContent) ===
                                "Cumulative Discharging Capacity" &&
                            el.getClientRects().length > 0
                    );
                }""",
                timeout=30000
            )

            body_text = page.locator("body").inner_text(timeout=15000)

            # Accepte 128.70 kWh ou 128,70 kWh.
            pattern = (
                r"Cumulative\s+Discharging\s+Capacity\s*"
                r"([0-9]+(?:[.,][0-9]+)?)\s*kWh"
            )

            match = re.search(pattern, body_text, re.IGNORECASE)

            if not match:
                raise ValueError(
                    "Le libellé ou la valeur de décharge "
                    "est introuvable sur la page."
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
            message = (
                "Die kumulierte Entladekapazität der Batterie beträgt: "
                f"{value}"
            )
        except Exception:
            app.logger.exception("Échec de lecture du tableau de bord")
            message = (
                "Der Wert konnte nicht gelesen werden. "
                "Bitte versuchen Sie es später erneut."
            )

        client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number
        )

    except Exception:
        app.logger.exception(
            "Échec de l'envoi du message WhatsApp"
        )


@app.route("/sms", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.form.get("Body", "").strip().lower()
    from_number = request.form.get("From", "")

    response = MessagingResponse()

    if incoming_msg in {"kw", "status", "bess"}:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            response.message(
                "Configuration Twilio manquante sur le serveur."
            )
        else:
            response.message(
                "Messung läuft. Ich sende Ihnen den Wert in Kürze."
            )

            threading.Thread(
                target=scrape_and_send,
                args=(from_number,),
                daemon=True
            ).start()
    else:
        response.message(
            "Envoyez « kw » pour recevoir la valeur."
        )

    return Response(
        str(response),
        mimetype="application/xml"
    )


@app.route("/", methods=["GET"])
def health_check():
    return "Application active", 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
