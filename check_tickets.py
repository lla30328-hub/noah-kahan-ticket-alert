"""
Noah Kahan Atlanta Ticket Checker
Checks the Ticketmaster Discovery API for Noah Kahan events in Atlanta, GA
and sends a Telegram notification when tickets are found.
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

# --- Search Settings ---
ARTIST_NAME = "Noah Kahan"
CITY = "Atlanta"
STATE_CODE = "GA"
COUNTRY_CODE = "US"


def search_ticketmaster():
    """Search Ticketmaster Discovery API for Noah Kahan events in Atlanta."""

    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"

    params = {
        "apikey": TICKETMASTER_API_KEY,
        "keyword": ARTIST_NAME,
        "city": CITY,
        "stateCode": STATE_CODE,
        "countryCode": COUNTRY_CODE,
        "size": 20,  # max results per page
        "sort": "date,asc",
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    print(f"[{datetime.now()}] Checking Ticketmaster for {ARTIST_NAME} in {CITY}, {STATE_CODE}...")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} - {e.reason}")
        return []
    except Exception as e:
        print(f"Request failed: {e}")
        return []

    # Check if any events were returned
    if "_embedded" not in data or "events" not in data["_embedded"]:
        print("No events found.")
        return []

    events = data["_embedded"]["events"]
    print(f"Found {len(events)} event(s)!")
    return events


def format_event(event):
    """Pull out the useful details from a Ticketmaster event object."""

    name = event.get("name", "Unknown Event")
    url = event.get("url", "No link available")
    status = event.get("dates", {}).get("status", {}).get("code", "unknown")

    # Get date and time
    start = event.get("dates", {}).get("start", {})
    date_str = start.get("localDate", "TBA")
    time_str = start.get("localTime", "")

    if date_str != "TBA":
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            date_str = date_obj.strftime("%B %d, %Y")  # e.g., "March 15, 2026"
        except ValueError:
            pass

    if time_str:
        try:
            time_obj = datetime.strptime(time_str, "%H:%M:%S")
            time_str = time_obj.strftime("%I:%M %p")  # e.g., "7:30 PM"
        except ValueError:
            pass

    # Get venue info
    venues = event.get("_embedded", {}).get("venues", [])
    venue_name = venues[0].get("name", "Unknown Venue") if venues else "Unknown Venue"

    # Get price range if available
    price_ranges = event.get("priceRanges", [])
    price_str = ""
    if price_ranges:
        low = price_ranges[0].get("min", "?")
        high = price_ranges[0].get("max", "?")
        currency = price_ranges[0].get("currency", "USD")
        price_str = f"${low} - ${high} {currency}"

    return {
        "name": name,
        "date": date_str,
        "time": time_str,
        "venue": venue_name,
        "status": status,
        "price": price_str,
        "url": url,
    }


def send_telegram_message(message):
    """Send a message via Telegram Bot API."""

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set. Printing message instead:")
        print(message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode())
            if result.get("ok"):
                print("Telegram notification sent!")
                return True
            else:
                print(f"Telegram error: {result}")
                return False
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False


def main():
    # Validate config
    if not TICKETMASTER_API_KEY:
        print("ERROR: TICKETMASTER_API_KEY is not set.")
        return

    events = search_ticketmaster()

    if not events:
        print("No Noah Kahan events in Atlanta right now. Will check again next run.")
        return

    # Build the notification message
    lines = ["🎵 <b>NOAH KAHAN TICKET ALERT!</b> 🎵\n"]
    lines.append(f"Found {len(events)} event(s) in Atlanta, GA:\n")

    for event in events:
        info = format_event(event)

        status_emoji = {
            "onsale": "✅ ON SALE",
            "offsale": "⏸ Off Sale",
            "cancelled": "❌ Cancelled",
            "postponed": "⏳ Postponed",
            "rescheduled": "🔄 Rescheduled",
        }.get(info["status"], f"ℹ️ {info['status'].title()}")

        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<b>{info['name']}</b>")
        lines.append(f"📅 {info['date']} {info['time']}")
        lines.append(f"📍 {info['venue']}")
        lines.append(f"🎫 Status: {status_emoji}")
        if info["price"]:
            lines.append(f"💰 {info['price']}")
        lines.append(f"🔗 <a href=\"{info['url']}\">Buy Tickets</a>\n")

    message = "\n".join(lines)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
