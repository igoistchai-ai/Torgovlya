# CRYPTO VISION ANALYST — Telegram Bot

Production-oriented Render worker for a Telegram crypto-analysis bot.

## Structure
All files are intentionally in the repository root so they can be uploaded without folders.

## Included
- Telegram bot with token selection and timeframes: 1m/5m/15m/1h/4h/1d/1w.
- CCXT live OHLCV/ticker acquisition with validation and short cache.
- Multi-timeframe context.
- Technical indicators: EMA/SMA/RSI/ATR/MACD/Bollinger/volume.
- Large rule-based candlestick registry and chart/structure pattern engine.
- Order book imbalance, funding, open interest and Binance futures liquidation data when available.
- Optional news endpoint through NEWS_URL.
- User chart screenshot analysis through OpenAI vision input.
- Data-faithful generated chart with Entry/Stop/TP levels when returned as numeric levels.
- LONG/SHORT/NEUTRAL/WAIT decision discipline and confidence fields.
- Fee/slippage-aware EMA backtest command.
- Full master specification included server-side in master_prompt.txt.
- Render worker configuration in render.yaml.

## Deploy to Render
1. Push this folder to GitHub.
2. Create a Render Background Worker from the repo, or use the included render.yaml Blueprint.
3. Set TELEGRAM_BOT_TOKEN and OPENAI_API_KEY in Render Environment Variables.
4. Deploy.

## Local
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py

## Important
The bot never treats the language model as the market-data source. Exact market values must come from the exchange backend. If a value is unavailable, the model is instructed to return null/WAIT rather than fabricate it.
