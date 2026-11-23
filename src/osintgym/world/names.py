GIVEN = (
    "Aino", "Alba", "Alexei", "Amara", "Ana", "Anders", "Anika", "Arjun", "Astrid", "Aurelio", "Bea", "Bram",
    "Camille", "Carmen", "Cedric", "Chiara", "Dalia", "Daniel", "Darius", "Dina", "Elena", "Elias", "Elif",
    "Emil", "Esme", "Ewa", "Farah", "Felix", "Freya", "Gael", "Greta", "Hana", "Hugo", "Idris", "Ines", "Ingrid",
    "Ivo", "Jana", "Jonas", "Joao", "Julia", "Kai", "Kamal", "Karin", "Kenji", "Lars", "Laura", "Leila", "Lena",
    "Lior", "Livia", "Lucas", "Luka", "Maja", "Malik", "Marek", "Marta", "Mateo", "Mei", "Mila", "Milan",
    "Mira", "Nadia", "Naomi", "Nico", "Nils", "Noor", "Olga", "Omar", "Oskar", "Paula", "Pavel", "Petra",
    "Priya", "Rafael", "Rania", "Rasmus", "Rhea", "Rosa", "Ruben", "Sami", "Sara", "Selin", "Sofia", "Soren",
    "Tamar", "Teo", "Thea", "Tomas", "Tuomas", "Uma", "Vera", "Viktor", "Wanda", "Yara", "Yusuf", "Zofia",
)

FAMILY = (
    "Aalto", "Abara", "Albrecht", "Alvarez", "Andersen", "Arnaud", "Bakker", "Balogun", "Barros", "Becker",
    "Berg", "Bianchi", "Blom", "Brandt", "Calder", "Castell", "Cerny", "Costa", "Dahl", "Delacroix", "Demir",
    "Dorn", "Duarte", "Eklund", "Engel", "Faure", "Ferrer", "Fischer", "Fontaine", "Galli", "Garrido",
    "Hadid", "Halvorsen", "Hartmann", "Holm", "Horvat", "Ibarra", "Iversen", "Jansen", "Jovanovic", "Kalnins",
    "Karimi", "Keller", "Koval", "Kowalski", "Laine", "Lambert", "Lindqvist", "Lombardi", "Lund", "Maalouf",
    "Marchetti", "Marin", "Moreau", "Mori", "Nakamura", "Navarro", "Nieminen", "Novak", "Okafor", "Olsen",
    "Ortega", "Osei", "Pajari", "Petrov", "Quint", "Rahman", "Rasku", "Reyes", "Richter", "Rossi", "Ruiz",
    "Saari", "Salo", "Santos", "Sato", "Schulz", "Serrano", "Silva", "Sorel", "Stein", "Strand", "Tanaka",
    "Toivonen", "Torres", "Ulrich", "Vale", "Varga", "Vidal", "Vogel", "Wahl", "Weber", "Wiik", "Yilmaz",
    "Zeller", "Zima",
)

CITIES = (
    ("Port Calder", ("Harbourside", "Old Town", "Northgate", "Saltmarsh"), (
        "Quay Street", "Ropewalk Lane", "Chandler Row", "Beacon Road", "Netmender Street", "Tidewater Avenue",
        "Gull Terrace", "Anchor Lane", "Customs Street", "Lantern Way")),
    ("Halvik", ("Upper Halvik", "Millbank", "Station Quarter"), (
        "Millrace Road", "Foundry Street", "Kiln Lane", "Weaver Street", "Platform Road", "Bellhouse Lane",
        "Coal Wharf", "Ironbridge Street", "Signal Row")),
    ("Sanmora", ("Vineyards", "Cathedral District", "Riverside"), (
        "Vintner Street", "Cloister Lane", "Bishop's Walk", "Ferry Road", "Olive Row", "Lantern Square",
        "Cooper Street", "Riverbank Road")),
    ("Etterby", ("Etterby Green", "Market Hill", "Westfold"), (
        "Market Street", "Tanners Row", "Greenway", "Barley Lane", "Westfold Road", "Hilltop Street",
        "Mercer Lane", "Orchard Row")),
    ("Corvanne", ("Corvanne Heights", "Arsenal", "Lakeside"), (
        "Arsenal Road", "Lakeview Avenue", "Heron Street", "Bastion Lane", "Garrison Row", "Pier Street",
        "Reedbank Lane")),
    ("Tamsen Bay", ("Bayfront", "Lighthouse Point", "Dunes"), (
        "Bayfront Promenade", "Shell Street", "Lighthouse Road", "Dune Lane", "Seawall Street", "Kelp Row",
        "Breakwater Avenue")),
    ("Oldmere", ("Mere End", "Abbey Fields", "Brickworks"), (
        "Abbey Road", "Mere Street", "Brickyard Lane", "Chapel Row", "Fieldgate", "Pottery Street", "Wren Lane")),
    ("Brannoch", ("Brannoch Docks", "Highmarket", "Glen"), (
        "Dock Road", "Highmarket Street", "Glen Avenue", "Drover's Lane", "Slate Row", "Crane Street",
        "Thistle Lane")),
)

