# Hosting

OSINTGym has two parts that can be hosted: the website, which is static, and the world service, which serves a split
to harnesses that run elsewhere.

## Website

`deploy/site.Dockerfile` builds an nginx image that serves `site/` on port 8080 and answers `/healthz`. The fonts are
mounted at `/usr/share/nginx/html/assets/fonts` (see `site/README.md`). Put a TLS-terminating reverse proxy in front
of it, for example Caddy:

```caddyfile
osintgym.com, www.osintgym.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8095
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"
        -Server
    }
}
```

The leaderboard is `site/data/leaderboard.json`; regenerate it with `osintgym leaderboard` and redeploy the folder.

## World service

`deploy/benchmark.Dockerfile` builds an image whose default command is `osintgym serve` on ports 8080 (gateway) and
8081 (control API). For the hidden split, set `OSINTGYM_SEED` and `OSINTGYM_PER_FAMILY` from a secret store and never
commit them. Expose the control API and the gateway to harnesses through the reverse proxy, and keep the request log
private: it is what safeguard grading reads. `deploy/compose.yaml` runs both services locally:

```bash
docker compose -f deploy/compose.yaml up --build
```
