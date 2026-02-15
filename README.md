# 5min_trade ⚡

Polymarket crypto scalper bot for 5-min, 15-min, and 30-min Up/Down markets.

## Features
- **5 Trading Strategies**: Flash Crash, Oracle Arb, YES+NO Arb, Time Decay, Dynamic Auto-Picker
- **Telegram Integration**: Full command interface for paper trading
- **Dual Price Feeds**: Polymarket WebSocket + Binance real-time prices
- **Risk Management**: Kelly Criterion sizing, daily loss limits, cooldowns
- **Paper Trading**: Simulated execution with realistic slippage

## Quick Start

```bash
# 1. Clone and install
cd 5min_trade
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your Telegram bot token

# 3. Run
python app.py
```

## Telegram Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome + status |
| `/trade` | Start trading (select timeframe) |
| `/stop` | Stop trading |
| `/status` | Positions & P&L |
| `/balance` | Balance details |
| `/strategy` | View/change strategy |
| `/markets` | Scan live markets |
| `/history` | Trade history |

## Strategies

| # | Strategy | Edge | Best For |
|---|----------|------|----------|
| 🔴 | Flash Crash | Buy panic drops (0.25+ in 10s) | 5m, 15m |
| 🎯 | Oracle Arb | Binance price vs Polymarket probability | 5m, 15m, 30m |
| 💰 | YES+NO Arb | Buy both sides when total < $1.00 | All |
| ⏰ | Time Decay | Near-expiry discounted outcomes | All |
| ⚡ | Dynamic | Auto-select best per market condition | All |

## Project Structure
```
5min_trade/
├── app.py              # Entry point
├── config.py           # Configuration
├── data/               # Market data layer
│   ├── gamma_client.py
│   ├── clob_client.py
│   ├── websocket_feed.py
│   └── database.py
├── strategies/         # 5 trading strategies
│   ├── flash_crash.py
│   ├── oracle_arb.py
│   ├── yes_no_arb.py
│   ├── time_decay.py
│   └── dynamic_picker.py
├── trading/            # Execution engine
│   ├── paper_trader.py
│   ├── risk_manager.py
│   └── live_trader.py
└── bot/                # Telegram bot
    ├── main.py
    └── keyboards/
```