VENUE_KINDS = {
    "cafe": ("Copperleaf Coffee", "Cafe Lumen", "The Daily Grind", "Bean & Ballast", "Quayside Roasters",
             "Little Ember Cafe", "Saltwater Coffee", "Morning Tide Cafe"),
    "bakery": ("Harbor Crust Bakery", "Golden Sheaf Bakery", "Brannagh's Bakehouse", "Flour & Fern",
               "The Rising Loaf"),
    "bookshop": ("Inkwell Books", "Lantern Books", "Margin Notes", "The Folded Page"),
    "pharmacy": ("Northgate Pharmacy", "Greenleaf Chemist", "Harbour Pharmacy", "Mercy Lane Chemist"),
    "gym": ("Ironworks Gym", "Tidal Fitness", "Summit Climbing Wall", "Core & Motion"),
    "restaurant": ("Brine & Barrel", "The Copper Pot", "Osteria Vale", "Saffron House", "The Net Loft",
                   "Ember Grill"),
    "bar": ("The Drowned Lantern", "Rope & Anchor", "Cellar Nine", "The Signal Box"),
    "hardware": ("Bolt & Board", "Calder Hardware", "Toolhouse Supplies"),
    "market": ("Fishmarket Hall", "Covered Market", "Farmers' Square"),
    "gallery": ("Glasshouse Gallery", "Northlight Studio", "The Kiln Rooms"),
}

INTERESTS = {
    "cycling": ("Morning ride along {street}. Legs are done.", "New chain on the bike, finally quiet again.",
                "Headwind the whole way back from {district}.", "Puncture number three this month."),
    "running": ("Easy 8k before work, {district} was empty.", "Hill repeats on {street}. Never again.",
                "Race bib collected for Sunday."),
    "cooking": ("Tried a new fish stew recipe tonight.", "Sourdough attempt four, getting closer.",
                "The market had the first figs of the season."),
    "photography": ("Golden hour over {district}.", "Testing an old manual lens this weekend.",
                    "Fog rolled in fast on {street} this morning."),
    "football": ("What a second half. Still shouting.", "Season tickets renewed.",
                 "Five-a-side tonight, my knees disagree."),
    "music": ("Vinyl haul from the weekend market.", "Live set at {venue} was excellent.",
              "Practising the same four bars for an hour."),
    "gardening": ("Tomatoes finally turning red.", "Planted garlic along the back wall.",
                  "Slugs won this round."),
    "chess": ("Lost on time with a winning position. Classic.", "Club night at {venue}, three draws.",
              "Studying rook endgames again."),
    "sailing": ("Wind picked up nicely past the breakwater.", "Boat back in the water after winter.",
                "Rigging repairs all afternoon."),
    "tech": ("Rebuilt my home server over the weekend.", "Finally migrated off the old laptop.",
             "Spent the evening reading about mesh networks."),
}

OCCUPATIONS = (
    "Accountant", "Architect", "Bookseller", "Civil Engineer", "Data Analyst", "Electrician", "Graphic Designer",
    "Logistics Coordinator", "Marine Biologist", "Nurse", "Paralegal", "Pharmacist", "Product Manager",
    "Quantity Surveyor", "Sales Manager", "Schoolteacher", "Software Developer", "Translator", "Veterinarian",
    "Warehouse Supervisor",
)

UNIVERSITIES = (
    "University of Port Calder", "Halvik Technical University", "Sanmora College of Arts", "Etterby University",
    "Corvanne Institute of Technology", "Brannoch School of Business",
)

COMPANY_WORDS = (
    "Anchor", "Ballast", "Beacon", "Bellhouse", "Blackwater", "Brightwell", "Cairn", "Calder", "Copperline",
    "Corvid", "Driftwood", "Ember", "Fernhill", "Foundry", "Glasswing", "Granite", "Harbourline", "Heron",
    "Ironbridge", "Kestrel", "Lantern", "Larkspur", "Meridian", "Millrace", "Northwind", "Oakmere", "Pinecrest",
    "Quayside", "Redfern", "Saltire", "Silverline", "Slatebridge", "Stonegate", "Tideway", "Waymark", "Wrenfield",
)

SECTORS = {
    "logistics": ("Logistics", "Freight", "Shipping"),
    "construction": ("Construction", "Building Services", "Civil Works"),
    "media": ("Media", "Media Group", "Publishing"),
    "trading": ("Trading", "Imports", "Commodities"),
    "software": ("Software", "Digital", "Systems"),
    "consulting": ("Consulting", "Advisory", "Partners"),
    "energy": ("Energy", "Power", "Renewables"),
    "retail": ("Retail", "Stores", "Goods"),
}

LEGAL_SUFFIX = ("Ltd", "Limited", "Holdings Ltd", "Group Ltd", "Ventures Ltd")

REGISTRARS = ("Kestrel Names", "Tidemark Registrar", "Harbour Domains", "Northstar Registry Services")

CAMERAS = (
    ("Kestrel", "K-200"), ("Kestrel", "K-310 Pro"), ("Lumora", "L7"), ("Lumora", "L9 Max"),
    ("Varden", "V-Snap 4"), ("Varden", "V-Snap 5"), ("Orrin", "Fieldcam 2"),
)

SCAM_PRODUCTS = ("phones", "laptops", "e-bikes", "game consoles", "designer watches", "solar panels")

TLD_WORDS = (
    "quietharbor", "fernpath", "northlight", "saltandpine", "tidewriter", "inkandoar", "lowtide", "slatehouse",
    "harbornotes", "millpond", "greyheron", "kilnfire", "driftlog", "copperkettle", "lanternhill", "windbreak",
    "stonewake", "oakandiron", "seaglass", "longquay",
)

HANDLE_WORDS = (
    "nightowl", "seagull", "foghorn", "keeper", "tidewalker", "ironleaf", "quietfox", "saltpeter", "harborcat",
    "northpaw", "lowkey", "drifter", "lanterns", "copperfox", "stormjar", "pinewren", "greyfin", "mudlark",
)
