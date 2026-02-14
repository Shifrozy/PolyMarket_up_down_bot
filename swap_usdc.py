"""
Swap native USDC to USDC.e (bridged) on Polygon via Uniswap V3.
Polymarket requires USDC.e for trading.
"""

from web3 import Web3
from dotenv import load_dotenv
import os, sys, time, json

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET = os.getenv("FUNDER_ADDRESS")
CHAIN_ID = 137

RPC = "https://polygon-bor-rpc.publicnode.com"

# Token addresses
USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"       # USDC.e (bridged)

# Uniswap V3 SwapRouter02 on Polygon
SWAP_ROUTER = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"

ERC20_ABI = [
    {"constant":True,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":False,"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"constant":True,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
]

# Uniswap V3 exactInputSingle
SWAP_ABI = [
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn", "type": "address"},
                {"name": "tokenOut", "type": "address"},
                {"name": "fee", "type": "uint24"},
                {"name": "recipient", "type": "address"},
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMinimum", "type": "uint256"},
                {"name": "sqrtPriceLimitX96", "type": "uint160"}
            ],
            "name": "params",
            "type": "tuple"
        }],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

MAX_UINT = 2**256 - 1


def main():
    web3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 30}))
    if not web3.is_connected():
        print("Cannot connect to RPC"); sys.exit(1)

    wallet = Web3.to_checksum_address(WALLET)
    
    native_usdc = web3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
    bridged_usdc = web3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI)
    
    native_bal = native_usdc.functions.balanceOf(wallet).call()
    bridged_bal = bridged_usdc.functions.balanceOf(wallet).call()
    
    native_dec = native_usdc.functions.decimals().call()
    bridged_dec = bridged_usdc.functions.decimals().call()
    
    print(f"Native USDC: ${native_bal / 10**native_dec:.2f} ({native_dec} decimals)")
    print(f"USDC.e:      ${bridged_bal / 10**bridged_dec:.2f} ({bridged_dec} decimals)")
    
    if native_bal == 0:
        print("\nNo native USDC to swap!")
        sys.exit(0)
    
    swap_amount = native_bal  # Swap all
    print(f"\nSwapping ${swap_amount / 10**native_dec:.2f} native USDC -> USDC.e")
    
    # Step 1: Approve router to spend native USDC
    router_addr = Web3.to_checksum_address(SWAP_ROUTER)
    current_allowance = native_usdc.functions.allowance(wallet, router_addr).call()
    
    if current_allowance < swap_amount:
        print("Approving swap router...")
        nonce = web3.eth.get_transaction_count(wallet)
        tx = native_usdc.functions.approve(router_addr, MAX_UINT).build_transaction({
            "chainId": CHAIN_ID, "from": wallet, "nonce": nonce,
            "gasPrice": web3.eth.gas_price,
        })
        signed = web3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
        web3.eth.wait_for_transaction_receipt(tx_hash, 120)
        print("Approved!")
        time.sleep(3)
    
    # Step 2: Swap via Uniswap V3
    # USDC/USDC.e pool fee tier: 100 (0.01%) for stablecoin pairs
    router = web3.eth.contract(address=router_addr, abi=SWAP_ABI)
    
    # Accept up to 1% slippage for stablecoin swap
    min_out = int(swap_amount * 0.99)
    
    # Try different fee tiers
    for fee in [100, 500, 3000]:
        print(f"\nTrying fee tier {fee/10000:.2f}%...")
        try:
            nonce = web3.eth.get_transaction_count(wallet)
            swap_params = (
                Web3.to_checksum_address(USDC_NATIVE),  # tokenIn
                Web3.to_checksum_address(USDC_E),        # tokenOut
                fee,                                      # fee
                wallet,                                   # recipient
                swap_amount,                              # amountIn
                min_out,                                  # amountOutMinimum
                0,                                        # sqrtPriceLimitX96
            )
            
            tx = router.functions.exactInputSingle(swap_params).build_transaction({
                "chainId": CHAIN_ID,
                "from": wallet,
                "nonce": nonce,
                "gasPrice": web3.eth.gas_price,
                "value": 0,
            })
            
            signed = web3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"Swap tx: {tx_hash.hex()}")
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, 120)
            
            if receipt["status"] == 1:
                new_bal = bridged_usdc.functions.balanceOf(wallet).call() / 10**bridged_dec
                print(f"\n✅ Swap successful!")
                print(f"USDC.e balance: ${new_bal:.2f}")
                return
            else:
                print(f"❌ Swap reverted with fee {fee}")
        except Exception as e:
            print(f"Failed with fee {fee}: {str(e)[:150]}")
    
    print("\n❌ All swap attempts failed. Try swapping manually on app.uniswap.org")


if __name__ == "__main__":
    main()
