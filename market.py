import time
from typing import Any

import httpx
import pandas as pd

from config import settings

# Primary public market-data source: OKX.
# Public market endpoints do not require API keys.
OKX_BASE_URL = "https://www.okx.com"
OKX_CANDLES_URL = f"{OKX_BASE_URL}/api/v5/market/candles"
OKX_TICKER_URL = f"{OKX_BASE_URL}/api/v5/market/ticker"

# OKX uses uppercase timeframe names for some intervals.
_TIMEFRAME_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "2d": "2D",
    "3d": "3D",
    "1w": "1W",
}

# Keep the process small and predictable. httpx is already a project dependency.
_client = httpx.Client(
    timeout=httpx.Timeout(15.0, connect=8.0),
    headers={"User-Agent": "CryptoVisionAnalyst/1.0"},
)
_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}


def _cached(key):
    item = _cache.get(key)
    if item and time.time() - item[0] < settings.cache_seconds:
        return item[1]
    return None


def _okx_symbol(symbol: str) -> str:
    value = symbol.strip().upper().replace("_", "/")
    if ":" in value:
        value = value.split(":", 1)[0]
    if "/" in value:
        base, quote = value.split("/", 1)
        return f"{base}-{quote}"
    if value.endswith("USDT") and len(value) > 4:
        return f"{value[:-4]}-USDT"
    if value.endswith("USDC") and len(value) > 4:
        return f"{value[:-4]}-USDC"
    raise ValueError("Неверный формат торговой пары")


def _display_symbol(symbol: str) -> str:
    return _okx_symbol(symbol).replace("-", "/")


def _timeframe(timeframe: str) -> str:
    key = timeframe.strip().lower()
    if key not in _TIMEFRAME_MAP:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")
    return _TIMEFRAME_MAP[key]


def _request(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = _client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Не удалось получить рыночные данные: OKX HTTP {exc.response.status_code}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Не удалось подключиться к OKX для получения рыночных данных") from exc

    if not isinstance(payload, dict) or payload.get("code") != "0":
        message = payload.get("msg") if isinstance(payload, dict) else None
        # Do not forward huge/raw exchange responses to Telegram.
        raise RuntimeError(f"OKX не вернул рыночные данные{f': {message}' if message else ''}")
    return payload


def _validate_ohlc(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("Рыночные данные пусты")

    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("Нарушен порядок свечей")

    bad = (
        (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df[["open", "high", "low", "close", "volume"]] < 0).any(axis=1)
    )
    if bad.any():
        raise ValueError("OKX вернул некорректные OHLCV данные")

    if df["timestamp"].duplicated().any():
        raise ValueError("Обнаружены дублирующиеся свечи")


def candles(symbol: str, timeframe: str, limit: int | None = None):
    requested_limit = limit or settings.candle_limit
    # OKX public candles endpoint allows up to 1440 recent entries.
    requested_limit = max(10, min(int(requested_limit), 1440))

    inst_id = _okx_symbol(symbol)
    bar = _timeframe(timeframe)
    key = ("okx", inst_id, bar, requested_limit)
    hit = _cached(key)
    if hit is not None:
        return hit

    payload = _request(
        OKX_CANDLES_URL,
        {"instId": inst_id, "bar": bar, "limit": str(requested_limit)},
    )

    rows = payload.get("data") or []
    if not rows:
        raise ValueError("OKX не вернул свечи для выбранной пары")

    # OKX candle row:
    # [timestamp, open, high, low, close, volume, volCcy, volCcyQuote, confirm]
    parsed = []
    for row in rows:
        if len(row) < 6:
            continue
        parsed.append(
            [
                int(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ]
        )

    if not parsed:
        raise ValueError("OKX вернул свечи в неожиданном формате")

    df = pd.DataFrame(
        parsed,
        columns=["timestamp_ms", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
    df = df.drop(columns=["timestamp_ms"]).sort_values("timestamp").drop_duplicates("timestamp")
    df = df.reset_index(drop=True)

    _validate_ohlc(df)

    result = {
        "df": df,
        "source": "okx",
        "symbol": _display_symbol(symbol),
        "timeframe": timeframe,
        "timestamp": df["timestamp"].iloc[-1].isoformat(),
    }
    _cache[key] = (time.time(), result)
    return result


def ticker(symbol: str):
    inst_id = _okx_symbol(symbol)
    key = ("okx-ticker", inst_id)
    hit = _cached(key)
    if hit is not None:
        return hit

    payload = _request(OKX_TICKER_URL, {"instId": inst_id})
    rows = payload.get("data") or []
    if not rows:
        raise ValueError("OKX не вернул текущую цену")

    item = rows[0]
    try:
        price = float(item["last"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("OKX вернул некорректную текущую цену") from exc

    timestamp = item.get("ts")
    result = {
        "price": price,
        "timestamp": pd.to_datetime(int(timestamp), unit="ms", utc=True).isoformat()
        if timestamp
        else None,
        "source": "okx",
        "symbol": _display_symbol(symbol),
    }
    _cache[key] = (time.time(), result)
    return result
