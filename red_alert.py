import requests
import time
import json
import os
import logging

# Initialize Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ============================
# CONFIGURATION
# ============================

GOOGLE_WEBHOOK_URL = os.getenv(
    "GOOGLE_WEBHOOK_URL",
    "https://script.google.com/macros/s/YOUR_ID/exec"
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

OREF_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"

# OREF blocks non-browser clients, so we spoof a real browser request.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json"
}

# Hebrew town names in Unicode-safe form (escapes survive any encoding mangling)
TOWNS_TO_WATCH = [
    "צור משה",   # צור משה
    "תל אביב",   # תל אביב
    "באר שבע",   # באר שבע
    "מטולה",          # מטולה
    "אילת"                 # אילת
]

# ============================
# NOTIFICATION FUNCTIONS
# ============================

def send_to_google(city, category, session=None):
    """POST a matched alert to the Google Apps Script webhook."""
    try:
        # Reuse the pooled session when provided, else fall back to requests.
        http_client = session if session else requests
        payload = {"city": city, "category": category}
        response = http_client.post(GOOGLE_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"[GOOGLE] Sent → {city} ({category})")
    except Exception as e:
        logging.error(f"[GOOGLE ERROR] {e}")


def send_telegram(city, category, session=None):
    """Send a Telegram message for a matched alert (no-op if not configured)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("[TELEGRAM] Missing Telegram config.")
        return

    try:
        http_client = session if session else requests
        message = f"🚨 *Red Alert*\n*City:* {city}\n*Category:* {category}"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = http_client.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"[TELEGRAM] Sent → {city}")
    except Exception as e:
        logging.error(f"[TELEGRAM ERROR] {e}")


# ============================
# CITY MATCHING (SUBSTRING)
# ============================

def normalize_city(city: str) -> str:
    """Normalize Hebrew town names for safer substring comparison."""
    # Collapse Hebrew punctuation variants and strip quotes/whitespace.
    return (
        city.replace("־", "-")
            .replace("–", "-")
            .replace("—", "-")
            .replace('"', '')
            .replace("'", "")
            .strip()
    )


# Normalize the watch list once so both sides of the comparison match.
_WATCHED_NORM = [normalize_city(t) for t in TOWNS_TO_WATCH]


def is_relevant_city(city: str) -> bool:
    """Check if any watched town is a substring of the reported city."""
    city_norm = normalize_city(city)
    # Substring match: OREF often reports "תל אביב - מרכז העיר" etc.
    return any(watched in city_norm for watched in _WATCHED_NORM)


# ============================
# MAIN ALERT LISTENER
# ============================

def check_alerts():
    logging.info("[SYSTEM] Starting Red Alert listener (15 sec interval)...")

    last_alert_id = None
    session = requests.Session()
    session.headers.update(HEADERS)

    while True:
        try:
            # Use utf-8-sig to automatically handle the BOM if present.
            response = session.get(OREF_URL, timeout=7)
            response.encoding = 'utf-8-sig'
            text = response.text.strip()

            # NO ALERT (usual empty responses from OREF)
            if not text or text in ('\n', '\r\n'):
                pass
            elif text.startswith("<"):
                logging.warning("[WARN] HTML received (possibly blocked). Sleeping 60s.")
                time.sleep(60)
                continue
            # Strip Cloudflare/anti-JSON-hijacking prefix noise
            elif text.startswith(")]}'"):
                text = text[4:].strip()

            if text and not text.startswith("<"):
                try:
                    data = json.loads(text)
                    alert_id = data.get("id")
                    cities = data.get("data", [])
                    category = data.get("title", "צבע אדום")

                    # Only act on a new alert id to avoid duplicate notifications.
                    if alert_id and alert_id != last_alert_id:
                        last_alert_id = alert_id
                        logging.info(f"[ALERT] New alert ({alert_id}) → {cities}")

                        for city in cities:
                            if is_relevant_city(city):
                                logging.info(f"[MATCH] Relevant alert: {city}")
                                send_to_google(city, category, session=session)
                                send_telegram(city, category, session=session)
                except json.JSONDecodeError:
                    logging.warning("[WARN] Could not parse JSON response.")

        except KeyboardInterrupt:
            # Allow Ctrl+C to stop the listener cleanly.
            logging.info("[SYSTEM] Stopping Red Alert listener.")
            break
        except Exception as e:
            logging.error(f"[ERROR] Unexpected error: {e}")

        time.sleep(15)


# ============================
# ENTRY POINT
# ============================

if __name__ == "__main__":
    check_alerts()
