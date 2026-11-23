from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta, timezone

from ..rng import keyed, token
from . import names
from .model import (
    Account, Article, Cert, City, Company, Domain, Experience, ForumPost, Holding, Officer, Person, Photo, Post,
    SanctionEntry, Thread, Venue, WhoisRecord, World,
)
from .urls import account_url, post_media_url, post_url

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
# Open ocean, so no generated coordinate lands on a real address.
REGION = (-31.6, -29.0, -139.2, -135.4)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Builder:
    def __init__(self, seed: int, now: datetime = NOW):
        self.seed = seed
        self.world = World(seed=seed, now=now)
        self._handles: set[tuple[str, str]] = set()
        self._numbers: set[str] = set()
        self._ips: set[str] = set()

    def rng(self, *key: object) -> random.Random:
        return keyed(self.seed, *key)

    def token(self, *key: object, length: int = 10) -> str:
        return token(self.seed, *key, length=length)

    def ago(self, rng: random.Random, min_days: float, max_days: float) -> datetime:
        delta = timedelta(days=rng.uniform(min_days, max_days))
        moment = self.world.now - delta
        return moment.replace(second=0, microsecond=0)

    # Geography

    def add_cities(self) -> None:
        rng = self.rng("cities")
        placed: list[tuple[float, float]] = []
        lat0, lat1, lon0, lon1 = REGION
        for index, (name, districts, streets) in enumerate(names.CITIES):
            while True:
                lat, lon = round(rng.uniform(lat0, lat1), 5), round(rng.uniform(lon0, lon1), 5)
                if all(abs(lat - a) + abs(lon - b) > 0.55 for a, b in placed):
                    break
            placed.append((lat, lon))
            key = f"city/{index}"
            self.world.cities[key] = City(key, name, lat, lon, list(districts), list(streets))

    def city_by_name(self, name: str) -> City:
        return next(c for c in self.world.cities.values() if c.name == name)

    def add_venue(self, key: str, city: City, category: str, name: str | None = None,
                  street: str | None = None, number: int | None = None) -> Venue:
        rng = self.rng("venue", key)
        venue = Venue(
            key=key,
            token=self.token("venue", key, length=8),
            name=name or rng.choice(names.VENUE_KINDS[category]),
            category=category,
            city=city.key,
            district=rng.choice(city.districts),
            street=street or rng.choice(city.streets),
            number=number if number is not None else rng.randint(1, 140),
            lat=round(city.lat + rng.uniform(-0.028, 0.028), 6),
            lon=round(city.lon + rng.uniform(-0.034, 0.034), 6),
        )
        self.world.venues[key] = venue
        return venue

    def venues_in(self, city: City) -> list[Venue]:
        return [v for v in self.world.venues.values() if v.city == city.key]

    # People and accounts

    def new_person(self, key: str, *, city: City | None = None, given: str | None = None,
                   family: str | None = None, occupation: str | None = None, born: date | None = None,
                   employer: str | None = None) -> Person:
        rng = self.rng("person", key)
        cities = list(self.world.cities.values())
        person = Person(
            key=key,
            given=given or rng.choice(names.GIVEN),
            family=family or rng.choice(names.FAMILY),
            born=born or date(rng.randint(1958, 2001), rng.randint(1, 12), rng.randint(1, 28)),
            city=(city or rng.choice(cities)).key,
            occupation=occupation or rng.choice(names.OCCUPATIONS),
            employer=employer,
            university=rng.choice(names.UNIVERSITIES),
            interests=rng.sample(sorted(names.INTERESTS), 2),
            officer_token=self.token("officer", key),
        )
        person.email = f"{slugify(person.given)}.{slugify(person.family)}{rng.randint(1, 99)}@mailbox.test"
        person.home_street = rng.choice(self.world.cities[person.city].streets)
        self.world.people[key] = person
        return person

    def unique_handle(self, site: str, base: str, rng: random.Random) -> str:
        handle = base
        while (site, handle.lower()) in self._handles:
            handle = f"{base}{rng.randint(2, 999)}"
        self._handles.add((site, handle.lower()))
        return handle

    def claim_handle(self, site: str, handle: str) -> bool:
        if (site, handle.lower()) in self._handles:
            return False
        self._handles.add((site, handle.lower()))
        return True

    def add_account(self, key: str, site: str, handle: str, person: Person | None, display_name: str,
                    created: datetime, **fields) -> Account:
        account = Account(key=key, site=site, handle=handle, person=person.key if person else None,
                          display_name=display_name, created=created, **fields)
        self.world.accounts[key] = account
        return account

    def guildhall_profile(self, key: str, person: Person, *, title: str | None = None,
                          company: Company | None = None, since: date | None = None,
                          extra_experience: list[Experience] | None = None, links: list[str] | None = None,
                          about: str = "", avatar: str | None = None) -> Account:
        rng = self.rng("guildhall", key)
        handle = self.unique_handle("guildhall", f"{slugify(person.given)}-{slugify(person.family)}-"
                                    f"{self.token('gh', key, length=4)}", rng)
        experience = list(extra_experience or [])
        role = title or person.occupation
        if company is not None:
            experience.insert(0, Experience(company.key, role, since or date(rng.randint(2015, 2024), rng.randint(1, 12), 1)))
            person.employer = company.key
        headline = f"{role} at {company.name}" if company else role
        return self.add_account(
            key, "guildhall", handle, person, person.name, self.ago(rng, 400, 2400),
            headline=headline, location=self.world.cities[person.city].name, about=about,
            experience=experience, education=[person.university] if person.university else [],
            links=list(links or []), avatar=avatar,
        )

    def add_post(self, key: str, account: Account, created: datetime, text: str, *, photo: Photo | None = None,
                 venue: Venue | None = None, deleted_at: datetime | None = None) -> Post:
        post = Post(key=key, account=account.key, token=self.token("post", key, length=12 if account.site == "murmur" else 9),
                    created=created, text=text, photo=photo.key if photo else None,
                    venue=venue.key if venue else None, deleted_at=deleted_at)
        self.world.posts[key] = post
        if photo is not None:
            self.world.appearances.setdefault(photo.key, []).append(post_media_url(self.world, post))
            self.world.appearances[photo.key].append(post_url(self.world, post))
        return post

    def add_photo(self, key: str, *, venue: Venue | None = None, lat: float | None = None,
                  lon: float | None = None, gps: bool = True, taken: datetime | None = None,
                  sign: list[str] | None = None, caption: str = "", comment: str = "") -> Photo:
        rng = self.rng("photo", key)
        make, model = rng.choice(names.CAMERAS)
        photo = Photo(
            key=key,
            token=self.token("photo", key),
            taken=taken or self.ago(rng, 5, 900),
            venue=venue.key if venue else None,
            lat=round(lat if lat is not None else (venue.lat + rng.uniform(-0.0002, 0.0002)), 6),
            lon=round(lon if lon is not None else (venue.lon + rng.uniform(-0.0002, 0.0002)), 6),
            gps=gps,
            make=make,
            model=model,
            serial=f"{make[:2].upper()}{rng.randint(1000000, 9999999)}",
            sign=sign if sign is not None else ([venue.name, f"{venue.number} {venue.street}"] if venue else []),
            hue=rng.randint(0, 359),
            caption=caption,
            comment=comment,
        )
        self.world.photos[key] = photo
        return photo

    def add_avatar(self, key: str, rng: random.Random) -> Photo:
        return self.add_photo(key, lat=0.0, lon=0.0, gps=False, sign=[], taken=self.ago(rng, 300, 2000))

    def register_avatar(self, account: Account, photo: Photo) -> None:
        account.avatar = photo.key
        self.world.appearances.setdefault(photo.key, []).append(account_url(account))

    # Companies, domains and records

    def company_number(self, rng: random.Random) -> str:
        while True:
            number = f"NV{rng.randint(100000, 999999)}"
            if number not in self._numbers:
                self._numbers.add(number)
                return number

    def add_company(self, key: str, name: str, *, city: City, kind: str = "operating", sector: str = "",
                    incorporated: date | None = None, website: str | None = None,
                    description: str = "") -> Company:
        rng = self.rng("company", key)
        street = rng.choice(city.streets)
        company = Company(
            key=key, name=name, number=self.company_number(rng),
            slug=f"{slugify(name)}-{self.token('ghc', key, length=3)}", kind=kind,
            incorporated=incorporated or date(rng.randint(2004, 2023), rng.randint(1, 12), rng.randint(1, 28)),
            city=city.key, address=f"{rng.randint(1, 120)} {street}, {city.name}", website=website,
            description=description, sector=sector,
        )
        self.world.companies[key] = company
        return company

    def company_name(self, rng: random.Random, sector: str | None = None) -> str:
        sector = sector or rng.choice(sorted(names.SECTORS))
        while True:
            word = rng.choice(names.SECTORS[sector])
            suffixes = [s for s in names.LEGAL_SUFFIX if not (word.endswith("Group") and s.startswith("Group"))]
            name = f"{rng.choice(names.COMPANY_WORDS)} {word} {rng.choice(suffixes)}"
            if all(c.name != name for c in self.world.companies.values()):
                return name

    def appoint(self, company: Company, person: Person, role: str, appointed: date,
                resigned: date | None = None) -> None:
        company.officers.append(Officer(person.key, role, appointed, resigned))

    def own(self, company: Company, kind: str, holder: str, percent: float, since: date,
            ceased: date | None = None) -> None:
        company.owners.append(Holding(kind, holder, percent, since, ceased))

    def ip(self, rng: random.Random) -> str:
        while True:
            address = f"198.51.100.{rng.randint(2, 254)}" if rng.random() < 0.5 else f"203.0.113.{rng.randint(2, 254)}"
            if address not in self._ips or len(self._ips) > 500:
                self._ips.add(address)
                return address

    def add_domain(self, name: str, *, kind: str, title: str, tagline: str, paragraphs: list[str],
                   whois: list[WhoisRecord], created: date, operator: str | None = None,
                   analytics: str | None = None, contact_email: str | None = None, team: list[str] | None = None,
                   footer: str = "", certs: list[Cert] | None = None, ip: str | None = None) -> Domain:
        rng = self.rng("domain", name)
        domain = Domain(
            name=name, created=created, kind=kind, title=title, tagline=tagline, paragraphs=paragraphs,
            whois=whois, ip=ip or self.ip(rng), operator=operator, analytics=analytics,
            certs=certs if certs is not None else [Cert(created + timedelta(days=rng.randint(1, 20)), [name, f"www.{name}"])],
            contact_email=contact_email, team=list(team or []), footer=footer,
        )
        self.world.domains[name] = domain
        return domain

    def whois_record(self, observed: date, rng: random.Random, *, name: str | None, org: str | None,
                     email: str | None, privacy: bool = False, registrar: str | None = None) -> WhoisRecord:
        return WhoisRecord(observed, registrar or rng.choice(names.REGISTRARS), None if privacy else name,
                           None if privacy else org, None if privacy else email, privacy)

    def unique_domain(self, base: str, rng: random.Random) -> str:
        name = f"{base}.test"
        while name in self.world.domains:
            name = f"{base}{rng.randint(2, 99)}.test"
        return name

    def add_article(self, key: str, published: datetime, title: str, paragraphs: list[str], byline: str) -> Article:
        article = Article(key, f"{slugify(title)[:60]}-{self.token('article', key, length=4)}", published, title,
                          byline, paragraphs)
        self.world.articles[key] = article
        return article

    def add_thread(self, key: str, board: str, title: str, posts: list[ForumPost], noindex: bool = False) -> Thread:
        thread = Thread(key, self.token("thread", key, length=8), board, title, posts, noindex)
        self.world.threads[key] = thread
        return thread

    def add_sanction(self, key: str, name: str, aliases: list[str], born: str, nationality: str, program: str,
                     listed: date, remarks: str = "") -> SanctionEntry:
        rng = self.rng("sanction", key)
        entry = SanctionEntry(key, f"NVS-{rng.randint(1000, 9999)}-{self.token('sanction', key, length=3).upper()}",
                              name, aliases, born, nationality, program, listed, remarks)
        self.world.sanctions[key] = entry
        return entry

    def capture(self, url: str, at: datetime) -> None:
        from .web import canonical

        moments = self.world.captures.setdefault(canonical(url), [])
        if at not in moments:
            moments.append(at)
            moments.sort()


