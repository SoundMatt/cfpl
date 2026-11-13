#!/usr/bin/env python3
"""Run the three Verify steps for several tokens and print a Markdown results table.

    export CF_ZONE=example.com CF_HOST=home.example.com
    export TOK_TEMPLATE=...   # token from the "Edit zone DNS" template only
    export TOK_ZONEREAD_DNSEDIT=...   # Zone:Zone:Read + Zone:DNS:Edit on that one zone
    export TOK_WRONGZONE=...  # valid token scoped to a different zone
    python3 scripts/token_matrix.py

Tokens are read from the environment and never printed. Read-only: nothing is created or changed.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API = os.environ.get("CF_API", "https://api.cloudflare.com/client/v4")
ZONE, HOST = os.environ.get("CF_ZONE"), os.environ.get("CF_HOST")
TOKENS = {"Edit-zone-DNS template only": "TOK_TEMPLATE",
          "Zone Read + DNS Edit (one zone)": "TOK_ZONEREAD_DNSEDIT",
          "Wrong zone": "TOK_WRONGZONE"}


def call(token, path):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}


def cell(ok, code):
    return f"pass" if ok else f"FAIL ({code})"


if not (ZONE and HOST):
    sys.exit("Set CF_ZONE and CF_HOST")
print("| Token | 1 verify | 2 zone lookup | 3 read records (zone ID supplied) | 3 read records (via lookup) |")
print("|---|---|---|---|---|")
for label, var in TOKENS.items():
    tok = os.environ.get(var)
    if not tok:
        print(f"| {label} | (set {var}) | | | |")
        continue
    c1, j1 = call(tok, "/user/tokens/verify")
    c2, j2 = call(tok, "/zones?name=" + urllib.parse.quote(ZONE))
    zid = (j2.get("result") or [{}])[0].get("id") if j2.get("success") else None
    zid_known = os.environ.get("CF_ZONE_ID") or zid
    c3 = j3 = None
    if zid_known:
        c3, j3 = call(tok, f"/zones/{zid_known}/dns_records?name=" + urllib.parse.quote(HOST))
    ok2 = bool(j2.get("success") and zid)
    print(f"| {label} | {cell(j1.get('success'), c1)} | {cell(ok2, c2)} | "
          f"{cell(bool(j3 and j3.get('success')), c3) if os.environ.get('CF_ZONE_ID') else 'n/a (set CF_ZONE_ID)'} | "
          f"{cell(bool(j3 and j3.get('success')), c3) if zid else 'skipped (no zone ID)'} |")
