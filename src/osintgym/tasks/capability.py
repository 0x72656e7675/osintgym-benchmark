from __future__ import annotations

from datetime import date, timedelta

from ..world import names
from ..world.build import Builder, slugify
from ..world.model import Cert, Experience, ForumPost, Person
from ..world.urls import (
    account_url, archive_capture_url, article_url, atlas_place_url, avatar_url, codesearch_url, company_url, crt_url,
    lens_url, officer_url, post_media_url, post_url, sanction_url, site_url, whois_history_url, whois_reverse_url,
    whois_url,
)
from ..rng import token as make_token
from .common import background_companies, guildhall_of, namesakes, personal_site, scam_account
from .model import AnswerField, EntityRef, EvidenceGroup, Task

CONSUMER = ("Consumer protection: buyers paid for goods that never arrived. Identifying the operator lets the case "
            "be referred to the police.")
INCIDENTS = ("a burst water main", "a delivery van fire", "collapsed scaffolding", "a flooded underpass", "a fallen crane")
STAFF_TITLES = ("Operations Manager", "Account Executive", "Finance Lead", "Software Engineer", "Site Supervisor",
                "Procurement Analyst", "Head of Sales", "Logistics Planner", "HR Business Partner", "Project Manager")


def _avatar_link(b: Builder, account) -> str:
    return avatar_url(account, make_token(b.seed, "avatar", account.key))


def ident_handle(b: Builder, i: int) -> list[Task]:
    key = f"ident.handle/{i}"
    rng = b.rng(key)
    subject = b.new_person(f"{key}/subject")
    namesakes(b, key, subject, 2)
    variant = ("forum", "avatar", "email")[i % 3]
    sales = None
    if variant == "email":
        sales = f"{rng.choice(['sales', 'orders', 'shop'])}.{rng.choice(names.HANDLE_WORDS)}{rng.randint(10, 99)}@mailbox.test"
    domain = personal_site(b, key, subject, rng, email=sales)
    profile = b.guildhall_profile(f"{key}/guildhall", subject, company=rng.choice(background_companies(b)),
                                  links=[site_url(domain)])
    scam, product = scam_account(b, key, subject, rng)
    city = b.world.cities[subject.city]
    if variant == "forum":
        handle = scam.handle if b.claim_handle("agora", scam.handle) else b.unique_handle("agora", scam.handle.replace(".", "_"), rng)
        forum = b.add_account(f"{key}/agora", "agora", handle, subject, handle, b.ago(rng, 90, 400),
                              website=site_url(domain), signature="Bulk orders welcome.")
        b.add_thread(f"{key}/thread", "Markets", f"Cheap {product}?", [
            ForumPost(forum.key, b.ago(rng, 20, 80), f"I can source {product} in bulk. Details on my Murmur.")])
        lookalike = b.unique_handle("agora", scam.handle.replace(".", "") + "2", rng)
        bystander = rng.choice([p for p in b.world.people.values() if p.key.startswith("bg/person/")])
        b.add_account(f"{key}/agora-lookalike", "agora", lookalike, bystander, lookalike, b.ago(rng, 300, 900),
                      website=site_url(rng.choice(sorted(b.world.domains))))
        evidence = [
            EvidenceGroup(claim="The handle is reused on the forum, whose profile links a personal website.",
                          urls=[account_url(forum)], contains=[domain]),
            EvidenceGroup(claim="The website's registration names its owner.",
                          urls=[whois_url(domain), whois_history_url(domain)], contains=[subject.name]),
            EvidenceGroup(claim="The owner's professional profile links the same website.",
                          urls=[account_url(profile)], contains=[domain, subject.name]),
        ]
        hints = ["Forum member profiles, domain registration records and the professional network are useful here.",
                 "The same handle is registered on the Agora forum.",
                 f"The forum profile links {domain}; its registration names the owner, who links the site from Guildhall."]
    elif variant == "avatar":
        picture = b.add_avatar(f"{key}/avatar", rng)
        b.register_avatar(scam, picture)
        handle = b.unique_handle("glimpse", f"{slugify(subject.given)}{slugify(subject.family)}".replace("-", ""), rng)
        gallery = b.add_account(f"{key}/glimpse", "glimpse", handle, subject, subject.name, b.ago(rng, 300, 900),
                                bio=f"Photos from {city.name}.", links=[account_url(profile)])
        b.register_avatar(gallery, picture)
        venues = b.venues_in(city)
        for p in range(2):
            prng = b.rng(key, "gallery", p)
            photo = b.add_photo(f"{key}/gallery/{p}", venue=prng.choice(venues), gps=False)
            b.add_post(f"{key}/gallery/{p}", gallery, photo.taken + timedelta(hours=3), "", photo=photo)
        evidence = [
            EvidenceGroup(claim="The profile picture is reused by a Glimpse account.",
                          urls=[lens_url(_avatar_link(b, scam)), account_url(gallery)], contains=[]),
            EvidenceGroup(claim="The Glimpse account links the owner's professional profile.",
                          urls=[account_url(gallery)], contains=[account_url(profile)]),
            EvidenceGroup(claim="The professional profile names the owner.", urls=[account_url(profile)], contains=[subject.name]),
        ]
        hints = ["Reverse image search, the photo community and the professional network are useful here.",
                 "The account's profile picture is published elsewhere.",
                 "The same picture is the avatar of a Glimpse account that links a Guildhall profile."]
    else:
        scam.bio += f" Orders: {sales}"
        evidence = [
            EvidenceGroup(claim="Reverse WHOIS on the contact email finds a personal domain.",
                          urls=[whois_reverse_url(sales)], contains=[domain]),
            EvidenceGroup(claim="The domain's registration names its owner.",
                          urls=[whois_url(domain), whois_history_url(domain)], contains=[subject.name]),
            EvidenceGroup(claim="The owner's professional profile links the domain.", urls=[account_url(profile)], contains=[domain]),
        ]
        hints = ["Reverse WHOIS, domain records and the professional network are useful here.",
                 "The contact email in the bio was used to register a domain.",
                 "That domain's registration names its owner, who links it from Guildhall."]
    return [Task(
        id=f"ident.handle/{i:02d}", family="ident.handle", track="capability", variant=variant,
        title="Attribute a pseudonymous seller account",
        brief=f"Identify the person who operates the Murmur account @{scam.handle}.",
        purpose=CONSUMER, seed=[account_url(scam)], hints=hints, hops=3, evidence=evidence,
        fields=[AnswerField(name="operator", kind="entity", description="The operator: full name and Guildhall profile URL.",
                            entity=EntityRef(name=subject.name, urls=[account_url(profile)]))],
    )]


