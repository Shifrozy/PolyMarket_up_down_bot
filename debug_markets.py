"""Get full BTC 15m market data with token IDs."""
import requests
import json
import time
import math

GAMMA = "https://gamma-api.polymarket.com"

now = time.time()
interval = 15 * 60
current = math.floor(now / interval) * interval

# Try current, next and prev boundaries
for label, epoch in [("PREV", current - interval), ("CURRENT", current), ("NEXT", current + interval)]:
    slug = f"btc-updown-15m-{int(epoch)}"
    print(f"\n{'='*60}")
    print(f"  {label}: {slug}")
    print(f"{'='*60}")
    
    try:
        r = requests.get(f"{GAMMA}/markets/slug/{slug}", timeout=10)
        if r.status_code == 200 and r.text.strip() != "null":
            data = r.json()
            print(json.dumps(data, indent=2)[:3000])
        else:
            print(f"  Not found (status={r.status_code})")
    except Exception as e:
        print(f"  Error: {e}")
