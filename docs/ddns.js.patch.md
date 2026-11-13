# Sketch: adding Cloudflare to Peplink's `ddns.js`

`ddns.js` is table-driven, so a new provider is mostly data. Sketch of the change against the 8.6 file:

```js
_ddm.splice(5, 0, [ "cloudflare", "Cloudflare" ]);          // provider list

_ddn.cloudflare = {                                          // field labels
    ddns_username: "Zone",
    ddns_password: "API Token",
    ddns_host:     "Hosts"
};

_ddd.cloudflare = [ "ddns_main_panel", "ddns_cloudflare_panel",   // visible rows
                    "ddns_default_panel", "ddns_host_panel" ];
```

New rows (`ddns_cloudflare_panel`): Zone ID (optional), Proxied checkbox (TTL → "Auto" when checked),
Update Mode (this WAN / follow active WAN / follow + standby IP), and a Verify button that runs the
three checks and reports each result. Validation: token matches `^[A-Za-z0-9_-]{20,}$`, zone is a valid
domain, hosts are inside the zone. The mockup in `ui-mockup/` shows the intended behaviour.
