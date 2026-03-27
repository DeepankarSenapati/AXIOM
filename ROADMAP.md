# AXIOM Roadmap

## Phase 2 — Planned

- **CCXT live data feed** — Add `CCXTFeed` class using `ccxt.binance()` (public, read-only) to fetch real OHLCV candles. Expose `data_source: 'mock' | 'live'` option on the backtest endpoint so users can run strategies against real Binance history instead of generated mock prices. Timeframes: `1h`, `4h`, `1d`. Default symbol: `BTC/USDT`.
- Real exchange connectivity (Binance, Coinbase, Kraken)
- Real blockchain / Solidity smart contracts
- KYC / AML
- Celery task queue
- PostgreSQL migration
- Email / notifications
- No-code visual bot builder UI

## Phase 3 — Future

- Real money / real orders
- Public token offerings
- Regulatory filings
- Mobile app
