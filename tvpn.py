#!/usr/bin/env python3
"""TVPN - Terminal VPN
Created by Arrow Dev

Pick a country, connect, done. No root and no VPN app on your phone.
Powered by Xray-core (downloaded automatically). Zero Python dependencies.
Supports vless / vmess / trojan / shadowsocks links and subscription URLs.
"""
import base64
import concurrent.futures as cf
import io
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

APP = "TVPN"
__version__ = "1.0.0"
__author__ = "Arrow Dev"

HOME = os.path.join(os.path.expanduser("~"), ".tvpn")
BIN = os.path.join(HOME, "bin")
SERVERS = os.path.join(HOME, "servers.json")
SUBS = os.path.join(HOME, "subs.json")
CONF = os.path.join(HOME, "xray.json")
PIDF = os.path.join(HOME, "xray.pid")
STATE = os.path.join(HOME, "state.json")
SOCKS_PORT, HTTP_PORT, API_PORT = 10808, 10809, 10085
WEBF = os.path.join(HOME, "web.json")
SOCKS_URL = "socks5h://127.0.0.1:%d" % SOCKS_PORT
HTTP_URL = "http://127.0.0.1:%d" % HTTP_PORT
UA = {"User-Agent": "tvpn/" + __version__}
TEST_URL = "https://www.gstatic.com/generate_204"

if os.name == "nt":
    os.system("")  # enable ANSI colors on Windows 10+

# ───────────────────────── UI helpers ─────────────────────────
NOCOLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()
ANSI = re.compile(r"\033\[[0-9;]*m")


def _c(code, s):
    return s if NOCOLOR else "\033[%sm%s\033[0m" % (code, s)


def bold(s): return _c("1", s)
def dim(s): return _c("2", s)
def red(s): return _c("31", s)
def green(s): return _c("32", s)
def yellow(s): return _c("33", s)
def cyan(s): return _c("36", s)


def c256(n, s):
    return s if NOCOLOR else "\033[38;5;%dm%s\033[0m" % (n, s)


def vlen(s):
    return len(ANSI.sub("", s))


