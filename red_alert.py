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
    "כפר סבא",   # כפר סבא
    "הוד השרון",   # Hod Hasharon
]

# ============================
# HELPER FUNCTIONS
# ============================

def is_relevant_city(city_name):
    """Checks if the city name matches any of our target towns."""
    if not city_name:
        return False
    city_clean = city_name.strip()
    return any(town in city_clean for town in TOWNS_TO_WATCH)


def send_to_google(city, category, session=None):
    """Sends the alert data to a Google Apps Script Webhook."""
    if not GOOGLE_WEBHOOK_URL or "YOUR_ID" in GOOGLE_WEBHOOK_URL:
        logging.warning("[GOOGLE] Missing or default webhook URL.")
        return

    try:
        http_client = session if session else requests
        payload = {"city": city, "category": category}
        response = http_client.post(GOOGLE_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"[GOOGLE] Sent → {city}")
    except Exception as e:
        logging.error(f"[GOOGLE ERROR] {e}")


def send_telegram(city, category, description, is_shelter_instruction, session=None):
    """Sends a formatted notification to a Telegram Chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("[TELEGRAM] Missing Telegram config.")
        return

    try:
        http_client = session if session else requests
        
        # קביעת הכותרת והדגש בהתאם לצורך בכניסה לממ"ד/מקלט כדי להרוויח את זמן ההתרעה המוקדם
        if is_shelter_instruction:
            header = "🚨🏃‍♂️ *[כניסה מיידית לממ''ד / מקלט]*"
        else:
            header = "⚠️ *[התרעת פיקוד העורף - הנחיה כללית]*"
            
        message = (
            f"{header}\n\n"
            f"*מיקום:* {city}\n"
            f"*סוג הסכנה:* {category}\n"
            f"*הנחיית התגוננות:* {description if description else 'פעל לפי הנחיות גורמי הביטחון.'}"
        )
        
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
# MAIN CORE LOGIC
# ============================

def check_alerts():
    """Polls the OREF API for new alerts and triggers webhooks/notifications."""
    logging.info("[SYSTEM] Red Alert monitoring script started.")
    last_alert_id = None
    session = requests.Session()

    while True:
        try:
            response = session.get(OREF_URL, headers=HEADERS, timeout=10)
            
            # 204 No Content means there are absolutely no active alerts in the country.
            if response.status_code == 204:
                time.sleep(15)
                continue

            response.raise_for_status()
            text = response.text.strip()

            # Strip malicious BOM or anti-scraping prefix if present.
            if text.startswith(")]}'"):
                text = text[4:].strip()

            if text and not text.startswith("<"):
                try:
                    data = json.loads(text)
                    alert_id = data.get("id")
                    cities = data.get("data", [])
                    
                    # חילוץ סוג הסכנה ושדה התיאור (הנחיה)
                    category = data.get("title", "צבע אדום")
                    description = data.get("desc", "").strip()

                    # בדיקה חכמה בשדה התיאור: האם יש הוראה אקטיבית לכניסה למחסה/מקלט/ממ"ד
                    keywords_to_shelter = ["היכנסו", "מרחב המוגן", "מרחב מוגן", "מקלט", "מחסה", "ממ''ד", "ממّد"]
                    is_shelter_instruction = any(word in description for word in keywords_to_shelter) or "טיס" in category or "רקטי" in category

                    # Only act on a new alert id to avoid duplicate notifications.
                    if alert_id and alert_id != last_alert_id:
                        last_alert_id = alert_id
                        logging.info(f"[ALERT] New alert ({alert_id}) → {cities} | Category: {category} | Desc: {description}")

                        for city in cities:
                            if is_relevant_city(city):
                                logging.info(f"[MATCH] Relevant alert for: {city}")
                                
                                # הכנת טקסט משולב עבור גוגל אנליטיקס/גיליון
                                google_category_text = f"[{'ממ''ד' if is_shelter_instruction else 'כללי'}] {category} - {description}"
                                send_to_google(city, google_category_text, session=session)
                                
                                # שליחה לטלגרם עם הפיצול הברור על בסיס שדה התיאור והקטגוריה
                                send_telegram(city, category, description, is_shelter_instruction, session=session)
                                
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