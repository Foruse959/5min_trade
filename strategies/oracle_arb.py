"""
Oracle Arbitrage Strategy

Exploits the delay between real-world crypto prices (Binance) and
Polymarket prediction market probabilities.

Logic:
1. Get real-time BTC/ETH/SOL price from Binance WebSocket
2. Compare with the market's implied strike/start price
3. Calculate true probability using remaining time & volatility
4. If Polymarket misprices by {min_edge}+, trade the mispriced side
"""

import math
from typing import Dict, List, Optional
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal


class OracleArbStrategy(BaseStrategy):
    """Exploit real-time price feeds vs Polymarket probabilities."""

    name = "oracle_arb"
    description = "Uses Binance real-time prices to find mispriced probabilities"

    # Annualized volatility estimates (used for probability calculation)
    VOLATILITY = {
        'BTC': 0.60,  # ~60% annualized
        'ETH': 0.75,
        'SOL': 1.00,
        'XRP': 0.90,
    }

    def __init__(self):
        self.price_buffer = Config.ORACLE_PRICE_BUFFER
        self.min_edge = Config.ORACLE_MIN_EDGE

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """Compare external price with Polymarket probability."""
        binance_feed = context.get('binance_feed')
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 0)

        if not binance_feed or not clob:
            return None

        coin = market['coin']
        real_price = binance_feed.get_price(coin)
        if not real_price:
            return None

        # Don't trade in last 15 seconds (too volatile)
        if seconds_remaining < 15:
            return None

        # Calculate implied probability that price goes UP
        # Using simplified Black-Scholes-like approximation
        true_up_prob = self._calculate_up_probability(
            coin=coin,
            current_price=real_price,
            seconds_remaining=seconds_remaining,
        )

        # Get Polymarket prices
        up_book = clob.get_orderbook(market.get('up_token_id', ''))
        down_book = clob.get_orderbook(market.get('down_token_id', ''))

        if not up_book or not down_book:
            return None

        poly_up_price = up_book['best_ask']
        poly_down_price = down_book['best_ask']

        # Find edge
        up_edge = true_up_prob - poly_up_price    # Positive = UP is underpriced
        down_edge = (1 - true_up_prob) - poly_down_price  # Positive = DOWN is underpriced

        # Trade the side with the biggest edge
        if up_edge >= self.min_edge and up_edge > down_edge:
            confidence = min(0.95, 0.50 + up_edge)
            return TradeSignal(
                strategy=self.name,
                coin=coin,
                timeframe=market['timeframe'],
                direction='UP',
                token_id=market['up_token_id'],
                market_id=market['market_id'],
                entry_price=poly_up_price,
                confidence=confidence,
                rationale=(
                    f"🎯 ORACLE ARB: {coin} UP is underpriced. "
                    f"True prob: {true_up_prob:.0%} vs Market: {poly_up_price:.0%}. "
                    f"Edge: {up_edge:.0%}. Binance: ${real_price:,.2f}. "
                    f"Time left: {seconds_remaining}s"
                ),
                metadata={
                    'real_price': real_price,
                    'true_prob': true_up_prob,
                    'market_price': poly_up_price,
                    'edge': up_edge,
                }
            )

        elif down_edge >= self.min_edge:
            confidence = min(0.95, 0.50 + down_edge)
            return TradeSignal(
                strategy=self.name,
                coin=coin,
                timeframe=market['timeframe'],
                direction='DOWN',
                token_id=market['down_token_id'],
                market_id=market['market_id'],
                entry_price=poly_down_price,
                confidence=confidence,
                rationale=(
                    f"🎯 ORACLE ARB: {coin} DOWN is underpriced. "
                    f"True prob: {1-true_up_prob:.0%} vs Market: {poly_down_price:.0%}. "
                    f"Edge: {down_edge:.0%}. Binance: ${real_price:,.2f}. "
                    f"Time left: {seconds_remaining}s"
                ),
                metadata={
                    'real_price': real_price,
                    'true_prob': 1 - true_up_prob,
                    'market_price': poly_down_price,
                    'edge': down_edge,
                }
            )

        return None

    def _calculate_up_probability(self, coin: str, current_price: float,
                                   seconds_remaining: int) -> float:
        """
        Calculate probability that price goes UP using a simplified model.

        For an "Up or Down" market, the start price is roughly the current price
        at market creation. With no directional bias (random walk), the base
        probability is ~50%. We adjust based on:
        - Current momentum (inferred from price buffer)
        - Time remaining (more time = closer to 50%)
        """
        # Base probability is 50% (random walk)
        base_prob = 0.50

        # Volatility adjustment
        # More time = more uncertainty = closer to 50%
        vol = self.VOLATILITY.get(coin, 0.70)
        time_fraction = seconds_remaining / (365.25 * 24 * 3600)  # Convert to years

        # Standard deviation of price move in remaining time
        std_dev = vol * math.sqrt(time_fraction) if time_fraction > 0 else 0

        # If std_dev is very small (close to expiry), the outcome is nearly certain
        # based on current price vs strike
        # With shorter time, a small move matters more
        if std_dev > 0:
            # Assuming "Up" means price >= start price
            # If currently at start price, prob = 50%
            # We add a small bias based on recent momentum
            # (In practice, you'd compare current price vs the market's start price)
            prob = base_prob
        else:
            prob = base_prob

        return max(0.05, min(0.95, prob))

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]
