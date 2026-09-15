import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ai import analyze
from chart import render
from config import settings
from indicators import compute
from market import candles, ticker
from patterns import candle_patterns, structure

bot = Bot(settings.telegram_token)
dp = Dispatcher()

APP_URL = os.getenv("WEBAPP_URL", "https://torgovlya-1.onrender.com/app").rstrip("/")
SITE_URL = "https://torgovlya-1.onrender.com"


def webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать анализ", web_app=WebAppInfo(url=APP_URL))],
            [InlineKeyboardButton(text="Открыть сайт", url=SITE_URL)],
        ]
    )


def _safe(value):
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def run_analysis(symbol: str, tf: str):
    """Shared analysis function used by the Telegram bot and the Mini App API."""
    frames = {}
    for frame in dict.fromkeys(["1d", "4h", "1h", tf]):
        df = candles(symbol, frame)
        frames[frame] = {
            "candles": _safe(df.tail(250).to_dict("records")),
            "timestamp": df["timestamp"].iloc[-1].isoformat(),
            "source": "OKX",
            "indicators": _safe(compute(df)),
            "candlestick_patterns": _safe(candle_patterns(df)),
            "structure": _safe(structure(df)),
        }

    tick = ticker(symbol)
    payload = {
        "asset": symbol,
        "symbol": symbol,
        "exchange": "OKX",
        "market_type": "spot",
        "timeframe": tf,
        "price": tick["price"],
        "timestamp": tick["timestamp"],
        "ticker": _safe(tick),
        "frames": frames,
    }
    result = analyze(payload)
    if not isinstance(result, dict):
        result = {"raw": str(result)}
    result.setdefault("symbol", symbol)
    result.setdefault("timeframe", tf)
    result.setdefault("price", tick["price"])
    result.setdefault("timestamp", tick["timestamp"])
    result.setdefault("source", "OKX")
    return _safe(result)


@dp.message(CommandStart())
async def start(message: Message):
    text = (
        "Вас приветствует ваш учёный NEZZX.\n\n"
        "Перейди сюда, чтобы начать зарабатывать."
    )
    await message.answer(text, reply_markup=webapp_keyboard())


@dp.message()
async def fallback(message: Message):
    await message.answer(
        "Открой NEZZX GRAFIK и запусти анализ рынка.",
        reply_markup=webapp_keyboard(),
    )


async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)
