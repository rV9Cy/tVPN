"""TVPN web dashboard backend. Created by Arrow Dev. Local only, stdlib only."""
import http.server
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.parse

import tvpn

DIR = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()
TOKEN = ""


def servers():
    return tvpn.load(tvpn.SERVERS, [])


def traffic():
    up = down = 0
    try:
        r = subprocess.run([tvpn.xray_path(), "api", "statsquery", "--server=127.0.0.1:%d" % tvpn.API_PORT],
                           capture_output=True, text=True, timeout=4)
        for s in json.loads(r.stdout).get("stat", []):
            if s["name"] == "outbound>>>proxy>>>traffic>>>uplink":
                up = int(s.get("value", 0))
            elif s["name"] == "outbound>>>proxy>>>traffic>>>downlink":
                down = int(s.get("value", 0))
    except Exception:
        pass
    return {"up": up, "down": down}


def state():
    on = bool(tvpn.running_pid())
    st = tvpn.load(tvpn.STATE, {}) if on else {}
    cc = st.get("cc", "XX")
    return {
        "version": tvpn.__version__, "author": tvpn.__author__, "connected": on,
        "cc": cc, "country": tvpn.cname(cc), "server": st.get("name"), "ip": st.get("ip"),
        "since": st.get("since"), "traffic": traffic() if on else {"up": 0, "down": 0},
        "subs": tvpn.load(tvpn.SUBS, []),
        "servers": [{"id": i, "name": s["name"], "cc": s["cc"], "country": tvpn.cname(s["cc"]), "host": s["host"],
                     "port": s["port"], "proto": s["out"]["protocol"], "src": s.get("src", "manual"), "ms": s.get("ms")}
                    for i, s in enumerate(servers())],
    }


def ping():
    sv = servers()
    tvpn.ping_all(sv)
    tvpn.save(tvpn.SERVERS, sv)


def connect(sid=None):
    sv = servers()
    if sid is None:  # auto: lowest latency
        ping()
        sv = servers()
        order = sorted([i for i, s in enumerate(sv) if s.get("ms") is not None], key=lambda i: sv[i]["ms"])[:5]
    else:
        order = [int(sid)]
    if not order:
        return {"error": "No reachable server"}
    if not tvpn.ensure_xray():
        return {"error": "Could not download Xray core"}
    for i in order:
        s = sv[i]
        tvpn.kill_core()
        if not tvpn.start_core(s):
            continue
        _, ms = tvpn.via_proxy(tvpn.TEST_URL)
        if ms is None:
            continue
        tvpn.save(tvpn.STATE, {"cc": s["cc"], "name": s["name"], "ip": tvpn.exit_ip(), "since": time.time(), "ms": ms})
        return {"ok": True}
    tvpn.kill_core()
    return {"error": "Server failed. Try another one."}


def act(name, body):
    if name == "connect":
        return connect(body.get("id"))
    if name == "disconnect":
        tvpn.kill_core()
    elif name == "ping":
        ping()
    elif name == "update":
        tvpn.cmd_update([])
    elif name == "add":
        n0 = len(servers())
        tvpn.cmd_add(str(body.get("text", "")).split())
        n = len(servers()) - n0
        return {"added": n} if n else {"error": "No valid config found"}
    elif name == "remove_sub":
        u = body.get("url")
        tvpn.save(tvpn.SUBS, [x for x in tvpn.load(tvpn.SUBS, []) if x != u])
        tvpn.save(tvpn.SERVERS, [s for s in servers() if s.get("src") != u])
    elif name == "remove":
        sv = servers()
        i = int(body.get("id", -1))
        if 0 <= i < len(sv):
            sv.pop(i)
            tvpn.save(tvpn.SERVERS, sv)
    else:
        return {"error": "Unknown action"}
    return {"ok": True}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, data, code=200, ctype="application/json"):
        b = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def host_ok(self):
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def authed(self):
        return self.host_ok() and secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if not self.host_ok():
            return self.send({"error": "forbidden"}, 403)
        if p in ("/", "/index.html"):
            try:
                with open(os.path.join(DIR, "web", "index.html"), "rb") as f:
                    return self.send(f.read(), 200, "text/html")
            except OSError:
                return self.send(b"Dashboard files not found. Run TVPN from the cloned repository.", 404, "text/plain")
        if p == "/api/state" and self.authed():
            with LOCK:
                return self.send(state())
        self.send({"error": "unauthorized"}, 401)

    def do_POST(self):
        if not self.authed() or not self.path.startswith("/api/"):
            return self.send({"error": "unauthorized"}, 401)
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            with LOCK:
                self.send(act(self.path[5:], body))
        except Exception as e:
            self.send({"error": str(e)}, 400)


def serve():
    global TOKEN
    TOKEN = secrets.token_hex(6)
    base = int(os.environ.get("TVPN_WEB_PORT", 8787))
    for port in range(base, base + 20):
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
            break
        except OSError:
            continue
    else:
        return
    tvpn.save(tvpn.WEBF, {"pid": os.getpid(), "port": port, "token": TOKEN})
    srv.serve_forever()
