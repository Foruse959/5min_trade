"""
Live Trader — Real Order Execution (Stub)

Placeholder for live trading via Polymarket CLOB API.
Requires funded Polygon wallet + API credentials.
"""

from typing import Dict, Optional
from strategies.base_strategy import TradeSignal


class LiveTrader:
    """
    Real trading execution via Polymarket CLOB API.
    
    ⚠️ STUB — Not yet implemented. Use paper mode first.
    When ready for live, this will use py-clob-client for:
    - EIP-712 order signing
    - POST /order for order placement
    - DELETE /order for cancellations
    - Gasless execution via Builder Program
    """

    def __init__(self):
        print("⚠️ LiveTrader is a STUB — use paper mode")

    async def execute_signal(self, signal: TradeSignal) -> Optional[Dict]:
        """Place a real order. NOT YET IMPLEMENTED."""
        print(f"⚠️ LIVE TRADE SKIPPED (stub): {signal}")
        return None
