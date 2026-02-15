"""
Base Strategy — Abstract interface for all trading strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class TradeSignal:
    """Represents a trading signal from a strategy."""

    def __init__(
        self,
        strategy: str,
        coin: str,
        timeframe: int,
        direction: str,     # 'UP' or 'DOWN'
        token_id: str,
        market_id: str,
        entry_price: float,
        confidence: float,
        rationale: str,
        metadata: Dict = None,
    ):
        self.strategy = strategy
        self.coin = coin
        self.timeframe = timeframe
        self.direction = direction
        self.token_id = token_id
        self.market_id = market_id
        self.entry_price = entry_price
        self.confidence = confidence
        self.rationale = rationale
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        return {
            'strategy': self.strategy,
            'coin': self.coin,
            'timeframe': self.timeframe,
            'direction': self.direction,
            'token_id': self.token_id,
            'market_id': self.market_id,
            'entry_price': self.entry_price,
            'confidence': self.confidence,
            'rationale': self.rationale,
            'metadata': self.metadata,
        }

    def __repr__(self):
        return (f"Signal({self.strategy} {self.coin} {self.direction} "
                f"@{self.entry_price:.4f} conf={self.confidence:.0%})")


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """
        Analyze a market and optionally return a trade signal.

        Args:
            market: Market data from GammaClient.discover_markets()
            context: {
                'clob': ClobClient,
                'poly_feed': PolymarketFeed,
                'binance_feed': BinanceFeed,
                'seconds_remaining': int,
            }

        Returns:
            TradeSignal if a trade should be made, None otherwise.
        """
        pass

    @abstractmethod
    def get_suitable_timeframes(self) -> List[int]:
        """Return list of timeframes this strategy works best with."""
        pass
