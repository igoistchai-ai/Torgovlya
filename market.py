import time
from typing import Any

import ccxt
import pandas as pd

from config import settings

# OKX is used as the public market-data source.
# No OKX API key is required for public market data.
_exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {
        "defaultType": "spot",
    },
})

_market_cache = None
_market_cache_at = 0.0


def _load_markets():
    global _market_cache, _market_cache_at

    now = time.time()
    if _market_cache is not None and now - _market_cache_at < 3600:
        return _market_cache

    try:
        _market_cache = _exchange.load_markets()
        _market_cache_at = now
        return _market_cache
    except Exception as exc:
        raise RuntimeError(f"Не удалось загрузить список рынков OKX: {exc}") from exc


def _normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper().replace("-", "/").replace("_", "/")

    if "/" not in symbol and symbol.endswith("USDT"):
        symbol = symbol[:-4] + "/USDT"

    return symbol


def _validate_symbol(symbol: str) -> str:
    symbol = _normalize_symbol(symbol)
    markets = _load_markets()

    if symbol not in markets:
        raise ValueError(f"Пара {symbol} недоступна на OKX")

    market = markets[symbol]
    if not market.get("spot", False):
        raise ValueError(f"Пара {symbol} не является спотовой парой OKX")

    return symbol


def candles(symbol: str, timeframe: str, limit: int | None = None) -> pd.DataFrame:
    """Fetch and validate OHLCV candles from OKX through CCXT."""

    symbol = _validate_symbol(symbol)
    limit = int(limit or getattr(settings, "candle_limit", 500))

    if limit < 50:
        limit = 50
    if limit > 1000:
        limit = 1000

    try:
        rows = _exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit,
        )
    except Exception as exc:
        raise RuntimeError(
            f"OKX не вернул свечи для {symbol} ({timeframe})."
        ) from exc

    if not rows:
        raise RuntimeError(f"OKX вернул пустые данные для {symbol} ({timeframe}).")

    df = pd.DataFrame(
        rows,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # Remove malformed rows.
    df = df.dropna(subset=numeric_columns).copy()

    # Validate OHLC relationships.
    valid_ohlc = (
        (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
        & (df["high"] >= df["low"])
        & (df["volume"] >= 0)
    )
    df = df.loc[valid_ohlc].copy()

    # Sort, remove duplicate timestamps and reset index.
    df = (
        df.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )

    if len(df) < 20:
        raise RuntimeError(
            f"Недостаточно корректных свечей OKX для {symbol} ({timeframe})."
        )

    return df


def ticker(symbol: str) -> dict[str, Any]:
    """Fetch current ticker from OKX through CCXT."""

    symbol = _validate_symbol(symbol)

    try:
        data = _exchange.fetch_ticker(symbol)
    except Exception as exc:
        raise RuntimeError(f"OKX не вернул текущую цену для {symbol}.") from exc

    last = data.get("last")
    if last is None:
        raise RuntimeError(f"OKX не вернул цену для {symbol}.")

    return {
        "symbol": symbol,
        "last": float(last),
        "bid": float(data["bid"]) if data.get("bid") is not None else None,
        "ask": float(data["ask"]) if data.get("ask") is not None else None,
        "high": float(data["high"]) if data.get("high") is not None else None,
        "low": float(data["low"]) if data.get("low") is not None else None,
        "volume": float(data["baseVolume"]) if data.get("baseVolume") is not None else None,
        "timestamp": data.get("timestamp"),
        "datetime": data.get("datetime"),
        "source": "OKX",
    }


def market_snapshot(symbol: str, timeframe: str, limit: int | None = None) -> dict[str, Any]:
    """Return a compact validated market package for the AI analyzer."""

    df = candles(symbol, timeframe, limit=limit)
    tick = ticker(symbol)

    latest = df.iloc[-1]

    return {
        "source": "OKX",
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "timestamp": tick.get("timestamp") or int(latest["timestamp"].timestamp() * 1000),
        "ticker": tick,
        "candles": [
            {
                "timestamp": int(row["timestamp"].timestamp() * 1000),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for _, row in df.iterrows()
        ],
    }
