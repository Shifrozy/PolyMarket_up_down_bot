"""
╔══════════════════════════════════════════════════════╗
║   POLYMARKET BTC STRATEGY BOT — TERMINAL DASHBOARD  ║
╚══════════════════════════════════════════════════════╝
Clean, beautiful terminal dashboard using Rich.
"""

import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.live import Live
from rich.columns import Columns
from rich.align import Align
from rich import box

try:
    from web3 import Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False

from candle_feed import CandleFeed, Candle
from trade_manager import TradeManager, Trade, TradeStatus, TradeDirection
from strategy import StrategyEngine, BotState
from config import (
    TRADE_AMOUNT, SHARE_PRICE, MAX_SLIPPAGE,
    COOLDOWN_MINUTES, PAPER_MODE, MAX_ENTRY_WAIT_MINUTES,
    FUNDER_ADDRESS,
)


class Dashboard:
    """Rich terminal dashboard for the bot."""

    def __init__(
        self,
        engine: StrategyEngine,
        feed: CandleFeed,
        trader: TradeManager,
    ):
        self.engine = engine
        self.feed = feed
        self.trader = trader
        self.console = Console()
        self.log_lines: list[str] = []
        self.max_log_lines = 12
        self._start_time = time.time()

        # Wallet data cache (refreshed every 60s)
        self._wallet_cache = {
            "usdc": 0.0,
            "matic": 0.0,
            "positions": [],
            "last_fetch": 0,
        }
        self._wallet_lock = threading.Lock()
        self._WALLET_REFRESH_SEC = 60

    def add_log(self, message: str):
        """Add a log line to the activity feed."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"[dim]{ts}[/dim]  {message}")
        if len(self.log_lines) > self.max_log_lines:
            self.log_lines = self.log_lines[-self.max_log_lines:]

    def _build_header(self) -> Panel:
        """Build the header panel."""
        mode = "[bold red]🔴 PAPER MODE[/bold red]" if PAPER_MODE else "[bold green]🟢 LIVE TRADING[/bold green]"
        uptime = time.time() - self._start_time
        h, remainder = divmod(int(uptime), 3600)
        m, s = divmod(remainder, 60)

        header_text = Text()
        header_text.append("  ₿  POLYMARKET BTC STRATEGY BOT  ", style="bold white on blue")
        header_text.append(f"  {mode}  ", style="")
        header_text.append(f"  ⏱ {h:02d}:{m:02d}:{s:02d}", style="dim")

        return Panel(
            Align.center(header_text),
            box=box.DOUBLE,
            style="bright_blue",
            height=3,
        )

    def _build_btc_panel(self) -> Panel:
        """Build the BTC price & candle panel."""
        btc_price = self.feed.get_btc_price()
        progress = self.feed.candle_progress_pct()
        remaining = self.feed.seconds_until_candle_close()
        remaining_min = int(remaining // 60)
        remaining_sec = int(remaining % 60)

        current = self.feed.get_current_candle()
        current_color = current.color if current else "—"
        current_change = f"{current.change_pct:+.2f}%" if current else "—"

        # Progress bar
        bar_len = 20
        filled = int(bar_len * progress / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        bar_color = "green" if current_color == "green" else "red" if current_color == "red" else "white"

        lines = [
            f"[bold yellow]BTC Price:[/bold yellow]  [bold white]${btc_price:,.2f}[/bold white]",
            f"[bold]Current Candle:[/bold]  [{bar_color}]{current_color.upper()}[/{bar_color}]  {current_change}",
            f"[bold]Progress:[/bold]      [{bar_color}]{bar}[/{bar_color}] {progress:.0f}%",
            f"[bold]Closes in:[/bold]     {remaining_min}m {remaining_sec}s",
        ]

        return Panel(
            "\n".join(lines),
            title="[bold yellow]₿ BTC Market[/bold yellow]",
            border_style="yellow",
            height=8,
        )

    def _build_candle_history(self) -> Panel:
        """Build recent candle history panel."""
        closed = self.feed.get_closed_candles()[-6:]

        table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
        table.add_column("Time", style="dim", width=12)
        table.add_column("Open", justify="right", width=10)
        table.add_column("Close", justify="right", width=10)
        table.add_column("Change", justify="right", width=8)
        table.add_column("Color", justify="center", width=6)

        for c in closed:
            color = "green" if c.color == "green" else "red"
            icon = "🟢" if c.color == "green" else "🔴"
            table.add_row(
                c.open_dt.strftime("%H:%M"),
                f"${c.open_price:,.0f}",
                f"${c.close_price:,.0f}",
                f"[{color}]{c.change_pct:+.2f}%[/{color}]",
                icon,
            )

        return Panel(
            table,
            title="[bold cyan]🕯 Recent Candles[/bold cyan]",
            border_style="cyan",
        )

    def _build_strategy_panel(self) -> Panel:
        """Build the strategy status panel."""
        state = self.engine.state
        state_colors = {
            BotState.SCANNING: ("🔍", "white"),
            BotState.SIGNAL_DETECTED: ("🎯", "yellow"),
            BotState.WAITING_ENTRY: ("⏳", "yellow"),
            BotState.IN_TRADE: ("📊", "green"),
            BotState.PROGRESSIVE: ("📈", "magenta"),
            BotState.COOLDOWN: ("❄️", "blue"),
        }
        icon, color = state_colors.get(state.bot_state, ("❓", "white"))

        lines = [
            f"[bold]State:[/bold]          [{color}]{icon} {state.bot_state.value}[/{color}]",
        ]

        if state.signal_direction:
            dir_color = "green" if state.signal_direction == TradeDirection.UP else "red"
            lines.append(
                f"[bold]Signal:[/bold]         [{dir_color}]{state.signal_direction.value}[/{dir_color}]"
            )

        if state.consecutive_count > 0:
            lines.append(f"[bold]Consec. Candles:[/bold] {state.consecutive_count}")

        if state.progressive_entry > 0:
            lines.append(f"[bold]Progressive #:[/bold]  {state.progressive_entry}/5")

        if state.is_cooldown_active:
            cd_sec = state.cooldown_remaining_sec
            cd_min = int(cd_sec // 60)
            cd_s = int(cd_sec % 60)
            lines.append(f"[bold]Cooldown:[/bold]       [blue]{cd_min}m {cd_s}s remaining[/blue]")

        if state.bot_state == BotState.WAITING_ENTRY:
            wait = state.entry_wait_elapsed_sec
            lines.append(f"[bold]Waiting:[/bold]        {int(wait)}s / {MAX_ENTRY_WAIT_MINUTES * 60}s")

        lines.append(f"\n[bold]Total Signals:[/bold]  {state.total_signals}")
        lines.append(f"[bold]Skipped:[/bold]        {state.skipped_signals}")

        return Panel(
            "\n".join(lines),
            title="[bold magenta]🧠 Strategy[/bold magenta]",
            border_style="magenta",
            height=12,
        )

    def _build_pnl_panel(self) -> Panel:
        """Build the P&L and statistics panel."""
        pnl = self.trader.total_pnl
        pnl_color = "green" if pnl >= 0 else "red"
        pnl_icon = "📈" if pnl >= 0 else "📉"

        wr = self.trader.win_rate
        wr_color = "green" if wr >= 50 else "yellow" if wr >= 30 else "red"

        lines = [
            f"[bold]Total P&L:[/bold]    [{pnl_color}]{pnl_icon} ${pnl:+.2f}[/{pnl_color}]",
            f"[bold]Total Trades:[/bold] {self.trader.total_trades}",
            f"[bold]Win Rate:[/bold]     [{wr_color}]{wr:.1f}%[/{wr_color}]",
            f"[bold]Wins:[/bold]         [green]{self.trader.wins}[/green]",
            f"[bold]Losses:[/bold]       [red]{self.trader.losses}[/red]",
            f"[bold]Volume:[/bold]       ${self.trader.total_volume:.2f}",
        ]

        # Current open trade
        if self.trader.current_trade:
            t = self.trader.current_trade
            dir_color = "green" if t.direction == TradeDirection.UP else "red"
            lines.append(f"\n[bold]Open Trade:[/bold]  [{dir_color}]{t.direction_emoji}[/{dir_color}]")
            lines.append(f"[bold]Amount:[/bold]      ${t.amount:.2f}")
            lines.append(f"[bold]Candle #:[/bold]    {t.candle_number}")
        else:
            lines.append(f"\n[dim]No open trade[/dim]")

        return Panel(
            "\n".join(lines),
            title="[bold green]💰 Performance[/bold green]",
            border_style="green",
        )

    def _build_trade_history(self) -> Panel:
        """Build recent trade history table."""
        table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Time", width=8)
        table.add_column("Dir", width=6)
        table.add_column("Candle", justify="center", width=6)
        table.add_column("Amount", justify="right", width=7)
        table.add_column("P&L", justify="right", width=8)
        table.add_column("Status", justify="center", width=4)

        for i, t in enumerate(self.trader.recent_trades, 1):
            pnl_color = "green" if t.pnl >= 0 else "red"
            dir_icon = "🟢" if t.direction == TradeDirection.UP else "🔴"
            table.add_row(
                str(i),
                t.entry_time,
                dir_icon,
                str(t.candle_number),
                f"${t.amount:.2f}",
                f"[{pnl_color}]${t.pnl:+.2f}[/{pnl_color}]",
                t.status_emoji,
            )

        return Panel(
            table,
            title="[bold]📜 Trade History (Last 10)[/bold]",
            border_style="white",
        )

    def _build_activity_log(self) -> Panel:
        """Build the activity log panel."""
        if not self.log_lines:
            content = "[dim]Waiting for activity...[/dim]"
        else:
            content = "\n".join(self.log_lines)

        return Panel(
            content,
            title="[bold]📋 Activity Log[/bold]",
            border_style="bright_black",
        )

    def _fetch_wallet_data(self):
        """Fetch wallet balance and positions (cached, refreshes every 60s)."""
        now = time.time()
        if now - self._wallet_cache["last_fetch"] < self._WALLET_REFRESH_SEC:
            return  # Use cached data

        try:
            if HAS_WEB3 and FUNDER_ADDRESS and not PAPER_MODE:
                w3 = Web3(Web3.HTTPProvider("https://polygon-bor-rpc.publicnode.com"))
                wallet = Web3.to_checksum_address(FUNDER_ADDRESS)

                # USDC.e balance
                usdc_abi = [{"constant":True,"inputs":[{"name":"","type":"address"}],
                    "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],
                    "stateMutability":"view","type":"function"}]
                usdc = w3.eth.contract(
                    address=Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"),
                    abi=usdc_abi
                )
                usdc_bal = usdc.functions.balanceOf(wallet).call() / 1e6

                # MATIC balance
                matic_bal = w3.eth.get_balance(wallet) / 1e18

                with self._wallet_lock:
                    self._wallet_cache["usdc"] = usdc_bal
                    self._wallet_cache["matic"] = matic_bal

                # Positions from data-api
                try:
                    r = requests.get(
                        f"https://data-api.polymarket.com/positions?user={FUNDER_ADDRESS.lower()}",
                        timeout=8
                    )
                    if r.status_code == 200:
                        with self._wallet_lock:
                            self._wallet_cache["positions"] = r.json()
                except Exception:
                    pass

            with self._wallet_lock:
                self._wallet_cache["last_fetch"] = now

        except Exception:
            with self._wallet_lock:
                self._wallet_cache["last_fetch"] = now  # Avoid hammering on error

    def _build_wallet_panel(self) -> Panel:
        """Build the wallet balance and positions panel."""
        self._fetch_wallet_data()

        with self._wallet_lock:
            usdc = self._wallet_cache["usdc"]
            matic = self._wallet_cache["matic"]
            positions = self._wallet_cache["positions"]

        if PAPER_MODE:
            lines = [
                "[dim]Wallet info not available in Paper Mode[/dim]",
            ]
            return Panel(
                "\n".join(lines),
                title="[bold bright_cyan]👛 Wallet[/bold bright_cyan]",
                border_style="bright_cyan",
                height=6,
            )

        # Wallet address (truncated)
        addr = FUNDER_ADDRESS
        short_addr = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr

        # Calculate total position value
        total_value = sum(float(p.get("currentValue", 0)) for p in positions)
        total_cost = sum(float(p.get("initialValue", 0)) for p in positions)
        total_pnl = total_value - total_cost
        pnl_color = "green" if total_pnl >= 0 else "red"

        lines = [
            f"[bold]Wallet:[/bold]      [dim]{short_addr}[/dim]",
            f"[bold]USDC.e:[/bold]      [bold white]${usdc:.2f}[/bold white]",
            f"[bold]MATIC:[/bold]       [dim]{matic:.4f}[/dim]",
        ]

        if positions:
            lines.append(f"")
            lines.append(f"[bold]Positions:[/bold]   {len(positions)} active")
            lines.append(f"[bold]Holdings:[/bold]    [bold white]${total_value:.2f}[/bold white]")
            lines.append(f"[bold]Pos. PnL:[/bold]    [{pnl_color}]${total_pnl:+.2f}[/{pnl_color}]")
            lines.append(f"[bold]Total Equity:[/bold][bold yellow] ${usdc + total_value:.2f}[/bold yellow]")
        else:
            lines.append(f"")
            lines.append(f"[dim]No active positions[/dim]")

        height = max(8, 5 + len(positions) * 3)

        return Panel(
            "\n".join(lines),
            title="[bold bright_cyan]👛 Wallet & Holdings[/bold bright_cyan]",
            border_style="bright_cyan",
        )

    def _build_positions_table(self) -> Panel:
        """Build the active positions table."""
        with self._wallet_lock:
            positions = self._wallet_cache["positions"]

        table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold bright_cyan")
        table.add_column("Market", width=30, no_wrap=True)
        table.add_column("Side", justify="center", width=5)
        table.add_column("Shares", justify="right", width=7)
        table.add_column("Avg $", justify="right", width=6)
        table.add_column("Value", justify="right", width=7)
        table.add_column("PnL", justify="right", width=8)
        table.add_column("Status", justify="center", width=8)

        if not positions:
            table.add_row("[dim]No positions[/dim]", "", "", "", "", "", "")
        else:
            for p in positions:
                title = p.get("title", "Unknown")
                # Truncate long titles
                if len(title) > 28:
                    title = title[:25] + "..."

                outcome = p.get("outcome", "?")
                side_color = "green" if outcome == "Up" else "red" if outcome == "Down" else "white"
                side_icon = "▲" if outcome == "Up" else "▼" if outcome == "Down" else "?"

                size = float(p.get("size", 0))
                avg_price = float(p.get("avgPrice", 0))
                cur_value = float(p.get("currentValue", 0))
                cash_pnl = float(p.get("cashPnl", 0))
                pct_pnl = float(p.get("percentPnl", 0))
                redeemable = p.get("redeemable", False)
                cur_price = float(p.get("curPrice", 0))

                pnl_color = "green" if cash_pnl >= 0 else "red"

                if redeemable and cur_price >= 0.95:
                    status = "[bold green]WIN ✅[/bold green]"
                elif redeemable and cur_price <= 0.05:
                    status = "[bold red]LOSS ❌[/bold red]"
                elif redeemable:
                    status = "[yellow]CLAIM[/yellow]"
                else:
                    status = "[dim]ACTIVE[/dim]"

                table.add_row(
                    title,
                    f"[{side_color}]{side_icon}[/{side_color}]",
                    f"{size:.0f}",
                    f"${avg_price:.2f}",
                    f"${cur_value:.2f}",
                    f"[{pnl_color}]${cash_pnl:+.2f}[/{pnl_color}]",
                    status,
                )

        return Panel(
            table,
            title="[bold bright_cyan]📊 Active Positions[/bold bright_cyan]",
            border_style="bright_cyan",
        )

    def _build_config_bar(self) -> Panel:
        """Build the configuration bar."""
        items = [
            f"Trade: ${TRADE_AMOUNT}",
            f"Price: ${SHARE_PRICE}",
            f"Slip: ${MAX_SLIPPAGE}",
            f"Cooldown: {COOLDOWN_MINUTES}min",
            f"Entry Wait: {MAX_ENTRY_WAIT_MINUTES}min",
        ]
        config_text = "  │  ".join(items)

        return Panel(
            Align.center(Text(config_text, style="dim")),
            box=box.ROUNDED,
            style="dim",
            height=3,
        )

    def render(self) -> Layout:
        """Build the full dashboard layout."""
        layout = Layout()

        # Main structure
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="config", size=3),
            Layout(name="body"),
            Layout(name="bottom"),
            Layout(name="log", size=self.max_log_lines + 4),
        )

        # Body: left + right columns
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )

        # Left: BTC + Candles
        layout["left"].split_column(
            Layout(name="btc", size=8),
            Layout(name="candles"),
        )

        # Right: Strategy + P&L
        layout["right"].split_column(
            Layout(name="strategy", size=12),
            Layout(name="pnl"),
        )

        # Bottom: Wallet + Positions
        layout["bottom"].split_row(
            Layout(name="wallet", ratio=1),
            Layout(name="positions", ratio=2),
        )

        # Render panels
        layout["header"].update(self._build_header())
        layout["config"].update(self._build_config_bar())
        layout["btc"].update(self._build_btc_panel())
        layout["candles"].update(self._build_candle_history())
        layout["strategy"].update(self._build_strategy_panel())
        layout["pnl"].update(self._build_pnl_panel())
        layout["wallet"].update(self._build_wallet_panel())
        layout["positions"].update(self._build_positions_table())
        layout["log"].update(self._build_activity_log())

        return layout
