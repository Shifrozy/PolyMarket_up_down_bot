"""
╔══════════════════════════════════════════════════════╗
║   POLYMARKET REDEEM COMMAND                          ║
║   Claim winning positions and show WIN/LOSS results  ║
╚══════════════════════════════════════════════════════╝

Usage:
  python redeem.py           # Check and redeem all positions
  python redeem.py --check   # Only check positions (no redeem)
"""

import sys
import os
import argparse
import time
import requests

# Force UTF-8 for Windows terminal
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from web3 import Web3
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET = os.getenv("FUNDER_ADDRESS")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "0"))
CHAIN_ID = 137

RPC = "https://polygon-bor-rpc.publicnode.com"
CLOB_HOST = "https://clob.polymarket.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

CTF_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "bytes32", "name": "parentCollectionId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "indexSets", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"}
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
]


def get_usdc_balance(w3):
    """Get USDC.e balance on-chain."""
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI)
    return usdc.functions.balanceOf(Web3.to_checksum_address(WALLET)).call() / 1e6


def main():
    parser = argparse.ArgumentParser(description="Redeem Polymarket winning positions")
    parser.add_argument("--check", action="store_true", help="Only check positions, don't redeem")
    args = parser.parse_args()

    print("=" * 60)
    print("  💰 POLYMARKET POSITION REDEEMER")
    print("=" * 60)
    print(f"  Wallet: {WALLET}")

    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC))
    wallet = Web3.to_checksum_address(WALLET)
    ctf = w3.eth.contract(address=CTF_ADDRESS, abi=CTF_ABI)

    # Get USDC balance before
    usdc_before = get_usdc_balance(w3)
    print(f"  USDC.e Balance: ${usdc_before:.2f}")

    # Connect to CLOB API
    client = ClobClient(CLOB_HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID,
                       signature_type=SIGNATURE_TYPE, funder=WALLET)
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)

    # Get all trades
    trades = client.get_trades()
    if not trades:
        print("\n  No trades found.")
        return

    print(f"  Total trades on CLOB: {len(trades)}")

    # Map asset_id -> condition_id and trade info
    positions = {}
    for t in trades:
        aid = t.get('asset_id') or t.get('collection_id')
        cond_id = t.get('market')
        if aid and cond_id:
            if aid not in positions:
                positions[aid] = {
                    'condition_id': cond_id,
                    'side': t.get('side', 'BUY'),
                    'outcome': t.get('outcome', '?'),
                    'price': float(t.get('price', 0)),
                    'size': float(t.get('size', 0)),
                }

    print(f"\n{'='*60}")
    print(f"  📋 POSITIONS ({len(positions)} total)")
    print(f"{'='*60}\n")

    wins = 0
    losses = 0
    redeemed = 0
    total_redeemed_value = 0.0

    for aid, info in positions.items():
        balance = ctf.functions.balanceOf(wallet, int(aid)).call()
        shares = balance / 1e6

        if balance == 0:
            # No shares = position already resolved
            # If we bought and shares are 0, it means we lost (shares became worthless)
            # OR we already redeemed
            losses += 1
            print(f"  ❌ LOSS | {info['outcome']} | Bought {info['size']} shares @ ${info['price']:.2f}")
            print(f"     Shares left: 0 (resolved as LOSS or already redeemed)")
            print()
            continue

        # Still holding shares
        print(f"  📦 HOLDING | {info['outcome']} | {shares:.2f} shares")
        print(f"     Bought @ ${info['price']:.2f} | Cost: ${info['size'] * info['price']:.2f}")

        if args.check:
            print(f"     ℹ️  Use 'python redeem.py' (without --check) to redeem")
            print()
            continue

        # Try to redeem
        try:
            nonce = w3.eth.get_transaction_count(wallet)
            tx = ctf.functions.redeemPositions(
                Web3.to_checksum_address(USDC_E),
                "0x" + "0" * 64,
                Web3.to_bytes(hexstr=info['condition_id']),
                [1, 2]
            ).build_transaction({
                "chainId": CHAIN_ID,
                "from": wallet,
                "nonce": nonce,
                "gasPrice": int(w3.eth.gas_price * 1.3),
            })

            signed = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"     ⏳ Redeeming... TX: {tx_hash.hex()[:20]}...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 180)

            if receipt['status'] == 1:
                # Check how much USDC we got back
                new_balance = ctf.functions.balanceOf(wallet, int(aid)).call()
                if new_balance == 0:
                    # Successfully redeemed = WIN
                    wins += 1
                    redeemed += 1
                    value = shares  # Each winning share = $1.00, minus cost
                    total_redeemed_value += value
                    print(f"     ✅ WIN! Redeemed {shares:.2f} shares → ${value:.2f} USDC")
                else:
                    # Partial or market not resolved yet
                    print(f"     ⏳ Market not resolved yet. Shares still held.")
            else:
                print(f"     ❌ Redeem TX reverted (market may not be resolved yet)")
            print()
            time.sleep(3)  # Avoid rate limits

        except Exception as e:
            err = str(e)
            if "execution reverted" in err.lower():
                print(f"     ⏳ Market not resolved yet — cannot redeem")
            else:
                print(f"     ❌ Error: {err[:80]}")
            print()

    # Final summary
    usdc_after = get_usdc_balance(w3)
    gained = usdc_after - usdc_before

    print(f"{'='*60}")
    print(f"  📊 REDEMPTION SUMMARY")
    print(f"{'='*60}")
    print(f"  Positions checked:  {len(positions)}")
    print(f"  ✅ Wins redeemed:   {wins}")
    print(f"  ❌ Losses:          {losses}")
    if not args.check:
        print(f"  💰 USDC before:     ${usdc_before:.2f}")
        print(f"  💰 USDC after:      ${usdc_after:.2f}")
        if gained > 0:
            print(f"  📈 Gained:          +${gained:.2f}")
        elif gained < 0:
            print(f"  📉 Net change:      ${gained:.2f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