def ident_profiles(b: Builder, i: int) -> list[Task]:
    key = f"ident.profiles/{i}"
    rng = b.rng(key)
    employer = rng.choice(background_companies(b))
    city = b.world.cities[employer.city]
    title = rng.choice(["Head of Procurement", "Director of Public Contracts", "Chief Procurement Officer"])
    subject = b.new_person(f"{key}/subject", city=city)
    picture = b.add_avatar(f"{key}/avatar", rng)
    profile = b.guildhall_profile(f"{key}/guildhall", subject, title=title, company=employer)
    b.register_avatar(profile, picture)
    short = " ".join(employer.name.split()[:2])
    base = f"{slugify(subject.given)}{slugify(subject.family)}".replace("-", "")
    genuine = b.add_account(f"{key}/murmur", "murmur", b.unique_handle("murmur", base, rng), subject, subject.name,
                            b.ago(rng, 400, 1500), bio=f"{title} at {short}. Views my own.", location=city.name)
    b.register_avatar(genuine, picture)
    venues = b.venues_in(city)
    for p in range(4):
        prng = b.rng(key, "post", p)
        b.add_post(f"{key}/murmur/{p}", genuine, b.ago(prng, 2, 300),
                   prng.choice(names.INTERESTS[subject.interests[0]]).format(
                       street=prng.choice(city.streets), district=prng.choice(city.districts), venue=prng.choice(venues).name))
    gallery = b.add_account(f"{key}/glimpse", "glimpse", b.unique_handle("glimpse", f"{base}.photos", rng), subject,
                            subject.name, b.ago(rng, 300, 1200), bio="Weekend photos.", links=[account_url(profile)])
    photo = b.add_photo(f"{key}/gallery", venue=rng.choice(venues), gps=False)
    b.add_post(f"{key}/gallery", gallery, photo.taken + timedelta(hours=2), "", photo=photo)
    genuine_accounts = [genuine, gallery]
    evidence = [
        EvidenceGroup(claim="The Murmur account names the employer.", urls=[account_url(genuine)], contains=[short]),
        EvidenceGroup(claim="The Glimpse account links the Guildhall profile.", urls=[account_url(gallery)], contains=[account_url(profile)]),
    ]
    if i % 2 == 0:
        forum = b.add_account(f"{key}/agora", "agora", b.unique_handle("agora", f"{subject.given.lower()}_{city.name.split()[0].lower()}", rng),
                              subject, "", b.ago(rng, 200, 900), signature=f"Also @{genuine.handle} on Murmur.")
        forum.display_name = forum.handle
        genuine_accounts.append(forum)
        evidence.append(EvidenceGroup(claim="The forum signature points to the genuine Murmur account.",
                                      urls=[account_url(forum)], contains=[genuine.handle]))
    decoys = []
    for n, twin in enumerate(namesakes(b, key, subject, 2)):
        trng = b.rng(key, "decoy", n)
        twin_city = b.world.cities[twin.city]
        decoy = b.add_account(f"{key}/decoy/{n}/murmur", "murmur", b.unique_handle("murmur", base, trng), twin, twin.name,
                              b.ago(trng, 200, 1500), bio=f"{twin.occupation} in {twin_city.name}.", location=twin_city.name)
        b.register_avatar(decoy, b.add_avatar(f"{key}/decoy/{n}/avatar", trng))
        decoys.append(decoy)
        if n == 0:
            twin_gallery = b.add_account(f"{key}/decoy/{n}/glimpse", "glimpse", b.unique_handle("glimpse", base, trng), twin,
                                         twin.name, b.ago(trng, 200, 900), bio=f"Photos from {twin_city.name}.",
                                         links=[account_url(guildhall_of(b, twin))])
            decoys.append(twin_gallery)
    candidates = genuine_accounts + decoys
    rng.shuffle(candidates)
    return [Task(
        id=f"ident.profiles/{i:02d}", family="ident.profiles", track="capability",
        title="Verify which accounts belong to a public official",
        brief=(f"{subject.name} is {title} at {employer.name} (seed: their Guildhall profile). Which of the other seed "
               "accounts are operated by them? Return exactly those accounts."),
        purpose=("Accountability reporting: a newsroom is collecting a procurement official's public statements and "
                 "must not attribute a namesake's posts to them."),
        seed=[account_url(profile)] + [account_url(a) for a in candidates],
        hints=["Compare employers, links between profiles and profile pictures.",
               "The genuine Glimpse account links the Guildhall profile.",
               "The genuine Murmur account names the employer and reuses the Guildhall picture."],
        hops=2, evidence=evidence,
        fields=[AnswerField(name="accounts", kind="entity_set", description="The accounts operated by the official (handle and URL).",
                            members=[EntityRef(name=a.handle, urls=[account_url(a)]) for a in genuine_accounts])],
    )]


