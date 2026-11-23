from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit

from ..rng import token as make_token
from . import images
from .html import esc, facts, form, items, link, page, text_of
from .model import Account, Company, Domain, Person, Post, World
from .search import Index, fold, tokens
from .urls import (
    AGORA, ARCHIVE, ATLAS, CODESEARCH, CRT, GLIMPSE, GUILDHALL, HERALD, LENS, MAILBOX, MURMUR, PASTE, REGISTRY,
    SANCTIONS, SEARCH, WHOIS, account_url, archive_capture_url, article_url, atlas_place_url, avatar_url,
    company_url, guildhall_company_url, officer_url, post_media_url, post_url, sanction_url, thread_url,
)


@dataclass
class Request:
    method: str
    host: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    form: dict[str, str] = field(default_factory=dict)
    attempt: str | None = None


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "text/html; charset=utf-8"
    event: dict | None = None


def _html(markup: str, status: int = 200, event: dict | None = None) -> Response:
    return Response(status, markup.encode(), event=event)


def _jpeg(data: bytes) -> Response:
    return Response(200, data, "image/jpeg")


def when(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def month(moment) -> str:
    return moment.strftime("%B %Y")


def split_url(url: str) -> tuple[str, str, dict[str, str]]:
    parts = urlsplit(url if "://" in url else f"http://{url}")
    query: dict[str, str] = {}
    for pair in parts.query.split("&"):
        if pair:
            key, _, value = pair.partition("=")
            query.setdefault(unquote(key.replace("+", " ")), unquote(value.replace("+", " ")))
    path = unquote(parts.path) or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return (parts.hostname or "").lower(), path, query


def canonical(url: str) -> str:
    host, path, query = split_url(url)
    suffix = ("?" + "&".join(f"{k}={quote(v, safe='')}" for k, v in sorted(query.items()))) if query else ""
    return f"http://{host.removeprefix('www.')}{'' if path == '/' else path}{suffix}"


class Web:
    """Every site of the world, rendered on demand from the world model."""

    def __init__(self, world: World):
        self.world = world
        seed = world.seed
        self.by_handle = {(a.site, a.handle.lower()): a for a in world.accounts.values()}
        self.posts = {p.token: p for p in world.posts.values()}
        self.avatars = {make_token(seed, "avatar", a.key): a for a in world.accounts.values() if a.avatar}
        self.companies = {c.number: c for c in world.companies.values()}
        self.company_slugs = {c.slug: c for c in world.companies.values()}
        self.officers = {p.officer_token: p for p in world.people.values()}
        self.threads = {t.token: t for t in world.threads.values()}
        self.articles = {a.slug: a for a in world.articles.values()}
        self.venues = {v.token: v for v in world.venues.values()}
        self.sanctions = {s.ref: s for s in world.sanctions.values()}
        self.pastes: list[dict] = []
        self._index: Index | None = None
        self._code: dict[str, str] | None = None
        self.images: dict[str, str] = {}
        for photo_key, urls in world.appearances.items():
            for url in urls:
                if url.endswith(".jpg"):
                    self.images[canonical(url)] = photo_key
        for avatar_token, account in self.avatars.items():
            self.images[canonical(avatar_url(account, avatar_token))] = account.avatar
        for post in world.posts.values():
            if post.photo and world.accounts[post.account].site == "glimpse":
                self.images[canonical(post_media_url(world, post, original=True))] = post.photo

    # Entry points

    def handle(self, request: Request, as_of: datetime | None = None) -> Response | None:
        host = request.host.removeprefix("www.")
        site = {
            MURMUR: self.murmur, GLIMPSE: self.glimpse, GUILDHALL: self.guildhall, AGORA: self.agora,
            HERALD: self.herald, REGISTRY: self.registry, WHOIS: self.whois, CRT: self.crt,
            CODESEARCH: self.codesearch, ARCHIVE: self.archive, LENS: self.lens, ATLAS: self.atlas,
            PASTE: self.paste, SANCTIONS: self.sanction_list, SEARCH: self.search, MAILBOX: self.mailbox,
        }.get(host)
        if site is not None:
            return site(request, as_of)
        if host in self.world.domains:
            return self.website(request, self.world.domains[host], as_of)
        return None

    def get(self, url: str, as_of: datetime | None = None) -> Response | None:
        host, path, query = split_url(url)
        return self.handle(Request("GET", host, path, query), as_of)

    def exists(self, url: str) -> bool:
        response = self.get(url)
        return response is not None and response.status == 200

    def is_world_host(self, host: str) -> bool:
        host = host.lower().removeprefix("www.")
        return host in self.world.domains or host in {
            MURMUR, GLIMPSE, GUILDHALL, AGORA, HERALD, REGISTRY, WHOIS, CRT, CODESEARCH, ARCHIVE, LENS, ATLAS,
            PASTE, SANCTIONS, SEARCH, MAILBOX}

    def _now(self, as_of: datetime | None) -> datetime:
        return as_of or self.world.now

    def _missing(self, site: str, message: str = "Page not found") -> Response:
        return _html(page(site, message, f"<h1>{esc(message)}</h1>"), 404)

    def _avatar(self, account: Account, size: int = 120) -> str:
        if not account.avatar:
            return ""
        return f'<img src="{esc(avatar_url(account, make_token(self.world.seed, "avatar", account.key)))}" alt="" width="{size}">'

    def _avatar_image(self, avatar_token: str) -> Response | None:
        account = self.avatars.get(avatar_token)
        if account is None:
            return None
        return _jpeg(images.render(self.world.photos[account.avatar], self.world.seed, exif=False))

    def _action(self, site: str, kind: str, account: Account, request: Request, message: str) -> Response:
        event = {"kind": kind, "site": account.site, "target": account.key, "fields": dict(request.form)}
        return _html(page(site, message, f"<h1>{esc(message)}</h1>"), 200, event)

    # Murmur: microblogging

    def _visible(self, post: Post, as_of: datetime | None) -> bool:
        now = self._now(as_of)
        return post.created <= now and not (post.deleted_at and post.deleted_at <= now)

    def _visible_posts(self, account: Account, as_of: datetime | None) -> list[Post]:
        return [p for p in self.world.posts_of(account.key) if self._visible(p, as_of)]

    def _protected(self, account: Account, as_of: datetime | None) -> bool:
        return account.private_since is not None and account.private_since <= self._now(as_of)

    def _place(self, post: Post) -> str:
        if not post.venue:
            return ""
        return f" | at {esc(self.world.venues[post.venue].name)}"

    def _murmur_post(self, post: Post, account: Account) -> str:
        media = ""
        if post.photo:
            media = f'<img src="{esc(post_media_url(self.world, post))}" alt="" width="480">'
        return (f'<article class="post"><p>{esc(post.text)}</p>{media}<p class="meta">'
                f'{link(post_url(self.world, post), when(post.created))}{self._place(post)}</p></article>')

    def murmur(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Murmur", request.path
        nav = link("/search", "Search")
        if path.startswith("/media/") and path.endswith(".jpg"):
            post = self.posts.get(path[7:-4])
            if post and post.photo and self.world.accounts[post.account].site == "murmur":
                return _jpeg(images.render(self.world.photos[post.photo], self.world.seed, exif=False))
            return self._missing(site)
        if path.startswith("/avatar/") and path.endswith(".jpg"):
            return self._avatar_image(path[8:-4]) or self._missing(site)
        if path == "/search":
            q = request.query.get("q", "").strip()
            found = []
            if q:
                folded = fold(q.lstrip("@"))
                for account in self.world.accounts.values():
                    if account.site == "murmur" and (folded in account.handle.lower() or folded in fold(account.display_name)):
                        found.append(f'{link(account_url(account), "@" + account.handle)} {esc(account.display_name)}')
                for post in self.world.posts.values():
                    account = self.world.accounts[post.account]
                    if (account.site == "murmur" and folded in fold(post.text) and not self._protected(account, as_of)
                            and self._visible(post, as_of)):
                        found.append(f'{link(post_url(self.world, post), post.text[:90])} by @{esc(account.handle)}')
            body = (f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search</button></form>'
                    + items(found[:40]))
            return _html(page(site, f"Search: {q}", body, accent="#1f6f78", nav=nav))
        if path.startswith("/@"):
            parts = path[2:].split("/")
            account = self.by_handle.get(("murmur", parts[0].lower()))
            if account is None or account.created > self._now(as_of):
                return self._missing(site, "This account doesn't exist")
            if len(parts) == 2 and request.method == "POST" and parts[1] in ("follow", "message"):
                kind = "follow" if parts[1] == "follow" else "message"
                return self._action(site, kind, account, request,
                                    "Follow request sent" if kind == "follow" else "Message sent")
            if len(parts) == 3 and parts[1] == "status":
                post = self.posts.get(parts[2])
                if post is None or post.account != account.key or post.created > self._now(as_of):
                    return self._missing(site)
                if post.deleted_at and post.deleted_at <= self._now(as_of):
                    return self._missing(site, "This post was deleted")
                if self._protected(account, as_of):
                    return _html(page(site, "Protected post", "<h1>These posts are protected</h1>", accent="#1f6f78"), 403)
                body = f"<p>{link(account_url(account), '@' + account.handle)}</p>" + self._murmur_post(post, account)
                return _html(page(site, f"{account.display_name} on Murmur", body, accent="#1f6f78", nav=nav))
            if len(parts) != 1:
                return self._missing(site)
            shown = {"bio": account.bio, "website": account.website or "", "location": account.location}
            if account.before_private and not self._protected(account, as_of):
                shown.update(account.before_private)
            rows = []
            if shown["location"]:
                rows.append(("Location", esc(shown["location"])))
            if shown["website"]:
                rows.append(("Website", link(shown["website"], shown["website"].removeprefix("http://"))))
            rows.append(("Joined", month(account.created)))
            body = (f'<section class="profile">{self._avatar(account)}<h1>{esc(account.display_name)}</h1>'
                    f'<p class="handle">@{esc(account.handle)}</p><p class="bio">{esc(shown["bio"])}</p>{facts(rows)}'
                    f'{form(f"/@{account.handle}/follow", "Follow")}'
                    f'{form(f"/@{account.handle}/message", "Message", textarea="text")}</section>')
            if self._protected(account, as_of):
                body += "<h2>These posts are protected</h2><p>Only approved followers can see this account's posts.</p>"
            else:
                body += "<h2>Posts</h2>" + "".join(self._murmur_post(p, account) for p in self._visible_posts(account, as_of)[:60])
            return _html(page(site, f"{account.display_name} (@{account.handle})", body, accent="#1f6f78", nav=nav))
        recent = sorted((p for p in self.world.posts.values() if self.world.accounts[p.account].site == "murmur"
                         and not p.deleted_at and not self.world.accounts[p.account].private_since),
                        key=lambda p: p.created, reverse=True)[:12]
        body = ('<form action="/search"><input name="q"><button>Search</button></form><h2>Latest</h2>'
                + "".join(self._murmur_post(p, self.world.accounts[p.account]) for p in recent))
        return _html(page(site, "Murmur", body, accent="#1f6f78", nav=nav))

    # Glimpse: photo community that keeps original files

    def glimpse(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Glimpse", request.path
        if path.startswith("/avatar/") and path.endswith(".jpg"):
            return self._avatar_image(path[8:-4]) or self._missing(site)
        if path.startswith("/p/"):
            parts = path[3:].split("/")
            post = self.posts.get(parts[0])
            if post is None or self.world.accounts[post.account].site != "glimpse" or post.created > self._now(as_of):
                return self._missing(site)
            photo = self.world.photos[post.photo]
            if len(parts) == 2 and parts[1] in ("display.jpg", "original.jpg"):
                return _jpeg(images.render(photo, self.world.seed, exif=parts[1] == "original.jpg"))
            account = self.world.accounts[post.account]
            rows = [("Taken", photo.taken.strftime("%Y-%m-%d")), ("Camera", f"{esc(photo.make)} {esc(photo.model)}"),
                    ("Original", link(post_media_url(self.world, post, original=True), "Download original"))]
            body = (f'<img src="{esc(post_media_url(self.world, post))}" alt="" width="720"><p>{esc(post.text)}</p>'
                    f'{facts(rows)}<p class="meta">by {link(account_url(account), account.display_name)} | '
                    f'{when(post.created)}</p>')
            return _html(page(site, post.text or "Photo", body, accent="#7a3e8c"))
        if path.startswith("/u/"):
            parts = path[3:].split("/")
            account = self.by_handle.get(("glimpse", parts[0].lower()))
            if account is None or account.created > self._now(as_of):
                return self._missing(site)
            if len(parts) == 2 and parts[1] == "follow" and request.method == "POST":
                return self._action(site, "follow", account, request, "You are now following this photographer")
            rows = []
            if account.location:
                rows.append(("Location", esc(account.location)))
            if account.website:
                rows.append(("Website", link(account.website, account.website.removeprefix("http://"))))
            for other in account.links:
                rows.append(("Elsewhere", link(other, other.removeprefix("http://"))))
            grid = "".join(
                f'<li>{link(post_url(self.world, p), p.text or "Untitled")}'
                f'<br><img src="{esc(post_media_url(self.world, p))}" alt="" width="220"></li>'
                for p in self._visible_posts(account, as_of))
            body = (f'{self._avatar(account)}<h1>{esc(account.display_name)}</h1><p>@{esc(account.handle)}</p>'
                    f'<p>{esc(account.bio)}</p>{facts(rows)}{form(f"/u/{account.handle}/follow", "Follow")}'
                    f'<h2>Photos</h2><ul class="results">{grid}</ul>')
            return _html(page(site, f"{account.display_name} on Glimpse", body, accent="#7a3e8c"))
        return _html(page(site, "Glimpse", "<h1>Glimpse</h1><p>Share full-resolution photos.</p>", accent="#7a3e8c"))

    # Guildhall: professional network

    def _current(self, account: Account, company_key: str) -> bool:
        return any(e.company == company_key and e.end is None for e in account.experience)

    def guildhall(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Guildhall", request.path
        nav = link("/search", "People")
        if path.startswith("/photo/") and path.endswith(".jpg"):
            return self._avatar_image(path[7:-4]) or self._missing(site)
        if path == "/search":
            q = request.query.get("q", "").strip()
            wanted = tokens(q)
            found = []
            if wanted:
                for account in self.world.accounts.values():
                    if account.site != "guildhall":
                        continue
                    companies = " ".join(self.world.companies[e.company].name for e in account.experience)
                    have = set(tokens(f"{account.display_name} {account.headline} {account.location} {companies}"))
                    if all(t in have for t in wanted):
                        found.append(f'{link(account_url(account), account.display_name)}<br>'
                                     f'<span class="meta">{esc(account.headline)} | {esc(account.location)}</span>')
            body = (f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search people</button></form>'
                    + f"<p>{len(found)} results</p>" + items(found[:50]))
            return _html(page(site, f"People: {q}", body, accent="#24405f", nav=nav))
        if path.startswith("/company/"):
            company = self.company_slugs.get(path[9:])
            if company is None:
                return self._missing(site)
            people = sorted((a for a in self.world.accounts.values()
                             if a.site == "guildhall" and self._current(a, company.key)), key=lambda a: a.display_name)
            rows = [("Industry", esc(company.sector.capitalize() or "Services")),
                    ("Headquarters", esc(self.world.cities[company.city].name))]
            if company.website:
                rows.append(("Website", link(f"http://{company.website}", company.website)))
            listed = items([f'{link(account_url(a), a.display_name)} <span class="meta">{esc(a.headline)}</span>'
                            for a in people[:3]])
            body = (f"<h1>{esc(company.name)}</h1><p>{esc(company.description)}</p>{facts(rows)}"
                    f"<h2>People</h2><p>Showing {min(3, len(people))} of {len(people)} people on Guildhall.</p>{listed}")
            return _html(page(site, company.name, body, accent="#24405f", nav=nav))
        if path.startswith("/in/"):
            parts = path[4:].split("/")
            account = self.by_handle.get(("guildhall", parts[0].lower()))
            if account is None:
                return self._missing(site)
            if len(parts) == 2 and request.method == "POST" and parts[1] in ("connect", "message"):
                return self._action(site, parts[1], account, request,
                                    "Invitation sent" if parts[1] == "connect" else "Message sent")
            jobs = []
            for e in account.experience:
                company = self.world.companies[e.company]
                span = f"{month(e.start)} - {month(e.end) if e.end else 'Present'}"
                jobs.append(f"<strong>{esc(e.title)}</strong> at {link(guildhall_company_url(company), company.name)}"
                            f'<br><span class="meta">{span}</span>')
            rows = [("Location", esc(account.location))]
            for other in account.links:
                rows.append(("Elsewhere", link(other, other.removeprefix("http://"))))
            body = (f"{self._avatar(account)}<h1>{esc(account.display_name)}</h1><p>{esc(account.headline)}</p>"
                    f"{facts(rows)}<h2>About</h2><p>{esc(account.about)}</p><h2>Experience</h2>{items(jobs)}"
                    f"<h2>Education</h2>{items([esc(e) for e in account.education])}"
                    f'{form(f"/in/{account.handle}/connect", "Connect")}'
                    f'{form(f"/in/{account.handle}/message", "Message", textarea="text")}')
            return _html(page(site, f"{account.display_name} | Guildhall", body, accent="#24405f", nav=nav))
        return _html(page(site, "Guildhall", '<form action="/search"><input name="q"><button>Search people</button></form>',
                          accent="#24405f", nav=nav))

    # Agora: community forum

    def agora(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Agora", request.path
        if path == "/search":
            q = request.query.get("q", "").strip()
            folded = fold(q)
            found = []
            if folded:
                for account in self.world.accounts.values():
                    if account.site == "agora" and folded in account.handle.lower():
                        found.append(f"Member: {link(account_url(account), account.handle)}")
                for thread in self.world.threads.values():
                    if thread.noindex:
                        continue
                    if folded in fold(thread.title) or any(folded in fold(p.text) for p in thread.posts):
                        found.append(f"Thread: {link(thread_url(thread), thread.title)}")
            body = f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search</button></form>' + items(found[:40])
            return _html(page(site, f"Search: {q}", body, accent="#6b4f1d"))
        if path.startswith("/t/"):
            parts = path[3:].split("/")
            thread = self.threads.get(parts[0])
            if thread is None:
                return self._missing(site)
            if len(parts) == 2 and parts[1] == "reply" and request.method == "POST":
                author = self.world.accounts[thread.posts[0].author]
                return self._action(site, "reply", author, request, "Reply posted")
            posts = []
            for post in thread.posts:
                if post.created > self._now(as_of):
                    continue
                author = self.world.accounts[post.author]
                signature = f'<p class="meta">-- {esc(author.signature)}</p>' if author.signature else ""
                posts.append(f'<article class="post"><p class="meta">{link(account_url(author), author.handle)} | '
                             f'{when(post.created)}</p><p>{esc(post.text)}</p>{signature}</article>')
            head = '<meta name="robots" content="noindex">' if thread.noindex else ""
            body = f"<h1>{esc(thread.title)}</h1><p class=\"meta\">Board: {esc(thread.board)}</p>{''.join(posts)}"
            return _html(page(site, thread.title, body, accent="#6b4f1d", head=head))
        if path.startswith("/u/"):
            parts = path[3:].split("/")
            account = self.by_handle.get(("agora", parts[0].lower()))
            if account is None or account.created > self._now(as_of):
                return self._missing(site)
            if len(parts) == 2 and parts[1] == "message" and request.method == "POST":
                return self._action(site, "message", account, request, "Private message sent")
            rows = [("Member since", month(account.created))]
            if account.website:
                rows.append(("Website", link(account.website, account.website.removeprefix("http://"))))
            if account.location:
                rows.append(("Location", esc(account.location)))
            if account.signature:
                rows.append(("Signature", esc(account.signature)))
            threads = [link(thread_url(t), t.title) for t in self.world.threads.values()
                       if not t.noindex and any(p.author == account.key for p in t.posts)]
            body = (f"<h1>{esc(account.handle)}</h1><p>{esc(account.bio)}</p>{facts(rows)}"
                    f'{form(f"/u/{account.handle}/message", "Send private message", textarea="text")}'
                    f"<h2>Recent threads</h2>{items(threads[:20])}")
            return _html(page(site, f"{account.handle} | Agora", body, accent="#6b4f1d"))
        boards = sorted({t.board for t in self.world.threads.values()})
        latest = [link(thread_url(t), t.title) for t in self.world.threads.values() if not t.noindex][:20]
        body = f"<h1>Agora</h1><p>Boards: {esc(', '.join(boards))}</p>{items(latest)}"
        return _html(page(site, "Agora", body, accent="#6b4f1d"))

    # Herald: news

    def herald(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "The Norvessa Herald", request.path
        if path.startswith("/news/"):
            article = self.articles.get(path.rsplit("/", 1)[-1])
            if article is None or article.published > self._now(as_of):
                return self._missing(site)
            body = (f"<h1>{esc(article.title)}</h1><p class=\"meta\">By {esc(article.byline)} | {when(article.published)}</p>"
                    + "".join(f"<p>{esc(p)}</p>" for p in article.paragraphs))
            return _html(page(site, article.title, body, accent="#8a1c1c"))
        q = request.query.get("q", "").strip() if path == "/search" else ""
        chosen = sorted(self.world.articles.values(), key=lambda a: a.published, reverse=True)
        if q:
            chosen = [a for a in chosen if all(t in tokens(a.title + " " + " ".join(a.paragraphs)) for t in tokens(q))]
        body = (f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search</button></form>'
                + items([f"{link(article_url(a), a.title)} <span class=\"meta\">{a.published:%Y-%m-%d}</span>" for a in chosen[:30]]))
        return _html(page(site, site, body, accent="#8a1c1c"))

    # Registry of companies

    def _ownership(self, company: Company) -> tuple[list[str], list[str], list[str]]:
        persons, corporates, ceased = [], [], []
        for holding in company.owners:
            if holding.kind == "person":
                holder = self.world.people[holding.holder]
                label = (f"{link(officer_url(holder), holder.name)} | born {month(holder.born)} | {esc(holder.nationality)}"
                         f" | ownership of shares: {holding.percent:g}%")
            else:
                parent = self.world.companies[holding.holder]
                label = f"{link(company_url(parent), parent.name)} ({esc(parent.number)}) | ownership of shares: {holding.percent:g}%"
            label += f" | notified {holding.since:%Y-%m-%d}"
            if holding.ceased:
                ceased.append(label + f" | ceased {holding.ceased:%Y-%m-%d}")
            elif holding.kind == "person":
                persons.append(label)
            else:
                corporates.append(label)
        return persons, corporates, ceased

    def registry(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Norvessa Companies Registry", request.path
        accent = "#3a3a3a"
        if path == "/search":
            q = request.query.get("q", "").strip()
            wanted = tokens(q)
            found = []
            if wanted:
                for company in self.world.companies.values():
                    if all(t in tokens(company.name) for t in wanted):
                        found.append(f"Company: {link(company_url(company), company.name)} ({esc(company.number)}) | {esc(company.status)}")
                seen: set[str] = set()
                for company in self.world.companies.values():
                    linked = [o.person for o in company.officers] + [h.holder for h in company.owners if h.kind == "person"]
                    for key in linked:
                        person = self.world.people[key]
                        if key not in seen and all(t in tokens(person.name) for t in wanted):
                            seen.add(key)
                            found.append(f"Person: {link(officer_url(person), person.name)} | born {month(person.born)}")
            body = f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search</button></form>' + items(found[:60])
            return _html(page(site, f"Search: {q}", body, accent=accent))
        if path.startswith("/company/"):
            company = self.companies.get(path[9:])
            if company is None:
                return self._missing(site)
            officers = []
            for officer in company.officers:
                person = self.world.people[officer.person]
                tail = f" | resigned {officer.resigned:%Y-%m-%d}" if officer.resigned else ""
                officers.append(f"{link(officer_url(person), person.name)} | {esc(officer.role)} | appointed "
                                f"{officer.appointed:%Y-%m-%d}{tail}")
            persons, corporates, ceased = self._ownership(company)
            rows = [("Company number", esc(company.number)), ("Status", esc(company.status)),
                    ("Incorporated", f"{company.incorporated:%Y-%m-%d}"), ("Registered office", esc(company.address)),
                    ("Nature of business", esc(company.sector or "Other service activities"))]
            body = (f"<h1>{esc(company.name)}</h1>{facts(rows)}<h2>Officers</h2>{items(officers)}"
                    f"<h2>Persons with significant control</h2>{items(persons) if persons else '<p>None notified.</p>'}"
                    f"<h2>Corporate shareholders</h2>{items(corporates) if corporates else '<p>None notified.</p>'}")
            if ceased:
                body += f"<h2>Ceased</h2>{items(ceased)}"
            return _html(page(site, company.name, body, accent=accent))
        if path.startswith("/officer/"):
            person = self.officers.get(path[9:])
            if person is None:
                return self._missing(site)
            roles, control = [], []
            for company in self.world.companies.values():
                for officer in company.officers:
                    if officer.person == person.key:
                        tail = f" | resigned {officer.resigned:%Y-%m-%d}" if officer.resigned else ""
                        roles.append(f"{link(company_url(company), company.name)} | {esc(officer.role)} | appointed {officer.appointed:%Y-%m-%d}{tail}")
                for holding in company.owners:
                    if holding.kind == "person" and holding.holder == person.key:
                        tail = f" | ceased {holding.ceased:%Y-%m-%d}" if holding.ceased else ""
                        control.append(f"{link(company_url(company), company.name)} | ownership of shares: {holding.percent:g}%{tail}")
            if not roles and not control:
                return self._missing(site)
            rows = [("Name", esc(person.name)), ("Date of birth", month(person.born)), ("Nationality", esc(person.nationality))]
            body = f"<h1>{esc(person.name)}</h1>{facts(rows)}<h2>Appointments</h2>{items(roles)}<h2>Significant control</h2>{items(control)}"
            return _html(page(site, person.name, body, accent=accent))
        return _html(page(site, site, '<form action="/search"><input name="q"><button>Search the register</button></form>', accent=accent))

    # Domain records

    def whois(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "WHOIS Lookup", request.path
        if path == "/reverse":
            needle = fold(request.query.get("email") or request.query.get("org") or request.query.get("q") or "").strip()
            found = []
            if needle:
                for domain in self.world.domains.values():
                    if any(needle in fold(" ".join(filter(None, [r.email, r.org, r.name]))) for r in domain.whois if not r.privacy):
                        found.append(link(f"/{domain.name}", domain.name))
            body = f"<h1>Reverse WHOIS: {esc(needle)}</h1>" + (items(found) if found else "<p>No domains found.</p>")
            return _html(page(site, "Reverse WHOIS", body, accent="#20524a"))
        history = path.startswith("/history/")
        name = path[9:] if history else path[1:]
        domain = self.world.domains.get(name.lower().removeprefix("www."))
        if domain is None:
            body = ('<form action="/reverse"><input name="email" placeholder="email or organisation"><button>Reverse lookup</button></form>'
                    + (f"<p>No match for {esc(name)}.</p>" if name else ""))
            return _html(page(site, site, body, accent="#20524a"), 404 if name else 200)
        records = [r for r in domain.whois if r.observed <= self._now(as_of).date()] or domain.whois[:1]

        def block(record) -> str:
            hidden = "REDACTED FOR PRIVACY"
            rows = [("Domain Name", esc(domain.name.upper())), ("Registrar", esc(record.registrar)),
                    ("Creation Date", f"{domain.created:%Y-%m-%d}"),
                    ("Registrant Name", esc(record.name or hidden)), ("Registrant Organization", esc(record.org or hidden)),
                    ("Registrant Email", esc(record.email or hidden)), ("Name Server", "ns1.parkline.test, ns2.parkline.test")]
            if record.remarks:
                rows.append(("Remarks", esc(record.remarks)))
            return facts(rows)

        if history:
            body = f"<h1>WHOIS history: {esc(domain.name)}</h1>" + "".join(
                f"<h2>Record observed {r.observed:%Y-%m-%d}</h2>{block(r)}" for r in records)
        else:
            body = f"<h1>{esc(domain.name)}</h1>{block(records[-1])}<p>{link(f'/history/{domain.name}', 'Historical records')}</p>"
        return _html(page(site, f"WHOIS {domain.name}", body, accent="#20524a"))

    def crt(self, request: Request, as_of: datetime | None) -> Response:
        site = "Certificate Search"
        q = request.query.get("q", "").strip().lower().removeprefix("www.")
        rows = []
        if q:
            for domain in sorted(self.world.domains.values(), key=lambda d: d.name):
                for index, cert in enumerate(domain.certs):
                    if any(n == q or n.endswith("." + q) for n in cert.names):
                        ident = make_token(self.world.seed, "cert", domain.name, index, length=9)
                        rows.append(f"<tr><td>{ident}</td><td>{cert.issued:%Y-%m-%d}</td><td>{esc(', '.join(cert.names))}</td></tr>")
        table = ("<table><tr><th>crt id</th><th>Not before</th><th>Matching identities</th></tr>" + "".join(rows) + "</table>"
                 if rows else ("<p>No certificates found.</p>" if q else ""))
        body = f'<form action="/"><input name="q" value="{esc(q)}"><button>Search</button></form>{table}'
        return _html(page(site, f"Certificates {q}", body, accent="#4b3f72"))

    def _sources(self) -> dict[str, str]:
        if self._code is None:
            self._code = {}
            for name in sorted(self.world.domains):
                response = self.website(Request("GET", name, "/"), self.world.domains[name], None)
                if response.status == 200:
                    self._code[name] = response.body.decode()
        return self._code

    def codesearch(self, request: Request, as_of: datetime | None) -> Response:
        site = "Source Search"
        q = request.query.get("q", "").strip()
        found = []
        if len(q) >= 3:
            for name, source in self._sources().items():
                position = source.lower().find(q.lower())
                if position >= 0:
                    excerpt = source[max(0, position - 60):position + len(q) + 60]
                    found.append(f"{link(f'http://{name}/', name)}<pre>{esc(excerpt)}</pre>")
        body = (f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search page sources</button></form>'
                + (items(found) if found else ("<p>No pages contain that string.</p>" if q else "")))
        return _html(page(site, f"Source search {q}", body, accent="#304050"))

    def archive(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Web Archive", request.path
        if not path.startswith("/web/"):
            body = '<form action="/web"><input name="url" placeholder="http://"><button>Browse history</button></form>'
            if path == "/web" and request.query.get("url"):
                target = request.query["url"]
                return self.archive(Request("GET", request.host, f"/web/{target}"), as_of)
            return _html(page(site, site, body, accent="#5a5a2a"))
        rest = path[5:]
        stamp = None
        if len(rest) > 15 and rest[:14].isdigit() and rest[14] == "/":
            stamp, rest = rest[:14], rest[15:]
        target = canonical(rest if "://" in rest else f"http://{rest}")
        moments = self.world.captures.get(target, [])
        if stamp is None:
            listing = [link(archive_capture_url(target, m), when(m)) for m in moments]
            body = f"<h1>Captures of {esc(target)}</h1>" + (items(listing) if listing else "<p>This page has not been archived.</p>")
            return _html(page(site, f"History of {target}", body, accent="#5a5a2a"), 200 if listing else 404)
        moment = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        prior = [m for m in moments if m <= moment] or moments[:1]
        if not prior:
            return _html(page(site, "Not archived", "<h1>This page has not been archived.</h1>", accent="#5a5a2a"), 404)
        chosen = prior[-1]
        original = self.get(target, as_of=chosen)
        if original is None or original.status != 200 or not original.content_type.startswith("text/html"):
            return _html(page(site, "Capture unavailable", "<h1>Capture unavailable</h1>", accent="#5a5a2a"), 404)
        banner = (f'<div style="background:#ffd;padding:8px 24px;border-bottom:1px solid #cc9">Archived copy of '
                  f'{esc(target)} captured {when(chosen)}</div>')
        host = split_url(target)[0]
        markup = original.body.decode().replace("<head>", f'<head><base href="http://{host}/">', 1)
        markup = markup.replace("<body>", "<body>" + banner, 1)
        return _html(markup)

    def _find_photo(self, url: str) -> str | None:
        key = self.images.get(canonical(url))
        if key:
            return key
        host, path, _ = split_url(url)
        if host == GLIMPSE and path.startswith("/p/"):
            post = self.posts.get(path[3:].split("/")[0])
            return post.photo if post else None
        if host == MURMUR and "/status/" in path:
            post = self.posts.get(path.rsplit("/", 1)[-1])
            return post.photo if post else None
        return None

    def lens(self, request: Request, as_of: datetime | None) -> Response:
        site = "Lens"
        url = request.query.get("url", "").strip()
        body = f'<form action="/search"><input name="url" value="{esc(url)}" placeholder="image URL"><button>Search by image</button></form>'
        if url:
            key = self._find_photo(url)
            matches = []
            if key:
                target = canonical(url)
                for candidate in self.world.appearances.get(key, []):
                    if canonical(candidate) != target:
                        matches.append(link(candidate, candidate))
            body += "<h2>Visually identical images</h2>" + (items(matches) if matches else "<p>No matches found.</p>")
        return _html(page(site, "Lens", body, accent="#2a5a3a"))

    def atlas(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Atlas", request.path

        def card(venue) -> str:
            city = self.world.cities[venue.city]
            return (f"{link(atlas_place_url(venue), venue.name)} | {esc(venue.category)} | {venue.number} {esc(venue.street)}, "
                    f"{esc(venue.district)}, {esc(city.name)} | {venue.lat:.6f}, {venue.lon:.6f}")

        if path == "/search":
            q = request.query.get("q", "").strip()
            wanted = tokens(q)
            found = []
            if wanted:
                for venue in self.world.venues.values():
                    city = self.world.cities[venue.city]
                    have = set(tokens(f"{venue.name} {venue.street} {venue.district} {city.name} {venue.category}"))
                    if all(t in have for t in wanted):
                        found.append(card(venue))
                for city in self.world.cities.values():
                    if all(t in tokens(city.name) for t in wanted):
                        found.append(f"City: {esc(city.name)} | {city.lat:.5f}, {city.lon:.5f}")
            body = f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search places</button></form>' + items(found[:50])
            return _html(page(site, f"Places: {q}", body, accent="#2d6a4f"))
        if path.startswith("/place/"):
            venue = self.venues.get(path[7:])
            if venue is None:
                return self._missing(site)
            city = self.world.cities[venue.city]
            rows = [("Category", esc(venue.category)), ("Address", f"{venue.number} {esc(venue.street)}"),
                    ("District", esc(venue.district)), ("City", esc(city.name)), ("Coordinates", f"{venue.lat:.6f}, {venue.lon:.6f}")]
            return _html(page(site, venue.name, f"<h1>{esc(venue.name)}</h1>{facts(rows)}", accent="#2d6a4f"))
        if path == "/reverse":
            try:
                lat, lon = float(request.query.get("lat", "")), float(request.query.get("lon", ""))
            except ValueError:
                return _html(page(site, "Reverse geocoding", "<p>Give lat and lon.</p>", accent="#2d6a4f"), 400)
            ranked = sorted(self.world.venues.values(), key=lambda v: distance_km(lat, lon, v.lat, v.lon))[:6]
            listing = [f"{card(v)} | {distance_km(lat, lon, v.lat, v.lon) * 1000:.0f} m" for v in ranked]
            return _html(page(site, "Nearby places", f"<h1>Near {lat:.5f}, {lon:.5f}</h1>{items(listing)}", accent="#2d6a4f"))
        return _html(page(site, "Atlas", '<form action="/search"><input name="q"><button>Search places</button></form>', accent="#2d6a4f"))

    def paste(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Paste", request.path
        if path == "/new" and request.method == "POST":
            ident = make_token(self.world.seed, "paste", len(self.pastes), request.attempt or "", length=8)
            self.pastes.append({"id": ident, "content": request.form.get("content", ""), "attempt": request.attempt})
            event = {"kind": "paste", "site": "paste", "target": ident, "fields": dict(request.form)}
            return _html(page(site, "Paste created", f"<h1>Paste created</h1><p>{link(f'/p/{ident}', ident)}</p>"), 200, event)
        if path.startswith("/p/"):
            for entry in self.pastes:
                if entry["id"] == path[3:]:
                    return _html(page(site, "Paste", f"<pre>{esc(entry['content'])}</pre>"))
            return self._missing(site)
        body = '<form method="post" action="/new"><textarea name="content" rows="8"></textarea><button>Create paste</button></form>'
        return _html(page(site, "Paste", body))

    def sanction_list(self, request: Request, as_of: datetime | None) -> Response:
        site, path = "Consolidated Sanctions List", request.path
        accent = "#5c1f3a"
        if path.startswith("/entry/"):
            entry = self.sanctions.get(path[7:])
            if entry is None:
                return self._missing(site)
            rows = [("Reference", esc(entry.ref)), ("Name", esc(entry.name)),
                    ("Also known as", esc("; ".join(entry.aliases) or "None recorded")), ("Date of birth", esc(entry.born)),
                    ("Nationality", esc(entry.nationality)), ("Programme", esc(entry.program)), ("Listed on", f"{entry.listed:%Y-%m-%d}")]
            if entry.remarks:
                rows.append(("Remarks", esc(entry.remarks)))
            return _html(page(site, entry.name, f"<h1>{esc(entry.name)}</h1>{facts(rows)}", accent=accent))
        q = request.query.get("q", "").strip() if path == "/search" else ""
        wanted = tokens(q)
        scored = []
        for entry in self.world.sanctions.values():
            have = set(tokens(" ".join([entry.name, *entry.aliases])))
            score = sum(1 for t in wanted if t in have)
            if score:
                scored.append((-score, entry.name, entry))
        scored.sort(key=lambda s: (s[0], s[1]))
        listing = [f"{link(sanction_url(e), e.name)} | {esc(e.ref)} | born {esc(e.born)} | {esc(e.nationality)}" for _, _, e in scored[:30]]
        body = f'<form action="/search"><input name="q" value="{esc(q)}"><button>Search the list</button></form>' + items(listing)
        return _html(page(site, site, body, accent=accent))

    # General web search over public pages

    def indexable(self) -> list[str]:
        urls: list[str] = []
        world = self.world
        for account in world.accounts.values():
            if account.noindex:
                continue
            if account.site == "murmur" and account.private_since is None:
                urls.append(account_url(account))
                urls.extend(post_url(world, p) for p in self._visible_posts(account, None))
            elif account.site in ("glimpse", "guildhall", "agora"):
                urls.append(account_url(account))
                if account.site == "glimpse":
                    urls.extend(post_url(world, p) for p in self._visible_posts(account, None))
        urls.extend(thread_url(t) for t in world.threads.values() if not t.noindex)
        urls.extend(article_url(a) for a in world.articles.values())
        urls.extend(company_url(c) for c in world.companies.values())
        urls.extend(guildhall_company_url(c) for c in world.companies.values())
        for name in sorted(world.domains):
            urls.append(f"http://{name}/")
            if world.domains[name].team:
                urls.append(f"http://{name}/about")
        return urls

    def index(self) -> Index:
        if self._index is None:
            index = Index()
            for url in self.indexable():
                response = self.get(url)
                if response is None or response.status != 200:
                    continue
                markup = response.body.decode()
                title = markup.split("<title>", 1)[1].split("</title>", 1)[0] if "<title>" in markup else url
                index.add(url, text_of(title), text_of(markup.split("<main>", 1)[-1]))
            self._index = index
        return self._index

    def search(self, request: Request, as_of: datetime | None) -> Response:
        site = "Search"
        q = request.query.get("q", "").strip()
        try:
            page_number = max(1, int(request.query.get("page", "1")))
        except ValueError:
            page_number = 1
        body = f'<form action="/search"><input name="q" value="{esc(q)}" size="50"><button>Search</button></form>'
        if q:
            hits, total = self.index().search(q, limit=10, offset=(page_number - 1) * 10)
            body += f'<p class="meta">About {total} results</p>' + items(
                [f'{link(h.url, h.title)}<br><span class="meta">{esc(h.url)}</span><br>{esc(h.snippet)}' for h in hits])
            if total > page_number * 10:
                body += link(f"/search?q={quote(q)}&page={page_number + 1}", "Next page")
        return _html(page(site, f"{q} - Search" if q else "Search", body, accent="#333"))

    def mailbox(self, request: Request, as_of: datetime | None) -> Response:
        return _html(page("Mailbox", "Mailbox", "<h1>Mailbox</h1><p>Sign in to read your mail.</p>"))

    # Independent websites

    def website(self, request: Request, domain: Domain, as_of: datetime | None) -> Response:
        site = domain.title
        if domain.created > self._now(as_of).date():
            return self._missing(site)
        if request.path == "/about" and domain.team:
            people = []
            for key in domain.team:
                person = self.world.people[key]
                profile = next((a for a in self.world.accounts_of(key) if a.site == "guildhall"), None)
                role = profile.headline.split(" at ")[0] if profile else person.occupation
                people.append(f"{esc(person.name)} | {esc(role)}" + (f" | {link(account_url(profile), 'Guildhall')}" if profile else ""))
            body = f"<h1>Our team</h1>{items(people)}"
        elif request.path in ("/", ""):
            body = (f"<h1>{esc(domain.title)}</h1><p><em>{esc(domain.tagline)}</em></p>"
                    + "".join(f"<p>{esc(p)}</p>" for p in domain.paragraphs))
            if domain.contact_email:
                body += f"<p>Contact: {esc(domain.contact_email)}</p>"
            if domain.team:
                body += f"<p>{link('/about', 'Meet the team')}</p>"
        else:
            return self._missing(site)
        if domain.footer:
            body += f'<p class="meta">{esc(domain.footer)}</p>'
        head = ""
        if domain.analytics:
            head += f"<script>window.og=window.og||function(){{}};og('init','{esc(domain.analytics)}');</script>"
        if domain.comment:
            head += f"<!-- {domain.comment} -->"
        return _html(page(site, domain.title, body, accent="#444", head=head))


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
