"""
Gamma API Client — Market Discovery

Discovers active 5m/15m/30m crypto Up/Down markets on Polymarket.
Markets follow the pattern: "BTC Up or Down? (5 min)" or "Will BTC go up in the next 5 minutes?"
"""

import re
import time
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from config import Config


class GammaClient:
    """Discovers and tracks active crypto minute-markets on Polymarket."""

    # Market question patterns for crypto Up/Down
    MARKET_PATTERNS = [
        # "BTC Up or Down? (5 min)"
        r'(?P<coin>BTC|ETH|SOL|XRP)\s+[Uu]p\s+or\s+[Dd]own\??\s*\((?P<tf>\d+)\s*min',
        # "Will BTC go up in the next 5 minutes?"
        r'[Ww]ill\s+(?P<coin>BTC|ETH|SOL|XRP)\s+go\s+up.*?(?P<tf>\d+)\s*min',
        # "Bitcoin 5-Minute Up/Down"
        r'(?P<coin>Bitcoin|Ethereum|Solana)\s+(?P<tf>\d+)[-\s]*[Mm]inute\s+[Uu]p',
        # "BTC 5 min Up/Down"
        r'(?P<coin>BTC|ETH|SOL|XRP)\s+(?P<tf>\d+)\s*min\s+[Uu]p',
    ]

    COIN_ALIASES = {
        'Bitcoin': 'BTC', 'Ethereum': 'ETH', 'Solana': 'SOL',
        'BTC': 'BTC', 'ETH': 'ETH', 'SOL': 'SOL', 'XRP': 'XRP',
    }

    def __init__(self):
        self.base_url = Config.GAMMA_API_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': '5min-trade-bot/1.0',
            'Accept': 'application/json',
        })
        # Cache: key = (coin, timeframe) -> market data
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0
        self._cache_ttl: float = 30  # seconds

    def discover_markets(self, coins: List[str] = None, timeframes: List[int] = None) -> List[Dict]:
        """
        Find all active crypto Up/Down markets.

        Returns list of dicts:
        {
            'coin': 'BTC',
            'timeframe': 5,
            'question': 'BTC Up or Down? (5 min)',
            'condition_id': '...',
            'up_token_id': '...',
            'down_token_id': '...',
            'up_price': 0.52,
            'down_price': 0.48,
            'end_date': '2026-02-15T19:35:00Z',
            'market_id': '...',
            'volume': 12345.0,
        }
        """
        coins = coins or Config.ENABLED_COINS
        timeframes = timeframes or Config.ENABLED_TIMEFRAMES

        # Check cache
        if time.time() - self._cache_ts < self._cache_ttl and self._cache:
            return self._filter_cached(coins, timeframes)

        # Fetch markets from Gamma API
        raw_markets = self._fetch_markets()
        matched = []

        for market in raw_markets:
            parsed = self._parse_market(market)
            if parsed:
                matched.append(parsed)

        self._cache = {f"{m['coin']}_{m['timeframe']}": m for m in matched}
        self._cache_ts = time.time()

        return self._filter_cached(coins, timeframes)

    def get_market(self, coin: str, timeframe: int) -> Optional[Dict]:
        """Get a specific market by coin and timeframe."""
        markets = self.discover_markets()
        for m in markets:
            if m['coin'] == coin.upper() and m['timeframe'] == timeframe:
                return m
        return None

    def get_market_by_id(self, market_id: str) -> Optional[Dict]:
        """Fetch a specific market by its ID."""
        try:
            url = f"{self.base_url}/markets/{market_id}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"❌ Error fetching market {market_id}: {e}")
        return None

    def _fetch_markets(self, limit: int = 500) -> List[Dict]:
        """Fetch all active markets from Gamma API."""
        markets = []
        offset = 0
        batch = 100

        while len(markets) < limit:
            try:
                url = f"{self.base_url}/markets?limit={batch}&offset={offset}&closed=false&active=true"
                resp = self.session.get(url, timeout=30)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                markets.extend(data)
                if len(data) < batch:
                    break
                offset += batch
            except Exception as e:
                print(f"❌ Error fetching markets: {e}")
                break

        return markets

    def _parse_market(self, market: Dict) -> Optional[Dict]:
        """Parse a raw market into our standard format if it's a crypto Up/Down market."""
        question = market.get('question', '')

        for pattern in self.MARKET_PATTERNS:
            match = re.search(pattern, question)
            if match:
                coin_raw = match.group('coin')
                coin = self.COIN_ALIASES.get(coin_raw, coin_raw.upper())
                timeframe = int(match.group('tf'))

                # Extract token IDs
                tokens = market.get('tokens', [])
                clob_ids_raw = market.get('clobTokenIds', '')

                up_token = None
                down_token = None
                up_price = 0.5
                down_price = 0.5

                # Parse tokens
                if tokens and len(tokens) >= 2:
                    for token in tokens:
                        outcome = token.get('outcome', '').lower()
                        if 'up' in outcome or 'yes' in outcome:
                            up_token = token.get('token_id', '')
                            up_price = float(token.get('price', 0.5))
                        elif 'down' in outcome or 'no' in outcome:
                            down_token = token.get('token_id', '')
                            down_price = float(token.get('price', 0.5))

                # Fallback: parse from clobTokenIds string
                if not up_token and clob_ids_raw:
                    try:
                        if isinstance(clob_ids_raw, str):
                            ids = clob_ids_raw.strip('[]"').split('","')
                        else:
                            ids = clob_ids_raw
                        if len(ids) >= 2:
                            up_token = ids[0]
                            down_token = ids[1]
                    except Exception:
                        pass

                # Parse prices from outcomePrices
                if up_price == 0.5:
                    prices_raw = market.get('outcomePrices', '')
                    if prices_raw:
                        try:
                            if isinstance(prices_raw, str):
                                prices = prices_raw.strip('[]"').split('","')
                            else:
                                prices = prices_raw
                            if len(prices) >= 2:
                                up_price = float(prices[0])
                                down_price = float(prices[1])
                        except Exception:
                            pass

                return {
                    'coin': coin,
                    'timeframe': timeframe,
                    'question': question,
                    'condition_id': market.get('conditionId', ''),
                    'market_id': market.get('id', ''),
                    'market_slug': market.get('market_slug', ''),
                    'up_token_id': up_token or '',
                    'down_token_id': down_token or '',
                    'up_price': up_price,
                    'down_price': down_price,
                    'end_date': market.get('endDate', ''),
                    'volume': float(market.get('volume', 0) or 0),
                    'liquidity': float(market.get('liquidity', 0) or 0),
                }

        return None

    def _filter_cached(self, coins: List[str], timeframes: List[int]) -> List[Dict]:
        """Filter cached markets by coins and timeframes."""
        results = []
        for key, market in self._cache.items():
            if market['coin'] in coins and market['timeframe'] in timeframes:
                results.append(market)
        return results

    def get_seconds_remaining(self, market: Dict) -> int:
        """Calculate seconds remaining until market settlement."""
        end_date = market.get('end_date', '')
        if not end_date:
            return 0
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            remaining = (end_dt - now).total_seconds()
            return max(0, int(remaining))
        except Exception:
            return 0
