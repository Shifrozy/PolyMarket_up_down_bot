"""
╔══════════════════════════════════════════════════════╗
║   POLYMARKET BTC STRATEGY BOT — CANDLE DATA FEED    ║
╚══════════════════════════════════════════════════════╝
Fetches BTC 15-minute candles from Binance public API
and provides candle color tracking.
"""

import time
import requests
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from config import BINANCE_KLINE_ENDPOINT, BTC_SYMBOL, CANDLE_INTERVAL


@dataclass
class Candle:
    """A single 15-minute BTC candle."""
    open_time: float          # Epoch ms
    close_time: float         # Epoch ms
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    is_closed: bool = False

    @property
    def color(self) -> str:
        """'green' if close >= open, else 'red'."""
        return "green" if self.close_price >= self.open_price else "red"

    @property
    def open_dt(self) -> datetime:
        return datetime.fromtimestamp(self.open_time / 1000, tz=timezone.utc)

    @property
    def close_dt(self) -> datetime:
        return datetime.fromtimestamp(self.close_time / 1000, tz=timezone.utc)

    @property
    def change_pct(self) -> float:
        if self.open_price == 0:
            return 0.0
        return ((self.close_price - self.open_price) / self.open_price) * 100

    def __repr__(self) -> str:
        arrow = "UP" if self.color == "green" else "DN"
        return (
            f"Candle({self.open_dt.strftime('%H:%M')}-{self.close_dt.strftime('%H:%M')} "
            f"{arrow} O:{self.open_price:.2f} C:{self.close_price:.2f} "
            f"{self.change_pct:+.2f}%)"
        )


class CandleFeed:
    """Fetches and tracks BTC 15-minute candles from Binance."""

    def __init__(self):
        self.candles: list[Candle] = []
        self._last_closed_time: Optional[float] = None

    def fetch_recent(self, limit: int = 10) -> list[Candle]:
        """Fetch the most recent `limit` candles from Binance."""
        try:
            resp = requests.get(
                BINANCE_KLINE_ENDPOINT,
                params={
                    "symbol": BTC_SYMBOL,
                    "interval": CANDLE_INTERVAL,
                    "limit": limit,
                },
                timeout=10,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            raise ConnectionError(f"Binance API error: {e}")

        candles = []
        now_ms = time.time() * 1000
        for k in raw:
            candle = Candle(
                open_time=float(k[0]),
                close_time=float(k[6]),
                open_price=float(k[1]),
                high_price=float(k[2]),
                low_price=float(k[3]),
                close_price=float(k[4]),
                volume=float(k[5]),
                is_closed=(float(k[6]) < now_ms),
            )
            candles.append(candle)

        self.candles = candles
        return candles

    def get_closed_candles(self) -> list[Candle]:
        """Return only fully closed candles."""
        return [c for c in self.candles if c.is_closed]

    def get_current_candle(self) -> Optional[Candle]:
        """Return the currently-forming (not yet closed) candle."""
        open_candles = [c for c in self.candles if not c.is_closed]
        return open_candles[-1] if open_candles else None

    def get_last_n_closed(self, n: int) -> list[Candle]:
        """Return the last N closed candles (oldest first)."""
        closed = self.get_closed_candles()
        return closed[-n:] if len(closed) >= n else closed

    def has_new_closed_candle(self) -> bool:
        """Check if there is a new closed candle since last check."""
        closed = self.get_closed_candles()
        if not closed:
            return False
        latest = closed[-1].close_time
        if self._last_closed_time is None or latest > self._last_closed_time:
            self._last_closed_time = latest
            return True
        return False

    def get_btc_price(self) -> float:
        """Get the latest BTC price."""
        try:
            resp = requests.get(
                f"https://api.binance.com/api/v3/ticker/price",
                params={"symbol": BTC_SYMBOL},
                timeout=10,
            )
            resp.raise_for_status()
            return float(resp.json()["price"])
        except Exception:
            # Fallback to last candle close price
            if self.candles:
                return self.candles[-1].close_price
            return 0.0

    def seconds_until_candle_close(self) -> float:
        """Seconds until the current candle closes."""
        current = self.get_current_candle()
        if not current:
            return 0.0
        now_ms = time.time() * 1000
        remaining_ms = current.close_time - now_ms
        return max(0.0, remaining_ms / 1000)

    def candle_progress_pct(self) -> float:
        """How far through the current candle we are (0-100%)."""
        current = self.get_current_candle()
        if not current:
            return 100.0
        now_ms = time.time() * 1000
        total = current.close_time - current.open_time
        elapsed = now_ms - current.open_time
        return min(100.0, max(0.0, (elapsed / total) * 100))
