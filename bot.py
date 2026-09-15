import asyncio
import os
import tempfile
from typing import Dict, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from config import settings
from market import candles, ticker
from indicators import compute
from patterns import candle_patterns, structure
from ai import analyze
from chart import render

bot = Bot(settings.telegram_token)
dp = Dispatcher()

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
TIMEFRAME_LABELS = {
    "1m": "1м",
    "5m": "5м",
    "15m": "15м",
    "1h": "1ч",
    "4h": "4ч",
    "1d": "1д",
    "1w": "1н",
}
TOKENS = [
    ("BTC/USDT", "BTC"),
    ("ETH/USDT", "ETH"),
    ("LTC/USDT", "LTC"),
    ("SOL/USDT", "SOL"),
    ("BNB/USDT", "BNB"),
    ("XRP/USDT", "XRP"),
    ("DOGE/USDT", "DOGE"),
    ("ADA/USDT", "ADA"),
]


def main_keyboard(symbol: str = "BTC/USDT", tf: str = "15m") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Выбрать монету", callback_data="tokens"),
            InlineKeyboardButton(text="Обновить", callback_data=f"refresh|{symbol}|{tf}"),
        ],
        [
            InlineKeyboardButton(text=TIMEFRAME_LABELS[x], callback_data=f"tf|{symbol}|{x}")
            for x in TIMEFRAMES[:4]
        ],
        [
            InlineKeyboardButton(text=TIMEFRAME_LABELS[x], callback_data=f"tf|{symbol}|{x}")
            for x in TIMEFRAMES[4:]
        ],
        [
            InlineKeyboardButton(text="Полный анализ", callback_data=f"analyze|{symbol}|{tf}"),
            InlineKeyboardButton(text="График", callback_data=f"chart|{symbol}|{tf}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def token_keyboard(tf: str = "15m") -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(TOKENS), 2):
        row = []
        for symbol, label in TOKENS[i:i + 2]:
            row.append(InlineKeyboardButton(text=label, callback_data=f"token|{symbol}|{tf}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"back|BTC/USDT|{tf}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def run_analysis(symbol: str, tf: str):
    pack = {
        "asset": symbol,
        "symbol": symbol,
        "exchange": settings.exchange_id,
        "market_type": "spot",
        "timeframe": tf,
    }
    frames = {}
    requested = ["4h", "1h", tf] if tf not in ["4h", "1h"] else ["1d", tf]
    for frame in dict.fromkeys(requested):
        data = candles(symbol, frame)
        frames[frame] = {
            "candles": data["df"].tail(250).to_dict("records"),
            "timestamp": data["timestamp"],
            "indicators": compute(data["df"]),
            "candlestick_patterns": candle_patterns(data["df"]),
            "structure": structure(data["df"]),
        }
    tick = ticker(symbol)
    pack["price"] = tick["price"]
    pack["timestamp"] = tick.get("timestamp")
    pack["frames"] = frames
    return analyze(pack)


def _value(r: dict, key: str, default: str = "нет данных"):
    value = r.get(key, default)
    if value is None or value == "":
        return default
    return value


def format_result(r: dict, symbol: str, tf: str) -> str:
    if "raw" in r:
        return str(r["raw"])

    bias_map = {
        "LONG": "ЛОНГ",
        "SHORT": "ШОРТ",
        "NEUTRAL": "НЕЙТРАЛЬНО",
        "WAIT": "ОЖИДАНИЕ",
    }
    status_map = {
        "CONFIRMED": "ПОДТВЕРЖДЕНО",
        "FORMING": "ФОРМИРУЕТСЯ",
        "WAIT": "ОЖИДАНИЕ",
    }

    bias = str(_value(r, "bias", "WAIT")).upper()
    status = str(_value(r, "setup_status", "WAIT")).upper()

    return (
        f"{symbol} — {TIMEFRAME_LABELS.get(tf, tf)}\n"
        f"Цена: {_value(r, 'price')}\n"
        f"Время данных: {_value(r, 'timestamp')}\n"
        f"Состояние рынка: {_value(r, 'market_state')}\n\n"
        f"Основное направление: {bias_map.get(bias, bias)}\n"
        f"Статус сделки: {status_map.get(status, status)}\n\n"
        f"Вход: {_value(r, 'entry_zone')}\n"
        f"Инвалидация: {_value(r, 'invalidation')}\n"
        f"Стоп: {_value(r, 'stop_reference')}\n"
        f"TP1: {_value(r, 'tp1')}\n"
        f"TP2: {_value(r, 'tp2')}\n"
        f"TP3: {_value(r, 'tp3')}\n"
        f"Риск/прибыль: {_value(r, 'risk_reward')}\n\n"
        f"Рыночная структура:\n{_value(r, 'structure')}\n\n"
        f"Свечные модели:\n{_value(r, 'candle_patterns')}\n\n"
        f"Графические модели:\n{_value(r, 'chart_patterns')}\n\n"
        f"Ликвидность:\n{_value(r, 'liquidity')}\n\n"
        f"Объём:\n{_value(r, 'volume')}\n\n"
        f"Индикаторы:\n{_value(r, 'indicators')}\n\n"
        f"Деривативы:\n{_value(r, 'derivatives')}\n\n"
        f"Альтернативный сценарий:\n{_value(r, 'alternative_scenario')}\n\n"
        f"Уверенность: {_value(r, 'confidence_score')} / 100\n"
        f"Причина:\n{_value(r, 'reason')}\n\n"
        "Анализ является условным и не гарантирует результат торговли."
    )


async def perform_analysis(message, symbol: str, tf: str):
    try:
        await message.edit_text("Проверяю рыночные данные...", reply_markup=main_keyboard(symbol, tf))
        result = await asyncio.to_thread(run_analysis, symbol, tf)
        await message.edit_text(format_result(result, symbol, tf), reply_markup=main_keyboard(symbol, tf))
    except Exception as exc:
        await message.edit_text(
            "Не удалось выполнить анализ.\n\n"
            f"Причина: {str(exc)[:1500]}",
            reply_markup=main_keyboard(symbol, tf),
        )


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "CRYPTO VISION ANALYST\n\n"
        "Анализ криптовалютного рынка на основе проверенных рыночных данных.\n\n"
        "Выберите монету и таймфрейм.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data == "tokens")
async def tokens_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "Выберите монету:",
        reply_markup=token_keyboard("15m"),
    )


@dp.callback_query(F.data.startswith("token|"))
async def token_callback(callback: CallbackQuery):
    _, symbol, tf = callback.data.split("|", 2)
    await callback.answer()
    await callback.message.edit_text(
        f"Выбрана монета: {symbol}\nТаймфрейм: {TIMEFRAME_LABELS.get(tf, tf)}",
        reply_markup=main_keyboard(symbol, tf),
    )


@dp.callback_query(F.data.startswith("back|"))
async def back_callback(callback: CallbackQuery):
    _, symbol, tf = callback.data.split("|", 2)
    await callback.answer()
    await callback.message.edit_text(
        "Главное меню",
        reply_markup=main_keyboard(symbol, tf),
    )


@dp.callback_query(F.data.startswith("tf|"))
async def timeframe_callback(callback: CallbackQuery):
    _, symbol, tf = callback.data.split("|", 2)
    await callback.answer(f"Таймфрейм: {TIMEFRAME_LABELS.get(tf, tf)}")
    await callback.message.edit_reply_markup(reply_markup=main_keyboard(symbol, tf))


@dp.callback_query(F.data.startswith("analyze|"))
async def analysis_callback(callback: CallbackQuery):
    _, symbol, tf = callback.data.split("|", 2)
    await callback.answer("Запускаю анализ")
    await perform_analysis(callback.message, symbol, tf)


@dp.callback_query(F.data.startswith("refresh|"))
async def refresh_callback(callback: CallbackQuery):
    _, symbol, tf = callback.data.split("|", 2)
    await callback.answer("Обновляю данные")
    await perform_analysis(callback.message, symbol, tf)


@dp.callback_query(F.data.startswith("chart|"))
async def chart_callback(callback: CallbackQuery):
    _, symbol, tf = callback.data.split("|", 2)
    await callback.answer("Создаю график")
    path = None
    try:
        result = await asyncio.to_thread(run_analysis, symbol, tf)
        data = await asyncio.to_thread(candles, symbol, tf)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = tmp.name
        await asyncio.to_thread(render, data["df"], {**result, "symbol": symbol, "timeframe": tf}, path)
        await callback.message.answer_photo(
            FSInputFile(path),
            caption=f"Аналитический график {symbol} — {TIMEFRAME_LABELS.get(tf, tf)}",
        )
    except Exception as exc:
        await callback.message.answer(
            f"Не удалось создать график.\nПричина: {str(exc)[:1500]}"
        )
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


async def main():
    # Для локального запуска. На Render используется webhook через run.py.
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
