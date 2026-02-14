"""
Setup token allowances for Polymarket CLOB trading.
Approves USDC and Conditional Tokens for all 3 exchange contracts.
Run ONCE before starting the bot.
"""

from web3 import Web3
from dotenv import load_dotenv
import os, sys, time

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
CHAIN_ID = 137

# Multiple RPCs for fallback
RPCS = [
    "https://polygon.llamarpc.com",
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon-rpc.com",
]

USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

EXCHANGES = [
    ("CTF Exchange", "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"),
    ("Neg Risk CTF Exchange", "0xC5d563A36AE78145C45a50134d48A1215220f80a"),
    ("Neg Risk Adapter", "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"),
]

ERC20_ABI = [
    {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"constant":True,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

ERC1155_ABI = [
    {"inputs":[{"name":"operator","type":"address"},{"name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"account","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"},
]

MAX_UINT = 2**256 - 1


def get_web3():
    for rpc in RPCS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
            if w3.is_connected():
                print(f"Connected to: {rpc}")
                return w3
        except:
            continue
    print("ERROR: Cannot connect to any Polygon RPC")
    sys.exit(1)


def send_tx(web3, tx_func, label):
    """Send a transaction with retry logic."""
    for attempt in range(3):
        try:
            nonce = web3.eth.get_transaction_count(FUNDER_ADDRESS)
            tx = tx_func.build_transaction({
                "chainId": CHAIN_ID,
                "from": FUNDER_ADDRESS,
                "nonce": nonce,
                "gasPrice": web3.eth.gas_price,
            })
            signed = web3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"   ⏳ {label}: tx sent {tx_hash.hex()[:20]}... waiting...")
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, 300)
            if receipt["status"] == 1:
                print(f"   ✅ {label}: confirmed!")
                return True
            else:
                print(f"   ❌ {label}: reverted")
                return False
        except Exception as e:
            err = str(e)
            if "rate limit" in err.lower() or "too many" in err.lower():
                wait = 15 * (attempt + 1)
                print(f"   ⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif "nonce too low" in err.lower() or "already known" in err.lower():
                print(f"   ⏳ {label}: tx already pending, skipping")
                return True
            else:
                print(f"   ❌ {label}: {err[:100]}")
                if attempt < 2:
                    time.sleep(10)
                else:
                    return False
    return False


def main():
    if not PRIVATE_KEY or not FUNDER_ADDRESS:
        print("ERROR: Set PRIVATE_KEY and FUNDER_ADDRESS in .env")
        sys.exit(1)

    web3 = get_web3()

    matic = web3.eth.get_balance(FUNDER_ADDRESS) / 1e18
    print(f"Wallet: {FUNDER_ADDRESS}")
    print(f"MATIC: {matic:.4f} POL")

    if matic < 0.005:
        print(f"\n❌ Need MATIC for gas! Send ~0.01 POL to {FUNDER_ADDRESS}")
        sys.exit(1)

    usdc = web3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
    ctf = web3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=ERC1155_ABI)

    usdc_bal = usdc.functions.balanceOf(FUNDER_ADDRESS).call() / 1e6
    print(f"USDC: ${usdc_bal:.2f}")

    print(f"\n🔧 Setting allowances for {len(EXCHANGES)} contracts...\n")

    success_count = 0
    total = len(EXCHANGES) * 2

    for name, exchange_addr in EXCHANGES:
        addr = Web3.to_checksum_address(exchange_addr)
        print(f"📋 {name}")

        # Check if USDC already approved
        current = usdc.functions.allowance(FUNDER_ADDRESS, addr).call()
        if current > 10**30:
            print(f"   ✅ USDC: already approved")
            success_count += 1
        else:
            ok = send_tx(web3, usdc.functions.approve(addr, MAX_UINT), "USDC approve")
            if ok:
                success_count += 1
            time.sleep(5)

        # Check if CTF already approved
        approved = ctf.functions.isApprovedForAll(FUNDER_ADDRESS, addr).call()
        if approved:
            print(f"   ✅ CTF: already approved")
            success_count += 1
        else:
            ok = send_tx(web3, ctf.functions.setApprovalForAll(addr, True), "CTF approve")
            if ok:
                success_count += 1
            time.sleep(5)

        print()

    print("=" * 50)
    print(f"✅ Done! {success_count}/{total} approvals successful")
    if usdc_bal < 5:
        print(f"\n⚠️  Send USDC to: {FUNDER_ADDRESS}")
        print("   Need at least $5 USDC for trading")
    print("\nRun bot: python -X utf8 bot.py")


if __name__ == "__main__":
    main()
