import os, re, signal, subprocess, sys, time, pathlib

WG_DEV = os.getenv("WG_DEVICE", "wg0")
ETH_IF = os.getenv("ETH_IF", "eth0")

PRIV = os.environ["WG_PRIVATE_KEY"]
ADDR = os.environ["WG_ADDRESS"]
DNS  = os.getenv("WG_DNS", "")
PUB  = os.environ["WG_PUBLIC_KEY"]
ALWD = os.getenv("WG_ALLOWED_IPS", "0.0.0.0/0, ::/0")
END  = os.environ["WG_ENDPOINT_IP"]             # IP only
PORT = os.getenv("WG_ENDPOINT_PORT", "51820")
PSK  = os.getenv("WG_PRESHARED_KEY", "")

LAN  = os.getenv("LAN_CIDR", "").strip()
TCPP = os.getenv("ALLOW_LAN_TCP_PORTS", "").strip()
UDPP = os.getenv("ALLOW_LAN_UDP_PORTS", "").strip()

def is_ipv4(s): return re.match(r"^\d{1,3}(\.\d{1,3}){3}$", s) is not None
def is_ipv6(s): return ":" in s
if not (is_ipv4(END) or is_ipv6(END)):
    print(f"WG_ENDPOINT_IP must be an IP (got {END})", file=sys.stderr); sys.exit(2)

# Write /etc/wireguard/wg0.conf from env
conf_dir = pathlib.Path("/etc/wireguard"); conf_dir.mkdir(parents=True, exist_ok=True)
conf = ["[Interface]", f"PrivateKey = {PRIV}", f"Address = {ADDR}"]
if DNS: conf.append(f"DNS = {DNS}")
conf += ["", "[Peer]", f"PublicKey = {PUB}", f"AllowedIPs = {ALWD}", f"Endpoint = {END}:{PORT}"]
if PSK: conf.append(f"PresharedKey = {PSK}")
(conf_dir / f"{WG_DEV}.conf").write_text("\n".join(conf) + "\n")

def run(*a): subprocess.run(list(a), check=True)
def ipt(*a, v6=False, ok=False):
    cmd = ["ip6tables" if v6 else "iptables"] + list(a)
    try: subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        if not ok: raise

# ---------- Hard kill switch: default DROP everywhere (v4+v6) ----------
for v6 in (False, True):
    ipt("-F", v6=v6, ok=True); ipt("-X", v6=v6, ok=True)
    ipt("-P", "INPUT", "DROP", v6=v6)
    ipt("-P", "OUTPUT", "DROP", v6=v6)
    ipt("-P", "FORWARD", "DROP", v6=v6)

# Loopback + established/related
for v6 in (False, True):
    ipt("-A", "INPUT", "-i", "lo", "-j", "ACCEPT", v6=v6)
    ipt("-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT", v6=v6)
    ipt("-A", "INPUT", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT", v6=v6)
    ipt("-A", "OUTPUT","-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT", v6=v6)

# Allow ONLY the WireGuard UDP handshake to the endpoint on eth0
if is_ipv4(END):
    ipt("-A", "OUTPUT", "-o", ETH_IF, "-p", "udp", "-d", END, "--dport", PORT, "-j", "ACCEPT")
else:
    ipt("-A", "OUTPUT", "-o", ETH_IF, "-p", "udp", "-d", END, "--dport", PORT, "-j", "ACCEPT", v6=True)

# Bring up WireGuard (installs policy routing in table 51820)
run("wg-quick", "up", WG_DEV)

# Allow traffic over wg0 (only)
for v6 in (False, True):
    ipt("-A", "INPUT", "-i", WG_DEV, "-j", "ACCEPT", v6=v6)
    ipt("-A", "OUTPUT","-o", WG_DEV, "-j", "ACCEPT", v6=v6)

# --- Allow LAN to reach selected ports on eth0 (optional) ---
# Replies are allowed by ESTABLISHED rule above.
if LAN:
    if TCPP:
        ipt("-A", "INPUT", "-i", ETH_IF, "-s", LAN, "-p", "tcp",
            "-m", "multiport", "--dports", TCPP, "-j", "ACCEPT")
    if UDPP:
        ipt("-A", "INPUT", "-i", ETH_IF, "-s", LAN, "-p", "udp",
            "-m", "multiport", "--dports", UDPP, "-j", "ACCEPT")

    # Ensure replies to LAN are routed out eth0 (not wg0) despite policy rules.
    # Add a specific route in the WireGuard policy table (51820) pointing LAN to the eth0 gateway.
    try:
        gw = subprocess.check_output(
            ["/bin/sh","-lc", f"ip -4 route show default dev {ETH_IF} | awk '/default/ {{print $3}}'"],
            text=True
        ).strip()
        if gw:
            subprocess.run(["ip", "route", "replace", LAN, "via", gw, "dev", ETH_IF, "table", "51820"], check=True)
    except subprocess.CalledProcessError:
        pass

print(f"Kill switch active. {WG_DEV} up via {END}:{PORT}")

def down(*_):
    try: run("wg-quick", "down", WG_DEV)
    except Exception: pass
    sys.exit(0)

signal.signal(signal.SIGTERM, down)
signal.signal(signal.SIGINT,  down)

# Idle; restart policy + wg-quick handle hiccups
while True:
    time.sleep(3600)
