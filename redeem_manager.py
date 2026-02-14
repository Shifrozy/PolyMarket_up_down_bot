"""
RedeemManager handles the automated redemption of winning positions on Polymarket.
It checks for resolved markets and claims the winnings into USDC.e.
"""

import os
import time
from web3 import Web3
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

class RedeemManager:
    def __init__(self, client: ClobClient, private_key: str, wallet_address: str):
        self._client = client
        self._pk = private_key
        self._wallet = Web3.to_checksum_address(wallet_address)
        self._rpc = "https://polygon-bor-rpc.publicnode.com"
        self._w3 = Web3(Web3.HTTPProvider(self._rpc))
        
        # CTF (Conditional Token Framework) Contract
        self._ctf_address = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
        self._usdc_e_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        self._ctf_abi = [
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
        self._ctf_contract = self._w3.eth.contract(address=self._ctf_address, abi=self._ctf_abi)

    def auto_redeem(self) -> int:
        """
        Check all historical trades, find holdings, and redeem if possible.
        Returns the number of successful redemptions.
        """
        try:
            trades = self._client.get_trades()
            if not trades:
                return 0
            
            # Map asset_id to condition_id (field 'market' in trades)
            asset_to_cond = {}
            for t in trades:
                aid = t.get('asset_id') or t.get('collection_id')
                cond_id = t.get('market')
                if aid and cond_id:
                    asset_to_cond[aid] = cond_id
            
            redemptions = 0
            for aid, cond_id in asset_to_cond.items():
                try:
                    balance = self._ctf_contract.functions.balanceOf(self._wallet, int(aid)).call()
                    if balance > 0:
                        # Try to redeem
                        nonce = self._w3.eth.get_transaction_count(self._wallet)
                        gas_price = int(self._w3.eth.gas_price * 1.3) # Slightly higher gas for reliability
                        
                        tx = self._ctf_contract.functions.redeemPositions(
                            Web3.to_checksum_address(self._usdc_e_address),
                            "0x" + "0" * 64, # parentCollectionId
                            Web3.to_bytes(hexstr=cond_id),
                            [1, 2] # Binary markets YES/NO
                        ).build_transaction({
                            "chainId": 137,
                            "from": self._wallet,
                            "nonce": nonce,
                            "gasPrice": gas_price,
                        })
                        
                        signed = self._w3.eth.account.sign_transaction(tx, private_key=self._pk)
                        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
                        self._w3.eth.wait_for_transaction_receipt(tx_hash, 120)
                        redemptions += 1
                except Exception as e:
                    # Individual asset redemption might fail if market hasn't resolved yet
                    continue
            
            return redemptions
        except Exception as e:
            print(f"RedeemManager Error: {e}")
            return 0

    def get_usdc_balance(self) -> float:
        """Get current USDC.e balance from the CLOB API profile."""
        try:
            ba = self._client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
            return float(ba.get('balance', 0)) / 1e6
        except:
            return 0.0
