"""
╔══════════════════════════════════════════════════════════╗
║   POLYMARKET BTC STRATEGY BOT — MARKET FINDER v2       ║
╚══════════════════════════════════════════════════════════╝
Finds and manages BTC UP/DOWN 15-minute markets on Polymarket
using the Gamma API. Updated with correct token parsing.
"""

import time
import math
import json
import requests
from dataclasses import dataclass
from typing import Optional
from config import GAMMA_API, CLOB_HOST


@dataclass
class BTCMarket:
    """A Polymarket BTC 15-minute UP/DOWN market."""
    condition_id: str
    question: str
    slug: str
    token_id_up: str        # "Up" outcome token
    token_id_down: str      # "Down" outcome token
    price_up: float         # Current price of UP
    price_down: float       # Current price of DOWN
    end_time: float         # Epoch seconds when market resolves
    active: bool
    accepting_orders: bool
    order_min_size: int     # Minimum shares per order
    liquidity: float

    @property
    def minutes_until_close(self) -> float:
        return max(0, (self.end_time - time.time()) / 60)

    @property
    def is_tradeable(self) -> bool:
        return self.active and self.accepting_orders and not self.is_expired

    @property
    def is_expired(self) -> bool:
        return time.time() > self.end_time


class MarketFinder:
    """Finds BTC 15-minute UP/DOWN markets on Polymarket."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._cache: Optional[BTCMarket] = None
        self._cache_time: float = 0
        self._cache_ttl: float = 30  # Cache for 30 seconds

    def _get_15m_boundaries(self) -> list[int]:
        """Get epoch timestamps for 15-minute boundaries."""
        now = time.time()
        interval = 15 * 60
        current = math.floor(now / interval) * interval
        # Return: prev, current, next, next+1
        return [
            current - interval,
            current,
            current + interval,
            current + interval * 2,
        ]

    def _parse_market(self, data: dict) -> Optional[BTCMarket]:
        """Parse a Gamma API market response into BTCMarket."""
        try:
            # Parse clobTokenIds — it's a JSON string like '["id1", "id2"]'
            clob_ids_raw = data.get("clobTokenIds", "[]")
            if isinstance(clob_ids_raw, str):
                clob_ids = json.loads(clob_ids_raw)
            else:
                clob_ids = clob_ids_raw

            if len(clob_ids) < 2:
                return None

            # Parse outcomes — '["Up", "Down"]'
            outcomes_raw = data.get("outcomes", '["Up", "Down"]')
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw

            # Map outcomes to token IDs
            token_id_up = ""
            token_id_down = ""
            for i, outcome in enumerate(outcomes):
                if i >= len(clob_ids):
                    break
                if outcome.lower() in ("up", "yes"):
                    token_id_up = clob_ids[i]
                elif outcome.lower() in ("down", "no"):
                    token_id_down = clob_ids[i]

            if not token_id_up or not token_id_down:
                return None

            # Parse outcome prices — '["0.515", "0.485"]'
            prices_raw = data.get("outcomePrices", '["0.5", "0.5"]')
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw

            price_up = float(prices[0]) if len(prices) > 0 else 0.5
            price_down = float(prices[1]) if len(prices) > 1 else 0.5

            # Parse end date
            end_date_str = data.get("endDate", "")
            end_time = 0.0
            if end_date_str:
                from datetime import datetime, timezone
                try:
                    dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    end_time = dt.timestamp()
                except Exception:
                    pass

            # Fallback: extract from slug
            if end_time == 0.0:
                slug = data.get("slug", "")
                parts = slug.split("-")
                for p in parts:
                    if p.isdigit() and len(p) >= 10:
                        end_time = float(p) + 900
                        break

            return BTCMarket(
                condition_id=data.get("conditionId", ""),
                question=data.get("question", "BTC UP/DOWN"),
                slug=data.get("slug", ""),
                token_id_up=token_id_up,
                token_id_down=token_id_down,
                price_up=price_up,
                price_down=price_down,
                end_time=end_time,
                active=data.get("active", False),
                accepting_orders=data.get("acceptingOrders", False),
                order_min_size=data.get("orderMinSize", 5),
                liquidity=float(data.get("liquidityNum", 0)),
            )
        except Exception:
            return None

    def find_current_market(self) -> Optional[BTCMarket]:
        """Find the current active BTC 15-minute UP/DOWN market."""
        # Return cache if fresh
        if self._cache and (time.time() - self._cache_time) < self._cache_ttl:
            if self._cache.is_tradeable:
                return self._cache

        boundaries = self._get_15m_boundaries()
        best_market = None
        now = time.time()

        for epoch in boundaries:
            slug = f"btc-updown-15m-{int(epoch)}"
            try:
                resp = self.session.get(
                    f"{GAMMA_API}/markets/slug/{slug}",
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue

                text = resp.text.strip()
                if text == "null" or not text:
                    continue

                data = resp.json()
                market = self._parse_market(data)

                if market and market.is_tradeable and market.end_time > now:
                    # Prefer the market closest to expiry but still open
                    if best_market is None or market.end_time < best_market.end_time:
                        best_market = market

            except Exception:
                continue

        # Update cache
        if best_market:
            self._cache = best_market
            self._cache_time = time.time()

        return best_market

    def find_next_market(self) -> Optional[BTCMarket]:
        """Find the upcoming (next) BTC 15-minute market."""
        boundaries = self._get_15m_boundaries()
        now = time.time()

        for epoch in boundaries:
            if epoch <= now:
                continue
            slug = f"btc-updown-15m-{int(epoch)}"
            try:
                resp = self.session.get(
                    f"{GAMMA_API}/markets/slug/{slug}",
                    timeout=10,
                )
                if resp.status_code == 200:
                    text = resp.text.strip()
                    if text != "null" and text:
                        market = self._parse_market(resp.json())
                        if market:
                            return market
            except Exception:
                continue
        return None

    def get_live_price(self, token_id: str) -> Optional[float]:
        """Get live midpoint price from CLOB."""
        try:
            resp = self.session.get(
                f"{CLOB_HOST}/midpoint",
                params={"token_id": token_id},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                mid = data.get("mid")
                if mid:
                    return float(mid)
        except Exception:
            pass
        return None

    def refresh_market_prices(self, market: BTCMarket) -> BTCMarket:
        """Refresh live prices for a market."""
        up_price = self.get_live_price(market.token_id_up)
        down_price = self.get_live_price(market.token_id_down)

        if up_price is not None:
            market.price_up = up_price
        if down_price is not None:
            market.price_down = down_price

        return market
