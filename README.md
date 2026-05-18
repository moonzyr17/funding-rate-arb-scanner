# Funding Rate Arb Scanner 📈

> Real-time perpetual futures funding rate arbitrage scanner across **Binance** and **Bybit**. Spot delta-neutral opportunities ranked by 8h-normalized spread and annualized APR.

[![Live Demo](https://img.shields.io/badge/Live-Demo-22c55e?style=flat-square)](https://web-production-862ee.up.railway.app)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

## Demo

🔗 **[https://web-production-862ee.up.railway.app](https://web-production-862ee.up.railway.app)**

![Funding Rate Arb Scanner](https://img.shields.io/badge/Pairs%20Scanned-500%2B-7dd3fc?style=for-the-badge)

## What it does

Funding-rate arbitrage is a delta-neutral strategy: long a perp on one exchange and short the same perp on another exchange whose funding rate is significantly higher. You collect the spread on every funding interval (typically 3× per day) regardless of price direction.

This scanner:

- Pulls live funding rates for every USDT-margined perpetual on **Binance** (737+ pairs) and **Bybit** (660+ pairs).
- **Normalizes to 8h** because Bybit funding intervals can be 4h or 8h depending on the asset.
- Computes the spread, sorts by absolute magnitude, and shows the **suggested long/short side**.
- Estimates **annualized APR** from funding alone (excludes fees, slippage, basis risk).

## Features

- 🔄 **Auto-refresh** every 30s with 30s in-memory cache to respect rate limits
- 🔍 **Symbol search** + **min-spread filter** for quick triage
- ↕️ **Click any column header to sort** — Symbol, Binance rate, Bybit rate, Spread, APR
- 📊 Color-coded rates (green for positive, red for negative)
- 📱 Mobile-friendly dark UI with sticky stats
- 🧮 8h-normalized spread + per-side rates side by side
- ⚡ Pure server-side fetch — no API keys, no signups, no rate-limit headaches for the user

## Stack

- **Backend** — Flask + `requests`
- **Frontend** — Tailwind (CDN) + vanilla JS
- **Deploy** — Railway (`gunicorn` via `Procfile`)
- **Data** — Public REST endpoints, no authentication required

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web dashboard |
| `/api/scan` | GET | Full scan: `{rows, total_pairs, binance_pairs, bybit_pairs, errors, timestamp, cached}` |
| `/api/health` | GET | Health check |

### Sample response

```json
{
  "total_pairs": 503,
  "binance_pairs": 692,
  "bybit_pairs": 561,
  "rows": [
    {
      "symbol": "EDEN",
      "binance_rate_8h": -0.002653,
      "bybit_rate_8h": -0.010535,
      "spread_8h": -0.007881,
      "apr_pct": 863.0,
      "long_exchange": "Bybit",
      "short_exchange": "Binance"
    }
  ],
  "cached": false,
  "timestamp": 1779080443000
}
```

## Local setup

```bash
git clone https://github.com/moonzyr17/funding-rate-arb-scanner.git
cd funding-rate-arb-scanner

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app.py
# → http://localhost:5000
```

No environment variables required.

## Data sources

| Exchange | Endpoint | Rate limit |
|---|---|---|
| Binance | `GET fapi.binance.com/fapi/v1/premiumIndex` | 1 req/s plenty |
| Bybit | `GET api.bybit.com/v5/market/tickers?category=linear` | 600 req/5s |

Both endpoints are public and require no API keys.

## How spreads work

```
Long  ←  the side with LOWER funding (you pay less or get paid more)
Short ←  the side with HIGHER funding (you collect more or pay less)
```

Example: if Binance funding = +0.01% and Bybit funding = +0.20%, shorts on Bybit collect more than longs on Binance pay → **long Binance, short Bybit**, net +0.19% per 8h ≈ 207% APR (before fees).

## Caveats

- APR assumes the spread persists across all funding intervals — in reality it mean-reverts.
- Excludes maker/taker fees (~0.02–0.05% per side), borrow rates, and slippage.
- Cross-exchange execution requires margin on both venues and adds operational risk.
- Funding rates can flip direction within a single 8h window.

**Educational tool. Not financial advice.**

## License

MIT — see [LICENSE](LICENSE).
