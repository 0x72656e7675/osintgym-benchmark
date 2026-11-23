from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from .model import Account, Article, Company, Person, Post, SanctionEntry, Thread, Venue, World

MURMUR = "murmur.test"
GLIMPSE = "glimpse.test"
GUILDHALL = "guildhall.test"
AGORA = "agora.test"
HERALD = "herald.test"
REGISTRY = "registry.test"
WHOIS = "whois.test"
CRT = "crt.test"
CODESEARCH = "codesearch.test"
ARCHIVE = "archive.test"
LENS = "lens.test"
ATLAS = "atlas.test"
PASTE = "paste.test"
SANCTIONS = "sanctions.test"
SEARCH = "search.test"
MAILBOX = "mailbox.test"

SOCIAL_HOSTS = {"murmur": MURMUR, "glimpse": GLIMPSE, "guildhall": GUILDHALL, "agora": AGORA}
SERVICE_HOSTS = (
    MURMUR, GLIMPSE, GUILDHALL, AGORA, HERALD, REGISTRY, WHOIS, CRT, CODESEARCH, ARCHIVE, LENS, ATLAS, PASTE,
    SANCTIONS, SEARCH, MAILBOX,
)


def account_url(account: Account) -> str:
    prefix = {"murmur": "/@", "glimpse": "/u/", "guildhall": "/in/", "agora": "/u/"}[account.site]
    return f"http://{SOCIAL_HOSTS[account.site]}{prefix}{account.handle}"


def post_url(world: World, post: Post) -> str:
    account = world.accounts[post.account]
    if account.site == "glimpse":
        return f"http://{GLIMPSE}/p/{post.token}"
    return f"http://{MURMUR}/@{account.handle}/status/{post.token}"


def post_media_url(world: World, post: Post, original: bool = False) -> str:
    account = world.accounts[post.account]
    if account.site == "glimpse":
        return f"http://{GLIMPSE}/p/{post.token}/{'original' if original else 'display'}.jpg"
    return f"http://{MURMUR}/media/{post.token}.jpg"


def avatar_url(account: Account, avatar_token: str) -> str:
    path = {"murmur": "/avatar/", "glimpse": "/avatar/", "guildhall": "/photo/", "agora": "/avatar/"}[account.site]
    return f"http://{SOCIAL_HOSTS[account.site]}{path}{avatar_token}.jpg"


def company_url(company: Company) -> str:
    return f"http://{REGISTRY}/company/{company.number}"


def officer_url(person: Person) -> str:
    return f"http://{REGISTRY}/officer/{person.officer_token}"


def guildhall_company_url(company: Company) -> str:
    return f"http://{GUILDHALL}/company/{company.slug}"


def site_url(domain: str, path: str = "/") -> str:
    return f"http://{domain}{path}"


def whois_url(domain: str) -> str:
    return f"http://{WHOIS}/{domain}"


def whois_history_url(domain: str) -> str:
    return f"http://{WHOIS}/history/{domain}"


def whois_reverse_url(email: str) -> str:
    return f"http://{WHOIS}/reverse?email={quote(email)}"


def crt_url(domain: str) -> str:
    return f"http://{CRT}/?q={quote(domain)}"


def codesearch_url(text: str) -> str:
    return f"http://{CODESEARCH}/search?q={quote(text)}"


def archive_index_url(url: str) -> str:
    return f"http://{ARCHIVE}/web/{url}"


def archive_capture_url(url: str, at: datetime) -> str:
    return f"http://{ARCHIVE}/web/{at.strftime('%Y%m%d%H%M%S')}/{url}"


def lens_url(image_url: str) -> str:
    return f"http://{LENS}/search?url={quote(image_url, safe='')}"


def atlas_place_url(venue: Venue) -> str:
    return f"http://{ATLAS}/place/{venue.token}"


def atlas_search_url(query: str) -> str:
    return f"http://{ATLAS}/search?q={quote(query)}"


def sanction_url(entry: SanctionEntry) -> str:
    return f"http://{SANCTIONS}/entry/{entry.ref}"


def article_url(article: Article) -> str:
    return f"http://{HERALD}/news/{article.published:%Y/%m}/{article.slug}"


def thread_url(thread: Thread) -> str:
    return f"http://{AGORA}/t/{thread.token}"


def search_url(query: str) -> str:
    return f"http://{SEARCH}/search?q={quote(query)}"