def cut(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def cols():
    return shutil.get_terminal_size((60, 24)).columns


def clear():
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[3J\033[H")
        sys.stdout.flush()


def ok(m): print("  %s %s" % (green("✔"), m))
def fail(m): print("  %s %s" % (red("✖"), m))
def info(m): print("  %s %s" % (cyan("›"), m))


LETTERS = {
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "V": ["██╗   ██╗", "██║   ██║", "██║   ██║", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚═══╝  "],
    "P": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
}
GRADIENT = [51, 45, 39, 33, 63, 99]


def vcenter(s, w):
    return " " * max(0, (w - vlen(s)) // 2) + s


def banner():
    w = cols() - 1
    print()
    if w >= 38:
        for i in range(6):
            row = "".join(LETTERS[ch][i] for ch in "TVPN")
            print(c256(GRADIENT[i], row.center(w)))
    else:
        print(bold(cyan("[ T V P N ]".center(w))))
    print(dim(("─" * min(w - 4, 40)).center(w)))
    print(vcenter(bold("Terminal VPN  ·  v%s" % __version__), w))
    print(vcenter(dim("Created by ") + bold(cyan(__author__)), w))
    print()


def panel(rows, title=""):
    w = max(32, min(cols() - 2, 58))
    inner = w - 2
    if title:
        top = "╭─ " + title + " " + "─" * max(0, inner - len(title) - 3) + "╮"
    else:
        top = "╭" + "─" * inner + "╮"
    print(cyan(top))
    for r in rows:
        pad = max(0, inner - 2 - vlen(r))
        print(cyan("│") + " " + r + " " * pad + " " + cyan("│"))
    print(cyan("╰" + "─" * inner + "╯"))


def ask(prompt="> "):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def pause():
    ask("\n  " + dim("Press Enter to continue..."))


USE_FLAGS = not (os.name == "nt" and "WT_SESSION" not in os.environ)

COUNTRIES = {
    "DE": ("Germany", ["germany", "deutschland", "de", "آلمان"]),
    "NL": ("Netherlands", ["netherlands", "holland", "nl", "هلند"]),
    "US": ("United States", ["united states", "usa", "us", "america", "آمریکا"]),
    "TR": ("Turkey", ["turkey", "turkiye", "tr", "ترکیه"]),
    "GB": ("United Kingdom", ["united kingdom", "england", "britain", "uk", "gb", "انگلیس"]),
    "FR": ("France", ["france", "fr", "فرانسه"]),
    "FI": ("Finland", ["finland", "fi", "فنلاند"]),
    "SE": ("Sweden", ["sweden", "se", "سوئد"]),
    "CA": ("Canada", ["canada", "ca", "کانادا"]),
    "AE": ("UAE", ["uae", "dubai", "ae", "امارات"]),
    "SG": ("Singapore", ["singapore", "sg", "سنگاپور"]),
    "JP": ("Japan", ["japan", "jp", "ژاپن"]),
    "CH": ("Switzerland", ["switzerland", "ch", "سوئیس"]),
    "PL": ("Poland", ["poland", "pl", "لهستان"]),
    "AM": ("Armenia", ["armenia", "am", "ارمنستان"]),
    "RU": ("Russia", ["russia", "ru", "روسیه"]),
    "XX": ("Other", []),
}


def cname(cc):
    return COUNTRIES.get(cc, ("Other", []))[0]


def ctag(cc):
    if cc == "XX" or not USE_FLAGS:
        return "[%s]" % cc if cc != "XX" else "[??]"
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc)


def detect_country(name):
    m = re.search("[\U0001F1E6-\U0001F1FF]{2}", name)
    if m:
        cc = "".join(chr(ord(ch) - 0x1F1E6 + 65) for ch in m.group())
        if cc in COUNTRIES:
            return cc
    low = name.lower()
    tokens = set(re.findall(r"[a-z]+|[\u0600-\u06FF]+", low))
    for cc, (_, aliases) in COUNTRIES.items():
        for a in aliases:
            if (" " in a and a in low) or a in tokens:
                return cc
    return "XX"


def resolve_cc(text, available):
    t = text.strip().lower()
    if t.upper() in available:
        return t.upper()
    for cc in available:
        if t == cname(cc).lower() or t in COUNTRIES.get(cc, ("", []))[1]:
            return cc
    return None


# ───────────────────────── link parsing ─────────────────────────
def b64d(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")


def stream(p, net=None, sec=None):
    net = net or p.get("type", "tcp")
    sec = sec or p.get("security", "none")
    s = {"network": net, "security": sec}
    if sec == "tls":
        s["tlsSettings"] = {"serverName": p.get("sni") or p.get("host", ""), "fingerprint": p.get("fp") or "chrome"}
        if p.get("alpn"):
            s["tlsSettings"]["alpn"] = p["alpn"].split(",")
    elif sec == "reality":
        s["realitySettings"] = {
            "serverName": p.get("sni", ""), "fingerprint": p.get("fp") or "chrome",
            "publicKey": p.get("pbk", ""), "shortId": p.get("sid", ""), "spiderX": p.get("spx", ""),
        }
    if net == "ws":
        s["wsSettings"] = {"path": p.get("path", "/"), "headers": {"Host": p.get("host", "")}}
    elif net == "grpc":
        s["grpcSettings"] = {"serviceName": p.get("serviceName", "")}
    return s


def parse_link(link):
    link = link.strip()
    try:
        if link.startswith("vmess://"):
            j = json.loads(b64d(link[8:]))
            p = {"host": j.get("host", ""), "path": j.get("path", "/"), "sni": j.get("sni", ""),
                 "serviceName": j.get("path", "")}
            out = {"protocol": "vmess",
                   "settings": {"vnext": [{"address": j["add"], "port": int(j["port"]),
                                           "users": [{"id": j["id"], "alterId": int(j.get("aid", 0)), "security": "auto"}]}]},
                   "streamSettings": stream(p, j.get("net", "tcp"), "tls" if j.get("tls") == "tls" else "none")}
            return {"name": j.get("ps", j["add"]), "host": j["add"], "port": int(j["port"]), "out": out}

        if link.startswith("ss://"):
            body, name = link[5:], ""
            if "#" in body:
                body, name = body.split("#", 1)
                name = urllib.parse.unquote(name)
            body = body.split("?")[0]
            if "@" in body:
                ui, hp = body.rsplit("@", 1)
                ui = ui if ":" in ui else b64d(ui)
            else:
                ui, hp = b64d(body).rsplit("@", 1)
            method, pw = ui.split(":", 1)
            host, port = hp.rsplit(":", 1)
            out = {"protocol": "shadowsocks",
                   "settings": {"servers": [{"address": host, "port": int(port), "method": method, "password": pw}]}}
            return {"name": name or host, "host": host, "port": int(port), "out": out}

        u = urllib.parse.urlparse(link)
        p = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        name = urllib.parse.unquote(u.fragment) or u.hostname
        if u.scheme == "vless":
            user = {"id": u.username, "encryption": p.get("encryption", "none")}
            if p.get("flow"):
                user["flow"] = p["flow"]
            out = {"protocol": "vless", "settings": {"vnext": [{"address": u.hostname, "port": u.port, "users": [user]}]},
                   "streamSettings": stream(p)}
        elif u.scheme == "trojan":
            out = {"protocol": "trojan",
                   "settings": {"servers": [{"address": u.hostname, "port": u.port,
                                             "password": urllib.parse.unquote(u.username)}]},
                   "streamSettings": stream(p, sec=p.get("security", "tls"))}
        else:
            return None
        return {"name": name, "host": u.hostname, "port": u.port, "out": out}
    except Exception:
        return None


def fetch(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def parse_many(text):
    text = text.strip()
    if "://" not in text.split("\n")[0]:
        try:
            text = b64d(text)
        except Exception:
            pass
    res = []
    for line in text.splitlines():
        s = parse_link(line) if "://" in line else None
        if s:
            s["cc"] = detect_country(s["name"])
            res.append(s)
    return res


# ───────────────────────── storage ─────────────────────────
def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    os.makedirs(HOME, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ───────────────────────── Xray core ─────────────────────────
def xray_path():
    return os.path.join(BIN, "xray.exe" if os.name == "nt" else "xray")


def asset_name():
    m = platform.machine().lower()
    arm64 = m in ("aarch64", "arm64", "armv8l")
    if os.name == "nt":
        return "Xray-windows-64.zip"
    if sys.platform == "darwin":
        return "Xray-macos-arm64-v8a.zip" if arm64 else "Xray-macos-64.zip"
    termux = "TERMUX_VERSION" in os.environ or "com.termux" in os.environ.get("PREFIX", "")
    if termux and arm64:
        return "Xray-android-arm64-v8a.zip"
    if arm64:
        return "Xray-linux-arm64-v8a.zip"
    if m in ("armv7l", "armv7", "arm"):
        return "Xray-linux-arm32-v7a.zip"
    return "Xray-linux-64.zip"


def ensure_xray():
    if os.path.exists(xray_path()):
        return True
    base = os.environ.get("XRAY_MIRROR", "https://github.com/XTLS/Xray-core/releases/latest/download")
    url = "%s/%s" % (base, asset_name())
    info("Downloading Xray core ...")
    print("    " + dim(url))
    try:
        data = fetch(url, 120)
        os.makedirs(BIN, exist_ok=True)
        zipfile.ZipFile(io.BytesIO(data)).extractall(BIN)
        if os.name != "nt":
            os.chmod(xray_path(), 0o755)
    except Exception as e:
        fail("Download failed: %s" % e)
        print("    Download the zip manually and put the 'xray' binary in:\n    %s" % BIN)
        print("    Or set XRAY_MIRROR to a mirror URL.")
        return False
    ok("Xray core ready")
    return True


def tcp_ping(host, port, timeout=2.5):
    t = time.time()
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return int((time.time() - t) * 1000)
    except Exception:
        return None


def ping_all(servers):
    with cf.ThreadPoolExecutor(32) as ex:
        res = list(ex.map(lambda s: tcp_ping(s["host"], s["port"]), servers))
    for s, ms in zip(servers, res):
        s["ms"] = ms
    return [s for s in servers if s["ms"] is not None]


def alive(pid):
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def running_pid():
    try:
        pid = int(open(PIDF).read())
        return pid if alive(pid) else None
    except Exception:
        return None


def kill_core():
    pid = running_pid()
    if pid:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            else:
                os.kill(pid, 15)
        except Exception:
            pass
    if os.path.exists(PIDF):
        os.remove(PIDF)
    return bool(pid)


def make_config(server):
    out = dict(server["out"], tag="proxy")
    return {
        "log": {"loglevel": "warning"},
        "stats": {},
        "api": {"tag": "api", "services": ["StatsService"]},
        "policy": {"system": {"statsOutboundUplink": True, "statsOutboundDownlink": True}},
        "routing": {"rules": [{"type": "field", "inboundTag": ["api"], "outboundTag": "api"}]},
        "inbounds": [
            {"tag": "api", "listen": "127.0.0.1", "port": API_PORT, "protocol": "dokodemo-door",
             "settings": {"address": "127.0.0.1"}},
            {"tag": "socks", "listen": "127.0.0.1", "port": SOCKS_PORT, "protocol": "socks", "settings": {"udp": True}},
            {"tag": "http", "listen": "127.0.0.1", "port": HTTP_PORT, "protocol": "http"},
        ],
        "outbounds": [out, {"protocol": "freedom", "tag": "direct"}],
    }


def start_core(server):
    save(CONF, make_config(server))
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000 | 0x00000200
    else:
        kw["start_new_session"] = True
    try:
        proc = subprocess.Popen([xray_path(), "run", "-c", CONF], **kw)
    except Exception:
        return None
    for _ in range(40):
        if proc.poll() is not None:
            return None
        if tcp_ping("127.0.0.1", SOCKS_PORT, 0.3) is not None:
            break
        time.sleep(0.1)
    with open(PIDF, "w") as f:
        f.write(str(proc.pid))
    return proc


def via_proxy(url, timeout=8):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": HTTP_URL, "https": HTTP_URL}))
    t = time.time()
    try:
        r = op.open(urllib.request.Request(url, headers=UA), timeout=timeout)
        return r, int((time.time() - t) * 1000)
    except Exception:
        return None, None


def exit_ip():
    r, _ = via_proxy("https://api.ipify.org", 6)
    try:
        return r.read().decode().strip() if r else "?"
    except Exception:
        return "?"


# ───────────────────────── web dashboard ─────────────────────────
def web_info():
    w = load(WEBF, {})
    return w if w.get("pid") and alive(w["pid"]) else None


def web_url(w):
    return "http://127.0.0.1:%d/?t=%s" % (w["port"], w["token"])


def detached_kw():
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000 | 0x00000200
    else:
        kw["start_new_session"] = True
    return kw


def ensure_web():
    """Start the dashboard in the background (once) and return its local URL."""
    w = web_info()
    if w:
        return web_url(w)
    if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")):
        return None
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "web-serve"], **detached_kw())
    except Exception:
        return None
    for _ in range(40):
        time.sleep(0.1)
        w = web_info()
        if w:
            return web_url(w)
    return None


def cmd_web(args):
    if args and args[0] == "stop":
        w = web_info()
        if w:
            try:
                os.kill(w["pid"], 15) if os.name != "nt" else subprocess.run(["taskkill", "/PID", str(w["pid"]), "/F"], capture_output=True)
            except Exception:
                pass
            ok("Dashboard stopped")
        else:
            info("Dashboard is not running")
        return
    url = ensure_web()
    if url:
        ok("Dashboard running")
        print("\n    " + bold(cyan(url)) + "\n")
    else:
        fail("Could not start the dashboard (web/ folder missing?)")


# ───────────────────────── screens ─────────────────────────
def screen(with_status=False):
    clear()
    banner()
    if with_status:
        status_panel()
        print()


def fmt_uptime(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return "%dh %02dm %02ds" % (h, m, s) if h else "%dm %02ds" % (m, s)


def status_panel():
    pid = running_pid()
    st = load(STATE, {})
    n = len(load(SERVERS, []))
    if pid:
        rows = [
            green("● CONNECTED"),
            "Country  %s %s" % (ctag(st.get("cc", "XX")), cname(st.get("cc", "XX"))),
            "Server   %s" % cut(st.get("name", "?"), 28),
            "Exit IP  %s" % st.get("ip", "?"),
            "Proxy    socks5 :%d  http :%d" % (SOCKS_PORT, HTTP_PORT),
            "Uptime   %s" % fmt_uptime(time.time() - st.get("since", time.time())),
        ]
    else:
        rows = [red("○ DISCONNECTED"), "Configs  %d saved" % n]
    w = web_info()
    if w:
        rows.append("Web UI   " + bold(cyan(web_url(w))))
    panel(rows, "STATUS")


def lat_bar(ms):
    lvl = 5 if ms < 80 else 4 if ms < 150 else 3 if ms < 250 else 2 if ms < 400 else 1
    col = green if lvl >= 4 else yellow if lvl == 3 else red
    return col("▰" * lvl) + dim("▱" * (5 - lvl))


# ───────────────────────── commands ─────────────────────────
def cmd_add(args):
    if not args:
        v = ask("  Paste subscription URL or config link: ")
        args = [v] if v else []
    if not args:
        fail("Usage: tvpn add <subscription-url | vless:// | vmess:// | trojan:// | ss://>")
        return
    servers = load(SERVERS, [])
    subs = load(SUBS, [])
    known = {(s["host"], s["port"], s["name"]) for s in servers}
    added = 0
    for a in args:
        try:
            if a.startswith("http"):
                new = parse_many(fetch(a).decode("utf-8", "ignore"))
                for s in new:
                    s["src"] = a
                if a not in subs:
                    subs.append(a)
            else:
                new = parse_many(a)
                for s in new:
                    s["src"] = "manual"
        except Exception as e:
            fail("%s: %s" % (cut(a, 30), e))
            continue
        for s in new:
            k = (s["host"], s["port"], s["name"])
            if k not in known:
                servers.append(s)
                known.add(k)
                added += 1
        if not new:
            fail("No valid configs found in: %s" % cut(a, 40))
    save(SERVERS, servers)
    save(SUBS, subs)
    ok("%d config(s) added  ·  total %d" % (added, len(servers)))


def cmd_update(args):
    subs = load(SUBS, [])
    if not subs:
        fail("No subscriptions saved. Use: tvpn add <subscription-url>")
        return
    servers = [s for s in load(SERVERS, []) if s.get("src") not in subs]
    total = 0
    for u in subs:
        try:
            new = parse_many(fetch(u).decode("utf-8", "ignore"))
            for s in new:
                s["src"] = u
            servers += new
            total += len(new)
            ok("%s  →  %d configs" % (cut(u, 34), len(new)))
        except Exception as e:
            fail("%s: %s" % (cut(u, 34), e))
    save(SERVERS, servers)
    ok("Updated  ·  total %d configs" % len(servers))


def cmd_list(args):
    servers = load(SERVERS, [])
    if not servers:
        info("No configs yet. Use: tvpn add <link>")
        return
    for s in servers:
        print("  %s %-26s %s:%s" % (ctag(s["cc"]), cut(s["name"], 26), cut(s["host"], 22), s["port"]))
    print("\n  " + dim("Total: %d" % len(servers)))


def build_groups():
    servers = load(SERVERS, [])
    if not servers:
        fail("No configs saved. Use: tvpn add <link>")
        return None
    info("Testing latency on %d server(s) ..." % len(servers))
    live = ping_all(servers)
    if not live:
        fail("No server responded. Check your internet or configs.")
        return None
    groups = {}
    for s in sorted(live, key=lambda x: x["ms"]):
        groups.setdefault(s["cc"], []).append(s)
    return groups


def cmd_test(args):
    groups = build_groups()
    if not groups:
        return
    print()
    for cc in sorted(groups, key=lambda k: groups[k][0]["ms"]):
        g = groups[cc]
        print("  %s %-16s %2d srv  %4d ms  %s" % (ctag(cc), cname(cc), len(g), g[0]["ms"], lat_bar(g[0]["ms"])))


def cmd_up(args):
    if not ensure_xray():
        return
    groups = build_groups()
    if not groups:
        return
    order = sorted(groups, key=lambda k: groups[k][0]["ms"])
    if args and args[0].lower() == "auto":
        cc = order[0]
    elif args:
        cc = resolve_cc(" ".join(args), groups)
        if not cc:
            fail("Country not available. Available: " + ", ".join(order))
            return
    else:
        print("\n  " + bold("Select a country:") + "\n")
        for i, k in enumerate(order, 1):
            g = groups[k]
            print("  %s  %s %-15s %2d srv  %4d ms  %s" % (bold("%2d" % i), ctag(k), cname(k), len(g), g[0]["ms"], lat_bar(g[0]["ms"])))
        print("  %s  %s" % (bold(" 0"), dim("Cancel")))
        pick = ask("\n  > ")
        if not pick.isdigit() or not (1 <= int(pick) <= len(order)):
            return
        cc = order[int(pick) - 1]

    print()
    kill_core()
    for i, s in enumerate(groups[cc][:5], 1):
        info("Connecting to %s %s  (%d/%d)" % (ctag(cc), cut(s["name"], 24), i, min(5, len(groups[cc]))))
        proc = start_core(s)
        if not proc:
            fail("Core failed to start, trying next ...")
            kill_core()
            continue
        _, ms = via_proxy(TEST_URL)
        if ms is None:
            fail("No traffic through this server, trying next ...")
            kill_core()
            continue
        ip = exit_ip()
        save(STATE, {"cc": cc, "name": s["name"], "ip": ip, "since": time.time(), "ms": ms})
        print()
        ok(green("Connected") + "  %s %s  ·  exit IP %s  ·  %d ms" % (ctag(cc), cname(cc), ip, ms))
        print("\n  Use it in this shell:\n")
        cmd_env([], indent=True)
        return
    fail("All servers in %s failed. Try another country or run: tvpn update" % cname(cc))


def cmd_down(args):
    if kill_core():
        ok("Disconnected")
    else:
        info("Not connected")


def cmd_status(args):
    status_panel()


def cmd_env(args, indent=False):
    pre = "    " if indent else ""
    if os.name == "nt":
        print(pre + '$env:ALL_PROXY="%s"; $env:HTTP_PROXY="%s"; $env:HTTPS_PROXY="%s"' % (SOCKS_URL, HTTP_URL, HTTP_URL))
        if indent:
            print(pre + dim("(cmd.exe: set HTTP_PROXY=%s & set HTTPS_PROXY=%s)" % (HTTP_URL, HTTP_URL)))
    else:
        print(pre + 'export ALL_PROXY="%s" HTTP_PROXY="%s" HTTPS_PROXY="%s" http_proxy="%s" https_proxy="%s"'
              % (SOCKS_URL, HTTP_URL, HTTP_URL, HTTP_URL, HTTP_URL))
        if indent:
            print(pre + dim('or in one go:  eval "$(tvpn env)"'))


def cmd_run(args):
    if not args:
        print("Usage: tvpn run <command ...>")
        return
    env = dict(os.environ, ALL_PROXY=SOCKS_URL, HTTP_PROXY=HTTP_URL, HTTPS_PROXY=HTTP_URL,
               http_proxy=HTTP_URL, https_proxy=HTTP_URL)
    try:
        sys.exit(subprocess.call(args, env=env))
    except FileNotFoundError:
        print("Command not found: %s" % args[0])
        sys.exit(127)


def cmd_check(args):
    if not args:
        v = ask("  Site to check (e.g. github.com): ")
        args = [v] if v else []
    if not args:
        return
    host = args[0].replace("https://", "").replace("http://", "").split("/")[0]
    if not running_pid():
        info(yellow("Not connected. Showing direct result only."))
    print()
    for label, handler in (("Direct", {}), ("Tunnel", {"http": HTTP_URL, "https": HTTP_URL})):
        if label == "Tunnel" and not running_pid():
            continue
        op = urllib.request.build_opener(urllib.request.ProxyHandler(handler))
        t = time.time()
        try:
            r = op.open(urllib.request.Request("https://" + host, headers=UA), timeout=8)
            ok("%-7s %s  (%d ms)" % (label, green("OK %s" % r.status), (time.time() - t) * 1000))
        except Exception as e:
            fail("%-7s %s" % (label, red(cut(str(e), 40))))


TOOLS = [
    ("pip", [sys.executable, "-m", "pip", "config", "set", "global.proxy", HTTP_URL],
     [sys.executable, "-m", "pip", "config", "unset", "global.proxy"]),
    ("git", ["git", "config", "--global", "http.proxy", HTTP_URL],
     ["git", "config", "--global", "--unset", "http.proxy"]),
    ("npm", ["npm", "config", "set", "proxy", HTTP_URL], ["npm", "config", "delete", "proxy"]),
    ("npm", ["npm", "config", "set", "https-proxy", HTTP_URL], ["npm", "config", "delete", "https-proxy"]),
]


def cmd_tools(args):
    mode = (args[0] if args else ask("  Dev tools proxy  [on/off]: ")).lower()
    if mode not in ("on", "off"):
        fail("Usage: tvpn tools on|off")
        return
    print()
    for name, on_cmd, off_cmd in TOOLS:
        cmd = on_cmd if mode == "on" else off_cmd
        if cmd[0] != sys.executable and shutil.which(cmd[0]) is None:
            info("%-4s %s" % (name, dim("not installed, skipped")))
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            (ok if r.returncode == 0 else info)("%-4s proxy %s" % (name, mode.upper()))
        except Exception:
            fail("%-4s failed" % name)
    print("\n  " + dim("Tip: turn it off when you disconnect:  tvpn tools off"))


def cmd_help(args):
    rows = [
        ("tvpn", "interactive menu"),
        ("tvpn up [country|auto]", "connect (e.g. tvpn up germany)"),
        ("tvpn down", "disconnect"),
        ("tvpn status", "show connection status"),
        ("tvpn add <link>", "add subscription URL or config link"),
        ("tvpn update", "refresh saved subscriptions"),
        ("tvpn list", "list saved configs"),
        ("tvpn test", "latency per country"),
        ("tvpn env", "print proxy env vars (eval it)"),
        ("tvpn run <cmd>", "run one command through the tunnel"),
        ("tvpn check <site>", "test a site: direct vs tunnel"),
        ("tvpn tools on|off", "set pip / npm / git proxy"),
        ("tvpn web [stop]", "open the web dashboard (local)"),
    ]
    print("  " + bold("Commands") + "\n")
    for a, b in rows:
        print("  %s  %s" % (cyan(a.ljust(24)), dim(b)))


def proxy_env():
    if not running_pid():
        return None
    return dict(os.environ, ALL_PROXY=SOCKS_URL, HTTP_PROXY=HTTP_URL, HTTPS_PROXY=HTTP_URL,
                http_proxy=HTTP_URL, https_proxy=HTTP_URL)


def run_shell(line):
    """Run any shell command from inside TVPN (through the tunnel when connected)."""
    try:
        parts = shlex.split(line, posix=(os.name != "nt"))
    except ValueError:
        parts = line.split()
    if not parts:
        return
    if parts[0] == "cd":
        try:
            os.chdir(os.path.expanduser(parts[1] if len(parts) > 1 else "~"))
        except OSError as e:
            fail(str(e))
        return
    if parts[0] in ("clear", "cls"):
        clear()
        return
    subprocess.call(line, shell=True, env=proxy_env())


def menu():
    items = [
        ("1", "Connect", cmd_up), ("2", "Disconnect", cmd_down),
        ("3", "Add config / subscription", cmd_add), ("4", "Update subscriptions", cmd_update),
        ("5", "Dev tools proxy (pip / npm / git)", cmd_tools), ("6", "Check a website", cmd_check),
        ("7", "Show env command", lambda a: (print(), cmd_env([], True))),
    ]

    def show():
        screen(True)
        for k, label, _ in items:
            print("  %s  %s" % (bold(cyan(k)), label))
        print("  %s  %s\n" % (bold(cyan("0")), dim("Exit")))
        print("  " + dim("Type a number, a tvpn command (up germany, status ...) or any shell command."))
        print("  " + dim("Enter = refresh   ·   !cmd = force shell   ·   menu = redraw"))
        if running_pid():
            print("  " + green("Connected: commands you type here go through the tunnel automatically."))
        print()

    show()
    while True:
        ch = ask("  > ")
        low = ch.lower()
        if ch == "" or low in ("menu", "m"):
            show()
            continue
        if low in ("0", "q", "exit", "quit"):
            clear()
            return
        try:
            hit = next((fn for k, _, fn in items if ch == k), None)
            if hit:
                print()
                hit([])
                pause()
                show()
                continue
            if ch.startswith("!"):
                run_shell(ch[1:].strip())
                continue
            parts = ch.split()
            if parts[0].lower() == "tvpn":
                parts = parts[1:]
                if not parts:
                    show()
                    continue
            name = parts[0].lower()
            if name == "env":
                cmd_env(parts[1:])
            elif name in COMMANDS:
                print()
                COMMANDS[name](parts[1:])
            else:
                run_shell(" ".join(parts) if parts[0] != ch.split()[0] else ch)
        except KeyboardInterrupt:
            print()
        except SystemExit:
            pass


COMMANDS = {
    "up": cmd_up, "connect": cmd_up, "down": cmd_down, "disconnect": cmd_down, "status": cmd_status,
    "add": cmd_add, "update": cmd_update, "list": cmd_list, "test": cmd_test,
    "check": cmd_check, "tools": cmd_tools, "web": cmd_web, "help": cmd_help, "-h": cmd_help, "--help": cmd_help,
}


def main():
    a = sys.argv[1:]
    cmd = a[0].lower() if a else "menu"
    rest = a[1:]
    if cmd in ("-v", "--version", "version"):
        print("%s %s by %s" % (APP, __version__, __author__))
        return
    try:
        if cmd == "web-serve":
            import tvpn_web
            tvpn_web.serve()
            return
        if cmd in ("menu", "up", "connect", "status", "web"):
            ensure_web()
        if cmd == "env":
            cmd_env(rest)
        elif cmd == "run":
            cmd_run(rest)
        elif cmd == "menu":
            menu()
        elif cmd in COMMANDS:
            screen(False)
            COMMANDS[cmd](rest)
            print()
        else:
            screen(False)
            fail("Unknown command: %s\n" % cmd)
            cmd_help([])
            print()
    except KeyboardInterrupt:
        print("\n  Bye.")


if __name__ == "__main__":
    main()