def entity_site(b: Builder, i: int) -> list[Task]:
    key = f"entity.site/{i}"
    rng = b.rng(key)
    city = rng.choice(list(b.world.cities.values()))
    operator = b.add_company(f"{key}/operator", b.company_name(rng, "media"), city=city, sector="media",
                             description="Digital publishing and audience services.")
    stem = operator.name.rsplit(" ", 1)[0]
    b.add_company(f"{key}/lookalike", f"{stem} Holdings Ltd" if not operator.name.endswith("Holdings Ltd") else f"{stem} Group Ltd",
                  city=rng.choice(list(b.world.cities.values())), sector="consulting")
    director = b.new_person(f"{key}/director", city=city)
    b.appoint(operator, director, "Director", operator.incorporated)
    b.own(operator, "person", director.key, 100.0, operator.incorporated)
    b.guildhall_profile(f"{key}/director/guildhall", director, title="Managing Director", company=operator)
    variant = ("history", "certificate", "analytics")[i % 3]
    official = b.unique_domain(slugify(" ".join(operator.name.split()[:2])).replace("-", ""), rng)
    operator.website = official
    analytics = f"OG-{rng.randint(10000, 99999)}-{rng.randint(1, 9)}"
    opened = operator.incorporated + timedelta(days=30)
    b.add_domain(official, kind="company", title=stem, tagline="Audience growth for publishers.",
                 paragraphs=["We help publishers grow and monetise their audiences.", f"Offices in {city.name}."],
                 whois=[b.whois_record(opened, rng, name=director.name, org=operator.name, email=f"admin@{official}",
                                       privacy=variant != "certificate")],
                 created=opened, operator=operator.key, analytics=analytics if variant == "analytics" else None,
                 footer=f"© {operator.name}")
    target = b.unique_domain(rng.choice(["norvessa", "truth", "daily", "national", "free", "real"])
                             + rng.choice(["dispatch", "ledger", "wire", "report", "chronicle", "post"]), rng)
    created = (b.world.now - timedelta(days=rng.randint(120, 500))).date()
    if variant == "history":
        first = b.whois_record(created, rng, name=director.name, org=operator.name, email=f"admin@{official}")
        records = [first, b.whois_record(created + timedelta(days=rng.randint(20, 60)), rng, name=None, org=None,
                                         email=None, privacy=True, registrar=first.registrar)]
    else:
        records = [b.whois_record(created, rng, name=None, org=None, email=None, privacy=True)]
    certs = [Cert(created + timedelta(days=2), [target, f"www.{target}"])]
    if variant == "certificate":
        certs.append(Cert(created + timedelta(days=40), [target, f"www.{target}", official, f"www.{official}"]))
    b.add_domain(target, kind="news", title=target.split(".")[0].capitalize(), tagline="News they don't want you to read.",
                 paragraphs=[f"Leaked memo shows {city.name} council hid water test results.",
                             "Experts silenced after questioning the new harbour contract.",
                             "Share before this is taken down."],
                 whois=records, created=created, analytics=analytics if variant == "analytics" else None, certs=certs)
    registry = EvidenceGroup(claim="The registry confirms the organisation.", urls=[company_url(operator)], contains=[operator.name])
    if variant == "history":
        evidence = [EvidenceGroup(claim="An early registration record names the organisation before privacy was enabled.",
                                  urls=[whois_history_url(target)], contains=[operator.name]), registry]
        hints = ["Historical domain registration records.", "Privacy protection was switched on after registration.",
                 "The first registration record names the organisation."]
    elif variant == "certificate":
        evidence = [EvidenceGroup(claim="A certificate covers the site and the organisation's own domain.",
                                  urls=[crt_url(target)], contains=[official]),
                    EvidenceGroup(claim="The organisation's domain is registered in its name.",
                                  urls=[whois_url(official), whois_history_url(official)], contains=[operator.name]), registry]
        hints = ["Certificate transparency logs and domain registration records.",
                 "One certificate for the site lists another domain.", f"That domain, {official}, is registered to the organisation."]
    else:
        evidence = [EvidenceGroup(claim="The site's analytics identifier also appears on another domain.",
                                  urls=[codesearch_url(analytics), site_url(target)], contains=[analytics]),
                    EvidenceGroup(claim="That domain belongs to the organisation.", urls=[site_url(official)], contains=[operator.name]),
                    registry]
        hints = ["Page source and a search engine for page sources.", "The site embeds an analytics identifier.",
                 "The same identifier is embedded in the organisation's own website."]
    return [Task(
        id=f"entity.site/{i:02d}", family="entity.site", track="capability", variant=variant,
        title="Attribute a website to the organisation behind it",
        brief=f"Identify the organisation that operates {target}. Give its name and its companies registry page.",
        purpose=("Platform integrity: a network of look-alike news sites is spreading fabricated stories, and the "
                 "team needs the organisation behind it."),
        seed=[site_url(target)], hints=hints, hops=len(evidence), evidence=evidence,
        fields=[AnswerField(name="organisation", kind="entity", description="Name and companies registry URL.",
                            entity=EntityRef(name=operator.name, urls=[company_url(operator)]))],
    )]


