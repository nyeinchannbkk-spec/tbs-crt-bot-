import os
import logging
import psycopg2
from flask import Flask, request, jsonify
from telegram import Bot

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DATABASE_URL = os.getenv('DATABASE_URL')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

def init_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal (
            id SERIAL PRIMARY KEY,
            pair TEXT,
            action TEXT,
            entry_price NUMERIC,
            tp NUMERIC,
            sl NUMERIC,
            status TEXT DEFAULT 'PENDING',
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    logging.error(f"Database Init Error: {e}")

@app.route('/')
def home():
    return "TBS+CRT Telegram Bot is Running Live!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data"}), 400

    pair = data.get('pair', 'UNKNOWN')
    action = data.get('action', 'INFO')
    tbs = data.get('tbs', 'N/A')
    crt = data.get('crt', 'N/A')
    entry = data.get('entry', 0)
    tp = data.get('tp', 0)
    sl = data.get('sl', 0)

    message = (
        f"🚨 **⚠️ TBS + CRT AUTO SIGNAL** 🚨\n\n"
        f"🪙 **Pair:** #{pair}\n"
        f"📈 **Action:** {action}\n"
        f"🔍 **TBS Strategy:** {tbs}\n"
        f"🕯️ **CRT Pattern:** {crt}\n\n"
        f"🎯 **Entry Price:** {entry}\n"
        f"🟢 **Take Profit:** {tp}\n"
        f"🔴 **Stop Loss:** {sl}\n"
    )

    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO journal (pair, action, entry_price, tp, sl, note) VALUES (%s, %s, %s, %s, %s, %s)",
            (pair, action, entry, tp, sl, f"Auto-Signal: {tbs} + {crt}")
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
