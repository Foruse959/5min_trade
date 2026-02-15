"""
Database — Trade Storage (SQLite)

Stores trades, positions, strategy stats, and P&L history.
"""

import os
import json
import aiosqlite
from typing import Dict, List, Optional
from datetime import datetime

from config import Config


class Database:
    """Async SQLite database for trade management."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)

    async def init(self):
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    market_id TEXT,
                    coin TEXT,
                    timeframe INTEGER,
                    strategy TEXT,
                    direction TEXT,
                    token_id TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    size_usd REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    confidence REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    exit_reason TEXT,
                    status TEXT DEFAULT 'open',
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    trade_id TEXT,
                    market_id TEXT,
                    coin TEXT,
                    timeframe INTEGER,
                    strategy TEXT,
                    direction TEXT,
                    token_id TEXT,
                    entry_price REAL,
                    current_price REAL,
                    target_price REAL,
                    stop_loss_price REAL,
                    size_usd REAL,
                    unrealized_pnl REAL,
                    entry_time TEXT,
                    status TEXT DEFAULT 'open'
                );

                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    avg_win REAL DEFAULT 0,
                    avg_loss REAL DEFAULT 0,
                    last_updated TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date TEXT PRIMARY KEY,
                    starting_balance REAL,
                    ending_balance REAL,
                    total_trades INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    gross_profit REAL,
                    gross_loss REAL,
                    net_pnl REAL
                );

                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_coin ON trades(coin);
                CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
                CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
            """)
            await db.commit()
        print("✅ Database initialized")

    async def save_trade(self, trade: Dict):
        """Save or update a trade."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO trades
                (id, market_id, coin, timeframe, strategy, direction, token_id,
                 entry_price, exit_price, size_usd, pnl, pnl_pct, confidence,
                 entry_time, exit_time, exit_reason, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['id'], trade.get('market_id', ''), trade.get('coin', ''),
                trade.get('timeframe', 0), trade.get('strategy', ''),
                trade.get('direction', ''), trade.get('token_id', ''),
                trade.get('entry_price', 0), trade.get('exit_price'),
                trade.get('size_usd', 0), trade.get('pnl'),
                trade.get('pnl_pct'), trade.get('confidence', 0),
                trade.get('entry_time', ''), trade.get('exit_time'),
                trade.get('exit_reason'), trade.get('status', 'open'),
                json.dumps(trade.get('metadata', {})),
            ))
            await db.commit()

    async def save_position(self, position: Dict):
        """Save or update a position."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO positions
                (id, trade_id, market_id, coin, timeframe, strategy, direction,
                 token_id, entry_price, current_price, target_price, stop_loss_price,
                 size_usd, unrealized_pnl, entry_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position['id'], position.get('trade_id', position['id']),
                position.get('market_id', ''), position.get('coin', ''),
                position.get('timeframe', 0), position.get('strategy', ''),
                position.get('direction', ''), position.get('token_id', ''),
                position.get('entry_price', 0), position.get('current_price', 0),
                position.get('target_price', 0), position.get('stop_loss_price', 0),
                position.get('size_usd', 0), position.get('unrealized_pnl', 0),
                position.get('entry_time', ''), position.get('status', 'open'),
            ))
            await db.commit()

    async def close_trade(self, trade_id: str, exit_price: float, pnl: float, reason: str):
        """Mark a trade as closed."""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE trades SET exit_price=?, pnl=?, exit_time=?, exit_reason=?, status='closed'
                WHERE id=?
            """, (exit_price, pnl, now, reason, trade_id))
            await db.execute("DELETE FROM positions WHERE id=?", (trade_id,))
            await db.commit()

    async def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM positions WHERE status='open'") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent closed trades."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT ?",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_strategy_stats(self, strategy: str, win: bool, pnl: float):
        """Update strategy performance stats."""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if exists
            async with db.execute("SELECT * FROM strategy_stats WHERE strategy=?", (strategy,)) as cur:
                row = await cur.fetchone()

            now = datetime.now().isoformat()
            if row:
                await db.execute("""
                    UPDATE strategy_stats
                    SET total_trades = total_trades + 1,
                        wins = wins + ?,
                        losses = losses + ?,
                        total_pnl = total_pnl + ?,
                        last_updated = ?
                    WHERE strategy = ?
                """, (1 if win else 0, 0 if win else 1, pnl, now, strategy))
            else:
                await db.execute("""
                    INSERT INTO strategy_stats (strategy, total_trades, wins, losses, total_pnl, last_updated)
                    VALUES (?, 1, ?, ?, ?, ?)
                """, (strategy, 1 if win else 0, 0 if win else 1, pnl, now))

            await db.commit()

    async def get_strategy_stats(self) -> List[Dict]:
        """Get performance stats for all strategies."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM strategy_stats ORDER BY total_pnl DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_daily_pnl(self, date: str = None) -> Optional[Dict]:
        """Get P&L for a specific date."""
        date = date or datetime.now().strftime('%Y-%m-%d')
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM daily_pnl WHERE date=?", (date,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
