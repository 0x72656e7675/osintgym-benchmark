from __future__ import annotations

import random
from datetime import timedelta

from ..world import names
from ..world.build import Builder
from ..world.model import Account, Company, Person

OFFERS = (
    "New batch of {product} in stock, 40% under retail. First come, first served.",
    "Payment by transfer secures your order. Dispatch within 48 hours.",
    "Restock on Friday. Message for the price list.",
    "Last units of the season. Ask about bundle prices.",
    "Wholesale buyers welcome, minimum order five units.",
    "Sold out in two hours last time. Reserve now.",
)


def background_companies(b: Builder) -> list[Company]:
    return [c for c in b.world.companies.values() if c.key.startswith("bg/company/")]


def namesakes(b: Builder, key: str, person: Person, count: int) -> list[Person]:
    twins = []
    cities = [c for c in b.world.cities.values() if c.key != person.city]
    companies = background_companies(b)
    for n in range(count):
        rng = b.rng(key, "namesake", n)
        twin = b.new_person(f"{key}/namesake/{n}", city=rng.choice(cities), given=person.given, family=person.family)
        b.guildhall_profile(f"{key}/namesake/{n}/guildhall", twin, company=rng.choice(companies))
        twins.append(twin)
    return twins


def personal_site(b: Builder, key: str, person: Person, rng: random.Random, *, email: str | None = None,
                  private_now: bool = False) -> str:
    domain = b.unique_domain(rng.choice(names.TLD_WORDS), rng)
    created = (b.world.now - timedelta(days=rng.randint(500, 2200))).date()
    records = [b.whois_record(created, rng, name=person.name, org=None, email=email or person.email)]
    if private_now:
        records.append(b.whois_record(created + timedelta(days=rng.randint(200, 400)), rng, name=None, org=None,
                                      email=None, privacy=True, registrar=records[0].registrar))
    interests = " and ".join(person.interests)
    b.add_domain(domain, kind="personal", title=f"{rng.choice(['Notes', 'Logbook', 'Workbench', 'Field notes'])} of {person.given}",
                 tagline=f"Writing about {interests}.", created=created, operator=person.key, whois=records,
                 paragraphs=[f"Mostly {interests}, written in the evenings.",
                             f"Based in {b.world.cities[person.city].name}. Comments are closed."])
    return domain


def scam_account(b: Builder, key: str, person: Person, rng: random.Random) -> tuple[Account, str]:
    product = rng.choice(names.SCAM_PRODUCTS)
    base = f"{rng.choice(['deals', 'outlet', 'direct', 'bargain', 'stock'])}.{rng.choice(['harbor', 'north', 'quay', 'metro', 'coast', 'bay'])}"
    handle = b.unique_handle("murmur", base, rng)
    words = handle.split(".")
    display = f"{words[-1].rstrip('0123456789').capitalize()} {words[0].capitalize()}"
    account = b.add_account(f"{key}/murmur", "murmur", handle, person, display, b.ago(rng, 70, 320),
                            bio=f"Wholesale {product} at outlet prices. DM to order. Bank transfer only.",
                            location="Norvessa")
    for p in range(6):
        prng = b.rng(key, "offer", p)
        b.add_post(f"{key}/murmur/{p}", account, b.ago(prng, 1, 60), prng.choice(OFFERS).format(product=product))
    return account, product


def guildhall_of(b: Builder, person: Person) -> Account:
    return next(a for a in b.world.accounts_of(person.key) if a.site == "guildhall")