def interest_text(rng: random.Random, interest: str, city: City, venue_name: str) -> str:
    template = rng.choice(names.INTERESTS[interest])
    return template.format(street=rng.choice(city.streets), district=rng.choice(city.districts), venue=venue_name)


def populate(b: Builder, people: int = 240, companies: int = 44) -> None:
    """Background population: the crowd every planted scenario hides in."""
    world = b.world
    b.add_cities()
    for city in list(world.cities.values()):
        rng = b.rng("venues", city.key)
        for index in range(22):
            category = rng.choice(sorted(names.VENUE_KINDS))
            b.add_venue(f"bg/venue/{city.key}/{index}", city, category)

    for index in range(companies):
        rng = b.rng("bg/company", index)
        sector = rng.choice(sorted(names.SECTORS))
        city = rng.choice(list(world.cities.values()))
        name = b.company_name(rng, sector)
        company = b.add_company(f"bg/company/{index}", name, city=city, sector=sector,
                                description=f"{name.split(' ')[0]} provides {sector} services across Norvessa.")
        if rng.random() < 0.6:
            domain = b.unique_domain(slugify(" ".join(name.split()[:2])).replace("-", ""), rng)
            company.website = domain

    company_list = list(world.companies.values())
    for index in range(people):
        rng = b.rng("bg/person", index)
        employer = rng.choice(company_list) if rng.random() < 0.7 else None
        person = b.new_person(f"bg/person/{index}", city=world.cities[employer.city] if employer and rng.random() < 0.7 else None)
        city = world.cities[person.city]
        venues = b.venues_in(city)
        if rng.random() < 0.75:
            avatar = b.add_avatar(f"bg/person/{index}/avatar", rng) if rng.random() < 0.6 else None
            account = b.guildhall_profile(f"bg/person/{index}/guildhall", person, company=employer)
            if avatar is not None:
                b.register_avatar(account, avatar)
        if rng.random() < 0.6:
            base = rng.choice([f"{person.given.lower()}{person.family[0].lower()}",
                               f"{rng.choice(names.HANDLE_WORDS)}_{person.given.lower()}",
                               f"{person.given.lower()}.{person.family.lower()}"])
            handle = b.unique_handle("murmur", base, rng)
            murmur = b.add_account(f"bg/person/{index}/murmur", "murmur", handle, person,
                                   rng.choice([person.name, person.given, handle]), b.ago(rng, 200, 2600),
                                   bio=rng.choice(["", f"{person.occupation}. {city.name}.", "Coffee, cycling, quiet weekends.",
                                                   f"{person.interests[0].capitalize()} and {person.interests[1]}."]),
                                   location=city.name if rng.random() < 0.6 else "")
            for p in range(rng.randint(3, 14)):
                prng = b.rng("bg/post", index, p)
                venue = prng.choice(venues)
                text = interest_text(prng, prng.choice(person.interests), city, venue.name)
                tagged = venue if prng.random() < 0.25 else None
                b.add_post(f"bg/person/{index}/murmur/{p}", murmur, b.ago(prng, 1, 900), text, venue=tagged)
        if rng.random() < 0.3:
            handle = b.unique_handle("glimpse", f"{person.given.lower()}{person.family.lower()}", rng)
            glimpse = b.add_account(f"bg/person/{index}/glimpse", "glimpse", handle, person, person.name,
                                    b.ago(rng, 200, 2000), bio=f"Photos from {city.name}.")
            for p in range(rng.randint(2, 6)):
                prng = b.rng("bg/glimpse", index, p)
                venue = prng.choice(venues)
                photo = b.add_photo(f"bg/person/{index}/photo/{p}", venue=venue, gps=prng.random() < 0.5)
                b.add_post(f"bg/person/{index}/glimpse/{p}", glimpse, photo.taken + timedelta(hours=prng.randint(1, 30)),
                           prng.choice(["", f"{venue.district} this week.", "Light was perfect.", venue.name]), photo=photo)
        if rng.random() < 0.25:
            handle = b.unique_handle("agora", rng.choice([f"{rng.choice(names.HANDLE_WORDS)}{rng.randint(1, 99)}",
                                                          f"{person.given.lower()}_{city.name.split()[0].lower()}"]), rng)
            b.add_account(f"bg/person/{index}/agora", "agora", handle, person, handle, b.ago(rng, 200, 2600),
                          signature=rng.choice(["", "Cheers.", f"{city.name} born and raised.", "Opinions my own."]))

    people_list = list(world.people.values())
    for company in company_list:
        rng = b.rng("bg/officers", company.key)
        staff = [p for p in people_list if p.employer == company.key] or rng.sample(people_list, 2)
        director = rng.choice(staff)
        b.appoint(company, director, "Director", company.incorporated)
        if rng.random() < 0.5:
            b.appoint(company, rng.choice(people_list), "Secretary", company.incorporated + timedelta(days=rng.randint(10, 900)))
        b.own(company, "person", director.key, 100.0 if rng.random() < 0.6 else 60.0, company.incorporated)
        if company.owners[-1].percent < 100:
            b.own(company, "person", rng.choice(people_list).key, 40.0, company.incorporated)
        if company.website:
            team = [p.key for p in staff[:3]]
            b.add_domain(company.website, kind="company", title=company.name.rsplit(" ", 1)[0],
                         tagline=company.description, paragraphs=[company.description,
                                                                  f"Registered office: {company.address}."],
                         whois=[b.whois_record(company.incorporated, rng, name=director.name, org=company.name,
                                               email=f"admin@{company.website}", privacy=rng.random() < 0.5)],
                         created=company.incorporated, operator=company.key,
                         analytics=f"OG-{rng.randint(10000, 99999)}-{rng.randint(1, 9)}" if rng.random() < 0.5 else None,
                         contact_email=f"hello@{company.website}", team=team, footer=f"© {company.name}")

    journalists = [b.new_person(f"bg/journalist/{i}", occupation="Journalist") for i in range(4)]
    herald = b.add_company("bg/herald", "Herald Media Norvessa Ltd", city=b.city_by_name("Port Calder"), sector="media")
    for journalist in journalists:
        b.guildhall_profile(f"bg/journalist/{journalist.key}/guildhall", journalist, title="Reporter", company=herald)
    for index in range(26):
        rng = b.rng("bg/article", index)
        company = rng.choice(company_list)
        city = world.cities[company.city]
        title = rng.choice([
            f"{company.name.rsplit(' ', 1)[0]} wins regional contract",
            f"{company.name.rsplit(' ', 1)[0]} opens new office in {city.name}",
            f"Council approves {rng.choice(city.streets)} works after delays",
            f"{city.name} market traders report a strong summer",
        ])
        b.add_article(f"bg/article/{index}", b.ago(rng, 10, 700), title, [
            f"{title}, according to documents seen by the Herald.",
            f"The decision affects businesses in {rng.choice(city.districts)}, where several firms have operated for years.",
            "A spokesperson declined to comment further.",
        ], rng.choice(journalists).name)

    agora_accounts = [a for a in world.accounts.values() if a.site == "agora"]
    for index in range(30):
        rng = b.rng("bg/thread", index)
        board = rng.choice(["Local", "Bikes", "Tech", "Markets", "Boats"])
        city = rng.choice(list(world.cities.values()))
        title = rng.choice([f"Parking on {rng.choice(city.streets)}?", "Best repair shop around here",
                            "Ferry timetable changes", f"Anyone selling a used {rng.choice(['dinghy', 'road bike', 'NAS', 'lathe'])}?",
                            f"Noise from the works in {rng.choice(city.districts)}"])
        authors = rng.sample(agora_accounts, min(len(agora_accounts), rng.randint(2, 4)))
        posts = [ForumPost(a.key, b.ago(rng, 5, 800), rng.choice([
            "Same here, it has been like this for weeks.", "Try the place near the old customs house.",
            "I asked at the council office, no answer yet.", "Following this.", "Sold mine last year, sorry."]))
            for a in authors]
        posts.sort(key=lambda p: p.created)
        b.add_thread(f"bg/thread/{index}", board, title, posts)

    foreign = ("Ostrian", "Kalvarian", "Velesian", "Draskan")
    for index in range(28):
        rng = b.rng("bg/sanction", index)
        given, family = rng.choice(names.GIVEN), rng.choice(names.FAMILY)
        b.add_sanction(f"bg/sanction/{index}", f"{family.upper()}, {given}", [f"{family.upper()}A, {given}"] if rng.random() < 0.3 else [],
                       f"{rng.randint(1950, 1990)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                       rng.choice(foreign), rng.choice(["Asset Freeze (Ostria)", "Arms Export Controls", "Corruption Designations"]),
                       date(rng.randint(2018, 2026), rng.randint(1, 9), rng.randint(1, 28)))
