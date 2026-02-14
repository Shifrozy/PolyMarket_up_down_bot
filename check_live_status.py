from py_clob_client.client import ClobClient
from config import CLOB_HOST, CHAIN_ID, PRIVATE_KEY, SIGNATURE_TYPE, FUNDER_ADDRESS
import json

def check_live_status():
    print(f"Checking status for wallet: {FUNDER_ADDRESS}")
    client = ClobClient(CLOB_HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, 
                       signature_type=SIGNATURE_TYPE, funder=FUNDER_ADDRESS)
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)

    # 1. Check Trades
    trades = client.get_trades()
    print(f"\n--- Recent Trades ({len(trades)} total) ---")
    for t in trades[:5]:
        status = t.get('status', 'N/A')
        side = t.get('side', 'N/A')
        price = t.get('price', 'N/A')
        size = t.get('size', 'N/A')
        outcome = t.get('outcome', 'N/A')
        print(f"Trade: {side} {outcome} | Size: {size} | Price: {price} | Status: {status}")

    # 2. Check Open Orders
    orders = client.get_orders()
    print(f"\n--- Open Orders ({len(orders) if orders else 0}) ---")
    if orders:
        for o in orders:
            print(f"Order ID: {o.get('id')} | Side: {o.get('side')} | Price: {o.get('price')}")

    # 3. Check for any held tokens (shares)
    # Note: py_clob_client doesn't have a direct 'get_positions' that returns everything,
    # but we can check the collateral balance and potentially common identifiers.
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    ba = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    print(f"\nUSDC Balance: ${float(ba.get('balance', 0))/1e6:.2f}")

if __name__ == "__main__":
    try:
        check_live_status()
    except Exception as e:
        print(f"Error checking status: {e}")
