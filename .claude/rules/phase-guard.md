# Phase Guard

## Phase 1 — Building NOW (local MVP)
✅ Paper trading bot arena (simulated prices)
✅ Blind backtesting engine
✅ Simulated tokenomics (SQLite, no blockchain)
✅ Governance voting logic (stages 1-2-3)
✅ FastAPI REST backend
✅ React dashboard (basic)
✅ Mock market data feed
✅ Bot registry + validator
✅ Two example strategies (MovingAverage, RSI)
✅ CCXT read-only historical data (public endpoints, no API keys, no orders)

## Phase 2 — NOT YET
❌ Real blockchain / Solidity smart contracts
❌ Real exchange connectivity (Binance, Coinbase, Kraken) — live orders, real money
❌ CCXT live trading / real orders (read-only historical data via CCXT is ✅ Phase 1 OK)
❌ KYC / AML
❌ Celery task queue
❌ PostgreSQL (stay on SQLite)
❌ Email / notifications
❌ No-code visual bot builder UI

## Phase 3 — FUTURE
❌ Real money / real orders
❌ Public token offerings
❌ Regulatory filings
❌ Mobile app

## IF ASKED TO BUILD SOMETHING FROM PHASE 2 or 3:
Respond: "That's Phase 2+. Adding to ROADMAP.md. Staying on Phase 1."
Then append the item to `ROADMAP.md` and stop.
Do not implement it. Do not partially implement it.
