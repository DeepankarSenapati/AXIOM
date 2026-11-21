# AXIOM Survival Lab — local demo

Survival Lab is a prototype for examining how a rule-based strategy behaves
under explicit hypothetical conditions. All prices in this lab are generated
locally. It does not place orders or use real money, exchange data, AI models,
or blockchain. Figures are simulated outcomes, not predictions.

## Run it

Use Python 3.11 or 3.12 and Node.js 20.19+ or 22.12+. Install Python 3.12
first if `python3.12 --version` is unavailable; the example below uses that
interpreter explicitly. From a fresh checkout of `holylarp`, open two terminals:

```bash
# Terminal 1 — from the project root
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Terminal 2 — from the project root
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. The first
startup seeds local demo accounts when the user table is empty; choose
**Explore demo credentials** on the sign-in screen. For example, the admin
demo uses `admin@axiom.com` and `admin123`. These are intentionally public
demo credentials; the app is not configured for production or public access.
The local SQLite database and seed state persist between runs.

If your own working copy moved the dependency file to `backend/requirements.txt`,
use that path in the `pip install -r ...` command. The committed checkout
still contains the root `requirements.txt`.

To check the project:

```bash
# With the virtual environment activated, from the project root
python -m pytest tests/ -q
cd frontend
npm run test:passport
npm run build
```

## Suggested demo

1. Open **Survival Lab** and run the default RSI experiment. It compares a
   baseline and a 12% hypothetical gap on the same seeded random factors.
2. Move the replay to candle 91. Read the bot's signal and the guard event;
   the guard pauses new buys after the threshold, but does not force a sale.
3. Generate Synthetic Worlds. Review each seed, including cases in which
   the guard worsens final equity, then load one world and replay it.
4. Generate Shock Landscape to compare a small grid of gap sizes and fees.
   Check prior-close exposure and blocked signals, then load a cell for replay.
5. Download the JSON passport for the current single experiment. It includes
   its inputs, assumptions, candles, decisions, and portfolio paths.
6. Open **Replay a saved passport**, select that file, and explicitly replay it.
   The interface compares the recorded baseline and scenario fingerprints with
   a new calculation; it displays the newly calculated results, not stored
   results from the file. Files are limited to 5 MiB and requests to the
   settings supported by this screen. A matching fingerprint does not prove
   the file's contents, source code, outputs, or execution are authentic.

The guard and strategy are not guaranteed to protect capital. Buy-and-hold
uses all starting cash, while the bot has a position cap, so their risks are
not matched. Results can change with the seed, parameters, model, and costs.

## How the lab calculates its results

- The generator produces daily synthetic OHLCV candles from a seed. A shock is
  one downward gap at a selected open. The baseline and shocked tapes use the
  same random factors but differ in prices from the gap onward.
- A bot sees only the current and earlier candles. A signal at the close may
  fill at the next candle's open, with adverse slippage and a fee on each fill.
  A final-candle signal cannot fill. Open holdings are marked at the final
  close without forced liquidation or estimated future exit costs.
- Buy signals request a configured fraction of cash; execution separately
  enforces the position cap. The guard, when enabled, permanently pauses new
  buys after the drawdown threshold is met at a close. Sells remain possible.
- Buy-and-hold enters at the first eligible next open using the same entry
  costs, but uses all available cash. No strategy is risk-matched to it.
- Synthetic Worlds runs up to 12 consecutive seeds with at most 240 candles
  each. It reports only this sample's actual results; a chosen seed can be
  rerun for its complete event trace. Counts and medians are descriptive, not
  probabilities, historical validation, or out-of-sample evidence.
- Shock Landscape runs up to nine combinations of shock and per-fill fee on
  a single synthetic seed, with at most 160 candles each. The cells share
  random factors, not identical post-shock prices. Prior-close exposure does
  not include pending orders that may fill at the shock open; a flat position
  before the gap is not proof of crash resilience. Zero fee retains the
  separately configured slippage.
- The fingerprint hashes the request, generated candles, declared strategy
  parameters, sizing assumption, and manually maintained engine version. It
  is useful for matching reruns under the same implementation, but it is not
  a source-code hash, a signature, independent verification, or proof that a
  run occurred. Share the code and dependencies alongside the passport.

The older Bot Arena remains available and uses different execution assumptions:
same-candle fills, no fees or slippage, and a fixed 252-period annualization
for Sharpe. Its results should not be mixed with Survival Lab results.

This is a local demonstration. Default credentials, simulated wallets,
in-process resource limits, and the existing database are not a production
security or compliance design. Consult qualified counsel before presenting
trading-performance claims or offering an actual financial product.
