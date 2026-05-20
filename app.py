import os
import time
import requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from flask import Flask

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload)
        print(f"Telegram Sent Status: {res.status_code}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def check_market_and_trade():
    print(f"Scanning market at {datetime.now()}...")
    try:
        ticker = "GC=F" 
        gold = yf.Ticker(ticker)
        df = gold.history(period="5d", interval="1h")
        
        if df.empty or len(df) < 30:
            return

        df['EMA_20'] = ta.ema(df['Close'], length=20)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        latest = df.iloc[-1]
        current_price = round(latest['Close'], 2)
        rsi_val = latest['RSI']
        
        if latest['EMA_20'] > latest['EMA_50']:
            trend = "BULLISH"
        else:
            trend = "BEARISH"
        
        boundary = "NO ZONE"
        if rsi_val <= 32 or current_price <= latest['EMA_50']:
            boundary = "SUPPORT BOUNCE ZONE"
        elif rsi_val >= 68 or current_price >= latest['EMA_50']:
            boundary = "RESISTANCE REJECTION ZONE"

        is_bullish_candle = latest['Close'] > latest['Open'] and (latest['Close'] - latest['Open']) > (latest['High'] - latest['Low']) * 0.3
        is_bearish_candle = latest['Close'] < latest['Open'] and (latest['Open'] - latest['Close']) > (latest['High'] - latest['Low']) * 0.3

        action = None
        crt_signal = "NO SIGNAL"
        tbs_status = f"Trend: {trend} | Zone: {boundary}"

        if trend == "BULLISH" and boundary == "SUPPORT BOUNCE ZONE" and is_bullish_candle:
            action = "BUY"
            crt_signal = "Bullish Reversal Candle (CRT Confirmed)"
        elif trend == "BEARISH" and boundary == "RESISTANCE REJECTION ZONE" and is_bearish_candle:
            action = "SELL"
            crt_signal = "Bearish Reversal Candle (CRT Confirmed)"

        if action:
            msg = (
                f"⚡ *💥 NYEIN CHAN CRT SIGNAL 💥* ⚡\n\n"
                f"🔹 *Pair:* XAUUSD (Gold)\n"
                f"🔸 *Action:* {action}\n"
                f"📈 *TBS Context:* {tbs_status}\n"
                f"⏳ *CRT Signal:* {crt_signal}\n"
                f"💵 *Entry Price:* ${current_price}\n"
                f"📅 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            send_telegram_message(msg)
        else:
            print(f"No setup. Gold: ${current_price} | RSI: {round(rsi_val, 2)} | Trend: {trend}")
    except Exception as e:
        print(f"Market scan error: {e}")

@app.route('/')
def home():
    return "CRT+TBS Trading Bot is Running Live without Database!"

def run_bot_loop():
    while True:
        check_market_and_trade()
        time.sleep(300)

if __name__ == "__main__":
    import threading
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
