"""
╔══════════════════════════════════════════════════════╗
║     POLYMARKET BTC STRATEGY BOT — CONFIGURATION     ║
╚══════════════════════════════════════════════════════╝
Loads settings from .env and exposes them as typed constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Polymarket Credentials ──────────────────────────
PRIVATE_KEY: str = os.getenv("PRIVATE_KEY", "")
FUNDER_ADDRESS: str = os.getenv("FUNDER_ADDRESS", "")
SIGNATURE_TYPE: int = int(os.getenv("SIGNATURE_TYPE", "1"))

# ── API Endpoints ───────────────────────────────────
CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CHAIN_ID = 137  # Polygon

# ── Binance (free BTC price data) ───────────────────
BINANCE_API = "https://api.binance.com"
BINANCE_KLINE_ENDPOINT = f"{BINANCE_API}/api/v3/klines"
BTC_SYMBOL = "BTCUSDT"
CANDLE_INTERVAL = "15m"

# ── Trading Parameters ─────────────────────────────
TRADE_AMOUNT: float = float(os.getenv("TRADE_AMOUNT", "1.0"))
SHARE_PRICE: float = float(os.getenv("SHARE_PRICE", "0.50"))
MAX_SLIPPAGE: float = float(os.getenv("MAX_SLIPPAGE", "0.02"))
COOLDOWN_MINUTES: int = int(os.getenv("COOLDOWN_MINUTES", "30"))
MAX_ENTRY_WAIT_MINUTES: int = int(os.getenv("MAX_ENTRY_WAIT_MINUTES", "5"))

# ── Strategy ────────────────────────────────────────
CONSECUTIVE_CANDLES_SIGNAL = 2      # 2 same-color candles trigger a signal
MAX_PROGRESSIVE_ENTRIES = 5         # Max candle to trade before cooldown (3rd, 4th, 5th)
PROGRESSIVE_START = 3               # Progressive entries start at candle 3

# ── Mode ────────────────────────────────────────────
PAPER_MODE: bool = os.getenv("PAPER_MODE", "true").lower() == "true"

# ── Validation ──────────────────────────────────────
def validate_config() -> list[str]:
    """Return a list of config errors (empty = all good)."""
    errors = []
    if not PAPER_MODE:
        if not PRIVATE_KEY or PRIVATE_KEY == "your_private_key_here":
            errors.append("PRIVATE_KEY is not set in .env")
        if not FUNDER_ADDRESS or FUNDER_ADDRESS == "your_funder_address_here":
            errors.append("FUNDER_ADDRESS is not set in .env")
    if TRADE_AMOUNT <= 0:
        errors.append("TRADE_AMOUNT must be > 0")
    if not (0 < SHARE_PRICE < 1):
        errors.append("SHARE_PRICE must be between 0 and 1")
    if MAX_SLIPPAGE < 0:
        errors.append("MAX_SLIPPAGE must be >= 0")
    return errors
