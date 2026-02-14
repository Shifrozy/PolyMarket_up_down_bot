# ₿ Polymarket BTC Strategy Bot

> **Contrarian 2-Candle Strategy** with Progressive Entries for Polymarket BTC 15-minute Markets

---

## 🧠 Strategy Overview

This bot trades BTC on Polymarket using 15-minute candles with a contrarian approach:

### Core Logic
| Signal | Condition | Action |
|--------|-----------|--------|
| **A** | 2 consecutive RED candles | → **BUY UP** |
| **B** | 2 consecutive GREEN candles | → **BUY DOWN** |

### Progressive Entries
After the initial 2-candle signal:
- **3rd candle**: Bot places the trade
- **If 3rd WINS** → Reset, scan for new signal
- **If 3rd LOSES** → Trade the **4th candle** (same direction)
- **If 4th LOSES** → Trade the **5th candle** (same direction)
- **After 5th** → **30-minute cooldown** regardless of result

### Trade Parameters
- **Trade Amount**: $1 per trade
- **Share Price**: $0.50/share
- **Max Slippage**: 0.02%
- **Entry Timeout**: 5 minutes (skip if price not right)

### Safety Rules
- ✅ Only one trade per candle signal (no overlap)
- ✅ Never exceeds $1 per trade
- ✅ 30-min cooldown after max progressive entries

---

## 📋 File Structure

```
Polymarket St bot/
├── bot.py             # Main entry point — starts the bot
├── config.py          # Configuration loader (from .env)
├── candle_feed.py     # BTC 15-min candle data from Binance
├── market_finder.py   # Finds BTC UP/DOWN markets on Polymarket
├── strategy.py        # Core strategy engine (state machine)
├── trade_manager.py   # Trade execution, tracking, P&L
├── dashboard.py       # Rich terminal dashboard
├── requirements.txt   # Python dependencies
├── .env.example       # Template for credentials
├── .env               # Your credentials (DO NOT COMMIT)
└── trade_history.json # Auto-generated trade log
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
```bash
cp .env.example .env
# Edit .env with your Polymarket private key and funder address
```

**To get your Private Key:**
1. Go to [polymarket.com](https://polymarket.com)
2. Click **Cash** → **...** → **Export Private Key**
3. Copy and paste into `.env`

### 3. Run in Paper Mode (default)
```bash
python bot.py
```

### 4. Run in Live Mode
```bash
python bot.py --live
```

### 5. Check Status
```bash
python bot.py --status
```

---

## 🖥️ Terminal Dashboard

The bot displays a clean, live-updating terminal dashboard showing:

| Panel | Contents |
|-------|----------|
| **BTC Market** | Current price, candle color, progress bar, time to close |
| **Recent Candles** | Last 6 closed candles with colors and changes |
| **Strategy** | Current state, signal direction, progressive entry # |
| **Performance** | Total P&L, win rate, wins/losses, volume |
| **Activity Log** | Real-time log of bot actions and decisions |

---

## ⚙️ Configuration

All settings can be overridden via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIVATE_KEY` | — | Polymarket wallet private key |
| `FUNDER_ADDRESS` | — | Funder/proxy wallet address |
| `SIGNATURE_TYPE` | `1` | 0=EOA, 1=Email, 2=Browser proxy |
| `TRADE_AMOUNT` | `1.0` | Trade amount in USDC |
| `SHARE_PRICE` | `0.50` | Target share price |
| `MAX_SLIPPAGE` | `0.02` | Max slippage (0.02 = 0.02%) |
| `COOLDOWN_MINUTES` | `30` | Cooldown after 5th candle |
| `MAX_ENTRY_WAIT_MINUTES` | `5` | Max wait for right price |
| `PAPER_MODE` | `true` | Paper trading mode |

---

## ⚠️ Disclaimer

This bot is for educational purposes. Trading involves risk. Never trade with money you can't afford to lose. The authors are not responsible for any financial losses.

---

## 📜 License

MIT License
