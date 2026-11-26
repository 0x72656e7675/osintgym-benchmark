# Website

Static site for osintgym.com: `index.html`, `assets/` and the leaderboard in `data/leaderboard.json`, which
`osintgym leaderboard` writes from results files.

The typeface is Satoshi by the Indian Type Foundry, distributed through Fontshare under its own terms. It is not
part of this repository: place the three files named in `assets/osintgym.css` (`satoshi-300.woff2`,
`satoshi-400.woff2`, `satoshi-700.woff2`) in `assets/fonts/`, or mount a directory holding them there, as
`deploy/compose.yaml` does. Without them the site falls back to system fonts.

`deploy/site.Dockerfile` serves the folder with nginx on port 8080 and answers `/healthz` for health checks.