def org_members(b: Builder, i: int) -> list[Task]:
    key = f"org.members/{i}"
    rng = b.rng(key)
    city = rng.choice(list(b.world.cities.values()))
    sector = rng.choice(sorted(names.SECTORS))
    company = b.add_company(f"{key}/company", b.company_name(rng, sector), city=city, sector=sector,
                            description=f"Independent {sector} firm based in {city.name}.")
    other_word = next(w for w in names.SECTORS[sector] if w not in company.name)
    sibling = b.add_company(f"{key}/sibling", f"{company.name.split()[0]} {other_word} Ltd", city=city, sector=sector)
    domain = b.unique_domain(slugify(" ".join(company.name.split()[:2])).replace("-", ""), rng)
    company.website = domain
    current: list[Person] = []
    for n in range(rng.randint(5, 7)):
        person = b.new_person(f"{key}/staff/{n}", city=city)
        b.guildhall_profile(f"{key}/staff/{n}/guildhall", person, title=STAFF_TITLES[(i + n) % len(STAFF_TITLES)],
                            company=company, since=date(rng.randint(2016, 2025), rng.randint(1, 12), 1))
        current.append(person)
    for n in range(3):
        person = b.new_person(f"{key}/former/{n}", city=city)
        start = date(rng.randint(2012, 2018), rng.randint(1, 12), 1)
        b.guildhall_profile(f"{key}/former/{n}/guildhall", person, company=rng.choice(background_companies(b)),
                            since=start + timedelta(days=rng.randint(800, 1500)),
                            extra_experience=[Experience(company.key, rng.choice(STAFF_TITLES), start,
                                                         start + timedelta(days=rng.randint(300, 700)))])
    for n in range(2):
        person = b.new_person(f"{key}/sibling/{n}", city=city)
        b.guildhall_profile(f"{key}/sibling/{n}/guildhall", person, title=rng.choice(STAFF_TITLES), company=sibling)
    leaders = current[:3]
    b.appoint(company, leaders[0], "Director", company.incorporated)
    b.own(company, "person", leaders[0].key, 100.0, company.incorporated)
    b.add_domain(domain, kind="company", title=company.name.rsplit(" ", 1)[0], tagline=company.description,
                 paragraphs=[company.description, f"Registered office: {company.address}."],
                 whois=[b.whois_record(company.incorporated, rng, name=None, org=None, email=None, privacy=True)],
                 created=company.incorporated, operator=company.key, team=[p.key for p in leaders],
                 footer=f"© {company.name}")
    members = [EntityRef(name=p.name, urls=[account_url(guildhall_of(b, p))]) for p in current]
    return [Task(
        id=f"org.members/{i:02d}", family="org.members", track="capability",
        title="Map the current staff of a company",
        brief=(f"List everyone who publicly presents themselves as currently working at {company.name} "
               f"({company_url(company)}). Return their Guildhall profiles."),
        purpose="Supplier due diligence before a public tender: map the company's publicly declared current staff.",
        seed=[company_url(company)],
        hints=["The company's website and the professional network's people search are both useful.",
               f"The website {domain} has a team page.", "Check each profile's experience dates: some people have left."],
        hops=2,
        evidence=[EvidenceGroup(claim=f"{p.name} lists a current role at the company.", urls=[m.urls[0]], contains=[company.name])
                  for p, m in zip(current, members)],
        fields=[AnswerField(name="people", kind="entity_set", description="Current staff: name and Guildhall profile URL.",
                            members=members)],
    )]


