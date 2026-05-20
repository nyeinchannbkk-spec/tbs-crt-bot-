import os
import time
import requests
import psycopg
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import schedule
from datetime import datetime
from telegram import Bot

# --- CONFIGURATION (Environment Variables) ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

def save_to_supabase(pair, action, tbs, crt, entry_price):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trading_journal (pair, action, tbs, crt, entry, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (pair, action, tbs, crt, entry_price, "OPEN", datetime.utcnow())
                )
                conn.commit()
                print("Journal successfully saved to Supabase!")
    except Exception as e:
        print(f"Supabase Logging Error: {e}")

# --- CRT + TBS TRADING LOGIC ---
def check_market_and_trade():
    print(f"Scanning market at {datetime.now()}...")
    
    # 1. Fetch Gold (XAUUSD) Data from yfinance
    # GC=F is the ticker for Gold Futures on Yahoo Finance
    ticker = "GC=F" 
    gold = yf.Ticker(ticker)
    
    # Get 1-hour interval data for Trend and Boundary
    df = gold.history(period="5d", interval="1h")
    if df.empty or len(df) < 30:
        return

    # 2. TBS: Trend & Boundary Calculations (EMA & RSI)
    df['EMA_20'] = ta.ema(df['Close'], length=20)
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    current_price = round(latest['Close'], 2)
    rsi_val = latest['RSI']
    
    # Define TBS Trend
    if latest['EMA_20'] > latest['EMA_50']:
        trend = "BULLISH"
    else:
        trend = "BEARISH"
    
    # Define TBS Boundary (Support/Resistance via RSI & EMA)
    boundary = "NO ZONE"
    if rsi_val <= 32 or current_price <= latest['EMA_50']:
        boundary = "SUPPORT BOUNCE ZONE"
    elif rsi_val >= 68 or current_price >= latest['EMA_50']:
        boundary = "RESISTANCE REJECTION ZONE"

    # 3. CRT: Candle Reversal Confirmation
    # Bullish Reversal Candle (Pin Bar / Hammer or Green engulfing)
    is_bullish_candle = latest['Close'] > latest['Open'] and (latest['Close'] - latest['Open']) > (latest['High'] - latest['Low']) * 0.3
    # Bearish Reversal Candle (Shooting Star / Red engulfing)
    is_bearish_candle = latest['Close'] < latest['Open'] and (latest['Open'] - latest['Close']) > (latest['High'] - latest['Low']) * 0.3

    # --- ACTION TRIGGER ---
    action = None
    crt_signal = "NO SIGNAL"
    tbs_status = f"Trend: {trend} | Zone: {boundary}"

    # BUY Trigger: Bullish Trend + Support Zone + Bullish Candle Confirmation
    if trend == "BULLISH" and boundary == "SUPPORT BOUNCE ZONE" and is_bullish_candle:
        action = "BUY"
        crt_signal = "Bullish Reversal Candle (CRT Confirmed)"
        
    # SELL Trigger: Bearish Trend + Resistance Zone + Bearish Candle Confirmation
    elif trend == "BEARISH" and boundary == "RESISTANCE REJECTION ZONE" and is_bearish_candle:
        action = "SELL"
        crt_signal = "Bearish Reversal Candle (CRT Confirmed)"

    if action:
        # 1. Format Message for Telegram
        msg = (
            f"⚡ *💥 NYEIN CHAN CRT SIGNAL 💥* ⚡\n\n"
            f"🔹 *Pair:* XAUUSD (Gold)\n"
            f"🔸 *Action:* {action}\n"
            f"📈 *TBS Context:* {tbs_status}\n"
            f"⏳ *CRT Signal:* {crt_signal}\n"
            f"💵 *Entry Price:* ${current_price}\n"
            f"📅 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        # Send notifications & Save Journal
        send_telegram_message(msg)
        save_to_supabase("XAUUSD", action, boundary, crt_signal, current_price)
    else:
        print(f"No setup found. Gold Price: ${current_price} | RSI: {round(rsi_val, 2)} | Trend: {trend}")

# --- BACKGROUND RUNNER ---
# Loop to check every 5 minutes (You can adjust this as you like)
schedule.every(5).minutes.do(check_market_and_trade)

if __name__ == "__main__":
    # Run once at startup, then keep running on schedule
    check_market_and_trade()
    while True:
        schedule.run_pending()
        time.sleep(1)
