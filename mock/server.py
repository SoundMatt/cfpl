#!/usr/bin/env python3
"""Fake Peplink + fake Cloudflare + static UI mockup, in one process, for demos and CI.

  Peplink : POST/GET /cgi-bin/MANGA/api.cgi      (login, status.wan.connection)
  Cloudflare: /client/v4/...                     (tokens/verify, zones, dns_records)
  Control : POST /demo/wan?id=1&state=down|up    GET /demo/state
  Static  : /  -> ui-mockup/
Tokens: demo-token (ok) | template-only (cannot list zones) | wrong-zone | revoked
"""
import json
import os
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.environ.get("UI_DIR", os.path.join(os.path.dirname(__file__), "..", "ui-mockup"))
ZONE, ZONE_ID = "example.com", "7c1e0000000000000000000000a9f2"
lock = threading.Lock()
wans = {
    "1": {"name": "WAN 1", "enable": True, "ip": "203.0.113.10", "up": True, "priority": 1},
    "2": {"name": "WAN 2", "enable": True, "ip": "198.51.100.20", "up": True, "priority": 1},
    "3": {"name": "Cellular", "enable": True, "ip": "100.64.7.7", "up": True, "priority": 2},
}
records = []  # dns records


def wan_view():
    up = [w for w in wans.values() if w["up"]]
    best = min((w["priority"] for w in up), default=None)
    out = {}
    for k, w in wans.items():
        led = "red" if not w["up"] else ("green" if w["priority"] == best else "yellow")
        out[k] = {"name": w["name"], "enable": True, "ip": w["ip"] if w["up"] else "",
                  "statusLed": led, "priority": w["priority"],
                  "message": {"green": "Connected", "yellow": "Standby", "red": "Disconnected"}[led]}
    return out


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _token(self):
        return self.headers.get("Authorization", "").replace("Bearer ", "")

    def _cf(self, method, body=None):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path[len("/client/v4"):]
        tok = self._token()
        err = lambda c, m, code=403: self._json({"success": False, "errors": [{"code": c, "message": m}]}, code)
        if tok in ("", "revoked"):
            return err(1000, "Invalid API Token", 401)
        if p == "/user/tokens/verify":
            return self._json({"success": True, "result": {"status": "active"}})
        if p == "/zones":
            if tok == "template-only":
                return err(9109, "Unauthorized to access requested resource")
            ok = tok == "demo-token" and q.get("name") == ZONE
            return self._json({"success": True, "result": [{"id": ZONE_ID, "name": ZONE}] if ok else []})
        if p.startswith(f"/zones/{ZONE_ID}/dns_records"):
            if tok == "wrong-zone":
                return err(9109, "Unauthorized to access requested resource")
            rid = p.rsplit("/", 1)[-1] if p.count("/") > 3 else None
            with lock:
                if method == "GET":
                    res = [r for r in records if r["name"] == q.get("name") and q.get("type", r["type"]) == r["type"]]
                    return self._json({"success": True, "result": res})
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if method == "POST":
                    data["id"] = uuid.uuid4().hex
                    records.append(data)
                    return self._json({"success": True, "result": data})
                if method == "PUT":
                    for r in records:
                        if r["id"] == rid:
                            r.update(data)
                            return self._json({"success": True, "result": r})
        return err(7003, "Not found", 404)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/cgi-bin/MANGA/api.cgi":
            q = parse_qs(u.query)
            if q.get("func") == ["status.wan.connection"]:
                return self._json({"stat": "ok", "response": wan_view()})
            return self._json({"stat": "fail"})
        if u.path.startswith("/client/v4"):
            return self._cf("GET")
        if u.path == "/demo/state":
            return self._json({"wans": wan_view(), "records": records})
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/cgi-bin/MANGA/api.cgi":
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            return self._json({"stat": "ok"})
        if u.path.startswith("/client/v4"):
            return self._cf("POST")
        if u.path == "/demo/wan":
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if q.get("id") in wans:
                wans[q["id"]]["up"] = q.get("state") == "up"
            return self._json({"ok": True})
        self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/client/v4"):
            return self._cf("PUT")
        self.send_error(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"mock listening on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
