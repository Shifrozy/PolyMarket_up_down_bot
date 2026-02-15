"""
╔══════════════════════════════════════════════════════╗
║   POLYMARKET BTC STRATEGY BOT — TRADE MANAGER       ║
╚══════════════════════════════════════════════════════╝
Handles trade execution, tracking, P&L, and progressive entries.
"""

import json
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

from config import (
    TRADE_AMOUNT, SHARE_PRICE, MAX_SLIPPAGE,
    PAPER_MODE, CLOB_HOST, CHAIN_ID,
    PRIVATE_KEY, FUNDER_ADDRESS, SIGNATURE_TYPE,
)
from redeem_manager import RedeemManager


class TradeDirection(Enum):
    UP = "UP"
    DOWN = "DOWN"


class TradeStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    WON = "WON"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class Trade:
    """A single trade record."""
    trade_id: str
    direction: TradeDirection
    token_id: str
    amount: float           # USDC spent
    share_price: float      # Price per share at entry
    shares: float           # Number of shares bought
    timestamp: float        # Epoch seconds
    candle_number: int      # Which candle in the sequence (1-5)
    status: TradeStatus = TradeStatus.PENDING
    pnl: float = 0.0       # Realized P&L
    result_price: float = 0.0  # Final share price at resolution
    order_id: str = ""      # Polymarket order ID

    @property
    def entry_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%H:%M:%S")

    @property
    def direction_emoji(self) -> str:
        return "🟢 UP" if self.direction == TradeDirection.UP else "🔴 DOWN"

    @property
    def status_emoji(self) -> str:
        status_map = {
            TradeStatus.PENDING: "⏳",
            TradeStatus.OPEN: "📊",
            TradeStatus.WON: "✅",
            TradeStatus.LOST: "❌",
            TradeStatus.EXPIRED: "⏰",
            TradeStatus.CANCELLED: "🚫",
        }
        return status_map.get(self.status, "❓")

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "direction": self.direction.value,
            "token_id": self.token_id,
            "amount": self.amount,
            "share_price": self.share_price,
            "shares": self.shares,
            "timestamp": self.timestamp,
            "candle_number": self.candle_number,
            "status": self.status.value,
            "pnl": self.pnl,
            "result_price": self.result_price,
            "order_id": self.order_id,
        }


