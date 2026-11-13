import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "daemon"))
sys.path.insert(0, os.path.join(ROOT, "mock"))
os.environ["UI_DIR"] = os.path.join(ROOT, "ui-mockup")

import ddns  # noqa: E402
import server  # noqa: E402


def wan(ip, led="green", pri=1, enable=True):
    return {"ip": ip, "statusLed": led, "priority": pri, "enable": enable}


class Logic(unittest.TestCase):
    def test_publishable(self):
        for ip in ("8.8.8.8", "2606:4700::1111"):
            self.assertTrue(ddns.is_publishable(ip), ip)
        for ip in ("10.0.0.1", "192.168.1.5", "172.16.0.9", "100.64.1.1", "127.0.0.1",
                   "169.254.1.1", "0.0.0.0", "fe80::1", "garbage", ""):
            self.assertFalse(ddns.is_publishable(ip), ip)

    def test_test_nets_opt_in_only(self):
        self.assertFalse(ddns.is_publishable("203.0.113.5"))
        self.assertTrue(ddns.is_publishable("203.0.113.5", allow_test_nets=True))
        self.assertFalse(ddns.is_publishable("100.64.1.1", allow_test_nets=True))  # CGNAT stays blocked

    def test_pick_highest_priority_connected(self):
        w = {"1": wan("8.8.8.8", pri=2), "2": wan("1.1.1.1", pri=1), "3": wan("9.9.9.9", "red", 1)}
        self.assertEqual(ddns.pick_ip(w), "1.1.1.1")

    def test_pick_ties_lowest_id(self):
        w = {"2": wan("1.1.1.1"), "1": wan("8.8.8.8")}
        self.assertEqual(ddns.pick_ip(w), "8.8.8.8")

    def test_pick_skips_standby_disabled_and_cgnat(self):
        w = {"1": wan("8.8.8.8", "yellow"), "2": wan("1.1.1.1", enable=False), "3": wan("100.64.0.9")}
        self.assertIsNone(ddns.pick_ip(w))

    def test_pick_pinned_wan(self):
        w = {"1": wan("8.8.8.8"), "2": wan("1.1.1.1")}
        self.assertEqual(ddns.pick_ip(w, "2"), "1.1.1.1")
        self.assertIsNone(ddns.pick_ip({"1": wan("8.8.8.8", "red")}, "1"))

    def test_parse_hosts(self):
        self.assertEqual(ddns.parse_hosts("a.x.com, b.x.com=2\nc.x.com"),
                         [("a.x.com", None), ("b.x.com", "2"), ("c.x.com", None)])


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        server.records.clear()
        for w in server.wans.values():
            w["up"] = True
        self.pep = ddns.Peplink(self.base, "a", "b", False)
        self.cf = ddns.Cloudflare(f"{self.base}/client/v4", "demo-token", "example.com")
        self.assertTrue(self.cf.verify(["home.example.com"]))
        self.state = {"applied": {}, "pending": {}}

    def poll(self, n=2, **kw):
        for _ in range(n):
            ddns.poll_once(self.pep, self.cf, [("home.example.com", None)], self.state,
                           allow_tn=True, **kw)
        return [r["content"] for r in server.records]

    def test_follows_failover_and_failback(self):
        self.assertEqual(self.poll(), ["203.0.113.10"])
        server.wans["1"]["up"] = False
        self.assertEqual(self.poll(), ["198.51.100.20"])
        server.wans["1"]["up"] = True
        self.assertEqual(self.poll(), ["203.0.113.10"])

    def test_standby_when_all_down_never_cgnat(self):
        for w in server.wans.values():
            w["up"] = False
        self.assertEqual(self.poll(standby="192.0.2.99"), ["192.0.2.99"])
        for k in ("1", "2"):
            server.wans[k]["up"] = False
        server.wans["3"]["up"] = True  # only the CGNAT cellular WAN is up
        self.state["applied"].clear()
        self.assertEqual(self.poll(standby="192.0.2.99"), ["192.0.2.99"])

    def test_debounce_blocks_single_blip(self):
        self.poll()
        server.wans["1"]["up"] = False
        self.assertEqual(self.poll(n=1, debounce=2), ["203.0.113.10"])  # one poll: no write yet

    def test_proxied_sets_auto_ttl_and_tag(self):
        self.poll(proxied=True, ttl=60)
        r = server.records[0]
        self.assertEqual((r["proxied"], r["ttl"], r["comment"]), (True, 1, ddns.MANAGED_COMMENT))

    def test_idempotent_no_second_write(self):
        self.poll()
        self.assertFalse(self.cf.upsert("home.example.com", "203.0.113.10", False, 60))

    def test_verify_failure_modes(self):
        for tok in ("template-only", "wrong-zone", "revoked"):
            bad = ddns.Cloudflare(f"{self.base}/client/v4", tok, "example.com")
            self.assertFalse(bad.verify(["home.example.com"]), tok)
        # template-only token passes if the Zone ID is supplied (skips the lookup)
        tmpl = ddns.Cloudflare(f"{self.base}/client/v4", "template-only", "example.com", server.ZONE_ID)
        self.assertTrue(tmpl.verify(["home.example.com"]))


if __name__ == "__main__":
    unittest.main()
