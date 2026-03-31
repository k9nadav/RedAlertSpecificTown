import requests
import time
import json
import os
 
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
 
# Hebrew town names in Unicode-safe form
TOWNS_TO_WATCH = [
    "\u05E6\u05D5\u05E8 \u05DE\u05E9\u05D4",   # צור משה
    "\u05EA\u05DC \u05D0\u05D1\u05D9\u05D1",   # תל אביב
    "\u05D1\u05D0\u05E8 \u05E9\u05D1\u05E2",   # באר שבע
    "\u05DE\u05D8\u05D5\u05DC\u05D4",         # מטולה
    "\u05D0\u05D9\u05DC\u05EA"                # אילת
]
 
# ============================
# NOTIFICATION FUNCTIONS
# ============================
 
def send_to_google(city, category):
    try:
        payload = {"city": city, "category": category}
        requests.post(GOOGLE_WEBHOOK_URL, json=payload, timeout=7)
        print(f"[GOOGLE] Sent → {city} ({category})")
    except Exception as e:
        print(f"[GOOGLE ERROR] {e}")
 
 
def send_telegram(city, category):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Missing Telegram config.")
        return
 
    try:
        message = f"🚨 *Red Alert*\nCity: {city}\nCategory: {category}"
 
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
 
        requests.post(url, json=payload, timeout=7)
        print(f"[TELEGRAM] Sent → {city}")
 
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
 
 
# ============================
# CITY MATCHING (SUBSTRING)
# ============================
 
def normalize_city(city: str) -> str:
    """Normalize Hebrew town names for safer substring comparison."""
    return city.replace("־", "-").replace("–", "-").replace("—", "-").strip()
 
 
def is_relevant_city(city: str) -> bool:
    """Check if any watched town is a substring of the reported city."""
    city_norm = normalize_city(city)
    for watched in TOWNS_TO_WATCH:
        if watched in city_norm:
            return True
    return False
 
 
# ============================
# MAIN ALERT LISTENER
# ============================
 
def check_alerts():
    print("[SYSTEM] Starting optimized Red Alert listener (15 sec interval)...")
 
    last_alert_id = None
    session = requests.Session()
    session.headers.update(HEADERS)
 
    while True:
        try:
            response = session.get(OREF_URL, timeout=7)
            raw = response.content  # consume entire body
 
            # NO ALERT (usual)
            if raw in (b'\xef\xbb\xbf\n', b'\xef\xbb\xbf\r\n'):
                time.sleep(15)
                continue
 
            # Strip BOM
            if raw.startswith(b'\xef\xbb\xbf'):
                raw = raw[3:]
 
            text = raw.decode("utf-8", errors="replace").strip()
 
            # HTML → blocked/IP challenge
            if text.startswith("<"):
                print("[WARN] HTML from OREF (blocked?). Sleeping 60 sec.")
                time.sleep(60)
                continue
 
            # Cloudflare noise
            if text.startswith(")]}'"):
                text = text[4:].strip()
 
            try:
                data = json.loads(text)
            except Exception:
                print("[WARN] Malformed JSON from OREF, skipping.")
                time.sleep(15)
                continue
 
            alert_id = data.get("id")
            cities = data.get("data", [])
            category = data.get("title", "צבע אדום")
 
            if alert_id != last_alert_id:
                last_alert_id = alert_id
                print(f"[ALERT] New alert → {cities}")
 
                for city in cities:
                    if is_relevant_city(city):
                        print(f"[MATCH] Relevant alert: {city}")
                        send_to_google(city, category)
                        send_telegram(city, category)
 
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
 
        time.sleep(15)
 
 
# ============================
# ENTRY POINT
# ============================
 
if __name__ == "__main__":
    check_alerts()
