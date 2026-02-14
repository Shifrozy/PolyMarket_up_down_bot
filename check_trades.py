from py_clob_client.client import ClobClient
from config import CLOB_HOST, CHAIN_ID, PRIVATE_KEY, SIGNATURE_TYPE, FUNDER_ADDRESS

c = ClobClient(CLOB_HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, 
               signature_type=SIGNATURE_TYPE, funder=FUNDER_ADDRESS)
creds = c.create_or_derive_api_creds()
c.set_api_creds(creds)

trades = c.get_trades()
print(f"Total trades: {len(trades)}")
for t in trades:
    side = t["side"]
    outcome = t.get("outcome", "")
    size = t["size"]
    price = t["price"]
    status = t["status"]
    tx = t.get("transaction_hash", t.get("transactionHash", "N/A"))
    print(f"  {side} {outcome} | {size} shares @ ${price} | {status}")
    print(f"  TX: https://polygonscan.com/tx/{tx}")
    print()

print(f"PolygonScan wallet: https://polygonscan.com/address/{FUNDER_ADDRESS}")
