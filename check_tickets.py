"""
Noah Kahan Atlanta Ticket Checker
ONLY alerts when tickets go from SOLD OUT → AVAILABLE.
Checks every 5 minutes. Stays silent until that flip happens.
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime


# --- Configuration (pulled from GitHub Secrets) ---
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GIST_ID = os.environ.get("GIST_ID", "")
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")

# --- Search Settings ---
ARTIST_NAME = "Noah Kahan"
CITY = "Atlanta"
STATE_CODE = "GA"
COUNTRY_CODE = "US"

STATE_FILENAME = "ticket_state.json"


# ── State Management (GitHub Gist) ───────────────────────────────

def load_previous_state():
    """Load the last known statuses from GitHub Gist."""
    if not GIST_ID or not GITHUB_TOKEN:
        print("No Gist configured — will treat all 'onsale' events as new.")
        return {}

    url = f"https://api.github.com/gists/{GIST_ID}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            gist = json.loads(resp.read().decode())
        content = gist.get("files", {}).get(STATE_FILENAME, {}).get("content", "{}")
        state = json.loads(content)
        print(f"Loaded previous state: {len(state)} event(s) tracked.")
        return state
    except Exception as e:
        print(f"Could not load previous state: {e}")
        return {}


def save_current_state(state):
    """Save current statuses to GitHub Gist."""
    if not GIST_ID or not GITHUB_TOKEN:
        return

    url = f"https://api.github.com/gists/{GIST_ID}"
    payload = json.dumps({
        "files": {
            STATE_FILENAME: {
                "content": json.dumps(state, indent=2)
            }
        }
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="PATCH", headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                print("State saved.")
    except Exception as e:
        print(f"Could not save state: {e}")


# ── Ticketmaster API ─────────────────────────────────────────────

def search_ticketmaster():
    """Search for Noah Kahan events in Atlanta."""

    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TICKETMASTER_API_KEY,
        "keyword": ARTIST_NAME,
        "city": CITY,
        "stateCode": STATE_CODE,
        "countryCode": COUNTRY_CODE,
        "size": 20,
        "sort": "date,asc",
        "source": "ticketmaster",
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"[{datetime.now()}] Checking for {ARTIST_NAME} in {CITY}, {STATE_CODE}...")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"API request failed: {e}")
        return []

    if "_embedded" not in data or "events" not in data["_embedded"]:
        print("No events found.")
        return []

    events = data["_embedded"]["events"]
    print(f"Found {len(events)} event(s).")
    return events


# ── Telegram ─────────────────────────────────────────────────────

def send_telegram_message(message):
    """Send a Telegram notification."""

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured. Message:")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("ALERT SENT!")
    except Exception as e:
        print(f"Telegram send failed: {e}")


# ── Main Logic ───────────────────────────────────────────────────

def main():
    if not TICKETMASTER_API_KEY:
        print("ERROR: TICKETMASTER_API_KEY not set.")
        return

    # 1. Load what we knew last time
    previous_state = load_previous_state()

    # 2. Get current events
    events = search_ticketmaster()
    if not events:
        print("No events listed. Waiting for next check.")
        return

    # 3. Check each event — only care about sold out → on sale flips
    current_state = {}
    alerts = []

    for event in events:
        event_id = event.get("id", "unknown")
        name = event.get("name", "Unknown")
        status = event.get("dates", {}).get("status", {}).get("code", "unknown")
        event_url = event.get("url", "")

        # Get date info
        start = event.get("dates", {}).get("start", {})
        date_str = start.get("localDate", "TBA")
        time_str = start.get("localTime", "")
        if date_str != "TBA":
            try:
                date_str = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                pass
        if time_str:
            try:
                time_str = datetime.strptime(time_str, "%H:%M:%S").strftime("%I:%M %p")
            except ValueError:
                pass

        # Get venue
        venues = event.get("_embedded", {}).get("venues", [])
        venue = venues[0].get("name", "Unknown Venue") if venues else "Unknown Venue"

        # Get price
        price_ranges = event.get("priceRanges", [])
        price = ""
        if price_ranges:
            low = price_ranges[0].get("min", "?")
            high = price_ranges[0].get("max", "?")
            price = f"${low} - ${high}"

        # Save current status
        current_state[event_id] = status

        # What was the previous status?
        old_status = previous_state.get(event_id, "unknown")

        print(f"  {name}: {old_status} → {status}")

        # THE KEY CHECK: was it NOT on sale before, and IS on sale now?
        if status == "onsale" and old_status != "onsale":
            alerts.append({
                "name": name,
                "date": f"{date_str} {time_str}".strip(),
                "venue": venue,
                "price": price,
                "url": event_url,
                "old_status": old_status,
            })

    # 4. Save current state for next run
    save_current_state(current_state)

    # 5. Only send alert if a sold-out → on-sale flip happened
    if not alerts:
        print("No status flips detected. Staying quiet.")
        return

    lines = ["🚨 <b>TICKETS JUST BECAME AVAILABLE!</b> 🚨\n"]
    lines.append(f"<b>Noah Kahan — Atlanta</b>\n")

    for a in alerts:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<b>{a['name']}</b>")
        lines.append(f"📅 {a['date']}")
        lines.append(f"📍 {a['venue']}")
        lines.append(f"🎫 Was: {a['old_status']} → NOW ON SALE")
        if a["price"]:
            lines.append(f"💰 {a['price']}")
        lines.append(f"\n🔗 <a href=\"{a['url']}\">GET TICKETS NOW</a>\n")

    message = "\n".join(lines)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
