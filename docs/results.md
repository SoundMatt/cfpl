# Results (to be filled in from a real setup)

## Token scopes (`scripts/token_matrix.py`)
_Not run yet against real Cloudflare tokens._ Until then, treat the claim that the
"Edit zone DNS" template alone can't look up a zone by name as unverified.

## Failover timing (`scripts/failover_timing.py`)
_Not measured yet._ Fill in: seconds until the Cloudflare record changes, until a public resolver
returns the new IP (DNS-only, TTL 60), and until HTTP reaches the new origin (proxied).
