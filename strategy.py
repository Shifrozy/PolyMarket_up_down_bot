"""
╔══════════════════════════════════════════════════════╗
║   POLYMARKET BTC STRATEGY BOT — STRATEGY ENGINE     ║
╚══════════════════════════════════════════════════════╝
Implements the contrarian 2-candle strategy with progressive entries.

Strategy Rules:
  1. Two green 15-min candles → BUY DOWN (contrarian)
  2. Two red 15-min candles   → BUY UP   (contrarian)
  3. Progressive entries:
     - After signal (2 same-color candles), bot trades the 3rd candle
     - If 3rd candle trade LOSES → bot trades 4th candle (same direction)
     - If 4th candle trade LOSES → bot trades 5th candle (same direction)
     - After 5th candle trade   → 30-min cooldown regardless of result
  4. If 3rd candle trade WINS → bot resets and looks for new 2-candle signal
  5. $1 trade at $0.50/share with 0.02% max slippage
  6. Bot skips trade if it can't get the right price within 5 minutes
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable
from enum import Enum

from candle_feed import Candle, CandleFeed
from trade_manager import TradeManager, Trade, TradeDirection, TradeStatus
from market_finder import MarketFinder, BTCMarket
from config import (
    CONSECUTIVE_CANDLES_SIGNAL,
    MAX_PROGRESSIVE_ENTRIES,
    PROGRESSIVE_START,
    COOLDOWN_MINUTES,
    MAX_ENTRY_WAIT_MINUTES,
    SHARE_PRICE,
)


class BotState(Enum):
    SCANNING = "SCANNING"                # Watching candles for a signal
    SIGNAL_DETECTED = "SIGNAL_DETECTED"  # 2 same-color candles detected
    WAITING_ENTRY = "WAITING_ENTRY"      # Waiting for right price to enter
    IN_TRADE = "IN_TRADE"                # Active trade open
    PROGRESSIVE = "PROGRESSIVE"          # In progressive entry sequence
    COOLDOWN = "COOLDOWN"                # 30-min cooldown after 5th candle


@dataclass
class StrategyState:
    """Tracks the current strategy state."""
    bot_state: BotState = BotState.SCANNING
    signal_direction: Optional[TradeDirection] = None   # UP or DOWN
    signal_candle_color: Optional[str] = None           # Color that triggered signal
    consecutive_count: int = 0                          # Same-color candle count
    current_candle_number: int = 0                      # 1-based candle in sequence
    progressive_entry: int = 0                          # Which progressive entry (3, 4, 5)
    cooldown_until: float = 0.0                         # Epoch when cooldown ends
    entry_wait_start: float = 0.0                       # When we started waiting for price
    last_signal_time: float = 0.0
    last_processed_candle_time: float = 0.0             # Avoid reprocessing
    total_signals: int = 0
    skipped_signals: int = 0

    @property
    def is_cooldown_active(self) -> bool:
        return self.bot_state == BotState.COOLDOWN and time.time() < self.cooldown_until

    @property
    def cooldown_remaining_sec(self) -> float:
        if not self.is_cooldown_active:
            return 0.0
        return max(0, self.cooldown_until - time.time())

    @property
    def entry_wait_elapsed_sec(self) -> float:
        if self.entry_wait_start == 0:
            return 0.0
        return time.time() - self.entry_wait_start


class StrategyEngine:
    """
    The core strategy engine.
    Processes candle data and generates trade signals.
    """

    def __init__(
        self,
        candle_feed: CandleFeed,
        trade_manager: TradeManager,
        market_finder: MarketFinder,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        self.feed = candle_feed
        self.trader = trade_manager
        self.market = market_finder
        self.state = StrategyState()
        self._log = on_log or (lambda msg: None)
        self._current_market: Optional[BTCMarket] = None

    def process_tick(self):
        """
        Called every few seconds. Drives the strategy FSM.
        """
        # 1. Refresh candle data
        try:
            self.feed.fetch_recent(limit=10)
        except Exception as e:
            self._log(f"⚠ Candle fetch error: {e}")
            return

        # 2. Check cooldown
        if self.state.is_cooldown_active:
            return  # Still cooling down

        if self.state.bot_state == BotState.COOLDOWN and not self.state.is_cooldown_active:
            self._log("✅ Cooldown ended — resuming scanning")
            self._reset_state()

        # 3. Check for new closed candle
        closed = self.feed.get_closed_candles()
        if not closed:
            return

        latest_closed = closed[-1]

        # Avoid reprocessing the same candle
        if latest_closed.close_time <= self.state.last_processed_candle_time:
            # Still same candle — if waiting for entry, RETRY trade on every tick
            if self.state.bot_state == BotState.WAITING_ENTRY:
                if self._check_entry_timeout():
                    return  # Timed out, reset already done
                # Retry the trade — price may have changed
                self._attempt_trade()
            return

        # New candle closed!
        self.state.last_processed_candle_time = latest_closed.close_time
        self._log(f"🕯 Candle closed: {latest_closed}")

        # 4. State machine
        if self.state.bot_state == BotState.SCANNING:
            self._handle_scanning(closed)

        elif self.state.bot_state == BotState.SIGNAL_DETECTED:
            self._handle_signal(closed)

        elif self.state.bot_state == BotState.IN_TRADE:
            self._handle_trade_result(latest_closed)

        elif self.state.bot_state == BotState.PROGRESSIVE:
            self._handle_trade_result(latest_closed)

        elif self.state.bot_state == BotState.WAITING_ENTRY:
            # New candle closed while still waiting — retry one more time
            if not self._check_entry_timeout():
                self._attempt_trade()

    def _handle_scanning(self, closed: list[Candle]):
        """Look for 2 consecutive same-color candles."""
        if len(closed) < CONSECUTIVE_CANDLES_SIGNAL:
            return

        last_n = closed[-CONSECUTIVE_CANDLES_SIGNAL:]
        colors = [c.color for c in last_n]

        if all(c == "red" for c in colors):
            # 2 red candles → BUY UP (contrarian)
            self._log("🔴🔴 2 RED candles detected → Signal: BUY UP")
            self.state.signal_direction = TradeDirection.UP
            self.state.signal_candle_color = "red"
            self.state.consecutive_count = CONSECUTIVE_CANDLES_SIGNAL
            self.state.current_candle_number = CONSECUTIVE_CANDLES_SIGNAL
            self.state.bot_state = BotState.SIGNAL_DETECTED
            self.state.total_signals += 1
            self.state.last_signal_time = time.time()
            self._attempt_trade()

        elif all(c == "green" for c in colors):
            # 2 green candles → BUY DOWN (contrarian)
            self._log("🟢🟢 2 GREEN candles detected → Signal: BUY DOWN")
            self.state.signal_direction = TradeDirection.DOWN
            self.state.signal_candle_color = "green"
            self.state.consecutive_count = CONSECUTIVE_CANDLES_SIGNAL
            self.state.current_candle_number = CONSECUTIVE_CANDLES_SIGNAL
            self.state.bot_state = BotState.SIGNAL_DETECTED
            self.state.total_signals += 1
            self.state.last_signal_time = time.time()
            self._attempt_trade()

    def _handle_signal(self, closed: list[Candle]):
        """Signal was detected — waiting for entry or processing."""
        self._attempt_trade()

    def _attempt_trade(self):
        """Try to place a trade based on current signal."""
        if self.trader.has_open_trade():
            self._log("⚠ Trade already open — skipping overlap")
            return

        direction = self.state.signal_direction
        if not direction:
            return

        # Find the current Polymarket market
        self._current_market = self.market.find_current_market()

        if self._current_market:
            # Refresh live prices from CLOB
            self._current_market = self.market.refresh_market_prices(self._current_market)

            # Determine which token to buy
            if direction == TradeDirection.UP:
                token_id = self._current_market.token_id_up
                current_price = self._current_market.price_up
            else:
                token_id = self._current_market.token_id_down
                current_price = self._current_market.price_down

            candle_num = self.state.current_candle_number + 1  # Trading the NEXT candle

            self._log(
                f"📈 Attempting {direction.value} trade "
                f"(candle #{candle_num}) @ ${current_price:.4f}/share | "
                f"Market: {self._current_market.question[:50]}"
            )

            trade = self.trader.place_trade(
                direction=direction,
                token_id=token_id,
                candle_number=candle_num,
                current_price=current_price,
            )

            if trade:
                self._log(
                    f"✅ LIVE trade placed: {trade.direction_emoji} | "
                    f"${trade.amount:.2f} | {trade.shares:.1f} shares | "
                    f"Order: {trade.order_id[:20]}..."
                )
                self.state.bot_state = BotState.IN_TRADE
                self.state.entry_wait_start = 0
            else:
                # Trade failed — show why
                err = self.trader._last_error or "Price not right"
                self._log(f"⏳ Trade not placed: {err}")
                self.state.bot_state = BotState.WAITING_ENTRY
                if self.state.entry_wait_start == 0:
                    self.state.entry_wait_start = time.time()
                self._check_entry_timeout()
        else:
            # No market found — use paper simulation
            self._log("📋 No Polymarket market found — using paper simulation")
            candle_num = self.state.current_candle_number + 1

            trade = self.trader.place_trade(
                direction=direction,
                token_id=f"PAPER-{direction.value}-{int(time.time())}",
                candle_number=candle_num,
                current_price=SHARE_PRICE,
            )

            if trade:
                self._log(
                    f"📝 Paper trade: {trade.direction_emoji} | "
                    f"${trade.amount:.2f} | Candle #{candle_num}"
                )
                self.state.bot_state = BotState.IN_TRADE

    def _check_entry_timeout(self) -> bool:
        """Check if we've waited too long for the right price. Returns True if timed out."""
        if self.state.entry_wait_elapsed_sec > MAX_ENTRY_WAIT_MINUTES * 60:
            self._log(
                f"⏰ Entry timeout ({MAX_ENTRY_WAIT_MINUTES}min) — "
                f"skipping this signal"
            )
            self.state.skipped_signals += 1
            self._reset_state()
            return True
        return False

    def _handle_trade_result(self, latest_closed: Candle):
        """Check if the current trade won or lost based on candle close."""
        trade = self.trader.current_trade
        if not trade:
            self._reset_state()
            return

        # Determine win/loss:
        # If we bought UP → we WIN if candle closes GREEN (price went up)
        # If we bought DOWN → we WIN if candle closes RED (price went down)
        candle_color = latest_closed.color
        won = False

        if trade.direction == TradeDirection.UP:
            won = (candle_color == "green")
        else:  # DOWN
            won = (candle_color == "red")

        self.trader.resolve_trade(trade, won)

        if won:
            self._log(
                f"🎉 TRADE WON! {trade.direction_emoji} | "
                f"P&L: +${trade.pnl:.2f} | Candle #{trade.candle_number}"
            )
            # Win on any candle → reset and look for new signal
            self._reset_state()
        else:
            self._log(
                f"💔 TRADE LOST! {trade.direction_emoji} | "
                f"P&L: ${trade.pnl:.2f} | Candle #{trade.candle_number}"
            )
            # Check progressive entry logic
            self._handle_progressive_loss(trade)

    def _handle_progressive_loss(self, trade: Trade):
        """Handle progressive entries after a loss."""
        candle_num = trade.candle_number

        if candle_num < MAX_PROGRESSIVE_ENTRIES:
            # Can still do progressive entry
            self.state.current_candle_number = candle_num
            self.state.bot_state = BotState.PROGRESSIVE
            self.state.progressive_entry = candle_num + 1

            self._log(
                f"📊 Progressive entry → will trade candle "
                f"#{self.state.progressive_entry}"
            )
            # Immediately attempt next trade
            self._attempt_trade()
        else:
            # Reached candle 5 (max) → cooldown
            self.state.cooldown_until = time.time() + (COOLDOWN_MINUTES * 60)
            self.state.bot_state = BotState.COOLDOWN
            self._log(
                f"❄️ Max progressive entries reached (candle #{candle_num}) — "
                f"Cooldown for {COOLDOWN_MINUTES} minutes"
            )

    def _reset_state(self):
        """Reset to scanning mode."""
        self.state.bot_state = BotState.SCANNING
        self.state.signal_direction = None
        self.state.signal_candle_color = None
        self.state.consecutive_count = 0
        self.state.current_candle_number = 0
        self.state.progressive_entry = 0
        self.state.entry_wait_start = 0.0
