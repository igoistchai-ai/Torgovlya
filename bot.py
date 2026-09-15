import asyncio
import os
import tempfile
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ai import analyze
from chart import render
from config import settings
from indicators import compute
from market import candles, ticker
from patterns import candle_patterns, structure

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


def main_keyboard(symbol="BTC/USDT", tf="15m"):
    return InlineKeyboardMarkup(inline_keyboard=[
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
    ])


def token_keyboard(tf="15m"):
    rows = []
    for i in range(0, len(TOKENS), 2):
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"token|{symbol}|{tf}",
            )
            for symbol, label in TOKENS[i:i + 2]
        ])
    rows.append([InlineKeyboardButton(
        text="Назад",
        callback_data=f"back|BTC/USDT|{tf}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
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
    requested = ["4h", "1h", tf] if tf not in ("4h", "1h") else ["1d", tf]
    frames = {}

    for frame in dict.fromkeys(requested):
        data = candles(symbol, frame)
        df = data["df"]

        frames[frame] = {
            "candles": _json_safe(df.tail(250).to_dict("records")),
            "timestamp": data["timestamp"],
            "source": data["source"],
            "indicators": _json_safe(compute(df)),
            "candlestick_patterns": _json_safe(candle_patterns(df)),
            "structure": _json_safe(structure(df)),
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
        "ticker": _json_safe(tick),
        "frames": frames,
    }

    return analyze(payload)


def _value(result: dict, key: str, default="нет данных"):
    value = result.get(key, default)
    if value is None or value == "":
        return default
    return value


def format_result(result: dict, symbol: str, tf: str):
    if "raw" in result:
        return str(result["raw"])[:3900]

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

    bias = str(_value(result, "bias", "WAIT")).upper()
    status = str(_value(result, "setup_status", "WAIT")).upper()

    text = (
        f"{symbol} — {TIMEFRAME_LABELS.get(tf, tf)}\n"
        f"Цена: {_value(result, 'price')}\n"
        f"Время данных: {_value(result, 'timestamp')}\n"
        f"Состояние рынка: {_value(result, 'market_state')}\n\n"
        f"Основное направление: {bias_map.get(bias, bias)}\n"
        f"Статус сделки: {status_map.get(status, status)}\n\n"
        f"Вход: {_value(result, 'entry_zone')}\n"
        f"Инвалидация: {_value(result, 'invalidation')}\n"
        f"Стоп: {_value(result, 'stop_reference')}\n"
        f"TP1: {_value(result, 'tp1')}\n"
        f"TP2: {_value(result, 'tp2')}\n"
        f"TP3: {_value(result, 'tp3')}\n"
        f"Риск/прибыль: {_value(result, 'risk_reward')}\n\n"
        f"Рыночная структура:\n{_value(result, 'structure')}\n\n"
        f"Свечные модели:\n{_value(result, 'candle_patterns')}\n\n"
        f"Графические модели:\n{_value(result, 'chart_patterns')}\n\n"
        f"Ликвидность:\n{_value(result, 'liquidity')}\n\n"
        f"Объём:\n{_value(result, 'volume')}\n\n"
        f"Индикаторы:\n{_value(result, 'indicators')}\n\n"
        f"Деривативы:\n{_value(result, 'derivatives')}\n\n"
        f"Альтернативный сценарий:\n{_value(result, 'alternative_scenario')}\n\n"
        f"Уверенность: {_value(result, 'confidence_score')} / 100\n"
        f"Причина:\n{_value(result, 'reason')}\n\n"
        "Анализ не является гарантией результата торговли."
    )
    return text[:4000]


async def perform_analysis(message: Message, symbol: str, tf: str):
    try:
        await message.edit_text(
            "Проверяю данные OKX и запускаю анализ...",
            reply_markup=main_keyboard(symbol, tf),
        )
        result = await asyncio.to_thread(run_analysis, symbol, tf)
        await message.edit_text(
            format_result(result, symbol, tf),
            reply_markup=main_keyboard(symbol, tf),
        )
    except Exception as exc:
        print(f"Analysis error: {type(exc).__name__}: {exc}", flush=True)
        await message.edit_text(
            "Не удалось выполнить анализ.\n\n"
            "Рыночные данные или сервис анализа временно недоступны.\n"
            f"Техническая причина: {str(exc)[:700]}",
            reply_markup=main_keyboard(symbol, tf),
        )


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "CRYPTO VISION ANALYST\n\n"
        "Проверенные рыночные данные OKX и ИИ-анализ.\n\n"
        "Выберите монету и таймфрейм.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "/help")
async def help_command(message: Message):
    await message.answer(
        "Выберите монету, таймфрейм и режим анализа.\n"
        "Кнопка «Полный анализ» получает свежие данные OKX и передаёт их модели."
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
    await callback.message.edit_reply_markup(
        reply_markup=main_keyboard(symbol, tf)
    )


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
        data = await asyncio.to_thread(candles, symbol, tf)
        # Render the technical chart independently from AI response so a
        # temporary model problem does not prevent chart creation.
        try:
            result = await asyncio.to_thread(run_analysis, symbol, tf)
        except Exception as exc:
            print(f"Chart analysis warning: {exc}", flush=True)
            result = {"symbol": symbol, "timeframe": tf, "bias": "WAIT"}

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = tmp.name

        await asyncio.to_thread(
            render,
            data["df"],
            {**result, "symbol": symbol, "timeframe": tf},
            path,
        )

        await callback.message.answer_photo(
            FSInputFile(path),
            caption=f"Аналитический график {symbol} — {TIMEFRAME_LABELS.get(tf, tf)}",
        )
    except Exception as exc:
        print(f"Chart error: {type(exc).__name__}: {exc}", flush=True)
        await callback.message.answer(
            "Не удалось создать график.\n"
            f"Техническая причина: {str(exc)[:700]}"
        )
    finally:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass


@dp.errors()
async def global_error_handler(event):
    print(f"Telegram handler error: {event.exception}", flush=True)
    return True


async def main():
    # Local fallback only. Render uses run.py webhook.
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)
