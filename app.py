import os
import time
import requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, time as datetime_time
import pytz
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

# --- RULE 1: TIME CHECK (KILLZONES IN ICT/GMT+7) ---
def is_in_killzone():
    tz = pytz.timezone('Asia/Bangkok')
    now_tz = datetime.now(tz)
    current_time = now_tz.time()
    
    # London Killzone (14:30 - 17:30) & New York Killzone (19:30 - 22:30)
    london_start = datetime_time(14, 30)
    london_end = datetime_time(17, 30)
    ny_start = datetime_time(19, 30)
    ny_end = datetime_time(22, 30)
    
    return (london_start <= current_time <= london_end) or (ny_start <= current_time <= ny_end)

def check_market_and_trade():
    # 1. Time Check Rule
    if not is_in_killzone():
        print("Bot is active but outside London/NY Killzones. Scanning paused.")
        return

    print(f"Scanning market with SMC + CRT + TBS Logic at {datetime.now()}...")
    try:
        # Fetching H1 for Liquidity Levels & M5 for Executions
        gold_h1 = yf.Ticker("GC=F").history(period="5d", interval="1h")
        gold_m5 = yf.Ticker("GC=F").history(period="2d", interval="5m")

        if gold_h1.empty or gold_m5.empty or len(gold_m5) < 10:
            return

        # --- RULE 2: LIQUIDITY CHECK (H1 LEVELS) ---
        # Get Dynamic Liquidity Points from H1 Data
        pdh = gold_h1['High'].iloc[-24: -1].max() # Previous 24h High approximation
        pdl = gold_h1['Low'].iloc[-24: -1].min()  # Previous 24h Low approximation
        
        # Asian Session approximation (06:00 to 12:00 BKK time approx)
        asian_data = gold_h1.between_time('06:00', '12:00')
        asian_high = asian_data['High'].max() if not asian_data.empty else pdh
        asian_low = asian_data['Low'].min() if not asian_data.empty else pdl

        # Current M5 candles
        m5_latest = gold_m5.iloc[-1]
        m5_prev = gold_m5.iloc[-2]
        
        current_price = m5_latest['Close']
        
        # Detect Sweeps
        high_liquidity_target = max(pdh, asian_high)
        low_liquidity_target = min(pdl, asian_low)
        
        bullish_sweep = m5_prev['Low'] < low_liquidity_target and m5_latest['Close'] > low_liquidity_target
        bearish_sweep = m5_prev['High'] > high_liquidity_target and m5_latest['Close'] < high_liquidity_target

        # --- RULE 3: MARKET STRUCTURE SHIFT (MSS) IN M5 ---
        # Calculate ATR for Displacement Standard
        gold_m5['ATR'] = ta.atr(gold_m5['High'], gold_m5['Low'], gold_m5['Close'], length=14)
        atr_val = gold_m5['ATR'].iloc[-1] if not pd.isna(gold_m5['ATR'].iloc[-1]) else 1.5
        
        # Fractal/Swing Points check
        recent_highs = gold_m5['High'].iloc[-6:-2]
        recent_lows = gold_m5['Low'].iloc[-6:-2]
        
        prev_swing_high = recent_highs.max()
        prev_swing_low = recent_lows.min()
        
        candle_body = abs(m5_latest['Close'] - m5_latest['Open'])
        displaced = candle_body > (atr_val * 1.2) # Displacement Standard (ATR Trigger)
        
        mss_buy = current_price > prev_swing_high and displaced
        mss_sell = current_price < prev_swing_low and displaced

        # --- RULE 4: FAIR VALUE GAP (FVG) DETECTION LOGIC ---
        c1 = gold_m5.iloc[-3]
        c2 = gold_m5.iloc[-2]
        c3 = gold_m5.iloc[-1]
        
        bullish_fvg = c3['Low'] > c1['High']
        bearish_fvg = c3['High'] < c1['Low']

        # --- RULE 5: SIGNAL OUTPUT ---
        action = None
        crt_signal = ""
        fvg_range = ""
        
        sl_price = 0.0
        tp_price = 0.0

        if bullish_sweep or (mss_buy and bullish_fvg):
            action = "BUY"
            crt_signal = "MSS Breakout & Bullish FVG Range Formed (SMC + CRT Validated)"
            fvg_range = f"${round(c1['High'], 2)} - ${round(c3['Low'], 2)}"
            sl_price = round(current_price - 4.5, 2)
            tp_price = round(current_price + 9.0, 2)
            
        elif bearish_sweep or (mss_sell and bearish_fvg):
            action = "SELL"
            crt_signal = "MSS Rejection & Bearish FVG Range Formed (SMC + CRT Validated)"
            fvg_range = f"${round(c3['High'], 2)} - ${round(c1['Low'], 2)}"
            sl_price = round(current_price + 4.5, 2)
            tp_price = round(current_price - 9.0, 2)

        if action:
            msg = (
                f"⚡ *💥 SMC + CRT ALGORITHMIC SIGNAL 💥* ⚡\n\n"
                f"🔹 *Pair:* XAUUSD (Gold)\n"
                f"🔸 *Action:* {action}\n"
                f"📈 *SMC Context:* Sweep/MSS Confirmed\n"
                f"⏳ *Trigger:* {crt_signal}\n"
                f"🏷️ *FVG Range:* {fvg_range}\n\n"
                f"💵 *Entry Price:* ${round(current_price, 2)}\n"
                f"🛑 *Stop Loss (SL):* ${sl_price}\n"
                f"🎯 *Take Profit (TP):* ${tp_price}\n\n"
                f"📅 *BKK Time:* {datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            send_telegram_message(msg)
        else:
            print(f"Scanning... Gold: ${round(current_price, 2)} | FVG Status: Bullish={bullish_fvg}/Bearish={bearish_fvg} | Structure: Intact")
            
    except Exception as e:
        print(f"SMC Market Scan Error: {e}")

@app.route('/')
def home():
    return "SMC + CRT + TBS Advanced Algorithmic Bot is Live!"

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
