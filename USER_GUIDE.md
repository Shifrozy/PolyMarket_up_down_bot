# 📖 USER GUIDE — Polymarket BTC Strategy Bot

> Complete step-by-step guide to set up and run your Polymarket BTC trading bot.

---

## 📋 Table of Contents

1. [What Does This Bot Do?](#1-what-does-this-bot-do)
2. [Prerequisites](#2-prerequisites)
3. [Getting Your Polymarket Credentials](#3-getting-your-polymarket-credentials)
4. [Installation &amp; Setup](#4-installation--setup)
5. [Configuration](#5-configuration)
6. [Running the Bot](#6-running-the-bot)
7. [Understanding the Terminal Dashboard](#7-understanding-the-terminal-dashboard)
8. [Strategy Explained](#8-strategy-explained)
9. [Trade History &amp; Logs](#9-trade-history--logs)
10. [Going Live](#10-going-live)
11. [Troubleshooting](#11-troubleshooting)
12. [FAQ](#12-faq)

---

## 1. What Does This Bot Do?

This bot automatically trades BTC UP/DOWN binary options on **Polymarket** using 15-minute candles.

**In Simple Words:**

- Bot watches BTC price every 15 minutes
- If BTC goes DOWN for 2 candles in a row → Bot bets it will go **UP** (contrarian)
- If BTC goes UP for 2 candles in a row → Bot bets it will go **DOWN** (contrarian)
- If the bet loses, bot tries again (up to 3 more times)
- If it wins, bot resets and waits for the next signal
- Maximum risk: **$1 per trade**

---

## 2. Prerequisites

Before starting, make sure you have:

### ✅ Software Required

| Software | Version       | Download Link                                          |
| -------- | ------------- | ------------------------------------------------------ |
| Python   | 3.9 or higher | [python.org/downloads](https://www.python.org/downloads/) |
| pip      | Latest        | Comes with Python                                      |
| Terminal | Any           | Command Prompt / PowerShell / Git Bash                 |

### ✅ Accounts Required

| Account                   | Purpose          | Link                                  |
| ------------------------- | ---------------- | ------------------------------------- |
| **Polymarket**      | Trading platform | [polymarket.com](https://polymarket.com) |
| **USDC on Polygon** | Trading funds    | Deposit via Polymarket                |

### ✅ Check Python Version

Open your terminal and run:

```bash
python --version
```

You should see `Python 3.9.x` or higher.

---

## 3. Getting Your Polymarket Credentials

You need **2 things** from your Polymarket account:

### 🔑 A) PRIVATE_KEY (Your Wallet's Private Key)

This is the secret key that allows the bot to trade on your behalf.

**Steps:**

1. Go to [polymarket.com](https://polymarket.com) and **log in**
2. Click on your **Profile** icon (top-right corner)
3. Click **"Cash"** or **"Wallet"**
4. Click the **three dots (⋯)** menu
5. Select **"Export Private Key"**
6. You may need to confirm via email or 2FA
7. Copy the key — it looks like this:
   ```
   0x1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z...
   ```

> ⚠️ **SECURITY WARNING:**
>
> - NEVER share your private key with anyone
> - NEVER post it online or on GitHub
> - The `.gitignore` file already protects your `.env` from being committed

---

### 📍 B) FUNDER_ADDRESS (Your Wallet Address)

This is the public address of your Polymarket wallet.

**Steps:**

1. Go to [polymarket.com](https://polymarket.com) and **log in**
2. Click on your **Profile** icon
3. Click **"Deposit"**
4. Your **Polygon wallet address** is shown there
5. It looks like this:
   ```
   0x742d35Cc6634C0532925a3b844Bc9e7595f2bD3e
   ```

**Alternative ways to find it:**

- Go to **Settings → Account** — your address is displayed there
- Check your **deposit/withdrawal history** on PolygonScan

---

### 🔧 C) SIGNATURE_TYPE (How You Log In)

This depends on HOW you created your Polymarket account:

| How You Log In                                 | Value to Use         |
| ---------------------------------------------- | -------------------- |
| **Email** (Magic link, Google, etc.)     | `1` ← Most common |
| **MetaMask** or hardware wallet (Ledger) | `0`                |
| **Browser extension** proxy wallet       | `2`                |

> 💡 **Most users** log in with email, so `SIGNATURE_TYPE=1` is the default.

---

## 4. Installation & Setup

### Step 1: Open Terminal

- **Windows:** Press `Win + R`, type `cmd` or `powershell`, press Enter
- Navigate to the bot folder:
  ```bash
  cd "D:\PROJECTS\New Projects\Polymarket St bot"
  ```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required Python packages. Wait until it finishes.

### Step 3: Create Your `.env` File

Copy the example file:

```bash
copy .env.example .env
```

### Step 4: Edit `.env` With Your Credentials

Open `.env` in any text editor (Notepad, VS Code, etc.) and fill in your values:

```env
# Replace with YOUR actual values:
PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
FUNDER_ADDRESS=0xYOUR_WALLET_ADDRESS_HERE
SIGNATURE_TYPE=1

# Trading settings (defaults are fine to start):
TRADE_AMOUNT=1.0
SHARE_PRICE=0.50
MAX_SLIPPAGE=0.02
COOLDOWN_MINUTES=30
MAX_ENTRY_WAIT_MINUTES=5

# Start in paper mode for testing:
PAPER_MODE=true
```

---

## 5. Configuration

All settings in `.env` explained:

### Trading Parameters

| Setting          | Default  | What It Does                            |
| ---------------- | -------- | --------------------------------------- |
| `TRADE_AMOUNT` | `1.0`  | How much USDC to spend per trade ($1)   |
| `SHARE_PRICE`  | `0.50` | Target price per share ($0.50)          |
| `MAX_SLIPPAGE` | `0.02` | Maximum price deviation allowed (0.02%) |

### Strategy Parameters

| Setting                    | Default | What It Does                           |
| -------------------------- | ------- | -------------------------------------- |
| `COOLDOWN_MINUTES`       | `30`  | Pause duration after 5th candle loss   |
| `MAX_ENTRY_WAIT_MINUTES` | `5`   | Max wait time to catch the right price |

### Mode

| Setting        | Default  | What It Does                                |
| -------------- | -------- | ------------------------------------------- |
| `PAPER_MODE` | `true` | `true` = simulated trades (no real money) |
|                |          | `false` = real trades with real USDC      |

---

## 6. Running the Bot

### 🧪 Paper Mode (Practice — No Real Money)

```bash
python bot.py
```

This is the **default mode**. The bot simulates trades without spending any real USDC.
Use this to test and observe the strategy before going live.

### 💰 Live Mode (Real Trading)

```bash
python bot.py --live
```

Or set `PAPER_MODE=false` in your `.env` file and run:

```bash
python bot.py
```

### 📊 Check Status (Quick View)

```bash
python bot.py --status
```

Shows your total trades, wins, losses, P&L, and recent trade history.

### 🛑 Stopping the Bot

Press **`Ctrl + C`** in the terminal. The bot will save all data and shut down gracefully.

---

## 7. Understanding the Terminal Dashboard

When the bot runs, you'll see a **live dashboard** like this:

```
╔══════════════════════════════════════════════════════════════╗
║   ₿  POLYMARKET BTC STRATEGY BOT   🔴 PAPER MODE   ⏱ 01:23:45  ║
╚══════════════════════════════════════════════════════════════╝

┌── ₿ BTC Market ──────────────┐  ┌── 🧠 Strategy ─────────────────┐
│ BTC Price:  $97,234.56       │  │ State:     🔍 SCANNING          │
│ Current:    GREEN  +0.12%    │  │ Signal:    —                     │
│ Progress:   ██████████░░ 75% │  │ Consec.:   0                    │
│ Closes in:  3m 45s           │  │ Signals:   5                    │
└──────────────────────────────┘  └─────────────────────────────────┘

┌── 🕯 Recent Candles ─────────┐  ┌── 💰 Performance ──────────────┐
│ Time   Open     Close   Color│  │ Total P&L:   📈 +$3.00         │
│ 14:00  $97,100  $97,250  🟢 │  │ Trades:      8                  │
│ 14:15  $97,250  $97,180  🔴 │  │ Win Rate:    62.5%              │
│ 14:30  $97,180  $97,050  🔴 │  │ Wins:        5                  │
│ 14:45  $97,050  $97,200  🟢 │  │ Losses:      3                  │
└──────────────────────────────┘  └─────────────────────────────────┘

┌── 📋 Activity Log ───────────────────────────────────────────────┐
│ 14:45:02  🕯 Candle closed: 14:30-14:45 GREEN +0.15%            │
│ 14:45:02  🔴🔴 2 RED candles detected → Signal: BUY UP          │
│ 14:45:03  📝 Paper trade: 🟢 UP | $1.00 | Candle #3             │
│ 15:00:01  🎉 TRADE WON! 🟢 UP | P&L: +$1.00 | Candle #3        │
└──────────────────────────────────────────────────────────────────┘
```

### Dashboard Panels Explained

| Panel                    | What It Shows                                                   |
| ------------------------ | --------------------------------------------------------------- |
| **Header**         | Bot name, mode (Paper/Live), uptime                             |
| **BTC Market**     | Current BTC price, candle color, progress bar, time until close |
| **Strategy**       | Current bot state (Scanning/In Trade/Cooldown etc.)             |
| **Recent Candles** | Last 6 closed 15-min candles with open/close/color              |
| **Performance**    | Total P&L, win rate, wins, losses, volume                       |
| **Activity Log**   | Real-time log of bot actions and decisions                      |

### Bot States Explained

| State           | Icon | Meaning                                              |
| --------------- | ---- | ---------------------------------------------------- |
| SCANNING        | 🔍   | Watching candles, waiting for 2 same-color signal    |
| SIGNAL_DETECTED | 🎯   | Found 2 consecutive candles, preparing trade         |
| WAITING_ENTRY   | ⏳   | Waiting for the right price (max 5 min)              |
| IN_TRADE        | 📊   | Trade is open, waiting for candle to close           |
| PROGRESSIVE     | 📈   | In progressive entry sequence (3rd→4th→5th candle) |
| COOLDOWN        | ❄️ | 30-min pause after 5th candle trade                  |

---

## 8. Strategy Explained

### The Core Idea (Contrarian)

The strategy bets **against** the current trend:

- Market going DOWN? → Bet it goes **UP** (reversal expected)
- Market going UP? → Bet it goes **DOWN** (reversal expected)

### Full Flow Diagram

```
START
  │
  ▼
[SCANNING] ──── Watch 15-min BTC candles
  │
  │  2 RED candles in a row?  ──── YES ──→ Signal: BUY UP
  │  2 GREEN candles in a row? ── YES ──→ Signal: BUY DOWN
  │
  ▼
[TRADE CANDLE #3]
  │
  ├── WON? ──→ Reset → Go back to SCANNING ✅
  │
  └── LOST? ──→ Progressive Entry
                  │
                  ▼
              [TRADE CANDLE #4]
                  │
                  ├── WON? ──→ Reset → SCANNING ✅
                  │
                  └── LOST? ──→ Progressive Entry
                                  │
                                  ▼
                              [TRADE CANDLE #5]
                                  │
                                  ├── WON? ──→ Reset → SCANNING ✅
                                  │
                                  └── LOST? ──→ COOLDOWN (30 min) ❄️
                                                  │
                                                  ▼
                                              Go back to SCANNING
```

### Example Scenario

| Candle # | BTC Move           | Color    | Bot Action                |
| -------- | ------------------ | -------- | ------------------------- |
| 1        | $97,000 → $96,800 | 🔴 RED   | Watching...               |
| 2        | $96,800 → $96,500 | 🔴 RED   | Signal! 2 RED → BUY UP   |
| 3        | $96,500 → $96,700 | 🟢 GREEN | ✅ WON! (+$1.00) → Reset |

### Example with Progressive Loss

| Candle # | BTC Move           | Color    | Bot Action                         |
| -------- | ------------------ | -------- | ---------------------------------- |
| 1        | $97,000 → $96,800 | 🔴 RED   | Watching...                        |
| 2        | $96,800 → $96,500 | 🔴 RED   | Signal! BUY UP                     |
| 3        | $96,500 → $96,300 | 🔴 RED   | ❌ LOST (-$1.00) → Progressive #4 |
| 4        | $96,300 → $96,100 | 🔴 RED   | ❌ LOST (-$1.00) → Progressive #5 |
| 5        | $96,100 → $96,400 | 🟢 GREEN | ✅ WON (+$1.00) → Reset           |

---

## 9. Trade History & Logs

### Automatic Trade Log

All trades are saved to `trade_history.json` in the bot folder:

```json
{
  "trades": [
    {
      "trade_id": "T1770734619568",
      "direction": "DOWN",
      "amount": 1.0,
      "share_price": 0.5,
      "shares": 2.0,
      "candle_number": 3,
      "status": "WON",
      "pnl": 1.0
    }
  ]
}
```

### Quick Status Check

Run this anytime (even while bot is stopped):

```bash
python bot.py --status
```

---

## 10. Going Live

### Pre-Flight Checklist

Before switching to live trading, make sure:

- [ ] ✅ You've run in **Paper Mode** for at least a few hours
- [ ] ✅ You understand the strategy and potential losses
- [ ] ✅ Your Polymarket account has **USDC deposited**
- [ ] ✅ Your `.env` has the correct **PRIVATE_KEY** and **FUNDER_ADDRESS**
- [ ] ✅ You're comfortable with **$1 per trade** risk

### Switch to Live

**Option A:** Edit `.env`:

```env
PAPER_MODE=false
```

Then run:

```bash
python bot.py
```

**Option B:** Use the `--live` flag:

```bash
python bot.py --live
```

### ⚠️ Important Notes for Live Trading

- Maximum trade amount is **$1** (hardcoded safety limit)
- Bot only trades **one position at a time** (no overlap)
- Bot will **skip** trades if the price is too far from $0.50/share
- Always monitor the bot — don't leave it unattended for extended periods
- You can stop anytime with **Ctrl + C**

---

## 11. Troubleshooting

### ❌ "PRIVATE_KEY is not set in .env"

**Fix:** Make sure you created the `.env` file (not just `.env.example`) and pasted your private key.

### ❌ "Binance API error"

**Fix:** Check your internet connection. The bot needs internet to fetch BTC prices.

### ❌ "No active BTC 15-min market found"

**This is normal!** Polymarket BTC 15-minute markets are not always available. The bot will automatically fall back to paper simulation mode and retry periodically.

### ❌ Unicode/Emoji errors in terminal

**Fix:** Run the bot with UTF-8 encoding:

```bash
python -X utf8 bot.py
```

### ❌ Bot not placing trades

**Possible reasons:**

1. No 2 consecutive same-color candles detected yet
2. Price is too far from $0.50 target (slippage protection)
3. Bot is in cooldown period (check dashboard)
4. Entry timeout exceeded (5 minutes)

### ❌ "Failed to initialize CLOB client"

**Fix:** Double-check your PRIVATE_KEY and FUNDER_ADDRESS in `.env`. Make sure you have the correct SIGNATURE_TYPE for your login method.

---

## 12. FAQ

### Q: How much money can I lose?

**A:** Maximum $1 per trade. In worst case (3 progressive losses before cooldown), you can lose $3 in a sequence. The bot then pauses for 30 minutes.

### Q: Does the bot run 24/7?

**A:** It runs as long as your terminal is open. For 24/7 operation, consider running on a VPS (cloud server).

### Q: Can I change the trade amount?

**A:** Yes, edit `TRADE_AMOUNT` in `.env`. However, the safety limit prevents trades above $1.

### Q: What happens if I lose internet?

**A:** The bot will show connection errors but won't crash. It will retry when connection is restored.

### Q: Can I run multiple bots?

**A:** Not recommended with the same account — it could cause trade overlaps.

### Q: How do I see my profits/losses?

**A:** Three ways:

1. Look at the **Performance** panel in the live dashboard
2. Run `python bot.py --status`
3. Open `trade_history.json` in any text editor

### Q: Is my private key safe?

**A:** Your key is stored locally in `.env` on your computer only. The `.gitignore` prevents it from being uploaded to GitHub. Never share this file.

---

## 💬 Need Help?

If you run into any issues:

1. Check the **Activity Log** in the dashboard for error messages
2. Review the **Troubleshooting** section above
3. Check `trade_history.json` for trade details

---

*Happy Trading! 🚀*
