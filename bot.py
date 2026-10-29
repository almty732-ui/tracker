import ccxt
import pandas as pd
import time
import requests
import json
import os

# ==========================================
# 1. الإعدادات
# ==========================================
API_KEY = 'zGUY5BwkqCWQ06Gyu0Eoc6I7kST0eVvs8BvLQWF5jvypxusv0HRdJr6WgA7hrNdn'
API_SECRET = '0i2povA9wDn3p0Q3E0dY205MY000pgNS3SPDH0kbBn6qIE3BX6eMonj0kuI7pLLs'
TG_TOKEN = 'YOUR_TG_TOKEN'  
TG_CHAT = 'YOUR_CHAT_ID'    

SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'
TRADE_AMOUNT = 0.001

STOP_LOSS_PCT = 0.01
TRAILING_PCT = 0.01

# ==========================================
# 2. الاتصال بمنصة Binance Spot Testnet
# ==========================================
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
exchange.set_sandbox_mode(True)

def send_tg(msg):
    if TG_TOKEN != 'YOUR_TG_TOKEN':
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"})
        except: pass

def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
    return pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

def analyze():
    df = get_data()
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    # ADX
    df['up'] = df['high'].diff()
    df['down'] = -df['low'].diff()
    df['+dm'] = ((df['up'] > df['down']) & (df['up'] > 0)) * df['up']
    df['-dm'] = ((df['down'] > df['up']) & (df['down'] > 0)) * df['down']
    tr = pd.concat([df['high'] - df['low'], abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    df['+di'] = 100 * (df['+dm'].rolling(14).mean() / atr)
    df['-di'] = 100 * (df['-dm'].rolling(14).mean() / atr)
    df['adx'] = (100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])).rolling(14).mean()
    
    last = df.iloc[-1]
    
    if last['adx'] < 25: return "SIDEWAYS", last['close']
    if last['ema20'] > last['ema50'] and last['rsi'] < 70: return "LONG", last['close']
    return "HOLD", last['close']

def get_balance(asset):
    try:
        return exchange.fetch_balance()['free'].get(asset, 0)
    except:
        return 0

def run_bot():
    print("🤖 البوت بدأ على Binance Spot Testnet...")
    send_tg("🤖 البوت شغال الآن على Binance Spot!")
    
    in_position = False
    entry_price = 0
    highest = 0

    while True:
        try:
            price = exchange.fetch_ticker(SYMBOL)['last']
            signal, _ = analyze()

            if not in_position:
                usdt = get_balance('USDT')
                if signal == "LONG" and usdt > price * TRADE_AMOUNT:
                    print(f"🟢 LONG عند {price}")
                    exchange.create_market_buy_order(SYMBOL, TRADE_AMOUNT)
                    in_position = True
                    entry_price = price
                    highest = price
                    send_tg(f"🟢 **LONG**\nالدخول: {price:.2f}")
                else:
                    print(f"⏳ {signal} | السعر: {price}")

            elif in_position:
                if price > highest: highest = price
                
                if price <= entry_price * (1 - STOP_LOSS_PCT):
                    exchange.create_market_sell_order(SYMBOL, TRADE_AMOUNT)
                    send_tg(f"🔴 **وقف خسارة** عند {price:.2f}")
                    in_position = False
                    
                elif highest > entry_price * 1.02 and price <= highest * (1 - TRAILING_PCT):
                    exchange.create_market_sell_order(SYMBOL, TRADE_AMOUNT)
                    profit = (price - entry_price) / entry_price * 100
                    send_tg(f"💰 **ربح**\nالربح: {profit:.2f}%")
                    in_position = False

            time.sleep(20)
        except Exception as e:
            print(f"⚠️ خطأ: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