class TradeManager:
    """Manages trade execution and tracking."""

    def __init__(self):
        self.trades: list[Trade] = []
        self.current_trade: Optional[Trade] = None
        self._client = None
        self._client_initialized = False
        self._redeem_manager = None
        self._trade_log_file = "trade_history.json"
        self._last_error = ""
        self._load_history()

    def _init_client(self):
        """Initialize the Polymarket CLOB client (lazy)."""
        if self._client_initialized:
            return
        if PAPER_MODE:
            self._client_initialized = True
            return
        try:
            from py_clob_client.client import ClobClient
            self._client = ClobClient(
                CLOB_HOST,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                signature_type=SIGNATURE_TYPE,
                funder=FUNDER_ADDRESS,
            )
            # Derive or create API credentials for this wallet
            try:
                creds = self._client.create_or_derive_api_creds()
                self._client.set_api_creds(creds)
            except Exception as cred_err:
                err_str = str(cred_err).lower()
                if "400" in err_str or "not found" in err_str or "invalid" in err_str:
                    raise ConnectionError(
                        f"API key error for wallet {FUNDER_ADDRESS}.\n"
                        f"This wallet may not be registered on Polymarket.\n"
                        f"Fix: 1) Open https://polymarket.com and connect this wallet\n"
                        f"     2) Accept terms and deposit any amount\n"
                        f"     3) Run: python setup_allowances.py\n"
                        f"     4) Then restart the bot\n"
                        f"Original error: {cred_err}"
                    )
                raise

            self._client_initialized = True
            
            # Initialize RedeemManager
            self._redeem_manager = RedeemManager(
                client=self._client,
                private_key=PRIVATE_KEY,
                wallet_address=FUNDER_ADDRESS
            )
        except ConnectionError:
            raise  # Re-raise our detailed error
        except Exception as e:
            err_str = str(e).lower()
            if "400" in err_str:
                raise ConnectionError(
                    f"HTTP 400 from Polymarket API.\n"
                    f"Wallet: {FUNDER_ADDRESS}\n"
                    f"This wallet needs setup:\n"
                    f"  1) Connect wallet at https://polymarket.com\n"
                    f"  2) Accept terms & deposit USDC\n"
                    f"  3) Run: python setup_allowances.py\n"
                    f"  4) Restart bot\n"
                    f"Error: {e}"
                )
            raise ConnectionError(f"Failed to initialize CLOB client: {e}")

    def place_trade(
        self,
        direction: TradeDirection,
        token_id: str,
        candle_number: int,
        current_price: float,
    ) -> Optional[Trade]:
        """
        Place a trade on Polymarket.
        
        Args:
            direction: UP or DOWN
            token_id: The token ID to buy (UP or DOWN token)
            candle_number: Which candle in the sequence (for tracking)
            current_price: Current market price of the token
        
        Returns:
            Trade object if successful, None otherwise
        """
        self._init_client()

        # Price check — Polymarket binary markets price UP+DOWN = $1.00
        # So UP at $0.54 means DOWN is $0.46. Both are valid prices.
        # We reject ONLY if price is extremely unfavorable (above max allowed)
        target_price = SHARE_PRICE  # $0.50
        max_price = target_price + MAX_SLIPPAGE  # e.g. $0.50 + $0.10 = $0.60 max

        if current_price > max_price:
            self._last_error = f"Price {current_price:.3f} > max {max_price:.3f}"
            return None  # Price too high, skip

        # Use the actual market price for the order
        order_price = round(current_price, 2)
        if order_price < 0.01:
            order_price = 0.01

        # Calculate shares based on trade amount and actual price
        shares = TRADE_AMOUNT / order_price
        if shares < 5:
            shares = 5  # Polymarket enforces orderMinSize=5

        actual_cost = shares * order_price

        trade_id = f"T{int(time.time()*1000)}"
        order_id = ""

        if PAPER_MODE:
            # Simulate trade
            order_id = f"PAPER-{trade_id}"
        else:
            try:
                from py_clob_client.clob_types import OrderArgs
                from py_clob_client.order_builder.constants import BUY

                # Use market price + 1 cent for fast fill, capped at max allowed
                limit_price = round(order_price + 0.01, 2)
                limit_price = min(limit_price, round(max_price, 2))

                order_args = OrderArgs(
                    token_id=token_id,
                    price=limit_price,
                    size=shares,
                    side=BUY,
                )

                signed = self._client.create_order(order_args)
                resp = self._client.post_order(signed)

                if isinstance(resp, dict):
                    order_id = resp.get("orderID", resp.get("id", ""))
                    if resp.get("status") == "matched":
                        order_id = order_id or "MATCHED"
                else:
                    order_id = str(resp)

                if not order_id:
                    self._last_error = f"Empty order response: {resp}"
                    return None

            except Exception as e:
                # Capture full error details
                err_msg = str(e)
                if hasattr(e, 'error_message'):
                    err_msg = f"{e.error_message}"
                if hasattr(e, 'status_code'):
                    err_msg = f"HTTP {e.status_code}: {err_msg}"
                self._last_error = f"Order error: {err_msg}"
                return None

        trade = Trade(
            trade_id=trade_id,
            direction=direction,
            token_id=token_id,
            amount=actual_cost,
            share_price=target_price,
            shares=shares,
            timestamp=time.time(),
            candle_number=candle_number,
            status=TradeStatus.OPEN,
            order_id=order_id,
        )

        self.trades.append(trade)
        self.current_trade = trade
        self._save_history()
        return trade

    def resolve_trade(self, trade: Trade, won: bool):
        """Resolve a trade as won or lost."""
        if won:
            trade.status = TradeStatus.WON
            trade.result_price = 1.0  # Won shares pay $1
            trade.pnl = (trade.result_price * trade.shares) - trade.amount
        else:
            trade.status = TradeStatus.LOST
            trade.result_price = 0.0  # Lost shares worth $0
            trade.pnl = -trade.amount

        if self.current_trade and self.current_trade.trade_id == trade.trade_id:
            self.current_trade = None

        self._save_history()

    def has_open_trade(self) -> bool:
        """Check if there's already an open/pending trade."""
        return self.current_trade is not None and \
               self.current_trade.status in (TradeStatus.OPEN, TradeStatus.PENDING)

    def cancel_current_trade(self):
        """Cancel the current trade if it exists."""
        if self.current_trade:
            self.current_trade.status = TradeStatus.CANCELLED
            self.current_trade.pnl = 0.0
            self.current_trade = None
            self._save_history()

    # ── Statistics ──────────────────────────────────

    @property
    def total_trades(self) -> int:
        return len([t for t in self.trades if t.status in (TradeStatus.WON, TradeStatus.LOST)])

    @property
    def wins(self) -> int:
        return len([t for t in self.trades if t.status == TradeStatus.WON])

    @property
    def losses(self) -> int:
        return len([t for t in self.trades if t.status == TradeStatus.LOST])

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.wins / self.total_trades) * 100

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def total_volume(self) -> float:
        return sum(t.amount for t in self.trades if t.status in (TradeStatus.WON, TradeStatus.LOST))

    @property
    def open_trades(self) -> list[Trade]:
        return [t for t in self.trades if t.status == TradeStatus.OPEN]

    @property
    def recent_trades(self) -> list[Trade]:
        """Last 10 resolved trades."""
        resolved = [t for t in self.trades if t.status in (TradeStatus.WON, TradeStatus.LOST)]
        return resolved[-10:]

    # ── Persistence ─────────────────────────────────

    def _save_history(self):
        """Save trade history to JSON file."""
        try:
            data = {
                "trades": [t.to_dict() for t in self.trades],
                "last_updated": time.time(),
            }
            with open(self._trade_log_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_history(self):
        """Load trade history from JSON file."""
        try:
            if os.path.exists(self._trade_log_file):
                with open(self._trade_log_file, "r") as f:
                    data = json.load(f)
                for td in data.get("trades", []):
                    trade = Trade(
                        trade_id=td["trade_id"],
                        direction=TradeDirection(td["direction"]),
                        token_id=td["token_id"],
                        amount=td["amount"],
                        share_price=td["share_price"],
                        shares=td["shares"],
                        timestamp=td["timestamp"],
                        candle_number=td["candle_number"],
                        status=TradeStatus(td["status"]),
                        pnl=td.get("pnl", 0.0),
                        result_price=td.get("result_price", 0.0),
                        order_id=td.get("order_id", ""),
                    )
                    self.trades.append(trade)
        except Exception:
            pass

    def get_pnl_summary(self) -> str:
        """Returns a string summarizing the P&L."""
        return f"Total P&L: {'📈' if self.total_pnl >= 0 else '📉'} ${self.total_pnl:+.2f}"

    def redeem_winnings(self) -> int:
        """Automated redemption of winning positions in live mode."""
        if PAPER_MODE:
            return 0
        
        self._init_client()
        if self._redeem_manager:
            return self._redeem_manager.auto_redeem()
        return 0

