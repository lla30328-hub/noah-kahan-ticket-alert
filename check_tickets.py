"""
Noah Kahan Atlanta Ticket Checker
Checks Ticketmaster for Noah Kahan events in Atlanta, GA
and sends a Telegram alert ONLY when something NEW changes:
- A new event appears
- Ticket status changes (e.g. goes on sale)
- Price range changes

Uses a GitHub Gist as free cloud storage to remember what it already told you.
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

# Filename used inside the Gist to store state
STATE_FILENAME = "ticket_state.json"


# ── State Management (GitHub Gist) ───────────────────────────────

def load_previous_state():
    """Load the last known state from a GitHub Gist."""
    if not GIST_ID or not GITHUB_TOKEN:
        print("No Gist configured — treating everything as new.")
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
    """Save the current state to a GitHub Gist."""
    if not GIST_ID or not GITHUB_TOKEN:
        print("No Gist configured — state not saved.")
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
                print("State saved to Gist.")
            else:
                print(f"Gist save returned status {resp.status}")
    except Exception as e:
        print(f"Could not save state: {e}")


# ── Ticketmaster API ─────────────────────────────────────────────

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


def get_event_snapshot(event):
    """
    Create a comparable snapshot of an event's key details.
    If any of these change, we send a new alert.
    """

    event_id = event.get("id", "unknown")
    name = event.get("name", "Unknown Event")
    status = event.get("dates", {}).get("status", {}).get("code", "unknown")

    # Skip cancelled/postponed
    if status in ("cancelled", "postponed"):
        return None

    start = event.get("dates", {}).get("start", {})
    date_str = start.get("localDate", "TBA")
    time_str = start.get("localTime", "")

    venues = event.get("_embedded", {}).get("venues", [])
    venue_name = venues[0].get("name", "Unknown Venue") if venues else "Unknown Venue"

    price_ranges = event.get("priceRanges", [])
    price_str = ""
    if price_ranges:
        low = price_ranges[0].get("min", "?")
        high = price_ranges[0].get("max", "?")
        price_str = f"${low}-${high}"

    event_url = event.get("url", "")

    return {
        "id": event_id,
        "name": name,
        "status": status,
        "date": date_str,
        "time": time_str,
        "venue": venue_name,
        "price": price_str,
        "url": event_url,
    }


def find_changes(previous_state, current_snapshots):
    """
    Compare current event snapshots to previous state.
    Returns lists of new events, changed events, and the updated state dict.
    """

    new_events = []
    changed_events = []
    current_state = {}

    for snap in current_snapshots:
        eid = snap["id"]
        current_state[eid] = snap

        if eid not in previous_state:
            # Brand new event we haven't seen before
            new_events.append(("NEW", snap))
        else:
            # Event exists — check if anything important changed
            old = previous_state[eid]
            changes = []

            if old.get("status") != snap["status"]:
                changes.append(f"Status: {old.get('status')} → {snap['status']}")
            if old.get("price") != snap["price"] and snap["price"]:
                changes.append(f"Price: {old.get('price', 'N/A')} → {snap['price']}")
            if old.get("date") != snap["date"]:
                changes.append(f"Date: {old.get('date')} → {snap['date']}")

            if changes:
                changed_events.append((changes, snap))

    return new_events, changed_events, current_state


# ── Formatting & Notifications ───────────────────────────────────

def format_date_nice(date_str, time_str):
    """Format date and time for display."""
    if date_str and date_str != "TBA":
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
    return f"{date_str} {time_str}".strip()


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
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("Telegram notification sent!")
                return True
            else:
                print(f"Telegram error: {result}")
                return False
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────

def main():
    if not TICKETMASTER_API_KEY:
        print("ERROR: TICKETMASTER_API_KEY is not set.")
        return

    # 1. Load what we already know about
    previous_state = load_previous_state()

    # 2. Search Ticketmaster
    events = search_ticketmaster()

    if not events:
        print("No Noah Kahan events in Atlanta right now. Will check again next run.")
        return

    # 3. Build snapshots of current events (skip cancelled/postponed)
    current_snapshots = []
    for event in events:
        snap = get_event_snapshot(event)
        if snap:
            current_snapshots.append(snap)

    if not current_snapshots:
        print("All found events are cancelled/postponed. Nothing to alert on.")
        return

    # 4. Compare to previous state
    new_events, changed_events, current_state = find_changes(previous_state, current_snapshots)

    # 5. Send alerts only if something is NEW or CHANGED
    if not new_events and not changed_events:
        print("No changes since last check. No alert needed.")
        # Still save state in case structure changed
        save_current_state(current_state)
        return

    lines = ["🎟️ <b>NOAH KAHAN — ATLANTA TICKET UPDATE!</b> 🎟️\n"]

    if new_events:
        lines.append(f"🆕 <b>{len(new_events)} NEW event(s) found:</b>\n")
        for reason, snap in new_events:
            date_nice = format_date_nice(snap["date"], snap["time"])
            lines.append(f"━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"<b>{snap['name']}</b>")
            lines.append(f"📅 {date_nice}")
            lines.append(f"📍 {snap['venue']}")
            lines.append(f"🎫 Status: {snap['status']}")
            if snap["price"]:
                lines.append(f"💰 {snap['price']}")
            lines.append(f"🔗 <a href=\"{snap['url']}\">CHECK TICKETS</a>\n")

    if changed_events:
        lines.append(f"🔄 <b>{len(changed_events)} event(s) UPDATED:</b>\n")
        for changes, snap in changed_events:
            date_nice = format_date_nice(snap["date"], snap["time"])
            lines.append(f"━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"<b>{snap['name']}</b>")
            lines.append(f"📅 {date_nice}")
            lines.append(f"📍 {snap['venue']}")
            for change in changes:
                lines.append(f"⚡ {change}")
            if snap["price"]:
                lines.append(f"💰 {snap['price']}")
            lines.append(f"🔗 <a href=\"{snap['url']}\">CHECK TICKETS</a>\n")

    message = "\n".join(lines)
    send_telegram_message(message)

    # 6. Save current state so next run knows what we already reported
    save_current_state(current_state)
    print("Done!")


if __name__ == "__main__":
    main()
