"""
WebSocket Feeds — Real-time Price Streams

Dual-feed architecture:
1. Polymarket WebSocket: real-time orderbook updates
2. Binance WebSocket: real-time BTC/ETH/SOL spot prices (for Oracle Arb)
"""

import json
import asyncio
import time
from typing import Callable, Dict, Optional, List
from collections import deque

import websockets

from config import Config


class PriceSnapshot:
    """Point-in-time price data."""
    __slots__ = ['token_id', 'price', 'best_bid', 'best_ask', 'timestamp']

    def __init__(self, token_id: str, price: float, best_bid: float = 0, best_ask: float = 0):
        self.token_id = token_id
        self.price = price
        self.best_bid = best_bid
        self.best_ask = best_ask
        self.timestamp = time.time()


class PolymarketFeed:
    """Real-time Polymarket orderbook feed via WebSocket."""

    def __init__(self):
        self.ws_url = Config.POLYMARKET_WS_URL
        self._ws = None
        self._running = False
        self._subscribed_tokens: List[str] = []

        # Price history per token (last 60 snapshots)
        self.price_history: Dict[str, deque] = {}
        self.latest_prices: Dict[str, PriceSnapshot] = {}

        # Callbacks
        self._on_price_update: Optional[Callable] = None
        self._on_flash_crash: Optional[Callable] = None

    def on_price_update(self, callback: Callable):
        """Register callback for price updates."""
        self._on_price_update = callback

    def on_flash_crash(self, callback: Callable):
        """Register callback for flash crash detection."""
        self._on_flash_crash = callback

    async def subscribe(self, token_ids: List[str]):
        """Subscribe to token price updates."""
        self._subscribed_tokens = token_ids
        for tid in token_ids:
            if tid not in self.price_history:
                self.price_history[tid] = deque(maxlen=120)

    async def run(self):
        """Connect and stream prices."""
        self._running = True

        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self._ws = ws
                    print(f"🔌 Polymarket WS connected")

                    # Subscribe to markets
                    for token_id in self._subscribed_tokens:
                        sub_msg = json.dumps({
                            "type": "subscribe",
                            "channel": "market",
                            "assets_id": token_id,
                        })
                        await ws.send(sub_msg)

                    # Listen for updates
                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_message(message)

            except websockets.ConnectionClosed:
                print("⚠️ Polymarket WS disconnected, reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"❌ Polymarket WS error: {e}")
                await asyncio.sleep(5)

    async def _handle_message(self, raw: str):
        """Parse WebSocket message and update prices."""
        try:
            data = json.loads(raw)
            msg_type = data.get('type', '')

            if msg_type in ('book', 'price_change', 'last_trade_price'):
                token_id = data.get('asset_id', '')
                if not token_id:
                    return

                price = float(data.get('price', data.get('last_trade_price', 0)))
                best_bid = float(data.get('best_bid', 0))
                best_ask = float(data.get('best_ask', 0))

                if price <= 0 and best_bid > 0 and best_ask > 0:
                    price = (best_bid + best_ask) / 2

                snap = PriceSnapshot(token_id, price, best_bid, best_ask)

                # Store
                self.latest_prices[token_id] = snap
                if token_id in self.price_history:
                    self.price_history[token_id].append(snap)

                # Callback
                if self._on_price_update:
                    await self._on_price_update(snap)

                # Flash crash detection
                self._detect_flash_crash(token_id, snap)

        except Exception as e:
            pass  # Silently ignore malformed messages

    def _detect_flash_crash(self, token_id: str, current: PriceSnapshot):
        """Detect if there was a sudden price drop."""
        history = self.price_history.get(token_id)
        if not history or len(history) < 3:
            return

        lookback = Config.FLASH_LOOKBACK_SECONDS
        threshold = Config.FLASH_DROP_THRESHOLD

        # Find price from lookback seconds ago
        cutoff = time.time() - lookback
        old_price = None
        for snap in history:
            if snap.timestamp >= cutoff:
                old_price = snap.price
                break

        if old_price is None or old_price <= 0:
            return

        drop = old_price - current.price
        if drop >= threshold and self._on_flash_crash:
            asyncio.create_task(self._on_flash_crash({
                'token_id': token_id,
                'old_price': old_price,
                'new_price': current.price,
                'drop': drop,
                'timestamp': current.timestamp,
            }))

    def get_latest(self, token_id: str) -> Optional[PriceSnapshot]:
        """Get latest price for a token."""
        return self.latest_prices.get(token_id)

    async def stop(self):
        """Stop the feed."""
        self._running = False
        if self._ws:
            await self._ws.close()


class BinanceFeed:
    """Real-time Binance spot price feed for Oracle Arb strategy."""

    def __init__(self):
        self._running = False
        self.latest_prices: Dict[str, float] = {}
        self._on_price: Optional[Callable] = None

    def on_price(self, callback: Callable):
        self._on_price = callback

    async def run(self, coins: List[str] = None):
        """Stream real-time prices from Binance."""
        coins = coins or Config.ENABLED_COINS
        symbols = [Config.BINANCE_SYMBOLS.get(c, f'{c.lower()}usdt') for c in coins]

        # Combined stream URL
        streams = '/'.join(f"{s}@trade" for s in symbols)
        url = f"{Config.BINANCE_WS_URL}/{streams}"

        self._running = True

        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    print(f"🔌 Binance WS connected ({', '.join(coins)})")

                    async for message in ws:
                        if not self._running:
                            break

                        data = json.loads(message)
                        symbol = data.get('s', '').upper()
                        price = float(data.get('p', 0))

                        if price > 0:
                            # Map back to coin name
                            for coin, sym in Config.BINANCE_SYMBOLS.items():
                                if sym.upper() == symbol:
                                    self.latest_prices[coin] = price
                                    if self._on_price:
                                        await self._on_price(coin, price)
                                    break

            except websockets.ConnectionClosed:
                print("⚠️ Binance WS disconnected, reconnecting...")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ Binance WS error: {e}")
                await asyncio.sleep(5)

    def get_price(self, coin: str) -> Optional[float]:
        """Get latest price for a coin."""
        return self.latest_prices.get(coin.upper())

    async def stop(self):
        self._running = False
