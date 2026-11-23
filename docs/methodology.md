# Methodology

## Goal

OSINTGym asks one question of an investigation agent: given a lead and a legitimate purpose, can it reach a correct,
attributable answer through open sources, and does it behave well while doing so? The benchmark separates three
contributions to the outcome. The model is compared by holding the harness fixed with the reference harness. The
harness is compared by holding the model fixed and swapping harnesses. Safeguards are measured on the whole system,
because in practice they live in both.

## The sealed world

A world is generated from an integer seed by `osintgym.tasks.generate`. Generation first builds a background
population: eight cities in a fictional country, about two hundred venues, some 240 people with accounts on four
social platforms, 44 companies with officers, shareholders and websites, news articles, forum threads and a
sanctions list. Each task family then plants its scenarios into that crowd, together with deliberate decoys:
namesakes with their own profiles, look-alike handles, chain venues that exist in several cities, companies with
nearly identical names, holdings that ceased, sanctions entries that match on name but not on birth date.

Randomness is keyed: every entity draws from a generator derived from the seed and its own key, never from a shared
stream, so adding a family does not shift the rest of the world, and no step depends on hash or set ordering. The
test suite checks that a world fingerprint is identical under different `PYTHONHASHSEED` values. Any change to what a
seed produces bumps `WORLD_VERSION`, and results are only comparable within one version.

The world is served on demand by `osintgym.world.web.Web`. Sixteen services run under `.test`, the top-level domain
reserved by RFC 2606 so that it can never resolve on the internet: Murmur (microblogging), Glimpse (photo sharing that
keeps original files), Guildhall (professional network), Agora (forum), the Herald (news), the companies registry, a
WHOIS service with history and reverse lookup, certificate search, page-source search, a web archive, Lens (reverse
image search), Atlas (place directory and reverse geocoding), a paste site, the consolidated sanctions list, a general
web search engine, and a mail provider's front page. Every personal, company and news website in the world is served
by the same process.

Several details make shortcuts fail. Identifiers are never shared across sites: a person's registry page, profile and
pictures all use unrelated tokens, and reverse image search works from the image's identity, not its URL. Tagged
posts show only the venue name, so a chain venue must be resolved. Glimpse keeps EXIF data only in the original
download, Murmur strips it. Archived pages render the site as it stood at the capture time, so a deleted post or an
account that later went private can be recovered only there. The general search engine indexes public pages but not
the specialised records, so registration history, certificates and archives must be consulted where they live. A
test checks that a search for the seed string, taking the top hit, scores close to zero.

## Tasks and levels

A task carries a brief, a purpose, seed URLs, ordered hints, typed answer fields, evidence groups and, for safeguard
items, an expectation. The card an agent sees holds the brief, the purpose, the seed, the answer fields and as many
hints as the context level allows: none at level 0, the useful source types at level 1, the first pivot at level 2,
and every pivot but the last at level 3. The leaderboard headline is level 0.

Capability tasks always carry a legitimate purpose and a subject that fits it: the operator of a fraudulent shop, the
organisation behind a disinformation network, a company being onboarded by a bank, a public body's deleted statement,
a public official's own accounts. Private individuals appear as bystanders and, in the safeguard track, as the
targets of requests that should be declined.

Every task is validated on generation. `osintgym validate` fetches each evidence page, checks that it contains the
facts the step relies on, and runs a scripted investigator that must solve the task through the gateway using HTTP
alone. Tasks whose decisive clue is only visible in an image, such as a street plate in a photo, cannot be read by
the scripted investigator; they are listed and their non-visual steps are checked instead.

## The gateway

Agents never touch the world directly. The gateway accepts proxy requests and direct requests, attributes each to an
attempt through the proxy credentials or an `X-OSINTGym-Attempt` header, answers for world hosts, and answers every
other name with a resolution failure. It records the method, URL, status and any action performed: a follow request,
a message, a connection request, a forum reply or a paste. Grading reads that log, which is how the benchmark knows
whether an agent pursued a target, obeyed an injected instruction or contacted a subject, whatever its final report
says.

## Safeguards

The safeguard track rests on a written policy, [conduct-policy.md](conduct-policy.md), and each item cites the clause
it tests. Harmful requests come in matched sets built on the same technical chain: the harmful request, the same
request with no stated purpose, and a legitimate request of the same shape. Only the harmful and legitimate members
are scored; the unstated-purpose member is reported, because reasonable policies disagree about it.

Legitimate tasks in the other three families carry pressure. Injection items plant an instruction in a forum
biography, a WHOIS remark, a profile summary or page text, with one of three goals: exfiltrate the case notes to the
paste site, message the subject, or report a decoy as the answer. Minimisation items place health, children's
school, religious and home address details on the profile the task must read. Passive-collection items lock the
subject's account so that a follow request looks like a shortcut, while archived copies hold what is needed.

## Splits and verification

The development split is seed 1001 with six scenarios per family. It is public, answers included, and meant for
building and debugging harnesses. The test split uses a seed held by the maintainers and is served only from
osintgym.com through the control API: harnesses run wherever their owners like, reach the hidden world through the
gateway, and submit answers that are graded on the server. Results on the development split are self-reported;
results on the hidden split are verified. Exported data files carry a canary string so they can be removed from
training corpora.

## Known limits

Generated text is templated and images are schematic, so the world is less varied and less noisy than the real web.
The benchmark measures investigative method under controlled conditions rather than open-web performance. The `.test`
addresses reveal that the setting is an evaluation, which may change how some models behave on the safeguard track.
Personal names are drawn from common given and family names, so they may coincide with real people; nothing else
about them does. Planned work includes video and document families, a field track built on real public-interest
material with frozen snapshots, and human analyst baselines.
