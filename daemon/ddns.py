#!/usr/bin/env python3
"""Peplink WAN-aware Cloudflare DDNS prototype.

Polls the router's local API for WAN status and keeps Cloudflare A/AAAA records
pointed at the active WAN (or a standby IP when every WAN is down).
Configuration is entirely through environment variables; see .env.example.
"""
import ipaddress
import logging
import os
import sys
import time

import requests

log = logging.getLogger("ddns")
MANAGED_COMMENT = "managed by cfpl"


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        sys.exit(f"Missing required environment variable {name}")
    return v


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------- Peplink ----
class Peplink:
    """Minimal client for the router's local web-admin API (api.cgi)."""

    def __init__(self, base, user, password, verify_tls):
        self.base = base.rstrip("/")
        self.user, self.password = user, password
        self.s = requests.Session()
        self.s.verify = verify_tls
        self.logged_in = False

    def _login(self):
        r = self.s.post(f"{self.base}/cgi-bin/MANGA/api.cgi",
                        json={"func": "login", "username": self.user, "password": self.password},
                        timeout=10)
        r.raise_for_status()
        if r.json().get("stat") != "ok":
            raise RuntimeError(f"Peplink login failed: {r.text[:200]}")
        self.logged_in = True

    def wans(self):
        """Return {id: wan_dict} from status.wan.connection."""
        for attempt in (1, 2):
            if not self.logged_in:
                self._login()
            r = self.s.get(f"{self.base}/cgi-bin/MANGA/api.cgi",
                           params={"func": "status.wan.connection"}, timeout=10)
            j = r.json() if r.ok else {}
            if j.get("stat") == "ok":
                return {k: v for k, v in j["response"].items()
                        if isinstance(v, dict) and "ip" in v}
            self.logged_in = False  # session expired; log in again once
        raise RuntimeError("Peplink API did not return WAN status")


TEST_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def is_publishable(ip, allow_test_nets=False):
    """Never publish private, CGNAT, loopback, link-local... addresses.

    allow_test_nets additionally accepts the RFC 5737 documentation ranges (demo/CI only).
    """
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if allow_test_nets and any(a in n for n in TEST_NETS if a.version == n.version):
        return True
    return a.is_global


def pick_ip(wans, wan_id=None, allow_test_nets=False):
    """Highest-priority connected WAN with a publishable IP (ties: lowest id)."""
    cands = []
    for wid, w in wans.items():
        if wan_id and str(wid) != str(wan_id):
            continue
        if w.get("enable", True) and w.get("statusLed") == "green" \
                and is_publishable(w.get("ip", ""), allow_test_nets):
            cands.append((w.get("priority", 99), int(wid), w["ip"]))
    return sorted(cands)[0][2] if cands else None


# ------------------------------------------------------------- Cloudflare ----
class Cloudflare:
    def __init__(self, api, token, zone, zone_id=None):
        self.api, self.zone, self.zone_id = api.rstrip("/"), zone, zone_id
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _call(self, method, path, **kw):
        for attempt in range(4):
            r = self.s.request(method, f"{self.api}{path}", timeout=15, **kw)
            if r.status_code != 429 or attempt == 3:
                break
            wait = min(int(r.headers.get("Retry-After", 2 ** (attempt + 1)) or 2), 60)
            log.warning("rate limited by Cloudflare; retrying in %ss", wait)
            time.sleep(wait)
        try:
            j = r.json()
        except ValueError:
            j = {"success": False, "errors": [{"message": r.text[:200]}]}
        return r.status_code, j

    def verify(self, hosts):
        """Three-step check. Returns True if the token can do its job."""
        code, j = self._call("GET", "/user/tokens/verify")
        if not j.get("success"):
            log.error("1/3 token check FAILED (HTTP %s): token invalid or revoked", code)
            return False
        log.info("1/3 token is active")
        if self.zone_id:
            log.info("2/3 skipped, using configured Zone ID")
        else:
            code, j = self._call("GET", "/zones", params={"name": self.zone})
            if not j.get("success"):
                log.error("2/3 zone lookup FAILED (HTTP %s): probably missing Zone:Zone:Read; "
                          "add it or set CF_ZONE_ID", code)
                return False
            if not j.get("result"):
                log.error("2/3 no zone named %s visible: token scoped to another zone, or typo", self.zone)
                return False
            self.zone_id = j["result"][0]["id"]
            log.info("2/3 zone found, id cached")
        ok = True
        for h in hosts:
            code, j = self._call("GET", f"/zones/{self.zone_id}/dns_records", params={"name": h})
            if not j.get("success"):
                log.error("3/3 %s: cannot read records (HTTP %s): probably missing Zone:DNS:Edit", h, code)
                ok = False
            else:
                cur = [f"{r['type']} {r['content']}" for r in j["result"]]
                log.info("3/3 %s readable; current: %s", h, ", ".join(cur) or "no record (will be created)")
        return ok

    def upsert(self, host, ip, proxied, ttl, dry_run=False):
        rtype = "AAAA" if ":" in ip else "A"
        code, j = self._call("GET", f"/zones/{self.zone_id}/dns_records",
                             params={"name": host, "type": rtype})
        if not j.get("success"):
            raise RuntimeError(f"list records failed: {j.get('errors')}")
        body = {"type": rtype, "name": host, "content": ip,
                "proxied": proxied, "ttl": 1 if proxied else ttl,
                "comment": MANAGED_COMMENT}
        recs = j["result"]
        if recs and recs[0]["content"] == ip and recs[0].get("proxied") == proxied:
            return False
        if dry_run:
            log.info("[dry-run] would set %s %s -> %s", rtype, host, ip)
            return True
        if recs:
            code, j = self._call("PUT", f"/zones/{self.zone_id}/dns_records/{recs[0]['id']}", json=body)
        else:
            code, j = self._call("POST", f"/zones/{self.zone_id}/dns_records", json=body)
        if not j.get("success"):
            raise RuntimeError(f"update failed (HTTP {code}): {j.get('errors')}")
        log.info("updated %s %s -> %s%s", rtype, host, ip, " (proxied)" if proxied else "")
        return True


