"""Funding Rate Arbitrage Scanner — Binance vs Bybit.

Fetches perpetual futures funding rates from multiple exchanges and surfaces
pairs with large funding-rate gaps (potential delta-neutral arb).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Simple in-memory cache so we don't hammer exchange APIs on every refresh.
_CACHE: Dict[str, Any] = {"data": None, "ts": 0.0}
_CACHE_TTL = 30  # seconds

REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Exchange fetchers
# ---------------------------------------------------------------------------
def fetch_binance() -> Dict[str, Dict[str, Any]]:
    """Return dict keyed by base symbol (e.g. 'BTC') -> funding info."""
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    raw = r.json()

    out: Dict[str, Dict[str, Any]] = {}
    for row in raw:
        symbol = row.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        base = symbol[:-4]
        try:
            rate = float(row.get("lastFundingRate") or 0)
            mark = float(row.get("markPrice") or 0)
        except (TypeError, ValueError):
            continue
        next_funding = int(row.get("nextFundingTime") or 0)
        out[base] = {
            "rate": rate,
            "mark_price": mark,
            "next_funding": next_funding,
            "interval_hours": 8,  # Binance default
        }
    return out


def fetch_bybit() -> Dict[str, Dict[str, Any]]:
    """Return dict keyed by base symbol (e.g. 'BTC') -> funding info."""
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    if payload.get("retCode") != 0:
        raise RuntimeError(f"Bybit error: {payload.get('retMsg')}")

    out: Dict[str, Dict[str, Any]] = {}
    for row in payload["result"]["list"]:
        symbol = row.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        base = symbol[:-4]
        try:
            rate = float(row.get("fundingRate") or 0)
            mark = float(row.get("markPrice") or 0)
            interval = int(row.get("fundingIntervalHour") or 8)
        except (TypeError, ValueError):
            continue
        next_funding = int(row.get("nextFundingTime") or 0)
        out[base] = {
            "rate": rate,
            "mark_price": mark,
            "next_funding": next_funding,
            "interval_hours": interval,
        }
    return out


# ---------------------------------------------------------------------------
# Core scanner
# ---------------------------------------------------------------------------
def scan() -> Dict[str, Any]:
    """Fetch both exchanges, compute spreads, return scan result."""
    errors: List[str] = []
    binance: Dict[str, Dict[str, Any]] = {}
    bybit: Dict[str, Dict[str, Any]] = {}

    try:
        binance = fetch_binance()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Binance: {exc}")

    try:
        bybit = fetch_bybit()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Bybit: {exc}")

    common = sorted(set(binance.keys()) & set(bybit.keys()))
    rows: List[Dict[str, Any]] = []
    for base in common:
        b = binance[base]
        y = bybit[base]
        # Normalize to 8h-equivalent so different funding intervals are comparable.
        b_norm = b["rate"] * (8 / max(b["interval_hours"], 1))
        y_norm = y["rate"] * (8 / max(y["interval_hours"], 1))
        spread = y_norm - b_norm  # positive => Bybit pays more longs => short Bybit, long Binance
        # Strategy: long the side with lower (or more negative) funding, short the higher side.
        if spread > 0:
            long_ex, short_ex = "Binance", "Bybit"
        else:
            long_ex, short_ex = "Bybit", "Binance"
        rows.append(
            {
                "symbol": base,
                "binance_rate": b["rate"],
                "binance_rate_8h": b_norm,
                "binance_interval": b["interval_hours"],
                "binance_mark": b["mark_price"],
                "binance_next": b["next_funding"],
                "bybit_rate": y["rate"],
                "bybit_rate_8h": y_norm,
                "bybit_interval": y["interval_hours"],
                "bybit_mark": y["mark_price"],
                "bybit_next": y["next_funding"],
                "spread_8h": spread,
                "spread_abs_8h": abs(spread),
                "long_exchange": long_ex,
                "short_exchange": short_ex,
                # Annualized: 8h funding * 3 funding events/day * 365
                "apr_pct": abs(spread) * 3 * 365 * 100,
            }
        )

    rows.sort(key=lambda r: r["spread_abs_8h"], reverse=True)

    return {
        "rows": rows,
        "total_pairs": len(rows),
        "binance_pairs": len(binance),
        "bybit_pairs": len(bybit),
        "errors": errors,
        "timestamp": int(time.time() * 1000),
    }


def get_scan_cached() -> Dict[str, Any]:
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["ts"]) < _CACHE_TTL:
        cached = dict(_CACHE["data"])
        cached["cached"] = True
        cached["cache_age_seconds"] = round(now - _CACHE["ts"], 1)
        return cached
    fresh = scan()
    fresh["cached"] = False
    fresh["cache_age_seconds"] = 0
    _CACHE["data"] = fresh
    _CACHE["ts"] = now
    return fresh


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/scan")
def api_scan() -> Any:
    try:
        result = get_scan_cached()
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "rows": []}), 500


@app.route("/api/health")
def api_health() -> Any:
    return jsonify({"status": "ok", "timestamp": int(time.time() * 1000)})


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
