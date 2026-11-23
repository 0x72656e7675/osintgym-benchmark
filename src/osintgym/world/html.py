from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def link(href: str, text: object) -> str:
    return f'<a href="{esc(href)}">{esc(text)}</a>'


def facts(rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
    return f'<dl class="facts">{body}</dl>'


def items(entries: list[str], cls: str = "results") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{e}</li>" for e in entries) + "</ul>"


def form(action: str, label: str, fields: dict[str, str] | None = None, textarea: str | None = None) -> str:
    hidden = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in (fields or {}).items())
    area = f'<textarea name="{esc(textarea)}" rows="3"></textarea>' if textarea else ""
    return f'<form method="post" action="{esc(action)}">{hidden}{area}<button type="submit">{esc(label)}</button></form>'


def page(site: str, title: str, body: str, *, accent: str = "#2d5b8a", nav: str = "", head: str = "") -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(title)}</title>{head}"
        "<style>body{font-family:system-ui,sans-serif;margin:0;color:#1c1c1c;background:#f6f6f4}"
        f"header{{background:{accent};color:#fff;padding:10px 24px;display:flex;gap:18px;align-items:center}}"
        "header a{color:#fff;text-decoration:none;font-weight:600}main{max-width:880px;margin:24px auto;padding:0 18px}"
        "dl.facts{display:grid;grid-template-columns:200px 1fr;gap:6px 14px}dt{color:#666}dd{margin:0}"
        "ul.results{list-style:none;padding:0}ul.results li{padding:10px 0;border-bottom:1px solid #ddd}"
        ".meta{color:#777;font-size:.9em}article.post{background:#fff;border:1px solid #e3e3e3;padding:12px 14px;margin:10px 0}"
        "img{max-width:100%}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left}"
        "</style></head><body>"
        f"<header><a href=\"/\">{esc(site)}</a>{nav}</header><main>{body}</main>"
        f"<footer class=\"meta\" style=\"text-align:center;padding:24px\">{esc(site)}</footer></body></html>"
    )


def text_of(markup: str) -> str:
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", markup))).strip()
