
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
                    r"""()
