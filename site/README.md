# Website

Static site for osintgym.com: `index.html`, `assets/` and the leaderboard in `data/leaderboard.json`, which
`osintgym leaderboard` writes from results files.

The typefaces are Satoshi and, in the navigation bar, Switzer, both by the Indian Type Foundry and distributed
through Fontshare under its own terms. They are not part of this repository: place the five files named in
`assets/osintgym.css` (`satoshi-300.woff2`, `satoshi-400.woff2`, `satoshi-700.woff2`, `switzer-400.woff2`,
`switzer-500.woff2`) in `assets/fonts/`, or mount a directory holding them there, as
`deploy/compose.yaml` does. Without them the site falls back to system fonts.

`deploy/site.Dockerfile` serves the folder with nginx on port 8080 and answers `/healthz` for health checks.