# ------------------------------------------------------------------- main ----
def parse_hosts(s):
    """'a.example.com, b.example.com=2' -> [(host, wan_id or None)]"""
    out = []
    for item in s.replace("\n", ",").split(","):
        item = item.strip()
        if item:
            h, _, w = item.partition("=")
            out.append((h.strip(), w.strip() or None))
    return out


def poll_once(pep, cf, hosts, state, standby="", allow_tn=False, proxied=False,
              ttl=60, debounce=2, dry_run=False):
    """One poll: read WANs, decide per host, update Cloudflare when stable."""
    applied, pending = state["applied"], state["pending"]
    wans = pep.wans()
    for host, wan_id in hosts:
        want = pick_ip(wans, wan_id, allow_tn)
        if want is None and standby and is_publishable(standby, allow_tn):
            want = standby
        if want is None:
            log.warning("%s: no publishable address; leaving record unchanged", host)
            pending.pop(host, None)
            continue
        if applied.get(host) == want:
            pending.pop(host, None)
            continue
        n = pending.get(host, (want, 0))
        n = (want, n[1] + 1) if n[0] == want else (want, 1)
        pending[host] = n
        if n[1] >= debounce:  # same answer N polls in a row: not flapping
            cf.upsert(host, want, proxied, ttl, dry_run)
            applied[host] = want
            pending.pop(host, None)


def main():
    logging.basicConfig(level=env("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(message)s")
    hosts = parse_hosts(env("CF_HOSTS", required=True))
    allow_tn = truthy(env("ALLOW_TEST_NETS", "0"))
    proxied = truthy(env("CF_PROXIED", "0"))
    ttl = int(env("CF_TTL", "60"))
    standby = env("STANDBY_IP", "")
    interval = int(env("POLL_INTERVAL", "10"))
    debounce = int(env("DEBOUNCE_POLLS", "2"))
    dry_run = truthy(env("DRY_RUN", "0"))

    pep = Peplink(env("PEPLINK_URL", required=True), env("PEPLINK_USER", required=True),
                  env("PEPLINK_PASS", required=True), truthy(env("PEPLINK_VERIFY_TLS", "0")))
    cf = Cloudflare(env("CF_API", "https://api.cloudflare.com/client/v4"),
                    env("CF_TOKEN", required=True), env("CF_ZONE", required=True), env("CF_ZONE_ID"))

    if not cf.verify([h for h, _ in hosts]):
        sys.exit("Verify failed; fix the token/zone and retry.")
    if "--verify" in sys.argv:
        return

    reconcile = int(env("RECONCILE_SECONDS", "1800"))
    state = {"applied": {}, "pending": {}}
    last_reconcile = time.monotonic()
    while True:
        if reconcile and time.monotonic() - last_reconcile >= reconcile:
            state["applied"].clear()  # re-read Cloudflare; upsert is a no-op if already correct
            last_reconcile = time.monotonic()
            log.info("periodic reconcile")
        try:
            poll_once(pep, cf, hosts, state, standby, allow_tn, proxied, ttl, debounce, dry_run)
        except Exception as e:  # keep running through transient failures
            log.error("poll failed: %s", e)
        if "--once" in sys.argv:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
