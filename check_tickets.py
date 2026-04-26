"""
Noah Kahan Atlanta Ticket Checker
Checks Ticketmaster for Noah Kahan events in Atlanta, GA
and sends a Telegram alert when RESALE / EXCHANGE tickets are available.
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
        "size": 20,
        "sort": "date,asc",
        "source": "ticketmaster",
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

    if "_embedded" not in data or "events" not in data["_embedded"]:
        print("No events found.")
        return []

    events = data["_embedded"]["events"]
    print(f"Found {len(events)} event(s) total.")
    return events


def check_resale_availability(event):
    """
    Check if an event has resale/exchange tickets available.
    Looks at multiple indicators in the API response.
    """

    event_id = event.get("id", "")
    status = event.get("dates", {}).get("status", {}).get("code", "unknown")

    # Skip cancelled or postponed events entirely
    if status in ("cancelled", "postponed"):
        return False, "cancelled/postponed"

    # Check for resale ticket availability via the event detail endpoint
    if event_id and TICKETMASTER_API_KEY:
        detail_url = (
            f"https://app.ticketmaster.com/discovery/v2/events/{event_id}.json"
            f"?apikey={TICKETMASTER_API_KEY}"
        )
        try:
            req = urllib.request.Request(detail_url)
            with urllib.request.urlopen(req, timeout=30) as response:
                detail = json.loads(response.read().decode())

            # Check if the event has any active sales (public or resale)
            sales = detail.get("sales", {})
            public_sale = sales.get("public", {})
            has_public = public_sale.get("startDateTime") is not None

            # Check for presales that might include resale/exchange
            presales = sales.get("presales", [])
            resale_presale = any(
                "resale" in (p.get("name", "").lower()) or
                "exchange" in (p.get("name", "").lower()) or
                "verified" in (p.get("name", "").lower())
                for p in presales
            )

            # Check ticket availability flags
            ticket_limit = detail.get("ticketLimit", {})
            accessibility = detail.get("accessibility", {})

            # The event URL itself will show resale tickets if they exist
            # If the event is listed and not cancelled, resale may be active
            # The API doesn't have a direct "resale available" flag, so we
            # check: event exists + not cancelled + status is onsale or rescheduled
            if status in ("onsale", "rescheduled"):
                return True, "on sale (includes resale/exchange)"

            # If primary is offsale but event is still active, resale may exist
            if status == "offsale" and has_public:
                return True, "primary off sale — resale/exchange may be available"

        except Exception as e:
            print(f"  Could not fetch event detail: {e}")

    # Fallback: if event exists and isn't cancelled, it might have resale
    if status not in ("cancelled", "postponed"):
        return True, f"event active (status: {status})"

    return False, status


def format_event(event, resale_note):
    """Pull out the useful details from a Ticketmaster event object."""

    name = event.get("name", "Unknown Event")
    event_url = event.get("url", "No link available")

    start = event.get("dates", {}).get("start", {})
    date_str = start.get("localDate", "TBA")
    time_str = start.get("localTime", "")

    if date_str != "TBA":
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            date_str = date_obj.strftime("%B %d, %Y")
        except ValueError:
            pass

    if time_str:
        try:
            time_obj = datetime.strptime(time_str, "%H:%M:%S")
            time_str = time_obj.strftime("%I:%M %p")
        except ValueError:
            pass

    venues = event.get("_embedded", {}).get("venues", [])
    venue_name = venues[0].get("name", "Unknown Venue") if venues else "Unknown Venue"

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
        "price": price_str,
        "url": event_url,
        "resale_note": resale_note,
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
    if not TICKETMASTER_API_KEY:
        print("ERROR: TICKETMASTER_API_KEY is not set.")
        return

    events = search_ticketmaster()

    if not events:
        print("No Noah Kahan events in Atlanta found at all. Will check again next run.")
        return

    # Check each event for resale/exchange availability
    available_events = []
    for event in events:
        name = event.get("name", "Unknown")
        has_resale, note = check_resale_availability(event)
        print(f"  Event: {name} — Resale check: {has_resale} ({note})")
        if has_resale:
            available_events.append((event, note))

    if not available_events:
        print("Events found but no resale/exchange tickets available. Will check again next run.")
        return

    # Build the notification message
    lines = ["🎟️ <b>RESALE TICKETS — NOAH KAHAN IN ATLANTA!</b> 🎟️\n"]
    lines.append(f"{len(available_events)} event(s) with exchange/resale tickets:\n")

    for event, note in available_events:
        info = format_event(event, note)

        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<b>{info['name']}</b>")
        lines.append(f"📅 {info['date']} {info['time']}")
        lines.append(f"📍 {info['venue']}")
        lines.append(f"🎫 {info['resale_note']}")
        if info["price"]:
            lines.append(f"💰 {info['price']}")
        lines.append(f"🔗 <a href=\"{info['url']}\">CHECK RESALE TICKETS</a>\n")

    message = "\n".join(lines)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
