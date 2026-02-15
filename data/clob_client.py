"""
CLOB API Client — Orderbook & Order Execution

Fetches orderbooks, prices, and places orders on Polymarket's CLOB.
"""

import requests
from typing import Dict, List, Optional, Tuple

from config import Config


class ClobClient:
    """Client for Polymarket's Central Limit Order Book API."""

    def __init__(self):
        self.base_url = Config.CLOB_API_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': '5min-trade-bot/1.0',
            'Accept': 'application/json',
        })

    def get_price(self, token_id: str) -> Optional[float]:
        """Get current mid-price for a token."""
        try:
            url = f"{self.base_url}/price?token_id={token_id}"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get('price', 0))
        except Exception as e:
            print(f"❌ Price fetch error: {e}")
        return None

    def get_prices(self, token_ids: List[str]) -> Dict[str, float]:
        """Get prices for multiple tokens."""
        prices = {}
        for tid in token_ids:
            price = self.get_price(tid)
            if price is not None:
                prices[tid] = price
        return prices

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        Fetch full orderbook for a token.

        Returns:
        {
            'token_id': str,
            'bids': [(price, size), ...],
            'asks': [(price, size), ...],
            'best_bid': float,
            'best_ask': float,
            'spread': float,
            'spread_pct': float,
            'mid_price': float,
            'bid_depth': float,
            'ask_depth': float,
            'imbalance': float,  # positive = more bids
        }
        """
        try:
            url = f"{self.base_url}/book?token_id={token_id}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            data = resp.json()

            bids = sorted(
                [(float(b['price']), float(b['size'])) for b in data.get('bids', [])],
                key=lambda x: x[0], reverse=True
            )
            asks = sorted(
                [(float(a['price']), float(a['size'])) for a in data.get('asks', [])],
                key=lambda x: x[0]
            )

            best_bid = bids[0][0] if bids else 0.0
            best_ask = asks[0][0] if asks else 1.0
            spread = best_ask - best_bid
            mid = (best_bid + best_ask) / 2 if (best_bid + best_ask) > 0 else 0.5

            bid_depth = sum(p * s for p, s in bids[:10])
            ask_depth = sum(p * s for p, s in asks[:10])
            total_depth = bid_depth + ask_depth
            imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0

            return {
                'token_id': token_id,
                'bids': bids,
                'asks': asks,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_pct': (spread / best_ask * 100) if best_ask > 0 else 0,
                'mid_price': mid,
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'imbalance': imbalance,
            }

        except Exception as e:
            print(f"❌ Orderbook error for {token_id[:12]}...: {e}")
            return None

    def get_dual_orderbook(self, up_token: str, down_token: str) -> Optional[Dict]:
        """
        Fetch orderbooks for both Up and Down tokens.
        Returns combined view useful for arbitrage detection.
        """
        up_book = self.get_orderbook(up_token)
        down_book = self.get_orderbook(down_token)

        if not up_book or not down_book:
            return None

        combined_price = up_book['best_ask'] + down_book['best_ask']

        return {
            'up': up_book,
            'down': down_book,
            'combined_ask': combined_price,
            'arb_opportunity': combined_price < 0.98,  # Can buy both for < $0.98
            'arb_profit': max(0, 1.0 - combined_price),
        }

    def calculate_slippage(self, orderbook: Dict, amount_usd: float, side: str) -> float:
        """Calculate expected slippage for a given order size."""
        levels = orderbook['asks'] if side == 'buy' else orderbook['bids']
        if not levels:
            return float('inf')

        remaining = amount_usd
        weighted_price = 0.0
        total_filled = 0.0

        for price, size in levels:
            if remaining <= 0:
                break
            level_value = price * size
            fill = min(remaining, level_value)
            weighted_price += price * fill
            total_filled += fill
            remaining -= fill

        if total_filled == 0:
            return float('inf')

        avg_price = weighted_price / total_filled
        ref_price = levels[0][0]
        return abs(avg_price - ref_price) / ref_price * 100