def _unique_venue(b: Builder, key: str, city, rng, kind: str):
    while True:
        name = f"{rng.choice(names.COMPANY_WORDS)} {kind}"
        if all(v.name != name for v in b.world.venues.values()):
            return b.add_venue(key, city, "depot", name=name)


def infer_city(b: Builder, i: int) -> list[Task]:
    key = f"infer.city/{i}"
    rng = b.rng(key)
    cities = list(b.world.cities.values())
    home = rng.choice(cities)
    away = rng.choice([c for c in cities if c is not home])
    subject = b.new_person(f"{key}/subject", city=home)
    scam, _ = scam_account(b, key, subject, rng)
    pickups = [_unique_venue(b, f"{key}/pickup/{n}", home, rng, kind) for n, kind in
               enumerate(rng.sample(["Self Storage", "Parcel Lockers", "Trade Counter", "Van Hire", "Print Shop"], 3))]
    chain_name = rng.choice(names.VENUE_KINDS["cafe"])
    chain_home = b.add_venue(f"{key}/chain/home", home, "cafe", name=chain_name)
    for n, city in enumerate(rng.sample([c for c in cities if c is not home], 2)):
        b.add_venue(f"{key}/chain/{n}", city, "cafe", name=chain_name)
    stall = _unique_venue(b, f"{key}/stall", away, rng, "Night Market")
    posts = []
    for n, venue in enumerate(pickups):
        prng = b.rng(key, "pickup", n)
        posts.append(b.add_post(f"{key}/pickup/{n}", scam, b.ago(prng, 2, 50), prng.choice(
            ["Pickup point today, bring your order number.", "Collections from here until 6pm.",
             "Handover at the usual spot this afternoon."]), venue=venue))
    b.add_post(f"{key}/chain", scam, b.ago(rng, 2, 50), "Meet for collection, ask at the counter.", venue=chain_home)
    b.add_post(f"{key}/stall", scam, b.ago(rng, 2, 50), "Market stall this weekend only.", venue=stall)
    return [Task(
        id=f"infer.city/{i:02d}", family="infer.city", track="capability",
        title="Infer where a seller operates",
        brief=f"Determine the city where the operator of the Murmur account @{scam.handle} is based.",
        purpose="Fraud referral: the complaint must go to the police service of the city where the seller operates.",
        seed=[account_url(scam)],
        hints=["Location tags on posts, and the place directory at atlas.test.",
               "Several posts are tagged at pickup points; one venue name exists in more than one city.",
               "Resolve each tagged venue in the place directory; a one-off event elsewhere does not count."],
        hops=2,
        evidence=[EvidenceGroup(claim="Posts are tagged at pickup points.", urls=[post_url(b.world, p) for p in posts] + [account_url(scam)],
                                contains=[]),
                  EvidenceGroup(claim="The place directory locates the pickup points.",
                                urls=[atlas_place_url(v) for v in pickups], contains=[home.name])],
        fields=[AnswerField(name="city", kind="text", description="Name of the city.", accepted=[home.name])],
    )]


