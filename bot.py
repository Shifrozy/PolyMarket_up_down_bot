"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║      ₿  POLYMARKET BTC STRATEGY BOT                                 ║
║      ─────────────────────────────────                               ║
║      Contrarian 2-Candle Strategy with Progressive Entries           ║
║                                                                      ║
║      • 2 Red   candles → BUY UP                                     ║
║      • 2 Green candles → BUY DOWN                                   ║
║      • Progressive: 3rd → 4th → 5th candle on losses               ║
║      • 30-min cooldown after 5th candle trade                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

Usage:
  python bot.py              # Run bot (paper mode by default)
  python bot.py --live       # Run bot in live mode (requires .env)
  python bot.py --status     # Show current status and exit
"""

import sys
import os
import time
import signal
import argparse
from datetime import datetime

# Force UTF-8 for Windows terminal (Rich uses emojis)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich import box

import config
from candle_feed import CandleFeed
from trade_manager import TradeManager
from market_finder import MarketFinder
from strategy import StrategyEngine
from dashboard import Dashboard


# ── Globals ─────────────────────────────────────────
console = Console()
running = True


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global running
    running = False


def print_banner():
    """Print startup banner."""
    banner = """
[bold bright_blue]
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   ₿  POLYMARKET BTC STRATEGY BOT  v1.0                  ║
  ║   ──────────────────────────────────                     ║
  ║   Contrarian 2-Candle Strategy                           ║
  ║   with Progressive Entries                               ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
[/bold bright_blue]
"""
    console.print(banner)


def print_strategy_summary():
    """Print a summary of the bot's strategy."""
    summary = """
[bold white]Strategy Summary:[/bold white]
  [yellow]A.[/yellow] Two red 15-min candles   → [green]BUY UP[/green]   (contrarian)
  [yellow]B.[/yellow] Two green 15-min candles → [red]BUY DOWN[/red] (contrarian)
  [yellow]C.[/yellow] Progressive entries on losses:
     • Trade 3rd candle → if LOSES → Trade 4th → if LOSES → Trade 5th
     • After 5th candle trade → 30-min cooldown
  [yellow]D.[/yellow] If bot WINS any trade → reset, look for new 2-candle signal
  [yellow]E.[/yellow] $1 trade at $0.50/share, 0.02% max slippage
  [yellow]F.[/yellow] Skip trade if right price not found within 5 minutes
"""
    console.print(Panel(summary, title="🧠 Strategy", border_style="cyan"))


def validate_and_start():
    """Validate configuration and start the bot."""
    errors = config.validate_config()
    if errors:
        console.print("\n[bold red]❌ Configuration Errors:[/bold red]")
        for err in errors:
            console.print(f"  • {err}")
        console.print(
            "\n[dim]Copy .env.example to .env and fill in your credentials.[/dim]"
        )
        sys.exit(1)

    mode = "[red]🔴 PAPER MODE[/red]" if config.PAPER_MODE else "[green]🟢 LIVE TRADING[/green]"
    console.print(f"\n  Mode: {mode}")
    console.print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print()


def run_bot():
    """Main bot loop."""
    global running
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize components
    console.print("[dim]Initializing components...[/dim]")
    feed = CandleFeed()
    trader = TradeManager()
    finder = MarketFinder()

    # Create strategy engine
    dashboard = None  # Will be set below

    def on_log(msg: str):
        if dashboard:
            dashboard.add_log(msg)

    engine = StrategyEngine(
        candle_feed=feed,
        trade_manager=trader,
        market_finder=finder,
        on_log=on_log,
    )

    # Create dashboard
    dashboard_obj = Dashboard(engine=engine, feed=feed, trader=trader)
    dashboard = dashboard_obj  # Enable logging

    # Initial data fetch
    console.print("[dim]Fetching initial candle data...[/dim]")
    try:
        feed.fetch_recent(limit=10)
        btc = feed.get_btc_price()
        console.print(f"[green]✓[/green] BTC Price: ${btc:,.2f}")
        console.print(f"[green]✓[/green] Loaded {len(feed.get_closed_candles())} closed candles")
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch candle data: {e}[/red]")
        console.print("[dim]Will retry when bot starts...[/dim]")

    # Check for market
    console.print("[dim]Searching for BTC 15-min markets on Polymarket...[/dim]")
    market = finder.find_current_market()
    if market:
        console.print(f"[green]✓[/green] Found market: {market.question[:60]}...")
    else:
        console.print("[yellow]⚠ No active BTC 15-min market found — will use paper simulation[/yellow]")

    console.print("\n[bold green]✅ Bot started! Press Ctrl+C to stop.[/bold green]\n")
    time.sleep(2)

    # Main loop with live dashboard
    tick_interval = 5  # seconds between ticks
    last_tick = 0

    with Live(
        dashboard_obj.render(),
        console=console,
        refresh_per_second=1,
        screen=True,
    ) as live:
        while running:
            now = time.time()

            # Process strategy tick
            if now - last_tick >= tick_interval:
                try:
                    engine.process_tick()
                except Exception as e:
                    dashboard_obj.add_log(f"[red]⚠ Error: {str(e)[:50]}[/red]")
                last_tick = now
            # Update dashboard
            try:
                live.update(dashboard_obj.render())
            except Exception:
                pass

            time.sleep(0.5)

    # Shutdown
    console.print("\n[yellow]🛑 Bot stopped by user.[/yellow]")
    console.print(f"[dim]Total trades: {trader.total_trades} | P&L: ${trader.total_pnl:+.2f}[/dim]")


def show_status():
    """Show current bot status and exit."""
    trader = TradeManager()
    console.print("\n[bold]📊 Bot Status[/bold]\n")
    console.print(f"  Total Trades:  {trader.total_trades}")
    console.print(f"  Wins:          {trader.wins}")
    console.print(f"  Losses:        {trader.losses}")
    console.print(f"  Win Rate:      {trader.win_rate:.1f}%")
    console.print(f"  Total P&L:     ${trader.total_pnl:+.2f}")
    console.print(f"  Total Volume:  ${trader.total_volume:.2f}")

    if trader.recent_trades:
        console.print("\n[bold]Recent Trades:[/bold]")
        for t in trader.recent_trades:
            pnl_str = f"[green]+${t.pnl:.2f}[/green]" if t.pnl >= 0 else f"[red]${t.pnl:.2f}[/red]"
            console.print(f"  {t.status_emoji} {t.direction_emoji} | {t.entry_time} | {pnl_str}")
    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket BTC Strategy Bot — Contrarian 2-Candle Strategy"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Run in live trading mode (requires .env credentials)"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current status and exit"
    )
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # Override paper mode if --live is passed
    if args.live:
        import config
        config.PAPER_MODE = False

    print_banner()
    print_strategy_summary()
    validate_and_start()
    run_bot()


if __name__ == "__main__":
    main()
