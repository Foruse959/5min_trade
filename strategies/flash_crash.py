"""
Cheap Outcome Hunter — The Core Strategy

THE EDGE: In 5-minute crypto markets, probabilities swing wildly.
When one side drops to $0.01-0.05, buying it is a lottery ticket
that pays $1.00 if it hits. Buy BOTH sides when both are cheap.

Logic:
1. Scan all active markets every few seconds
2. If Up OR Down is at 1-8 cents → BUY IT (potential 12-100x)
3. If BOTH sides are cheap (combined < $0.25) → BUY BOTH (guaranteed-ish profit)
4. Hold dynamically: ride to $1.00, or sell at 3x+, or cut at -16%
5. Trade FREQUENTLY — volume is king
"""

import time
from typing import Dict, List, Optional
from strategies.base_strategy import BaseStrategy, TradeSignal


class CheapOutcomeHunter(BaseStrategy):
    """Buy dirt-cheap outcomes for massive potential returns."""

    name = "cheap_hunter"
    description = "Buys outcomes at 1-8 cents for 12-100x potential returns"

    # THRESHOLDS
    MAX_BUY_PRICE = 0.08        # Buy anything under 8 cents
    SWEET_SPOT_MAX = 0.03       # 1-3 cents = highest confidence
    BOTH_SIDES_MAX = 0.25       # If Up + Down < 25 cents, buy BOTH
    MIN_BUY_PRICE = 0.005       # Below half a cent = no liquidity

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 0)

        if not clob:
            return None

        # Skip last 5 seconds — settlement chaos
        if seconds_remaining < 5:
            return None

        up_token = market.get('up_token_id', '')
        down_token = market.get('down_token_id', '')

        if not up_token or not down_token:
            return None

        up_book = clob.get_orderbook(up_token)
        down_book = clob.get_orderbook(down_token)

        if not up_book or not down_book:
            return None

        up_ask = up_book['best_ask']
        down_ask = down_book['best_ask']

        # ═══════════════════════════════════════════════════════════
        # STRATEGY 1: Buy BOTH sides if combined is insanely cheap
        # ═══════════════════════════════════════════════════════════
        combined = up_ask + down_ask
        if combined < self.BOTH_SIDES_MAX and up_ask > self.MIN_BUY_PRICE and down_ask > self.MIN_BUY_PRICE:
            # Both sides cheap — one MUST pay $1.00 at settlement
            profit_potential = 1.0 - combined
            return TradeSignal(
                strategy=self.name,
                coin=market['coin'],
                timeframe=market['timeframe'],
                direction='BOTH',
                token_id=f"{up_token}|{down_token}",
                market_id=market['market_id'],
                entry_price=combined,
                confidence=0.95,
                rationale=(
                    f"💎 BOTH SIDES CHEAP: {market['coin']} "
                    f"Up@{up_ask:.3f} + Down@{down_ask:.3f} = {combined:.3f}. "
                    f"Guaranteed ${profit_potential:.3f} profit per share!"
                ),
                metadata={
                    'up_ask': up_ask, 'down_ask': down_ask,
                    'combined': combined, 'type': 'both_sides',
                }
            )

        # ═══════════════════════════════════════════════════════════
        # STRATEGY 2: Buy the cheap side (lottery ticket)
        # ═══════════════════════════════════════════════════════════
        for side, ask_price, token_id in [
            ('UP', up_ask, up_token),
            ('DOWN', down_ask, down_token),
        ]:
            if self.MIN_BUY_PRICE < ask_price <= self.MAX_BUY_PRICE:
                # Cheap outcome found!
                potential_return = 1.0 / ask_price  # e.g. $0.02 → 50x

                # Higher confidence for cheaper prices
                if ask_price <= self.SWEET_SPOT_MAX:
                    confidence = 0.80  # Sweet spot: 1-3 cents
                elif ask_price <= 0.05:
                    confidence = 0.70  # Good: 3-5 cents
                else:
                    confidence = 0.60  # OK: 5-8 cents

                # Boost confidence in last 2 minutes (more volatility = more swings)
                if seconds_remaining < 120:
                    confidence = min(0.95, confidence + 0.10)

                # Check there's liquidity to actually fill
                book = up_book if side == 'UP' else down_book
                if book['ask_depth'] < 0.50:  # Need at least 50 cents depth
                    continue

                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction=side,
                    token_id=token_id,
                    market_id=market['market_id'],
                    entry_price=ask_price,
                    confidence=confidence,
                    rationale=(
                        f"🎰 CHEAP {side}: {market['coin']} {side} "
                        f"@${ask_price:.3f} = {potential_return:.0f}x potential! "
                        f"Time left: {seconds_remaining}s"
                    ),
                    metadata={
                        'ask_price': ask_price,
                        'potential_return': potential_return,
                        'type': 'cheap_single',
                        'seconds_remaining': seconds_remaining,
                    }
                )

        return None

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]


class MomentumReversal(BaseStrategy):
    """
    Buy when a side rapidly drops and looks like it'll bounce.
    In 5-min markets, a coin that was at 50% and drops to 10%
    often bounces back as people buy the dip.
    """

    name = "momentum_reversal"
    description = "Catches sharp reversals — buys the dip in probability"

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        poly_feed = context.get('poly_feed')
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 0)

        if not poly_feed or not clob:
            return None

        if seconds_remaining < 10:
            return None

        for side, token_key in [('UP', 'up_token_id'), ('DOWN', 'down_token_id')]:
            token_id = market.get(token_key, '')
            if not token_id:
                continue

            history = poly_feed.price_history.get(token_id)
            if not history or len(history) < 5:
                continue

            # Check for a big recent drop (last 15 seconds)
            recent = [s for s in history if s.timestamp > time.time() - 15]
            if len(recent) < 3:
                continue

            prices = [s.price for s in recent]
            max_recent = max(prices)
            current = prices[-1]
            drop = max_recent - current

            # If dropped 15+ cents in 15 seconds: reversal opportunity
            if drop >= 0.15 and current < 0.40:
                book = clob.get_orderbook(token_id)
                if not book or book['ask_depth'] < 0.50:
                    continue

                confidence = min(0.90, 0.55 + drop)

                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction=side,
                    token_id=token_id,
                    market_id=market['market_id'],
                    entry_price=book['best_ask'],
                    confidence=confidence,
                    rationale=(
                        f"📉➡️📈 REVERSAL: {market['coin']} {side} "
                        f"dropped {drop:.2f} ({max_recent:.2f}→{current:.2f}) in 15s. "
                        f"Buying the dip @ {book['best_ask']:.3f}"
                    ),
                    metadata={
                        'drop': drop, 'max_price': max_recent,
                        'current_price': current, 'type': 'reversal',
                    }
                )

        return None

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15]