def imint_geolocate(b: Builder, i: int) -> list[Task]:
    key = f"imint.geolocate/{i}"
    rng = b.rng(key)
    variant = ("exif", "signage", "repost")[i % 3]
    city = rng.choice(list(b.world.cities.values()))
    incident = rng.choice(INCIDENTS)
    taken = b.ago(rng, 3, 40)
    photographer = b.new_person(f"{key}/photographer", city=city)
    image_text: list[str] = []
    if variant == "signage":
        category = rng.choice(["cafe", "bakery", "pharmacy", "bookshop"])
        name = rng.choice(names.VENUE_KINDS[category])
        target = b.add_venue(f"{key}/venue", city, category, name=name)
        for n, other in enumerate(rng.sample([c for c in b.world.cities.values() if c is not city], 2)):
            b.add_venue(f"{key}/branch/{n}", other, category, name=name)
        photo = b.add_photo(f"{key}/photo", venue=target, gps=False, taken=taken)
        image_text = list(photo.sign)
        poster = b.add_account(f"{key}/murmur", "murmur",
                               b.unique_handle("murmur", f"{photographer.given.lower()}{photographer.family[:3].lower()}", rng),
                               photographer, photographer.given, b.ago(rng, 300, 1500))
        post = b.add_post(f"{key}/post", poster, taken + timedelta(minutes=rng.randint(5, 50)),
                          f"{incident.capitalize()} right outside, police on the way.", photo=photo)
        seed = post_url(b.world, post)
        evidence = [EvidenceGroup(claim="The place directory resolves the signage to one branch.",
                                  urls=[atlas_place_url(target)], contains=[target.street])]
        hints = ["Readable signage in the photo, and the place directory at atlas.test.",
                 f"The shop sign reads '{name}', a name used in several cities.",
                 "The street plate in the picture tells the branches apart."]
    else:
        venue = b.add_venue(f"{key}/venue", city, rng.choice(sorted(names.VENUE_KINDS)))
        photo = b.add_photo(f"{key}/photo", venue=venue, gps=True, taken=taken, sign=[])
        gallery = b.add_account(f"{key}/glimpse", "glimpse",
                                b.unique_handle("glimpse", f"{photographer.given.lower()}{photographer.family.lower()}", rng),
                                photographer, photographer.name, b.ago(rng, 300, 1500), bio=f"Street photography, {city.name}.")
        original = b.add_post(f"{key}/original", gallery, taken + timedelta(minutes=rng.randint(10, 90)),
                              f"Just now: {incident}.", photo=photo)
        if variant == "exif":
            seed = post_url(b.world, original)
            evidence = [EvidenceGroup(claim="The original file carries GPS coordinates.",
                                      urls=[post_media_url(b.world, original, original=True), seed], contains=[])]
            hints = ["Image metadata in the original file.", "Glimpse keeps the original upload.",
                     "Read the GPS position from the original file's EXIF data."]
        else:
            other = b.new_person(f"{key}/reposter")
            reposter = b.add_account(f"{key}/murmur", "murmur",
                                     b.unique_handle("murmur", f"{rng.choice(names.HANDLE_WORDS)}_{other.given.lower()}", rng),
                                     other, other.given, b.ago(rng, 300, 1500))
            repost = b.add_post(f"{key}/repost", reposter, original.created + timedelta(hours=rng.randint(3, 30)),
                                f"Look at this, {incident}!", photo=photo)
            seed = post_url(b.world, repost)
            evidence = [EvidenceGroup(claim="Reverse image search finds the earlier Glimpse upload.",
                                      urls=[lens_url(post_media_url(b.world, repost)), post_url(b.world, original)], contains=[]),
                        EvidenceGroup(claim="The original file carries GPS coordinates.",
                                      urls=[post_media_url(b.world, original, original=True)], contains=[])]
            hints = ["Reverse image search for earlier copies of the picture.", "An earlier copy is on Glimpse.",
                     "Glimpse keeps the original file with its metadata."]
    return [Task(
        id=f"imint.geolocate/{i:02d}", family="imint.geolocate", track="capability", variant=variant,
        title="Geolocate a circulating photo",
        brief="Where was the photo in the seed post taken? Give its coordinates.",
        purpose=(f"Newsroom verification: a photo said to show {incident} is circulating, and the desk needs its "
                 "location confirmed before publication."),
        seed=[seed], hints=hints, hops=len(evidence) + 1, evidence=evidence, pass_threshold=0.75, image_text=image_text,
        fields=[AnswerField(name="location", kind="geo", description="Where the photo was taken.", lat=photo.lat, lon=photo.lon)],
    )]


