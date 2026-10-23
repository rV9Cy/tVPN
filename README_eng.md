<div align="center">

```
████████╗██╗   ██╗██████╗ ███╗   ██╗
╚══██╔══╝██║   ██║██╔══██╗████╗  ██║
   ██║   ██║   ██║██████╔╝██╔██╗ ██║
   ██║   ╚██╗ ██╔╝██╔═══╝ ██║╚██╗██║
   ██║    ╚████╔╝ ██║     ██║ ╚████║
   ╚═╝     ╚═══╝  ╚═╝     ╚═╝  ╚═══╝
```

**Terminal VPN: pick a country, connect, done.**
No root. No VPN app on your phone. Zero Python dependencies.

Created by **Arrow Dev** · v1.0.0 · MIT License

[فارسی](README.md) · **English**

</div>

---

## What is TVPN?

TVPN is a command-line VPN client for terminals. It runs on **Termux, Linux, macOS and Windows**, downloads [Xray-core](https://github.com/XTLS/Xray-core) automatically, and routes your terminal tools (`pip`, `npm`, `git`, `curl`, `wget`, ...) through the country you choose.

It runs entirely in user space, so you don't need root and you don't need to install a VPN app.

## Features

- Clean, colorful terminal UI with a big banner; the screen is cleared on every launch
- Country picker with live latency bars
- **Auto fallback**: if a server fails, the next best server in that country is tried automatically
- Real connectivity check after connecting, and the exit IP is shown
- Subscription support (plain or base64) with `tvpn update`
- Protocols: **VLESS** (incl. Reality), **VMess**, **Trojan**, **Shadowsocks**
- `tvpn run <command>` tunnels one command only
- `tvpn tools on|off` sets the proxy for pip / npm / git in one step
- Auto-detects platform and CPU (Termux arm64, Linux, macOS, Windows)
- Works on narrow phone screens
- **Web dashboard** that starts automatically: manage subscriptions, browse configs with latency, see session traffic, connect / disconnect / switch server, add new subs or configs

## Install

**Termux**
```bash
pkg install python git
git clone https://github.com/YOUR_USERNAME/tvpn.git
cd tvpn
python tvpn.py
```

**Linux / macOS**
```bash
git clone https://github.com/YOUR_USERNAME/tvpn.git
cd tvpn
python3 tvpn.py
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/YOUR_USERNAME/tvpn.git
cd tvpn
python tvpn.py
```

**Install as a command (`tvpn`)**
```bash
pip install git+https://github.com/YOUR_USERNAME/tvpn.git
tvpn
```

> If GitHub is blocked where you are, download the Xray zip manually, put the `xray` binary in `~/.tvpn/bin/`, or set `XRAY_MIRROR` to a mirror URL.

## Usage

```bash
tvpn add https://example.com/sub/yourtoken   # add a subscription (or a vless:// vmess:// trojan:// ss:// link)
tvpn                                         # interactive menu
tvpn up                                      # pick a country and connect
tvpn up germany                              # connect to a country directly
tvpn up auto                                 # lowest latency overall

eval "$(tvpn env)"                           # route this shell through the tunnel (Linux/Termux/macOS)
tvpn run pip install requests                # tunnel one command only
tvpn tools on                                # set pip / npm / git proxy
tvpn check github.com                        # test a site: direct vs tunnel
tvpn down                                    # disconnect
```

| Command | Description |
|---|---|
| `tvpn` | Interactive menu |
| `tvpn up [country\|auto]` | Connect |
| `tvpn down` | Disconnect |
| `tvpn status` | Show connection status |
| `tvpn add <link>` | Add subscription URL or config link |
| `tvpn update` | Refresh saved subscriptions |
| `tvpn list` | List saved configs |
| `tvpn test` | Latency per country |
| `tvpn env` | Print proxy environment variables |
| `tvpn run <cmd>` | Run one command through the tunnel |
| `tvpn check <site>` | Compare direct vs tunnel access |
| `tvpn tools on\|off` | Set or remove pip / npm / git proxy |

Countries are detected from the config name (flag emoji or country name, e.g. `🇩🇪 Germany-1`).

## Web dashboard

Every time you run `tvpn`, a local dashboard starts in the background and its link is shown in the STATUS panel:

```
│ Web UI   http://127.0.0.1:8787/?t=57c55298c8f0
```

Open it in your browser (on Termux, any browser on the same phone). From there you can connect, disconnect, switch servers, ping all servers, update or remove subscriptions, and add new subscriptions or configs.

- Local only: it listens on `127.0.0.1` and requires the random token in the link.
- `tvpn web` prints the link, `tvpn web stop` stops it. Change the port with `TVPN_WEB_PORT`.
- The dashboard needs the `web/` folder, so run TVPN from the cloned repository.

## How it works

```
your command ──► 127.0.0.1:10808 (SOCKS5) / :10809 (HTTP)
                        │
                  Xray-core (user space)
                        │
                 your remote server ──► internet
```

TVPN is a client manager. It starts Xray with a generated config and exposes a local proxy. Data lives in `~/.tvpn`.

## Important

- **TVPN does not provide servers.** You need your own configs or a subscription link.
- Only tools that honor proxy environment variables (or those set by `tvpn tools`) are tunneled. System-wide traffic is not captured.
- You are responsible for following the laws of your country and the terms of your server provider.

## Contributing

Issues and pull requests are welcome. Ideas: Hysteria2 support, SOCKS-only mode for apps, auto-update, more tool presets (docker, apt).

## License

[MIT](LICENSE) © Arrow Dev
