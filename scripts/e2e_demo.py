#!/usr/bin/env python3
"""Assert the running demo stack follows WAN changes. Used by CI and handy locally.

    docker compose --profile demo up -d --build && python3 scripts/e2e_demo.py
"""
import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.load(r)


def wan(i, state):
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/demo/wan?id={i}&state={state}", method="POST"), timeout=5)


def record():
    r = [x["content"] for x in get("/demo/state")["records"] if x["name"] == "home.example.com"]
    return r[0] if r else None


def expect(want, why, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if record() == want:
            print(f"ok   {why}: {want}")
            return
        time.sleep(1)
    sys.exit(f"FAIL {why}: wanted {want}, got {record()}")


for i in (1, 2, 3):
    wan(i, "up")
expect("203.0.113.10", "initial (WAN 1)")
wan(1, "down"); expect("198.51.100.20", "WAN 1 down -> WAN 2")
wan(2, "down"); expect("192.0.2.99", "all primaries down -> standby, never CGNAT")
wan(1, "up");   expect("203.0.113.10", "WAN 1 back -> failback")
print("all good")