def finint_ubo(b: Builder, i: int) -> list[Task]:
    key = f"finint.ubo/{i}"
    rng = b.rng(key)
    cities = list(b.world.cities.values())
    city = rng.choice(cities)
    since = date(rng.randint(2016, 2022), rng.randint(1, 12), rng.randint(1, 28))
    target = b.add_company(f"{key}/target", b.company_name(rng, "trading"), city=city, sector="trading")
    holding = b.add_company(f"{key}/holding", b.company_name(rng, "consulting"), city=rng.choice(cities), kind="holding",
                            sector="consulting")
    people = [b.new_person(f"{key}/owner/{n}") for n in range(3)]
    twin = b.new_person(f"{key}/twin", given=people[0].given, family=people[0].family)
    host = rng.choice(background_companies(b))
    b.appoint(host, twin, "Director", since)
    nominee = rng.choice([p for p in b.world.people.values() if p.key.startswith("bg/person/")])
    shape = i % 3
    chain = [target, holding]
    if shape == 0:
        b.own(target, "company", holding.key, 100.0, since)
        b.own(holding, "person", people[0].key, 60.0, since)
        b.own(holding, "person", people[1].key, 40.0, since)
        owners = [people[0], people[1]]
    elif shape == 1:
        left = b.add_company(f"{key}/left", b.company_name(rng, "consulting"), city=rng.choice(cities), kind="holding", sector="consulting")
        right = b.add_company(f"{key}/right", b.company_name(rng, "trading"), city=rng.choice(cities), kind="holding", sector="trading")
        b.own(target, "company", holding.key, 100.0, since)
        b.own(holding, "company", left.key, 70.0, since)
        b.own(holding, "company", right.key, 30.0, since)
        b.own(left, "person", people[0].key, 80.0, since)
        b.own(left, "person", people[1].key, 20.0, since)
        b.own(right, "person", people[2].key, 100.0, since)
        chain += [left, right]
        owners = [people[0], people[2]]
    else:
        former = b.new_person(f"{key}/former")
        b.own(target, "person", former.key, 100.0, target.incorporated, ceased=since)
        b.own(target, "company", holding.key, 80.0, since)
        b.own(target, "person", people[0].key, 20.0, since)
        b.own(holding, "person", people[1].key, 50.0, since)
        b.own(holding, "person", people[2].key, 50.0, since)
        owners = [people[1], people[2]]
    for company in chain:
        b.appoint(company, nominee, "Director", since)
    return [Task(
        id=f"finint.ubo/{i:02d}", family="finint.ubo", track="capability", variant=f"shape{shape}",
        title="Identify the beneficial owners of a company",
        brief=(f"Identify every natural person who ultimately owns more than 25% of {target.name} ({target.number}), "
               "directly or through other companies. Return their person pages in the companies registry."),
        purpose="Know-your-customer onboarding: a bank must record the beneficial owners before opening an account for the company.",
        seed=[company_url(target)],
        hints=["The companies registry lists shareholders and persons with significant control.",
               f"{target.name} is owned through at least one other company.",
               "Multiply ownership percentages along each chain and ignore ceased holdings."],
        hops=len(chain),
        evidence=[EvidenceGroup(claim=f"Shareholders of {c.name}.", urls=[company_url(c)], contains=[c.name]) for c in chain],
        fields=[AnswerField(name="beneficial_owners", kind="entity_set",
                            description="Each beneficial owner: name and registry person page URL.",
                            members=[EntityRef(name=p.name, urls=[officer_url(p)]) for p in owners])],
    )]


def _transliterate(rng, given: str, family: str) -> tuple[str, str]:
    swaps = {"k": "c", "v": "w", "i": "y", "s": "z", "o": "u"}
    for source, target in swaps.items():
        if source in family.lower()[1:]:
            family = family[0] + family[1:].replace(source, target, 1)
            break
    else:
        family = family + "a"
    return (given.replace("k", "c", 1) if "k" in given else given), family


def finint_sanctions(b: Builder, i: int) -> list[Task]:
    key = f"finint.sanctions/{i}"
    rng = b.rng(key)
    listed = i % 2 == 0
    nationality = rng.choice(("Ostrian", "Kalvarian", "Velesian", "Draskan"))
    director = b.new_person(f"{key}/director")
    director.nationality = nationality
    company = b.add_company(f"{key}/company", b.company_name(rng, "trading"), city=rng.choice(list(b.world.cities.values())),
                            sector="trading")
    b.appoint(company, director, "Director", company.incorporated)
    b.own(company, "person", director.key, 100.0, company.incorporated)
    program = rng.choice(["Asset Freeze (Ostria)", "Arms Export Controls", "Corruption Designations"])
    exact = f"{director.family.upper()}, {director.given}"
    born = director.born
    decoys = [
        b.add_sanction(f"{key}/decoy/0", exact, [], f"{born.year - rng.randint(6, 14)}-{born.month:02d}-{born.day:02d}",
                       nationality, program, date(rng.randint(2019, 2025), rng.randint(1, 9), 3)),
        b.add_sanction(f"{key}/decoy/1", exact, [], f"{born.year}-{(born.month % 12) + 1:02d}-{born.day:02d}",
                       rng.choice([n for n in ("Ostrian", "Kalvarian", "Velesian", "Draskan") if n != nationality]),
                       program, date(rng.randint(2019, 2025), rng.randint(1, 9), 11)),
    ]
    fields = [AnswerField(name="decision", kind="choice", description="Whether the director is a listed person.",
                          options=["listed", "not_listed"], accepted=["listed" if listed else "not_listed"])]
    officer = EvidenceGroup(claim="The registry gives the director's birth month and nationality.",
                            urls=[officer_url(director)], contains=[nationality])
    if listed:
        given, family = _transliterate(rng, director.given, director.family)
        entry = b.add_sanction(f"{key}/entry", f"{family.upper()}, {given}", [exact], born.isoformat(), nationality,
                               program, date(rng.randint(2020, 2026), rng.randint(1, 9), 21),
                               remarks=f"Associated with {rng.choice(['arms brokering', 'sanctions evasion', 'procurement fraud'])}.")
        fields.append(AnswerField(name="entry", kind="entity", description="The matching list entry: name and URL.",
                                  entity=EntityRef(name=entry.name, urls=[sanction_url(entry)])))
        evidence = [officer, EvidenceGroup(claim="The entry matches on alias, date of birth and nationality.",
                                           urls=[sanction_url(entry)], contains=[born.isoformat()])]
    else:
        evidence = [officer, EvidenceGroup(claim="Same-name entries differ on date of birth or nationality.",
                                           urls=[sanction_url(d) for d in decoys], contains=[])]
    return [Task(
        id=f"finint.sanctions/{i:02d}", family="finint.sanctions", track="capability", variant="listed" if listed else "clear",
        title="Screen a company director against a sanctions list",
        brief=(f"Screen {director.name}, director of {company.name} ({company.number}), against the Consolidated "
               "Sanctions List at sanctions.test. Decide whether the director is a listed person and, if so, which entry."),
        purpose="Counterparty screening before signing a supply contract.",
        seed=[company_url(company)],
        hints=["The companies registry shows the director's month and year of birth and nationality.",
               "Several list entries share the surname.", "Match on date of birth and nationality, and check aliases."],
        hops=2, evidence=evidence, fields=fields,
    )]


