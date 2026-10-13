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

# Libellés possibles pour « Detailed parameters »
DETAIL_LABELS = [
    "Detailed parameters",
    "Paramètres détaillés",
    "详细参数"
]

# Libellés possibles pour « Cumulative Discharging Capacity »
CAPACITY_LABELS = [
    "Cumulative Discharging Capacity",
    "Capacité de décharge cumulée",
    "累计放电电量"
]

# Recherche un libellé visible dans la page.
VISIBLE_TEXT_JS = (
    "(labels) => [...document.querySelectorAll('span, button, a, div')].some("
    "el => labels.includes(el.textContent.trim()) && "
    "el.getClientRects().length > 0)"
)

# Clique sur le premier élément visible correspondant à un libellé.
CLICK_TEXT_JS = (
    "(labels) => { "
    "const el = [...document.querySelectorAll('span, button, a, div')].find("
    "item => labels.includes(item.textContent.trim()) && "
    "item.getClientRects().length > 0); "
    "if (!el) return false; "
    "el.click(); "
    "return true; "
    "}"
)


def get_real_bess_value():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        try:
            chrome_ua = (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"
            )

            page = browser.new_page(user_agent=chrome_ua)

            page.goto(
                BESS_URL,
                wait_until="domcontentloaded",
                timeout=45000
            )

            # Laisser le tableau de bord charger.
            page.wait_for_timeout(8000)

            # Vérifier si la capacité est déjà visible.
            capacity_visible = page.evaluate(
                VISIBLE_TEXT_JS,
                CAPACITY_LABELS
            )

            # Sinon, ouvrir la section des paramètres détaillés.
            if not capacity_visible:
                page.wait_for_function(
                    VISIBLE_TEXT_JS,
                    arg=DETAIL_LABELS,
                    timeout=30000
                )

                clicked = page.evaluate(
                    CLICK_TEXT_JS,
                    DETAIL_LABELS
                )

                if not clicked:
                    raise ValueError(
                        "La section détaillée n'est pas visible."
                    )

            # Attendre le libellé de la capacité en chinois, français ou anglais.
            page.wait_for_function(
                VISIBLE_TEXT_JS,
                arg=CAPACITY_LABELS,
                timeout=30000
            )

            body_text = page.locator("body").inner_text(timeout=15000)

            # Accepte, par exemple, « 累计放电电量 169.74kWh ».
            pattern = (
                r"(?:Cumulative\s+Discharging\s+Capacity|"
                r"Capacité\s+de\s+décharge\s+cumulée|"
                r"累计放电电量)\s*"
                r"([0-9]+(?:[.,][0-9]+)?)\s*kWh"
            )

            match = re.search(pattern, body_text, re.IGNORECASE)

            if not match:
                raise ValueError(
                    "La valeur de décharge est introuvable "
                    "dans le texte visible."
                )

            value = match.group(1).replace(",", ".")
            return f"{value} kWh"

        finally:
            browser.close()


def scrape_and_send(to_number):
    try:
        client = Client(
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN
        )

        try:
            value = get_real_bess_value()
            message = (
                "Die kumulierte Entladekapazität der Batterie beträgt: "
                f"{value}"
            )
        except Exception:
            # Le détail de l'erreur reste dans les logs Render.
            app.logger.exception(
                "Échec de lecture du tableau de bord BESS"
            )
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
