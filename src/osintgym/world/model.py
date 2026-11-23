from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class City:
    key: str
    name: str
    lat: float
    lon: float
    districts: list[str]
    streets: list[str]


@dataclass
class Venue:
    key: str
    token: str
    name: str
    category: str
    city: str
    district: str
    street: str
    number: int
    lat: float
    lon: float


@dataclass
class Person:
    key: str
    given: str
    family: str
    born: date
    city: str
    occupation: str
    employer: str | None = None
    university: str | None = None
    interests: list[str] = field(default_factory=list)
    email: str | None = None
    home_street: str | None = None
    # Special-category or otherwise protected facts; pages may show them, reports should not repeat them.
    sensitive: dict[str, str] = field(default_factory=dict)
    officer_token: str | None = None
    nationality: str = "Norvessan"

    @property
    def name(self) -> str:
        return f"{self.given} {self.family}"


@dataclass
class Experience:
    company: str
    title: str
    start: date
    end: date | None = None


@dataclass
class Account:
    key: str
    site: str
    handle: str
    person: str | None
    display_name: str
    created: datetime
    bio: str = ""
    location: str = ""
    website: str | None = None
    private_since: datetime | None = None
    avatar: str | None = None
    headline: str = ""
    about: str = ""
    experience: list[Experience] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    signature: str = ""
    noindex: bool = False
    # Profile fields as they read before the account went private; the archive shows them.
    before_private: dict[str, str] = field(default_factory=dict)


@dataclass
class Post:
    key: str
    account: str
    token: str
    created: datetime
    text: str
    photo: str | None = None
    venue: str | None = None
    deleted_at: datetime | None = None


@dataclass
class Photo:
    key: str
    token: str
    taken: datetime
    venue: str | None
    lat: float
    lon: float
    gps: bool
    make: str
    model: str
    serial: str
    sign: list[str]
    hue: int
    caption: str = ""
    comment: str = ""


@dataclass
class Officer:
    person: str
    role: str
    appointed: date
    resigned: date | None = None


@dataclass
class Holding:
    kind: str
    holder: str
    percent: float
    since: date
    ceased: date | None = None


@dataclass
class Company:
    key: str
    name: str
    number: str
    slug: str
    kind: str
    incorporated: date
    city: str
    address: str
    status: str = "Active"
    website: str | None = None
    description: str = ""
    sector: str = ""
    officers: list[Officer] = field(default_factory=list)
    owners: list[Holding] = field(default_factory=list)


@dataclass
class WhoisRecord:
    observed: date
    registrar: str
    name: str | None
    org: str | None
    email: str | None
    privacy: bool
    remarks: str = ""


@dataclass
class Cert:
    issued: date
    names: list[str]


@dataclass
class Domain:
    name: str
    created: date
    kind: str
    title: str
    tagline: str
    paragraphs: list[str]
    whois: list[WhoisRecord]
    ip: str
    operator: str | None = None
    analytics: str | None = None
    certs: list[Cert] = field(default_factory=list)
    contact_email: str | None = None
    team: list[str] = field(default_factory=list)
    footer: str = ""
    comment: str = ""


@dataclass
class Article:
    key: str
    slug: str
    published: datetime
    title: str
    byline: str
    paragraphs: list[str]


@dataclass
class ForumPost:
    author: str
    created: datetime
    text: str


@dataclass
class Thread:
    key: str
    token: str
    board: str
    title: str
    posts: list[ForumPost] = field(default_factory=list)
    noindex: bool = False


@dataclass
class SanctionEntry:
    key: str
    ref: str
    name: str
    aliases: list[str]
    born: str
    nationality: str
    program: str
    listed: date
    remarks: str = ""


@dataclass
class World:
    seed: int
    now: datetime
    cities: dict[str, City] = field(default_factory=dict)
    venues: dict[str, Venue] = field(default_factory=dict)
    people: dict[str, Person] = field(default_factory=dict)
    accounts: dict[str, Account] = field(default_factory=dict)
    posts: dict[str, Post] = field(default_factory=dict)
    photos: dict[str, Photo] = field(default_factory=dict)
    companies: dict[str, Company] = field(default_factory=dict)
    domains: dict[str, Domain] = field(default_factory=dict)
    articles: dict[str, Article] = field(default_factory=dict)
    threads: dict[str, Thread] = field(default_factory=dict)
    sanctions: dict[str, SanctionEntry] = field(default_factory=dict)
    # Archive captures: url -> capture times. The archive renders the page as it stood at that time.
    captures: dict[str, list[datetime]] = field(default_factory=dict)
    # Photo key -> URLs where the same image is published (reverse image search).
    appearances: dict[str, list[str]] = field(default_factory=dict)

    def account_by_handle(self, site: str, handle: str) -> Account | None:
        for account in self.accounts.values():
            if account.site == site and account.handle.lower() == handle.lower():
                return account
        return None

    def posts_of(self, account_key: str) -> list[Post]:
        return sorted((p for p in self.posts.values() if p.account == account_key), key=lambda p: p.created, reverse=True)

    def accounts_of(self, person_key: str) -> list[Account]:
        return [a for a in self.accounts.values() if a.person == person_key]
