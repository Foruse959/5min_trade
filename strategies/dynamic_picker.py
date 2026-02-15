"""
Dynamic Strategy Picker — ALL-IN Edition

Runs ALL 9 strategies on every scan. Trades CONTINUOUSLY.
Uses the BalanceManager to adjust aggression based on balance tier.

Strategies (9 total):
1. Cheap Outcome Hunter — buy at 1-8 cents for 100x
2. Momentum Reversal — catch big dips
3. YES+NO Arb — guaranteed profit arbitrage
4. Oracle Arb — Binance price edge
5. Time Decay — near-expiry farming
6. Trend Follower — ride momentum
7. Straddle — buy both sides during volatility
8. Spread Scalper — profit from wide spreads
9. Mid-Price Sniper — buy underpriced mid-range outcomes
"""

from typing import Dict, List, Optional
from strategies.base_strategy import BaseStrategy, TradeSignal
from strategies.flash_crash import CheapOutcomeHunter, MomentumReversal
from strategies.oracle_arb import OracleArbStrategy
from strategies.yes_no_arb import YesNoArbStrategy
from strategies.time_decay import TimeDecayStrategy
from strategies.continuous import (
    TrendFollower, StraddleStrategy, SpreadScalper, MidPriceSniper
)


class DynamicPicker(BaseStrategy):
    """
    Master strategy — evaluates ALL strategies, returns the best signal.
    Respects balance tier when filtering.
    """

    name = "dynamic"
    description = "All 9 strategies — trades continuously, adapts to balance"

    def __init__(self):
        self.strategies: List[BaseStrategy] = [
            CheapOutcomeHunter(),     # Lottery tickets
            YesNoArbStrategy(),       # Guaranteed profit
            MomentumReversal(),       # Catch dips
            TrendFollower(),          # Ride momentum
            MidPriceSniper(),         # Underpriced outcomes
            StraddleStrategy(),       # Volatility play
            SpreadScalper(),          # Bid-ask profit
            OracleArbStrategy(),      # Binance edge
            TimeDecayStrategy(),      # Near-expiry
        ]

    async def analyze(self, market: Dict, context: Dict,
                       balance_prefs: Dict = None) -> Optional[TradeSignal]:
        """
        Run ALL strategies. Return the best signal.
        Optionally filter by balance tier preferences.
        """
        signals: List[TradeSignal] = []
        min_confidence = 0.30  # Default low bar

        # Apply balance tier preferences if available
        enabled = None
        disabled = []
        if balance_prefs:
            enabled_cfg = balance_prefs.get('enabled', 'all')
            if enabled_cfg != 'all':
                enabled = enabled_cfg
            disabled = balance_prefs.get('disabled', [])
            min_confidence = balance_prefs.get('min_confidence', 0.30)

        for strategy in self.strategies:
            # Skip disabled strategies
            if strategy.name in disabled:
                continue
            # Only run enabled strategies (if specified)
            if enabled and strategy.name not in enabled:
                continue

            try:
                signal = await strategy.analyze(market, context)
                if signal and signal.confidence >= min_confidence:
                    signals.append(signal)
            except Exception as e:
                continue

        if not signals:
            return None

        # Priority boost for guaranteed-profit strategies
        for s in signals:
            sig_type = s.metadata.get('type', '')
            if sig_type == 'both_sides':
                s.confidence = min(0.99, s.confidence + 0.20)
            elif sig_type == 'cheap_single':
                s.confidence = min(0.95, s.confidence + 0.10)
            elif sig_type in ('trend', 'mid_sniper'):
                s.confidence = min(0.90, s.confidence + 0.05)

        # Sort by confidence
        signals.sort(key=lambda s: s.confidence, reverse=True)
        best = signals[0]
        best.metadata['alternatives'] = len(signals) - 1
        best.metadata['strategies_checked'] = len(self.strategies)
        return best

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    def get_all_strategies(self) -> List[BaseStrategy]:
        return self.strategies
