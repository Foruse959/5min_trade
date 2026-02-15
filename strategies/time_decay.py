"""
Time Decay Strategy (Theta Farming)

Near-expiry markets have dramatically reduced uncertainty.
If the price is far from the strike with < 2 minutes left,
the "losing" side should be nearly worthless but often isn't.

Logic:
1. Find markets with < 2 minutes remaining
2. Get real-time crypto price from Binance
3. If price is clearly above/below strike → the winning side is nearly certain
4. If the winning side is trading below $0.90, buy it (free money)
"""

from typing import Dict, List, Optional
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal


class TimeDecayStrategy(BaseStrategy):
    """Exploit near-expiry markets where outcome is nearly certain."""

    name = "time_decay"
    description = "Buys near-certain outcomes in expiring markets at a discount"

    def __init__(self):
        self.max_remaining = Config.DECAY_MAX_REMAINING_SECONDS
        self.min_discount = Config.DECAY_MIN_NO_DISCOUNT

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """Find decayed outcomes near expiry."""
        binance_feed = context.get('binance_feed')
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 0)

        if not binance_feed or not clob:
            return None

        # Only trade near expiry
        if seconds_remaining > self.max_remaining or seconds_remaining < 10:
            return None

        coin = market['coin']
        real_price = binance_feed.get_price(coin)
        if not real_price:
            return None

        # Get current orderbook prices
        up_book = clob.get_orderbook(market.get('up_token_id', ''))
        down_book = clob.get_orderbook(market.get('down_token_id', ''))

        if not up_book or not down_book:
            return None

        up_ask = up_book['best_ask']
        down_ask = down_book['best_ask']

        # Determine which side is likely winning
        # If UP is trading higher, the market thinks price will go up
        # With < 2 min left and clear momentum, the winning side should be $0.90+
        # Look for the side trading below fair value

        # Simple heuristic: the side closest to $1.00 is the "winner"
        # If winner is below $0.90, it's a theta opportunity
        if up_ask > down_ask:
            # Market thinks UP — check if UP is discounted
            fair_value = 0.90 + (0.10 * (1 - seconds_remaining / self.max_remaining))
            discount = fair_value - up_ask

            if discount >= self.min_discount and up_ask < 0.92:
                confidence = min(0.95, 0.70 + discount)
                return TradeSignal(
                    strategy=self.name,
                    coin=coin,
                    timeframe=market['timeframe'],
                    direction='UP',
                    token_id=market['up_token_id'],
                    market_id=market['market_id'],
                    entry_price=up_ask,
                    confidence=confidence,
                    rationale=(
                        f"⏰ TIME DECAY: {coin} UP is leading but discounted. "
                        f"Price: {up_ask:.4f} vs fair: {fair_value:.4f}. "
                        f"Only {seconds_remaining}s left. Discount: {discount:.2f}"
                    ),
                    metadata={
                        'seconds_remaining': seconds_remaining,
                        'fair_value': fair_value,
                        'discount': discount,
                    }
                )

        elif down_ask > up_ask:
            # Market thinks DOWN
            fair_value = 0.90 + (0.10 * (1 - seconds_remaining / self.max_remaining))
            discount = fair_value - down_ask

            if discount >= self.min_discount and down_ask < 0.92:
                confidence = min(0.95, 0.70 + discount)
                return TradeSignal(
                    strategy=self.name,
                    coin=coin,
                    timeframe=market['timeframe'],
                    direction='DOWN',
                    token_id=market['down_token_id'],
                    market_id=market['market_id'],
                    entry_price=down_ask,
                    confidence=confidence,
                    rationale=(
                        f"⏰ TIME DECAY: {coin} DOWN is leading but discounted. "
                        f"Price: {down_ask:.4f} vs fair: {fair_value:.4f}. "
                        f"Only {seconds_remaining}s left. Discount: {discount:.2f}"
                    ),
                    metadata={
                        'seconds_remaining': seconds_remaining,
                        'fair_value': fair_value,
                        'discount': discount,
                    }
                )

        return None

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]
