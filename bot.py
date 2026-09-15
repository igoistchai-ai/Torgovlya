import asyncio, json, os, tempfile
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from config import settings
from market import candles, ticker
from indicators import compute
from patterns import candle_patterns, structure
from ai import analyze
from chart import render

bot=Bot(settings.telegram_token); dp=Dispatcher()
TF=["1m","5m","15m","1h","4h","1d","1w"]

def kb(symbol="BTC/USDT",tf="15m"):
    rows=[[InlineKeyboardButton(text="Select Token",callback_data="token"),InlineKeyboardButton(text="Refresh",callback_data=f"refresh|{symbol}|{tf}")]]
    rows += [[InlineKeyboardButton(text=x,callback_data=f"tf|{symbol}|{x}") for x in TF[:4]], [InlineKeyboardButton(text=x,callback_data=f"tf|{symbol}|{x}") for x in TF[4:]]]
    rows += [[InlineKeyboardButton(text="Full Analysis",callback_data=f"analyze|{symbol}|{tf}"),InlineKeyboardButton(text="Chart Image",callback_data=f"chart|{symbol}|{tf}")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def run_analysis(symbol,tf):
    pack={"asset":symbol,"symbol":symbol,"exchange":settings.exchange_id,"market_type":"spot","timeframe":tf}
    frames={}
    for t in (["4h","1h",tf] if tf not in ["4h","1h"] else ["1d",tf]):
        d=candles(symbol,t); frames[t]={"candles":d["df"].tail(250).to_dict("records"),"timestamp":d["timestamp"],"indicators":compute(d["df"]),"candlestick_patterns":candle_patterns(d["df"]),"structure":structure(d["df"])}
    pack["price"]=ticker(symbol)["price"]; pack["frames"]=frames
    return analyze(pack)

def format_result(r,symbol,tf):
    if "raw" in r: return r["raw"]
    def g(k,default="DATA NOT AVAILABLE"): return r.get(k,default)
    return (f"{symbol} — {tf}\nPrice: {g('price')}\nTimestamp: {g('timestamp')}\n"
            f"Market state: {g('market_state')}\n\nPrimary bias: {g('bias','WAIT')}\nSetup status: {g('setup_status','WAIT')}\n\n"
            f"Entry: {g('entry_zone')}\nInvalidation: {g('invalidation')}\nStop reference: {g('stop_reference')}\n"
            f"TP1: {g('tp1')}\nTP2: {g('tp2')}\nTP3: {g('tp3')}\nRisk/Reward: {g('risk_reward')}\n\n"
            f"Market structure:\n{g('structure')}\n\nCandlestick:\n{g('candle_patterns')}\n\n"
            f"Chart patterns:\n{g('chart_patterns')}\n\nLiquidity:\n{g('liquidity')}\n\nVolume:\n{g('volume')}\n\n"
            f"Indicators:\n{g('indicators')}\n\nDerivatives:\n{g('derivatives')}\n\n"
            f"Alternative scenario:\n{g('alternative_scenario')}\n\nConfidence: {g('confidence_score')} / 100\n"
            f"Reason:\n{g('reason')}\n\nThis is market analysis, not a guarantee of future performance.")

@dp.message(CommandStart())
async def start(m:Message):
    await m.answer("Crypto Vision Analyst\nSelect timeframe and run a full market analysis.",reply_markup=kb())

@dp.callback_query(F.data.startswith("tf|"))
async def tf(c:CallbackQuery):
    _,symbol,t=c.data; await c.message.edit_reply_markup(reply_markup=kb(symbol,t)); await c.answer()

@dp.callback_query(F.data.startswith("analyze|"))
async def analysis(c:CallbackQuery):
    _,symbol,t=c.data; await c.answer("Analyzing")
    try:
        r=await asyncio.to_thread(run_analysis,symbol,t)
        await c.message.edit_text(format_result(r,symbol,t),reply_markup=kb(symbol,t))
    except Exception as e: await c.message.edit_text(f"DATA NOT AVAILABLE\n{e}",reply_markup=kb(symbol,t))

@dp.callback_query(F.data.startswith("chart|"))
async def chart(c:CallbackQuery):
    _,symbol,t=c.data; await c.answer("Rendering")
    try:
        r=await asyncio.to_thread(run_analysis,symbol,t)
        import pathlib
        d=candles(symbol,t)["df"]
        with tempfile.NamedTemporaryFile(suffix=".png",delete=False) as f: path=f.name
        render(d,{**r,"symbol":symbol,"timeframe":t},path)
        await c.message.answer_photo(FSInputFile(path),caption="Analytical chart generated from verified OHLCV data.")
        os.unlink(path)
    except Exception as e: await c.message.answer(f"Image generation failed: {e}")

@dp.callback_query(F.data.startswith("refresh|"))
async def refresh(c:CallbackQuery):
    _,symbol,t=c.data; await c.answer("Refreshed"); await analysis(c)

async def main(): await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
