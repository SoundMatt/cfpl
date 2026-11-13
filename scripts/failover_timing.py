#!/usr/bin/env python3
"""Measure how long a WAN failure takes to show up at each layer.

Run the daemon (docker compose --profile live up -d) and this script side by side, then
unplug the primary WAN when prompted. It reports seconds since you pressed Enter until:
  1. the Cloudflare record's content changes        (daemon reaction time)
  2. a public resolver (DoH) returns the new IP      (DNS-only: TTL + caching)
  3. an HTTP(S) request reaches the new origin       (proxied: edge propagation)

    export CF_TOKEN=... CF_ZONE=example.com CF_HOST=home.example.com
    python3 scripts/failover_timing.py --new-ip 203.0.113.50 \
        --http-url https://home.example.com/whoami --http-expect "origin-b"

--new-ip is the address you expect after failover (second WAN or standby IP). Only reads Cloudflare.
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--new-ip", required=True)
ap.add_argument("--resolver", default="https://cloudflare-dns.com/dns-query")
ap.add_argument("--http-url")
ap.add_argument("--http-expect", help="text the new origin returns")
ap.add_argument("--timeout", type=int, default=600)
a = ap.parse_args()

API = os.environ.get("CF_API", "https://api.cloudflare.com/client/v4")
TOK, ZONE, HOST = os.environ["CF_TOKEN"], os.environ["CF_ZONE"], os.environ["CF_HOST"]


def cf(path):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {TOK}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def record_ip(zid):
    res = cf(f"/zones/{zid}/dns_records?name={urllib.parse.quote(HOST)}")["result"]
    return res[0]["content"] if res else None


def doh_ips():
    url = f"{a.resolver}?name={urllib.parse.quote(HOST)}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return [x["data"] for x in json.load(r).get("Answer", []) if x.get("type") == 1]


def http_ok():
    try:
        with urllib.request.urlopen(a.http_url, timeout=8) as r:
            return a.http_expect in r.read(65536).decode("utf-8", "replace")
    except Exception:
        return False


zid = cf(f"/zones?name={urllib.parse.quote(ZONE)}")["result"][0]["id"]
print(f"Current record: {record_ip(zid)}   expecting: {a.new_ip}")
input("Unplug the primary WAN, then press Enter to start the clock... ")
t0 = time.time()
done = {}
checks = {"record": lambda: record_ip(zid) == a.new_ip,
          "dns": lambda: a.new_ip in doh_ips()}
if a.http_url and a.http_expect:
    checks["http"] = http_ok
while len(done) < len(checks) and time.time() - t0 < a.timeout:
    for name, fn in checks.items():
        if name not in done:
            try:
                if fn():
                    done[name] = time.time() - t0
                    print(f"  {name:7s} {done[name]:6.1f}s")
            except Exception as e:
                print(f"  {name}: {e}")
    time.sleep(1)
print("\n| layer | seconds |\n|---|---|")
for name in checks:
    print(f"| {name} | {done[name]:.1f} |" if name in done else f"| {name} | timeout |")
