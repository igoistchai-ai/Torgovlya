import time
import ccxt
import pandas as pd
from config import settings

_exchange = getattr(ccxt, settings.exchange_id)({"enableRateLimit": True})
_cache = {}

def _cached(key):
    item = _cache.get(key)
    if item and time.time() - item[0] < settings.cache_seconds:
        return item[1]
    return None

def candles(symbol: str, timeframe: str, limit: int | None = None):
    limit = limit or settings.candle_limit
    key = (symbol.upper(), timeframe, limit)
    hit = _cached(key)
    if hit is not None:
        return hit
    rows = _exchange.fetch_ohlcv(symbol.upper(), timeframe=timeframe, limit=limit)
    if not rows:
        raise ValueError("DATA NOT AVAILABLE")
    df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    if ((df.high < df[["open","close"]].max(axis=1)) | (df.low > df[["open","close"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC data")
    result = {"df": df, "source": settings.exchange_id, "symbol": symbol.upper(), "timeframe": timeframe,
              "timestamp": df.timestamp.iloc[-1].isoformat()}
    _cache[key] = (time.time(), result)
    return result

def ticker(symbol: str):
    t = _exchange.fetch_ticker(symbol.upper())
    return {"price": t.get("last"), "timestamp": pd.to_datetime(t.get("timestamp"), unit="ms", utc=True).isoformat() if t.get("timestamp") else None}
