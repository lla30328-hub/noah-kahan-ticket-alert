# 🎵 Noah Kahan Atlanta Ticket Alert

A free, automated ticket checker that monitors Ticketmaster for Noah Kahan concerts in Atlanta, GA and sends you instant Telegram notifications when tickets are found.

**Cost: $0** — runs entirely on free services (Ticketmaster API + GitHub Actions + Telegram).

---

## How It Works

Every 10 minutes, GitHub Actions runs a Python script that:
1. Queries the Ticketmaster Discovery API for Noah Kahan events in Atlanta
2. If events are found, sends you a Telegram message with all the details (date, venue, price, direct buy link)
3. If nothing is found, it quietly waits and checks again in 10 minutes

---

## Setup Guide (No Coding Required)

### Step 1: Get a Free Ticketmaster API Key

1. Go to [developer.ticketmaster.com](https://developer.ticketmaster.com/)
2. Click **"Get Your API Key"** (top right)
3. Sign up for a free account
4. Once logged in, go to **My Apps** and you'll see your **Consumer Key** — this is your API key
5. **Copy and save this key** — you'll need it in Step 4

### Step 2: Create a Telegram Bot (for notifications)

1. Open Telegram on your phone or computer
2. Search for **@BotFather** (the official Telegram bot maker)
3. Send it the message: `/newbot`
4. It will ask you for a **name** — type something like: `Noah Kahan Ticket Bot`
5. It will ask for a **username** — type something like: `noahkahan_tickets_bot` (must end in "bot")
6. BotFather will give you a **token** that looks like: `7123456789:AAHx1234abcd5678efgh`
7. **Copy and save this token** — you'll need it in Step 4

### Step 3a: Get Your Telegram Chat ID

1. In Telegram, search for your new bot by its username and tap **Start**
2. Send it any message (like "hello")
3. Now open this URL in your browser (replace YOUR_BOT_TOKEN with the token from Step 2):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. You'll see some JSON text. Look for `"chat":{"id":` followed by a number — that number is your **Chat ID**
5. **Copy and save this number** — you'll need it in Step 4

### Step 3b: Create a GitHub Account

1. Go to [github.com](https://github.com) and sign up for a free account (if you don't already have one)

### Step 4: Upload This Project to GitHub

1. Log in to GitHub
2. Click the **+** icon (top right) → **New repository**
3. Name it `noah-kahan-ticket-alert`
4. Make sure **Public** is selected (required for free GitHub Actions minutes)
5. Click **Create repository**
6. On the next page, click **"uploading an existing file"**
7. Drag and drop ALL the files from this folder:
   - `check_tickets.py`
   - The `.github` folder (contains the `workflows/check_tickets.yml` file)
   - `README.md`
   
   **Important:** The `.github` folder may be hidden on your computer. On Mac, press `Cmd + Shift + .` in Finder to show hidden files. On Windows, check "Hidden items" in File Explorer's View tab.
8. Click **Commit changes**

### Step 5: Add Your Secret Keys to GitHub

This is how GitHub securely stores your API keys without exposing them publicly.

1. In your new repository, click **Settings** (tab at the top)
2. In the left sidebar, click **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these three secrets one at a time:

| Name | Value |
|------|-------|
| `TICKETMASTER_API_KEY` | Your Ticketmaster Consumer Key from Step 1 |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from Step 2 |
| `TELEGRAM_CHAT_ID` | Your Chat ID number from Step 3a |

### Step 6: Enable GitHub Actions

1. In your repository, click the **Actions** tab
2. You should see the "Noah Kahan Ticket Checker" workflow
3. If it says "Workflows aren't being run on this repository," click **"I understand my workflows, go ahead and enable them"**
4. Click on **"Noah Kahan Ticket Checker"** on the left
5. Click **"Run workflow"** → **"Run workflow"** (green button) to test it manually

### Step 7: Verify It Works

1. After clicking Run workflow, wait about 30 seconds
2. Click into the workflow run to see the logs
3. If everything is set up correctly, you'll either:
   - See "No events found" (meaning no Noah Kahan Atlanta tickets exist yet — the bot will keep checking!)
   - Get a Telegram message with event details (if tickets are currently listed)

---

## 🎉 That's It! You're Done!

The checker will now run every 10 minutes, 24/7, completely free. When Noah Kahan tickets for Atlanta appear on Ticketmaster, you'll get an instant Telegram notification with all the details and a direct link to buy.

---

## Sharing With Friends

Anyone can use this! They just need to:
1. **Fork** your repository (there's a Fork button at the top of your GitHub repo page)
2. Follow Steps 1–3 above to get their own API key, Telegram bot, and Chat ID
3. Add their own secrets (Step 5)
4. Enable Actions (Step 6)

They do NOT need to know how to code.

---

## Customization

Want to monitor a different artist or city? Open `check_tickets.py` and change these lines near the top:

```python
ARTIST_NAME = "Noah Kahan"    # Change to any artist
CITY = "Atlanta"               # Change to any city
STATE_CODE = "GA"              # Change to the state abbreviation
```

---

## Free Tier Limits

- **Ticketmaster API:** 5,000 requests/day (you'll use ~144/day at 10-min intervals — well within limits)
- **GitHub Actions:** 2,000 minutes/month for free accounts (each run takes ~30 seconds — you'll use ~72 minutes/month)
- **Telegram:** Completely unlimited and free

---

## Troubleshooting

**"No events found" every time:**
This is normal! It just means Noah Kahan hasn't listed Atlanta dates on Ticketmaster yet. The bot keeps watching.

**Not getting Telegram messages:**
- Make sure you sent a message to your bot first (Step 3a, part 2)
- Double-check your bot token and chat ID in GitHub Secrets
- Try the manual "Run workflow" button and check the logs

**GitHub Actions not running:**
- Make sure your repository is **Public** (private repos have limited free minutes)
- Check the Actions tab for any error messages
