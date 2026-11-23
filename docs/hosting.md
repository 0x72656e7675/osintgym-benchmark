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
8081 (control API). `deploy/compose.yaml` runs it locally with the development split:

```bash
docker compose -f deploy/compose.yaml up --build
```

## Hosting a hidden split

A hidden split is the same service started with a secret seed and a state directory:

```bash
OSINTGYM_SEED=... OSINTGYM_PER_FAMILY=6 OSINTGYM_STATE=/srv/hidden-split \
  osintgym serve --host 0.0.0.0 --public-gateway https://benchmark.example
```

Draw the seed at random with at least 128 bits, for example `python -c "import secrets; print(secrets.randbits(128))"`,
keep it and the scenario count in a secret store, and never print or commit them. The generator is public, so a
short seed could be found by generating worlds until one matches a task card. Run `osintgym validate` with the same
environment before serving a new seed or a new build: it must report no problems.

With a state directory, every control API call needs a run key, each run opens a fixed number of attempts per task,
the gateway serves only attempts that are open, and nothing about a submission is returned. The directory holds the
issued runs (by key digest), the opened attempts, the request log and the submissions as JSON lines, and survives
restarts; it is private, since the request log is what safeguard grading reads. Only rows published from verified
runs are served, at `GET /v1/leaderboard`, which the website merges into its leaderboard.

Runs are managed with `osintgym runs`, in the same environment as the service:

| Command | Effect |
|---|---|
| `osintgym runs issue --system NAME --model MODEL --harness HARNESS [--level N] [--repeats N]` | Issues a run and prints its key once |
| `osintgym runs list` | Runs with their attempts opened and submitted |
| `osintgym runs close RUN` | Stops the run from opening attempts |
| `osintgym runs verify RUN [--publish]` | Grades every task of the split for the run, writes the full report to the state directory and prints the leaderboard row, publishing it with `--publish` |
| `osintgym runs withdraw RUN` | Removes a published row |

`verify` also prints integrity counts for the reviewer: attempts submitted, left open or never opened, and solved
attempts that cite pages they never requested.

Harnesses reach a hosted split over HTTPS, where a proxy cannot be addressed, so the reverse proxy must forward two
paths besides the website: `/v1/` to the control API and `/gateway/` to the gateway, both without stripping the
prefix. Responses of the gateway carry `Cache-Control: no-store, no-transform`, which keeps a CDN from caching them or
rewriting pages and images; check that pages fetched through it are identical to the ones the gateway serves. With
Caddy:

```caddyfile
benchmark.example {
    encode zstd gzip
    reverse_proxy /v1/* 127.0.0.1:8081
    reverse_proxy /gateway/* 127.0.0.1:8080
    reverse_proxy 127.0.0.1:8095
    @service path /v1/* /gateway/*
    header @service {
        Content-Security-Policy "sandbox; default-src 'none'"
        X-Robots-Tag "noindex, nofollow"
    }
}
```