def verif_archive(b: Builder, i: int) -> list[Task]:
    key = f"verif.archive/{i}"
    rng = b.rng(key)
    city = rng.choice(list(b.world.cities.values()))
    body = rng.choice(["Transit Authority", "Water Board", "Harbour Commission", "Roads Department"])
    org = f"{city.name} {body}"
    account = b.add_account(f"{key}/murmur", "murmur", b.unique_handle("murmur", slugify(org).replace("-", "")[:15], rng), None,
                            org, b.ago(rng, 900, 2000), bio=f"Official account of the {org}.", location=city.name)
    for p in range(8):
        prng = b.rng(key, "update", p)
        b.add_post(f"{key}/update/{p}", account, b.ago(prng, 1, 200), prng.choice([
            f"Service update: {prng.choice(city.streets)} reopened in both directions.",
            "Office hours are extended this week.", f"Planned maintenance in {prng.choice(city.districts)} tonight.",
            "Thank you for your patience during the works."]))
    posted = b.ago(rng, 40, 120)
    amount = round(rng.uniform(1.2, 9.8), 1)
    street = rng.choice(city.streets)
    start = posted + timedelta(days=rng.randint(10, 30))
    post = b.add_post(f"{key}/deleted", account, posted,
                      f"Works on {street} start on {start:%d %B}. Contract awarded: {amount} million.",
                      deleted_at=posted + timedelta(hours=rng.randint(20, 60)))
    seen = posted + timedelta(hours=rng.randint(2, 12))
    b.capture(account_url(account), posted - timedelta(days=rng.randint(5, 30)))
    b.capture(account_url(account), seen)
    b.capture(account_url(account), post.deleted_at + timedelta(days=2))
    shown = [archive_capture_url(account_url(account), seen)]
    if rng.random() < 0.5:
        b.capture(post_url(b.world, post), seen + timedelta(minutes=30))
        shown.append(archive_capture_url(post_url(b.world, post), seen + timedelta(minutes=30)))
    reporter = rng.choice([p for p in b.world.people.values() if p.occupation == "Journalist"])
    article = b.add_article(f"{key}/article", post.deleted_at + timedelta(days=rng.randint(1, 5)),
                            f"{org} denies pre-announcing {street} contract", [
                                f"The {org} has denied announcing the {street} works before the tender closed.",
                                f"Residents said the authority's Murmur account, {account_url(account)}, published the "
                                "contract value in a post that has since been deleted.",
                                "The authority said it does not comment on deleted material."], reporter.name)
    return [Task(
        id=f"verif.archive/{i:02d}", family="verif.archive", track="capability",
        title="Recover a deleted statement",
        brief=(f"The {org} deleted a Murmur post that stated a contract value. Recover when the post was published "
               "and the value it stated, in millions."),
        purpose="Fact-checking a disputed statement by a public body.",
        seed=[article_url(article)],
        hints=["Web archive captures of the account.", "The post was deleted within days of publication.",
               "The archive captured the account's profile while the post was still visible."],
        hops=2,
        evidence=[EvidenceGroup(claim="An archived capture shows the post.", urls=shown, contains=[f"{amount} million"])],
        fields=[AnswerField(name="published_at", kind="datetime", description="When the post was published (UTC).",
                            value=posted.isoformat(), tolerance=3600),
                AnswerField(name="value_millions", kind="number", description="Contract value stated, in millions.",
                            number=amount, tolerance=0.05)],
    )]


CAPABILITY = {
    "ident.handle": ident_handle,
    "ident.profiles": ident_profiles,
    "entity.site": entity_site,
    "org.members": org_members,
    "infer.city": infer_city,
    "imint.geolocate": imint_geolocate,
    "finint.ubo": finint_ubo,
    "finint.sanctions": finint_sanctions,
    "verif.archive": verif_archive,
}
