"""
Script to redeem winning positions for Polymarket.
"""

from web3 import Web3
from dotenv import load_dotenv
import os, sys, time

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET = os.getenv("FUNDER_ADDRESS")
CHAIN_ID = 137
RPC = "https://polygon-bor-rpc.publicnode.com"

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

# Mapping aid to cond_id from previous check
ASSET_TO_COND = {
    "45820741236247340038977610538680836254380212240603959780082212028811266387120": "0xe06883941a000c1548410b2f8a3a165fc07863a3ae0a7bba153fbc391f94bec6",
    "46375670191277336556428373371998020374229173658427088513100456167387236506487": "0xa9073ff4c8feaf0f6b180e0e824652d3a7a15a385d4ccf68d9242b17fc2439ab"
}

def main():
    w3 = Web3(Web3.HTTPProvider(RPC))
    wallet = Web3.to_checksum_address(WALLET)
    ctf = w3.eth.contract(address=CTF_ADDRESS, abi=CTF_ABI)

    print(f"Starting redemption for wallet: {wallet}")

    for aid, cond_id in ASSET_TO_COND.items():
        balance = ctf.functions.balanceOf(wallet, int(aid)).call()
        if balance > 0:
            print(f"\nHolding {balance / 1e6} shares of Token {aid[-10:]}...")
            print(f"Condition: {cond_id}")
            
            try:
                nonce = w3.eth.get_transaction_count(wallet)
                gas_price = int(w3.eth.gas_price * 1.5) # Boost gas price for speed
                
                tx = ctf.functions.redeemPositions(
                    Web3.to_checksum_address(USDC_E),
                    "0x" + "0" * 64,
                    Web3.to_bytes(hexstr=cond_id),
                    [1, 2]
                ).build_transaction({
                    "chainId": CHAIN_ID,
                    "from": wallet,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                })
                
                signed = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                print(f"  💸 TX sent: {tx_hash.hex()}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 300)
                if receipt['status'] == 1:
                    print("  ✅ Redeemed successfully!")
                else:
                    print("  ❌ Transaction reverted!")
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
        else:
            print(f"Asset {aid[-10:]}: No balance (already redeemed or loss)")

    # Final balance check
    new_bal = w3.eth.get_balance(wallet) # Placeholder check for gas change
    print(f"\nRedemption process finished.")

if __name__ == "__main__":
    main()
