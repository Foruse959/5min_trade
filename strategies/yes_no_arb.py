"""
YES+NO Arbitrage Strategy

Finds guaranteed-profit opportunities where buying both YES and NO
shares costs less than $1.00 (the guaranteed payout at settlement).

Logic:
1. Fetch ask prices for both Up and Down tokens
2. If Up_Ask + Down_Ask < $0.98 → buy BOTH sides
3. At settlement, one side pays $1.00 → guaranteed profit
"""

from typing import Dict, List, Optional
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal


class YesNoArbStrategy(BaseStrategy):
    """Guaranteed profit when YES + NO ask prices sum to less than $1.00."""

    name = "yes_no_arb"
    description = "Buys both sides when combined cost < $1.00 for guaranteed profit"

    def __init__(self):
        self.max_combined = Config.ARB_MAX_COMBINED_PRICE

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """Check if YES + NO < threshold for arbitrage."""
        clob = context.get('clob')
        if not clob:
            return None

        up_token = market.get('up_token_id', '')
        down_token = market.get('down_token_id', '')

        if not up_token or not down_token:
            return None

        # Get both orderbooks
        dual_book = clob.get_dual_orderbook(up_token, down_token)
        if not dual_book:
            return None

        combined = dual_book['combined_ask']
        profit = dual_book['arb_profit']

        if combined <= self.max_combined and profit > 0.01:
            # Arbitrage opportunity!
            up_ask = dual_book['up']['best_ask']
            down_ask = dual_book['down']['best_ask']

            # Check liquidity on both sides
            min_depth = min(dual_book['up']['ask_depth'], dual_book['down']['ask_depth'])
            if min_depth < 2:  # Need at least $2 depth
                return None

            confidence = min(0.99, 0.85 + profit * 2)

            return TradeSignal(
                strategy=self.name,
                coin=market['coin'],
                timeframe=market['timeframe'],
                direction='BOTH',  # Special: buy both sides
                token_id=f"{up_token}|{down_token}",  # Both tokens
                market_id=market['market_id'],
                entry_price=combined,
                confidence=confidence,
                rationale=(
                    f"💰 YES+NO ARB: {market['coin']} {market['timeframe']}m — "
                    f"Up@{up_ask:.4f} + Down@{down_ask:.4f} = {combined:.4f}. "
                    f"Guaranteed profit: ${profit:.4f} per share!"
                ),
                metadata={
                    'up_ask': up_ask,
                    'down_ask': down_ask,
                    'combined': combined,
                    'profit_per_share': profit,
                    'min_depth': min_depth,
                }
            )

        return None

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]
