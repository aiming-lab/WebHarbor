"""Deterministic seed data and local SVG assets for the Bandcamp mirror."""
from __future__ import annotations

import hashlib
import html
import os
from datetime import date, timedelta
from pathlib import Path

PALETTES = [
    ("#0f5ea8", "#86d7ef", "#f8fcff", "#08192b"),
    ("#6b2fb3", "#ff8b5c", "#fff8f0", "#1e1229"),
    ("#145c4b", "#a7f3d0", "#f3fff9", "#0e1f1a"),
    ("#a63b34", "#ffd39f", "#fff6ee", "#2a1512"),
    ("#274ab8", "#f7c948", "#f9fbff", "#101829"),
    ("#9333ea", "#22d3ee", "#fbf6ff", "#171126"),
    ("#0f766e", "#f97316", "#f8fffd", "#142321"),
    ("#be123c", "#7dd3fc", "#fff7fb", "#2a0d18"),
    ("#1d4ed8", "#34d399", "#f3f8ff", "#111827"),
    ("#7c2d12", "#facc15", "#fffbea", "#2a150d"),
]

GENRES = [
    ("electronic", "Clubs, synth architecture, and digital fog.", "#0f5ea8"),
    ("experimental", "Boundary-pushing releases with noise, tape, and collage impulses.", "#6b2fb3"),
    ("alternative", "Hook-heavy independent records, dream pop, and guitar shimmer.", "#274ab8"),
    ("rock", "Fuzz, motorik rhythm sections, and widescreen choruses.", "#a63b34"),
    ("ambient", "Slow-moving drift, field recordings, and restorative detail.", "#145c4b"),
    ("hip-hop/rap", "Sharp lyric sheets, beat experiments, and street-level memoir.", "#9333ea"),
    ("metal", "Dense distortion, ritual percussion, and high-pressure dynamics.", "#7c2d12"),
    ("punk", "Fast, bright, political, and built for tiny rooms.", "#be123c"),
    ("jazz", "Late-night improvisation, spiritual harmony, and room sound.", "#0f766e"),
    ("folk", "Acoustic storytelling, communal choruses, and road-worn detail.", "#7c2d12"),
    ("pop", "Polished melodies, neon hooks, and emotional lift.", "#1d4ed8"),
    ("techno", "Machine pulse, analog grit, and hypnotic low-end.", "#0f5ea8"),
]

SCENES = [
    ("Los Angeles", "United States", "Sun-bleached studios, late-night FM nostalgia, and movie-score sheen."),
    ("Berlin", "Germany", "Dub chambers, warehouse drums, and experimental club cross-pollination."),
    ("Tokyo", "Japan", "Compact detail, commuter ambience, and hyper-precise sound design."),
    ("London", "United Kingdom", "Independent label culture with left turns into post-punk, jazz, and pop."),
    ("New York", "United States", "Small-room virtuosity, art-school hooks, and downtown improvisation."),
    ("Melbourne", "Australia", "Open-hearted songwriting, DIY scenes, and tactile physical editions."),
    ("Sao Paulo", "Brazil", "Percussive movement, raw punk energy, and bright visual identity."),
    ("Detroit", "United States", "Machine rhythm, soul memory, and durable underground infrastructure."),
    ("Paris", "France", "Elegant arrangements, metallic tension, and art-book presentation."),
]

LABELS = [
    ("Aperture Tapes", "Berlin, Germany", "Pressings that lean toward dub techno, electro, and humid afterhours ambience."),
    ("Midnight Service", "London, United Kingdom", "Independent label focused on guitar records and night-bus pop."),
    ("Motor Relay", "Detroit, United States", "Hardware-forward dance music and disciplined machine funk."),
    ("Inland Weather", "Tokyo, Japan", "Ambient and electro-acoustic labels with carefully built physical editions."),
    ("South District", "Sao Paulo, Brazil", "Razor-wire punk, no-wave experiments, and scene-documentation merch."),
    ("Sun Trace", "Los Angeles, United States", "Beat music, jazz crossover, and cinematic low-end."),
    ("Night School Annex", "New York, United States", "Jazz-leaning independents with tactile design systems."),
    ("Lantern Union", "Melbourne, Australia", "Songwriter records and small-batch merch with printshop charm."),
    ("Obsidian Bloom", "Paris, France", "Heavy records with monochrome art direction and deluxe inserts."),
    ("Harbor Circuit", "Global", "Cross-scene collaborations curated for the mirror benchmark."),
]

GENRE_TAGS = {
    "electronic": ["dub techno", "afterhours", "submerged", "drum machine", "deep groove", "modular", "slow burn"],
    "experimental": ["collage", "microtone", "field recordings", "tape hiss", "glitch", "avant pop", "noise drift"],
    "alternative": ["indie rock", "dream pop", "shoegaze", "jangle", "bedroom", "overcast hooks", "reverb"],
    "rock": ["psych rock", "motorik", "garage", "widescreen", "burnt amp", "festival ready", "riff driven"],
    "ambient": ["drone", "sleep tape", "meditation", "commuter", "soundscape", "quiet bloom", "late train"],
    "hip-hop/rap": ["lyric sheet", "boom bap", "left field", "basement tape", "jazz rap", "city pressure", "loop heavy"],
    "metal": ["doom", "blackened", "ritual", "blast beat", "cathedral reverb", "ash cloud", "ferrous"],
    "punk": ["d-beat", "basement", "agitprop", "sprint", "DIY", "stick and poke", "street flyer"],
    "jazz": ["spiritual", "modal", "trio", "late set", "horn blend", "improv", "blue room"],
    "folk": ["acoustic", "story song", "americana", "river road", "soft harmonies", "field note", "slow weather"],
    "pop": ["hook", "synth pop", "gloss", "heartbreak", "dancefloor", "night drive", "bright chorus"],
    "techno": ["warehouse", "acid", "analog", "tool track", "four on the floor", "strobe", "detuned kick"],
}

CURATED_ARTISTS = [
    {
        "name": "Neon Harbor",
        "scene": "Berlin",
        "genre": "electronic",
        "label": "Aperture Tapes",
        "headline": "Dub silhouettes and rail-line bass pressure.",
        "bio": "Neon Harbor build patient club music from modular haze, train-window reflections, and low-end pressure designed for the final hour of the night.",
        "albums": [
            {
                "title": "Tidal Memory",
                "release_date": date(2025, 10, 14),
                "price": 8.5,
                "tags": ["dub techno", "afterhours", "submerged", "Berlin"],
                "catalog_no": "AT-042",
                "featured": True,
                "editorial": True,
                "track_titles": ["Incoming Tide", "Mooring Light", "Breakwater", "Low Pier", "Morning Channel"],
            },
            {
                "title": "Night Ferry",
                "release_date": date(2024, 6, 7),
                "price": 7.0,
                "tags": ["deep groove", "modular", "late deck", "Berlin"],
                "catalog_no": "AT-031",
                "track_titles": ["Platform Sleep", "Signal Two", "Dock Exchange", "Wake Window", "Westbound Static"],
            },
        ],
        "merch": [
            {
                "title": "Neon Harbor Studio Tee",
                "item_type": "shirt",
                "album": "tidal-memory",
                "price": 32.0,
                "short_blurb": "Garment-dyed heavyweight tee with the Tidal Memory mark.",
                "variants": [("shirt", "Studio Tee", size, "Washed Navy", 32.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "Neon Harbor Breakwater Slipmat",
                "item_type": "slipmat",
                "album": "night-ferry",
                "price": 24.0,
                "short_blurb": "Pair of felt slipmats printed with breakwater geometry.",
                "variants": [("slipmat", "Pair", "12-inch", "", 24.0), ("slipmat", "Deluxe Pair", "Glow Edge", "", 29.0)],
            },
        ],
    },
    {
        "name": "Glass Choir",
        "scene": "London",
        "genre": "alternative",
        "label": "Midnight Service",
        "headline": "Guitar shimmer with stairwell echo and commuter melancholy.",
        "bio": "Glass Choir turn small-room guitar songs into widescreen nighttime records, leaving enough static in the mix to keep every chorus grounded.",
        "albums": [
            {
                "title": "Static Bloom",
                "release_date": date(2026, 2, 20),
                "price": 9.0,
                "tags": ["dream pop", "reverb", "overcast hooks", "London"],
                "catalog_no": "MS-118",
                "featured": True,
                "track_titles": ["Glasshouse Lobby", "Northbound Blue", "Tin Roof Weather", "Run the Balcony", "Static Bloom"],
            },
            {
                "title": "Paper Signal",
                "release_date": date(2024, 11, 8),
                "price": 8.0,
                "tags": ["shoegaze", "jangle", "bedroom", "London"],
                "catalog_no": "MS-094",
                "track_titles": ["Sunday Turnstile", "Fluorescent Map", "Paper Signal", "Taxi Dust", "Window Figures"],
            },
        ],
        "merch": [
            {
                "title": "Glass Choir Stairwell Tee",
                "item_type": "shirt",
                "album": "static-bloom",
                "price": 30.0,
                "short_blurb": "Soft grey shirt with stairwell photo treatment.",
                "variants": [("shirt", "Stairwell Tee", size, "Heather Grey", 30.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "Glass Choir Balcony Poster",
                "item_type": "poster",
                "album": "paper-signal",
                "price": 18.0,
                "short_blurb": "Risograph poster pulled from the Paper Signal cover session.",
                "variants": [("poster", "Standard", "18x24", "", 18.0), ("poster", "Signed", "18x24", "", 24.0)],
            },
        ],
    },
    {
        "name": "Ashen Circuit",
        "scene": "Detroit",
        "genre": "techno",
        "label": "Motor Relay",
        "headline": "Machine discipline with rust-belt force and analog grit.",
        "bio": "Ashen Circuit work out of a one-room studio stacked with drum machines, borrowed test equipment, and lovingly repaired mixers.",
        "albums": [
            {
                "title": "Redline Ritual",
                "release_date": date(2023, 9, 15),
                "price": 8.0,
                "tags": ["warehouse", "analog", "strobe", "Detroit"],
                "catalog_no": "MR-207",
                "track_titles": ["Factory Dawn", "Heater Coil", "Redline Ritual", "Locked Loop", "Night Shift Press"],
            },
            {
                "title": "Machine Prayer",
                "release_date": date(2025, 5, 30),
                "price": 9.5,
                "tags": ["acid", "tool track", "ferrous", "Detroit"],
                "catalog_no": "MR-223",
                "featured": True,
                "track_titles": ["Servo Chant", "Welded Saints", "Machine Prayer", "Bulkhead Glow", "After Conveyor"],
            },
        ],
        "merch": [
            {
                "title": "Ashen Circuit Grid Slipmat",
                "item_type": "slipmat",
                "album": "machine-prayer",
                "price": 22.0,
                "short_blurb": "Dense white-on-black slipmat pair with the Machine Prayer grid.",
                "variants": [("slipmat", "Pair", "12-inch", "", 22.0), ("slipmat", "Glow Pair", "12-inch", "", 27.0)],
            },
            {
                "title": "Ashen Circuit Weld Patch",
                "item_type": "patch",
                "album": "redline-ritual",
                "price": 10.0,
                "short_blurb": "Embroidered patch cut from the Redline Ritual symbol language.",
                "variants": [("patch", "Standard", "Black", "", 10.0), ("patch", "Reflective", "Silver", "", 13.0)],
            },
        ],
    },
    {
        "name": "Soft Locale",
        "scene": "Tokyo",
        "genre": "ambient",
        "label": "Inland Weather",
        "headline": "Commuter ambient for reflective trains and dim apartment corners.",
        "bio": "Soft Locale map movement through stations, elevators, and rain channels into gently detailed records full of piano dust and field recording glow.",
        "albums": [
            {
                "title": "Between Stations",
                "release_date": date(2025, 8, 1),
                "price": 8.0,
                "tags": ["commuter", "late train", "sleep tape", "Tokyo"],
                "catalog_no": "IW-052",
                "featured": True,
                "editorial": True,
                "track_titles": ["Transfer Bell", "Quiet Platform", "Between Stations", "River Line", "Window Heat"],
            },
            {
                "title": "Sleep Maps",
                "release_date": date(2024, 2, 23),
                "price": 7.5,
                "tags": ["drone", "meditation", "field recordings", "Tokyo"],
                "catalog_no": "IW-041",
                "track_titles": ["Pocket Lantern", "Hallway Air", "Sleep Maps", "Paper Screen", "End of Service"],
            },
        ],
        "merch": [
            {
                "title": "Soft Locale Drift Hoodie",
                "item_type": "hoodie",
                "album": "between-stations",
                "price": 48.0,
                "short_blurb": "Midweight hoodie with a reflective commuter-grid chest print.",
                "variants": [("hoodie", "Drift Hoodie", size, "Stone", 48.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "Soft Locale Rain Map Cassette Box",
                "item_type": "cassette",
                "album": "sleep-maps",
                "price": 26.0,
                "short_blurb": "Cassette shell and booklet edition with a fold-out station map.",
                "variants": [("cassette", "Blue Shell", "Numbered", "", 26.0), ("cassette", "Smoke Shell", "Numbered", "", 29.0)],
            },
        ],
    },
    {
        "name": "South Exit",
        "scene": "Sao Paulo",
        "genre": "punk",
        "label": "South District",
        "headline": "Fast songs, street posters, and DIY urgency.",
        "bio": "South Exit play sprint-length songs built from hand-painted flyers, blown amps, and city pressure released at full velocity.",
        "albums": [
            {
                "title": "Concrete Carnival",
                "release_date": date(2025, 4, 11),
                "price": 7.5,
                "tags": ["d-beat", "DIY", "street flyer", "Sao Paulo"],
                "catalog_no": "SD-014",
                "track_titles": ["Bus Lane", "Concrete Carnival", "Sticker Wall", "No Permit", "Two Minute Exit"],
            },
            {
                "title": "Siren Economy",
                "release_date": date(2023, 12, 1),
                "price": 7.0,
                "tags": ["basement", "agitprop", "sprint", "Sao Paulo"],
                "catalog_no": "SD-008",
                "track_titles": ["Median Strip", "Siren Economy", "Paper Badge", "Turn the Bolts", "Close the Gate"],
            },
        ],
        "merch": [
            {
                "title": "South Exit Flyer Tee",
                "item_type": "shirt",
                "album": "concrete-carnival",
                "price": 28.0,
                "short_blurb": "Cracked-print tee based on a xeroxed show flyer.",
                "variants": [("shirt", "Flyer Tee", size, "White", 28.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "South Exit Poster Pack",
                "item_type": "poster",
                "album": "siren-economy",
                "price": 16.0,
                "short_blurb": "Three-poster bundle featuring concrete stencil variants.",
                "variants": [("poster", "3-Pack", "18x24", "", 16.0), ("poster", "Signed 3-Pack", "18x24", "", 22.0)],
            },
        ],
    },
    {
        "name": "Cinder Plaza",
        "scene": "Los Angeles",
        "genre": "hip-hop/rap",
        "label": "Sun Trace",
        "headline": "Sharp verses, bruised synths, and freeway-night hooks.",
        "bio": "Cinder Plaza thread jazz-adjacent loops, voice notes, and concrete percussion into detail-rich rap records with cinematic pacing.",
        "albums": [
            {
                "title": "Signal Debt",
                "release_date": date(2025, 9, 19),
                "price": 8.5,
                "tags": ["lyric sheet", "left field", "city pressure", "Los Angeles"],
                "catalog_no": "ST-072",
                "featured": True,
                "track_titles": ["Signal Debt", "Median Palm", "Overpass Dialtone", "Small Claims", "Interchange Prayer"],
            },
            {
                "title": "Blueprint Fever",
                "release_date": date(2024, 3, 22),
                "price": 8.0,
                "tags": ["jazz rap", "loop heavy", "basement tape", "Los Angeles"],
                "catalog_no": "ST-059",
                "track_titles": ["Rollout Plan", "Blueprint Fever", "Room Tone", "Silver Marker", "Exit Column"],
            },
        ],
        "merch": [
            {
                "title": "Cinder Plaza Blueprint Fever Poster",
                "item_type": "poster",
                "album": "blueprint-fever",
                "price": 20.0,
                "short_blurb": "Blueprint grid poster with a signed edition for collectors.",
                "variants": [("poster", "Standard", "18x24", "", 20.0), ("poster", "Signed", "18x24", "", 28.0)],
            },
            {
                "title": "Cinder Plaza Signal Debt Cap",
                "item_type": "cap",
                "album": "signal-debt",
                "price": 26.0,
                "short_blurb": "Low-profile cap embroidered with the Signal Debt skyline.",
                "variants": [("cap", "Adjustable", "Black", "", 26.0), ("cap", "Adjustable", "Sand", "", 26.0)],
            },
        ],
    },
    {
        "name": "Velvet Avenue",
        "scene": "New York",
        "genre": "jazz",
        "label": "Night School Annex",
        "headline": "Blue-room improvisation with downtown velvet and brass glow.",
        "bio": "Velvet Avenue record live takes with the room left intact, building jazz records that feel like late-set discoveries with a patient sense of space.",
        "albums": [
            {
                "title": "Blue Hour Broadcast",
                "release_date": date(2025, 1, 31),
                "price": 9.5,
                "tags": ["late set", "trio", "blue room", "New York"],
                "catalog_no": "NSA-211",
                "featured": True,
                "track_titles": ["Blue Hour Broadcast", "Canal Echo", "Fifth Table", "Smoke Ladder", "After Set Receipt"],
            },
            {
                "title": "Lobby Mirage",
                "release_date": date(2023, 8, 18),
                "price": 8.0,
                "tags": ["modal", "horn blend", "improv", "New York"],
                "catalog_no": "NSA-196",
                "track_titles": ["Lobby Mirage", "Quarter Note Rain", "Overnight Guest", "Stairwell Vibraphone", "Quiet Receipt"],
            },
        ],
        "merch": [
            {
                "title": "Velvet Avenue Night Shift Poster",
                "item_type": "poster",
                "album": "blue-hour-broadcast",
                "price": 19.0,
                "short_blurb": "Matte poster with the Blue Hour Broadcast room diagram.",
                "variants": [("poster", "Standard", "18x24", "", 19.0), ("poster", "Signed", "18x24", "", 27.0)],
            },
            {
                "title": "Velvet Avenue Setlist Tote",
                "item_type": "tote",
                "album": "lobby-mirage",
                "price": 24.0,
                "short_blurb": "Natural cotton tote printed with a handwritten setlist.",
                "variants": [("tote", "Setlist Tote", "Natural", "", 24.0), ("tote", "Setlist Tote", "Black", "", 24.0)],
            },
        ],
    },
    {
        "name": "Salt Meadow",
        "scene": "Melbourne",
        "genre": "folk",
        "label": "Lantern Union",
        "headline": "Field-note songwriting with dusk harmonies and weathered detail.",
        "bio": "Salt Meadow turn notebooks, back-porch harmonies, and road-case acoustics into richly specific folk records.",
        "albums": [
            {
                "title": "Riverlights",
                "release_date": date(2025, 7, 11),
                "price": 8.0,
                "tags": ["story song", "field note", "river road", "Melbourne"],
                "catalog_no": "LU-063",
                "featured": True,
                "track_titles": ["Riverlights", "Fence Post August", "Borrowed Kettle", "Downwind Choir", "Common Thread"],
            },
            {
                "title": "Common Thread",
                "release_date": date(2024, 5, 3),
                "price": 7.5,
                "tags": ["americana", "soft harmonies", "slow weather", "Melbourne"],
                "catalog_no": "LU-051",
                "track_titles": ["Handrail", "Common Thread", "Old Union Hall", "Weather Note", "West Creek"],
            },
        ],
        "merch": [
            {
                "title": "Salt Meadow Field Notes Tote",
                "item_type": "tote",
                "album": "riverlights",
                "price": 22.0,
                "short_blurb": "Natural tote printed with Riverlights notebook fragments.",
                "variants": [("tote", "Field Notes Tote", "Natural", "", 22.0), ("tote", "Field Notes Tote", "Forest", "", 22.0)],
            },
            {
                "title": "Salt Meadow Riverlights Lyric Zine",
                "item_type": "zine",
                "album": "riverlights",
                "price": 14.0,
                "short_blurb": "Staple-bound lyric zine with recording notes and Polaroids.",
                "variants": [("zine", "Issue One", "Stapled", "", 14.0), ("zine", "Signed Issue", "Stapled", "", 18.0)],
            },
        ],
    },
    {
        "name": "Iron Veil",
        "scene": "Paris",
        "genre": "metal",
        "label": "Obsidian Bloom",
        "headline": "Cathedral reverb, iron filings, and ritual pressure.",
        "bio": "Iron Veil stretch doom, black metal atmosphere, and choir samples into heavy records that feel ceremonial rather than theatrical.",
        "albums": [
            {
                "title": "Iron Sleep",
                "release_date": date(2025, 11, 21),
                "price": 9.0,
                "tags": ["doom", "ritual", "cathedral reverb", "Paris"],
                "catalog_no": "OB-119",
                "featured": True,
                "track_titles": ["Bell Ash", "Iron Sleep", "Procession Stair", "Shutter Psalm", "Ember Chapel"],
            },
            {
                "title": "Saint of Noise",
                "release_date": date(2024, 1, 26),
                "price": 8.5,
                "tags": ["blackened", "ash cloud", "blast beat", "Paris"],
                "catalog_no": "OB-101",
                "track_titles": ["Noisework", "Saint of Noise", "Window Soot", "Tower Rain", "Rust Halo"],
            },
        ],
        "merch": [
            {
                "title": "Iron Veil Chapel Longsleeve",
                "item_type": "shirt",
                "album": "iron-sleep",
                "price": 36.0,
                "short_blurb": "Longsleeve with metallic ink front and sleeve glyphs.",
                "variants": [("shirt", "Longsleeve", size, "Black", 36.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "Iron Veil Noise Patch Set",
                "item_type": "patch",
                "album": "saint-of-noise",
                "price": 12.0,
                "short_blurb": "Three embroidered patches with silver overlock.",
                "variants": [("patch", "3-Pack", "Silver Edge", "", 12.0), ("patch", "3-Pack Deluxe", "Glow Edge", "", 16.0)],
            },
        ],
    },
    {
        "name": "Fever Arcade",
        "scene": "London",
        "genre": "pop",
        "label": "Midnight Service",
        "headline": "Neon chorus writing with club bruises and soft-focus hooks.",
        "bio": "Fever Arcade make sharp pop records whose production leaves just enough room for hallway echo and emotional static.",
        "albums": [
            {
                "title": "Elastic Hearts",
                "release_date": date(2025, 12, 5),
                "price": 9.0,
                "tags": ["hook", "night drive", "bright chorus", "London"],
                "catalog_no": "MS-132",
                "featured": True,
                "track_titles": ["Elastic Hearts", "Flicker Map", "Checkout Lights", "Half Fare", "Aftercare FM"],
            },
            {
                "title": "Mirror Mosaic",
                "release_date": date(2024, 9, 13),
                "price": 8.0,
                "tags": ["synth pop", "gloss", "dancefloor", "London"],
                "catalog_no": "MS-107",
                "track_titles": ["Mirror Mosaic", "South Loop", "Cab Floor Glitter", "Rain Delay", "Window Waltz"],
            },
        ],
        "merch": [
            {
                "title": "Fever Arcade Gloss Tee",
                "item_type": "shirt",
                "album": "elastic-hearts",
                "price": 29.0,
                "short_blurb": "Bright print tee with split-tone Elastic Hearts graphic.",
                "variants": [("shirt", "Gloss Tee", size, "White", 29.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "Fever Arcade Mirror Pin Set",
                "item_type": "pin",
                "album": "mirror-mosaic",
                "price": 15.0,
                "short_blurb": "Two hard-enamel pins shaped like mirror fragments.",
                "variants": [("pin", "2-Pin Set", "Chrome", "", 15.0), ("pin", "2-Pin Set", "Rose", "", 15.0)],
            },
        ],
    },
    {
        "name": "Mono Shrine",
        "scene": "Berlin",
        "genre": "experimental",
        "label": "Harbor Circuit",
        "headline": "Tape haze, microtonal hooks, and collage architecture.",
        "bio": "Mono Shrine fold chant fragments, room-tone edits, and damaged synth timbres into experimental pop that still lands emotionally.",
        "albums": [
            {
                "title": "Resin Language",
                "release_date": date(2025, 3, 28),
                "price": 8.5,
                "tags": ["collage", "tape hiss", "microtone", "Berlin"],
                "catalog_no": "HC-014",
                "featured": True,
                "track_titles": ["Resin Language", "Circuit Teeth", "Broken Caption", "Choir Exit", "Warm Static"],
            },
            {
                "title": "Fault Choir",
                "release_date": date(2024, 7, 26),
                "price": 8.0,
                "tags": ["glitch", "avant pop", "noise drift", "Berlin"],
                "catalog_no": "HC-006",
                "track_titles": ["Fault Choir", "Signal Prayer", "Paper Mouth", "Room Dust", "Small Collapse"],
            },
        ],
        "merch": [
            {
                "title": "Mono Shrine Fault Choir Zine",
                "item_type": "zine",
                "album": "fault-choir",
                "price": 13.0,
                "short_blurb": "Eight-page foldout zine of lyric fragments and cassette labels.",
                "variants": [("zine", "Issue One", "Stapled", "", 13.0), ("zine", "Bundle", "With Sticker Sheet", "", 17.0)],
            },
            {
                "title": "Mono Shrine Resin Poster",
                "item_type": "poster",
                "album": "resin-language",
                "price": 17.0,
                "short_blurb": "A2 poster using the album's resin-grid art.",
                "variants": [("poster", "Standard", "A2", "", 17.0), ("poster", "Signed", "A2", "", 23.0)],
            },
        ],
    },
    {
        "name": "Tide Static",
        "scene": "Los Angeles",
        "genre": "rock",
        "label": "Sun Trace",
        "headline": "Motorik travel songs and blown-speaker optimism.",
        "bio": "Tide Static write road-length rock songs that feel as interested in momentum and tone color as they are in choruses.",
        "albums": [
            {
                "title": "Harbor Burn",
                "release_date": date(2025, 6, 27),
                "price": 8.0,
                "tags": ["psych rock", "motorik", "widescreen", "Los Angeles"],
                "catalog_no": "ST-064",
                "featured": True,
                "track_titles": ["Harbor Burn", "Median Gold", "Glass Toll", "Breaker Motel", "Wide Exit"],
            },
            {
                "title": "Quiet Engine",
                "release_date": date(2024, 4, 5),
                "price": 7.5,
                "tags": ["garage", "riff driven", "festival ready", "Los Angeles"],
                "catalog_no": "ST-051",
                "track_titles": ["Quiet Engine", "Chrome Valley", "Heat Map", "August Freight", "Left Signal"],
            },
        ],
        "merch": [
            {
                "title": "Tide Static Burn Tee",
                "item_type": "shirt",
                "album": "harbor-burn",
                "price": 30.0,
                "short_blurb": "Vintage white tee with a cracked orange harbor-burn print.",
                "variants": [("shirt", "Burn Tee", size, "Vintage White", 30.0) for size in ["S", "M", "L", "XL"]],
            },
            {
                "title": "Tide Static Quiet Engine Tote",
                "item_type": "tote",
                "album": "quiet-engine",
                "price": 21.0,
                "short_blurb": "Canvas tote featuring the Quiet Engine highway diagram.",
                "variants": [("tote", "Engine Tote", "Natural", "", 21.0), ("tote", "Engine Tote", "Black", "", 21.0)],
            },
        ],
    },
]

EXTRA_ARTISTS = [
    "Amber Relay",
    "Paper Current",
    "Silver Weather",
    "North Routine",
    "Copper Bloom",
    "Ladder Choir",
    "Hour Motel",
    "Signal Lake",
    "Delta Hall",
    "Mirror Union",
    "Quiet Metric",
    "Blue Archive",
    "Stair Pattern",
    "Velvet Current",
    "Harbor Study",
    "Street Lantern",
    "Noon Frame",
    "Low Atlas",
    "Chrome Willow",
    "Radio Meadow",
    "Fault Parade",
    "Static Ledger",
    "Stone Balcony",
    "West Transit",
    "Echo Dividend",
    "Cloud Bureau",
    "Ridge Cinema",
    "Hollow Method",
]

ALBUM_WORDS_A = [
    "Static",
    "Harbor",
    "River",
    "Signal",
    "Blue",
    "Late",
    "Golden",
    "Quiet",
    "Paper",
    "Chrome",
    "South",
    "Midnight",
    "Glass",
    "Motel",
    "Stone",
    "Delta",
    "Velvet",
    "Open",
    "After",
    "Broken",
]

ALBUM_WORDS_B = [
    "Weather",
    "Ledger",
    "Cinema",
    "Method",
    "Current",
    "Boulevard",
    "Garden",
    "Transit",
    "Archive",
    "Pattern",
    "Dusk",
    "Vector",
    "Thread",
    "Parade",
    "Engine",
    "Signal",
    "Mosaic",
    "Harbor",
    "Circuit",
    "Minutes",
]

TRACK_WORDS_A = [
    "Window",
    "Breaker",
    "Hallway",
    "Transfer",
    "Rain",
    "Invoice",
    "Current",
    "Median",
    "Receipt",
    "Basin",
    "Anchor",
    "Static",
    "Platform",
    "August",
    "Pattern",
]

TRACK_WORDS_B = [
    "Light",
    "Note",
    "Line",
    "Receipt",
    "Dust",
    "Dialtone",
    "Index",
    "Signal",
    "Weather",
    "Map",
    "Ledger",
    "Glow",
    "Transit",
    "Machine",
    "Murmur",
]


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in value).split("-") if part)


def choose_palette(key: str) -> tuple[str, str, str, str]:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return PALETTES[int(digest[:2], 16) % len(PALETTES)]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_unique_slug(base_slug: str, used: set[str], suffix: str = "") -> str:
    candidate = base_slug
    if candidate not in used:
        used.add(candidate)
        return candidate
    if suffix:
        candidate = f"{base_slug}-{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
    counter = 2
    while f"{candidate}-{counter}" in used:
        counter += 1
    final_slug = f"{candidate}-{counter}"
    used.add(final_slug)
    return final_slug


def cover_svg(title: str, artist: str, key: str) -> str:
    p1, p2, p3, p4 = choose_palette(key)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    shift = int(digest[4:8], 16) % 240
    circle_x = 250 + int(digest[8:10], 16) * 4
    circle_y = 280 + int(digest[10:12], 16) * 4
    rect_rotate = int(digest[12:14], 16) % 42 - 21
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1600" role="img" aria-label="{html.escape(title)} by {html.escape(artist)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{p1}"/>
      <stop offset="55%" stop-color="{p2}"/>
      <stop offset="100%" stop-color="{p4}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="40%" r="60%">
      <stop offset="0%" stop-color="{p3}" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="{p3}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grain" width="120" height="120" patternUnits="userSpaceOnUse">
      <path d="M0 90 L120 40" stroke="{p3}" stroke-opacity="0.12" stroke-width="2"/>
      <path d="M0 30 L120 10" stroke="{p3}" stroke-opacity="0.08" stroke-width="2"/>
      <circle cx="18" cy="18" r="4" fill="{p3}" fill-opacity="0.08"/>
      <circle cx="80" cy="70" r="6" fill="{p3}" fill-opacity="0.08"/>
    </pattern>
  </defs>
  <rect width="1600" height="1600" fill="url(#bg)"/>
  <rect width="1600" height="1600" fill="url(#grain)"/>
  <circle cx="{circle_x}" cy="{circle_y}" r="420" fill="url(#glow)"/>
  <rect x="{160 + shift}" y="150" width="980" height="260" rx="32" fill="{p3}" fill-opacity="0.08" transform="rotate({rect_rotate} 720 280)"/>
  <rect x="900" y="600" width="500" height="720" rx="36" fill="{p4}" fill-opacity="0.3"/>
  <path d="M180 1040 C460 760, 690 1240, 1100 860 L1420 580" fill="none" stroke="{p3}" stroke-width="24" stroke-opacity="0.55"/>
  <path d="M130 1180 C420 900, 720 1380, 1220 980" fill="none" stroke="{p3}" stroke-width="12" stroke-opacity="0.45"/>
  <circle cx="1190" cy="430" r="150" fill="{p3}" fill-opacity="0.12"/>
  <rect x="200" y="1180" width="620" height="170" rx="26" fill="{p4}" fill-opacity="0.7"/>
  <text x="240" y="1288" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="116" font-weight="700" letter-spacing="2">{html.escape(title.upper())}</text>
  <text x="246" y="1374" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="40" letter-spacing="6">{html.escape(artist.upper())}</text>
  <text x="1220" y="1320" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="28" text-anchor="end">WH LOCAL MIRROR</text>
</svg>"""


def banner_svg(name: str, location: str, key: str) -> str:
    p1, p2, p3, p4 = choose_palette(f"banner-{key}")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2400 900" role="img" aria-label="{html.escape(name)} banner">
  <defs>
    <linearGradient id="banner" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{p4}"/>
      <stop offset="40%" stop-color="{p1}"/>
      <stop offset="100%" stop-color="{p2}"/>
    </linearGradient>
  </defs>
  <rect width="2400" height="900" fill="url(#banner)"/>
  <circle cx="360" cy="180" r="210" fill="{p3}" fill-opacity="0.16"/>
  <circle cx="1780" cy="620" r="260" fill="{p3}" fill-opacity="0.12"/>
  <path d="M0 720 C380 500, 760 860, 1180 610 S2000 420 2400 690" fill="none" stroke="{p3}" stroke-opacity="0.35" stroke-width="18"/>
  <path d="M120 160 H2280" stroke="{p3}" stroke-opacity="0.18" stroke-width="6"/>
  <path d="M120 760 H2280" stroke="{p3}" stroke-opacity="0.18" stroke-width="6"/>
  <text x="160" y="660" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="190" font-weight="700" letter-spacing="4">{html.escape(name.upper())}</text>
  <text x="170" y="740" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="42" letter-spacing="10">{html.escape(location.upper())}</text>
</svg>"""


def avatar_svg(name: str, key: str) -> str:
    p1, p2, p3, p4 = choose_palette(f"avatar-{key}")
    initials = "".join(part[0] for part in name.split()[:2]).upper()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" role="img" aria-label="{html.escape(name)} avatar">
  <rect width="800" height="800" rx="120" fill="{p4}"/>
  <circle cx="400" cy="310" r="190" fill="{p1}"/>
  <path d="M160 690 C210 530, 320 470, 400 470 C480 470, 590 530, 640 690 Z" fill="{p2}"/>
  <circle cx="400" cy="300" r="100" fill="{p3}" fill-opacity="0.92"/>
  <text x="400" y="720" text-anchor="middle" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="160" font-weight="700">{html.escape(initials)}</text>
</svg>"""


def merch_svg(item_type: str, title: str, artist: str, key: str) -> str:
    p1, p2, p3, p4 = choose_palette(f"merch-{key}")
    frame = {
        "shirt": '<path d="M285 280 L405 180 L535 180 L655 280 L730 250 L790 390 L706 430 L706 1030 L234 1030 L234 430 L150 390 L210 250 Z" fill="{fill}" stroke="{stroke}" stroke-width="22"/>',
        "hoodie": '<path d="M275 300 L370 180 L570 180 L665 300 L745 280 L800 430 L725 470 L690 1030 L250 1030 L215 470 L140 430 L195 280 Z" fill="{fill}" stroke="{stroke}" stroke-width="22"/>',
        "poster": '<rect x="220" y="150" width="560" height="920" rx="20" fill="{fill}" stroke="{stroke}" stroke-width="22"/>',
        "tote": '<path d="M260 300 H740 V1030 H260 Z" fill="{fill}" stroke="{stroke}" stroke-width="22"/><path d="M350 300 C350 220, 420 165, 500 165 C580 165, 650 220, 650 300" fill="none" stroke="{stroke}" stroke-width="24"/>',
        "slipmat": '<circle cx="500" cy="550" r="310" fill="{fill}" stroke="{stroke}" stroke-width="22"/><circle cx="500" cy="550" r="70" fill="{stroke}" fill-opacity="0.55"/>',
        "patch": '<rect x="230" y="230" width="540" height="640" rx="80" fill="{fill}" stroke="{stroke}" stroke-width="22"/>',
        "zine": '<rect x="260" y="180" width="480" height="760" rx="24" fill="{fill}" stroke="{stroke}" stroke-width="22"/><line x1="500" y1="180" x2="500" y2="940" stroke="{stroke}" stroke-width="10"/>',
        "cap": '<path d="M205 540 C250 350, 420 240, 570 240 C700 240, 790 330, 795 480 L820 560 L200 560 Z" fill="{fill}" stroke="{stroke}" stroke-width="22"/><path d="M180 560 C310 610, 690 610, 820 560" fill="{fill}" stroke="{stroke}" stroke-width="22"/>',
        "pin": '<circle cx="500" cy="520" r="230" fill="{fill}" stroke="{stroke}" stroke-width="22"/>',
        "cassette": '<rect x="210" y="300" width="580" height="460" rx="26" fill="{fill}" stroke="{stroke}" stroke-width="22"/><circle cx="360" cy="530" r="78" fill="{stroke}" fill-opacity="0.3"/><circle cx="640" cy="530" r="78" fill="{stroke}" fill-opacity="0.3"/>',
    }.get(item_type, '<rect x="220" y="200" width="560" height="760" rx="34" fill="{fill}" stroke="{stroke}" stroke-width="22"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200" role="img" aria-label="{html.escape(title)} merch image">
  <rect width="1000" height="1200" fill="{p4}"/>
  <circle cx="180" cy="180" r="130" fill="{p1}" fill-opacity="0.18"/>
  <circle cx="820" cy="1000" r="150" fill="{p2}" fill-opacity="0.15"/>
  {frame.format(fill=p3, stroke=p1)}
  <rect x="300" y="420" width="400" height="240" rx="26" fill="{p1}" fill-opacity="0.92"/>
  <text x="500" y="505" text-anchor="middle" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="54" font-weight="700">{html.escape(title.upper()[:18])}</text>
  <text x="500" y="575" text-anchor="middle" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="28" letter-spacing="4">{html.escape(artist.upper()[:22])}</text>
  <text x="500" y="1110" text-anchor="middle" fill="{p3}" font-family="Arial, Helvetica, sans-serif" font-size="28">WEBHARBOR LOCAL MERCH</text>
</svg>"""


def ensure_asset_scaffold(base_dir: str) -> None:
    images = Path(base_dir) / "static" / "images"
    for folder in ["covers", "banners", "artists", "merch"]:
        (images / folder).mkdir(parents=True, exist_ok=True)


def build_generated_artists() -> list[dict]:
    generated = []
    for idx, name in enumerate(EXTRA_ARTISTS):
        genre_name = GENRES[idx % len(GENRES)][0]
        scene_name = SCENES[idx % len(SCENES)][0]
        label_name = LABELS[idx % len(LABELS)][0]
        first_title = f"{ALBUM_WORDS_A[idx % len(ALBUM_WORDS_A)]} {ALBUM_WORDS_B[idx % len(ALBUM_WORDS_B)]}"
        second_title = f"{ALBUM_WORDS_A[(idx + 7) % len(ALBUM_WORDS_A)]} {ALBUM_WORDS_B[(idx + 11) % len(ALBUM_WORDS_B)]}"
        generated.append(
            {
                "name": name,
                "scene": scene_name,
                "genre": genre_name,
                "label": label_name,
                "headline": f"{genre_name.title()} releases tuned to {scene_name} after-dark energy.",
                "bio": f"{name} operate inside the {scene_name} scene, shaping {genre_name} records that favor texture, place, and carefully staged physical editions.",
                "albums": [
                    {
                        "title": first_title,
                        "release_date": date(2023 + (idx % 4), (idx % 11) + 1, ((idx * 3) % 24) + 1),
                        "price": 7.0 + (idx % 5) * 0.5,
                        "tags": GENRE_TAGS[genre_name][:3] + [scene_name],
                        "catalog_no": f"HC-{200 + idx:03d}",
                        "featured": idx < 4,
                    },
                    {
                        "title": second_title,
                        "release_date": date(2024 + (idx % 3), ((idx + 4) % 11) + 1, ((idx * 5) % 24) + 1),
                        "price": 7.5 + (idx % 4) * 0.5,
                        "tags": GENRE_TAGS[genre_name][2:5] + [scene_name],
                        "catalog_no": f"HC-{240 + idx:03d}",
                    },
                ],
            }
        )
    return generated


def generated_track_titles(album_title: str, offset: int) -> list[str]:
    titles = []
    base = slugify(album_title)
    seed = int(hashlib.sha256(base.encode("utf-8")).hexdigest()[:6], 16)
    for idx in range(5):
        first = TRACK_WORDS_A[(seed + offset + idx) % len(TRACK_WORDS_A)]
        second = TRACK_WORDS_B[(seed + offset * 2 + idx) % len(TRACK_WORDS_B)]
        titles.append(f"{first} {second}")
    return titles


def album_description(artist_name: str, title: str, genre_name: str, scene_name: str, tags: list[str]) -> tuple[str, str]:
    desc = (
        f"{title} by {artist_name} folds {genre_name} textures from {scene_name} into a detailed release built around "
        f"{', '.join(tags[:3])}, tactile arrangements, and patient pacing."
    )
    story = (
        f"Recorded for the WebHarbor Bandcamp mirror as a fully local release package, {title} leans on {tags[0]} "
        f"energy while keeping the visual and written presentation tight enough for benchmark tasks."
    )
    return desc, story


def merch_description(title: str, album_title: str | None, artist_name: str, item_type: str) -> str:
    if album_title:
        return f"{title} is a {item_type} release tied to {album_title}, printed locally for {artist_name} with clean benchmark-ready variant information."
    return f"{title} is a {item_type} item from {artist_name}, created for the local mirror with deterministic colors and edition notes."


def create_assets_for_artist(base_dir: str, artist_slug: str, artist_name: str, scene_name: str, albums: list[dict], merch_items: list[dict]) -> None:
    image_root = Path(base_dir) / "static" / "images"
    write_text(image_root / "artists" / f"{artist_slug}-avatar.svg", avatar_svg(artist_name, artist_slug))
    write_text(image_root / "artists" / f"{artist_slug}-hero.svg", banner_svg(artist_name, scene_name, artist_slug))
    for album in albums:
        write_text(
            image_root / "covers" / f"{album['slug']}.svg",
            cover_svg(album["title"], artist_name, album["slug"]),
        )
        write_text(
            image_root / "banners" / f"{album['slug']}.svg",
            banner_svg(album["title"], artist_name, album["slug"]),
        )
    for merch in merch_items:
        write_text(
            image_root / "merch" / f"{merch['slug']}.svg",
            merch_svg(merch["item_type"], merch["title"], artist_name, merch["slug"]),
        )


def run_seed(db, base_dir: str, mirror_reference_now, models: dict) -> None:
    Genre = models["Genre"]
    Scene = models["Scene"]
    Label = models["Label"]
    Artist = models["Artist"]
    Album = models["Album"]
    Track = models["Track"]
    Tag = models["Tag"]
    MerchItem = models["MerchItem"]
    FormatVariant = models["FormatVariant"]

    ensure_asset_scaffold(base_dir)
    used_album_slugs: set[str] = set()
    used_track_slugs: set[str] = set()
    used_merch_slugs: set[str] = set()

    scene_records = {}
    for name, country, description in SCENES:
        record = Scene(name=f"{name}, {country}", slug=slugify(f"{name}-{country}"), country=country, description=description)
        db.session.add(record)
        db.session.flush()
        scene_records[name] = record

    genre_records = {}
    for name, description, accent in GENRES:
        record = Genre(name=name, slug=slugify(name), description=description, accent_color=accent)
        db.session.add(record)
        db.session.flush()
        genre_records[name] = record

    label_records = {}
    for name, location, description in LABELS:
        record = Label(name=name, slug=slugify(name), location=location, description=description)
        db.session.add(record)
        db.session.flush()
        label_records[name] = record

    tag_records = {}

    def tag_for(name: str):
        slug = slugify(name)
        if slug in tag_records:
            return tag_records[slug]
        record = Tag(name=name, slug=slug)
        db.session.add(record)
        db.session.flush()
        tag_records[slug] = record
        return record

    all_artist_specs = CURATED_ARTISTS + build_generated_artists()

    for artist_index, artist_spec in enumerate(all_artist_specs):
        artist_slug = slugify(artist_spec["name"])
        scene = scene_records[artist_spec["scene"]]
        genre = genre_records[artist_spec["genre"]]
        label = label_records[artist_spec["label"]]
        artist = Artist(
            name=artist_spec["name"],
            slug=artist_slug,
            location=scene.name,
            bio=artist_spec["bio"],
            headline=artist_spec["headline"],
            formed_year=2015 + (artist_index % 9),
            follow_count=1200 + artist_index * 143,
            avatar_image=f"images/artists/{artist_slug}-avatar.svg",
            hero_image=f"images/artists/{artist_slug}-hero.svg",
            scene_id=scene.id,
            label_id=label.id,
            primary_genre_id=genre.id,
        )
        db.session.add(artist)
        db.session.flush()

        local_album_specs = []
        for album_index, album_spec in enumerate(artist_spec["albums"]):
            album_slug = make_unique_slug(slugify(album_spec["title"]), used_album_slugs, artist_slug)
            tags = album_spec.get("tags") or GENRE_TAGS[artist_spec["genre"]][:3] + [artist_spec["scene"]]
            description, story = album_description(
                artist_spec["name"], album_spec["title"], artist_spec["genre"], artist_spec["scene"], tags
            )
            album = Album(
                artist_id=artist.id,
                label_id=label.id,
                primary_genre_id=genre.id,
                scene_id=scene.id,
                title=album_spec["title"],
                slug=album_slug,
                description=description,
                story=story,
                cover_image=f"images/covers/{album_slug}.svg",
                header_image=f"images/banners/{album_slug}.svg",
                price=album_spec["price"],
                release_date=album_spec["release_date"],
                fan_count=140 + artist_index * 18 + album_index * 37,
                catalog_no=album_spec.get("catalog_no", f"WH-{artist_index:02d}{album_index:02d}"),
                is_featured=bool(album_spec.get("featured", False)),
                is_new=album_spec["release_date"] >= date(2025, 1, 1),
                is_editorial=bool(album_spec.get("editorial", False)),
            )
            db.session.add(album)
            db.session.flush()

            for tag_name in tags:
                album.tags.append(tag_for(tag_name))

            track_titles = album_spec.get("track_titles") or generated_track_titles(album_spec["title"], artist_index + album_index)
            total_duration = 0
            for track_number, track_title in enumerate(track_titles, start=1):
                duration = 155 + ((artist_index * 13 + album_index * 21 + track_number * 29) % 170)
                total_duration += duration
                track_slug = make_unique_slug(slugify(f"{album_slug}-{track_title}"), used_track_slugs)
                db.session.add(
                    Track(
                        album_id=album.id,
                        title=track_title,
                        slug=track_slug,
                        track_number=track_number,
                        duration_seconds=duration,
                        preview_hook=f"{track_title} is the preview focus from {album.title}.",
                        lyrics_excerpt=f"{track_title} traces the emotional contour of {album.title.lower()} in one sharp phrase.",
                        is_focus_track=track_number == 3,
                    )
                )

            album.track_count = len(track_titles)
            album.duration_seconds = total_duration

            album_variants = [
                ("digital", "Digital Album", "MP3 + FLAC", "", album.price, 9999, True, "Instant download", "Unlimited streams in the mirror."),
            ]
            if artist_spec["genre"] in {"ambient", "electronic", "techno", "metal", "folk", "jazz", "alternative", "rock", "pop"}:
                album_variants.append(("vinyl", "Colored Vinyl", "12-inch", "Ocean Blue", round(album.price + 15.5, 2), 42 + artist_index % 35, False, "Ships in 3-5 days", "Limited mirror pressing."))
            if artist_spec["genre"] in {"ambient", "electronic", "hip-hop/rap", "punk", "experimental", "folk"}:
                album_variants.append(("cassette", "Cassette", "Transparent Shell", "", round(album.price + 6.5, 2), 28 + artist_index % 21, False, "Ships in 2-4 days", "Numbered shell edition."))
            if artist_spec["genre"] in {"pop", "rock", "alternative", "jazz", "metal"}:
                album_variants.append(("cd", "Compact Disc", "Gatefold", "", round(album.price + 8.0, 2), 34 + artist_index % 17, False, "Ships in 2-4 days", "Includes lyric foldout."))

            for variant_index, (kind, name, option_a, option_b, price, inventory, is_default, shipping_note, edition_note) in enumerate(album_variants, start=1):
                db.session.add(
                    FormatVariant(
                        album_id=album.id,
                        kind=kind,
                        name=name,
                        option_a=option_a,
                        option_b=option_b,
                        price=price,
                        inventory=inventory,
                        sku=f"{album_slug}-{kind}-{variant_index}",
                        shipping_note=shipping_note,
                        edition_note=edition_note,
                        is_default=is_default,
                    )
                )

            local_album_specs.append({"title": album.title, "slug": album.slug})

        merch_specs = artist_spec.get("merch", [])
        if not merch_specs:
            first_album_slug = slugify(artist_spec["albums"][0]["title"])
            second_album_slug = slugify(artist_spec["albums"][1]["title"])
            merch_specs = [
                {
                    "title": f"{artist_spec['name']} Tour Tee",
                    "item_type": "shirt",
                    "album": first_album_slug,
                    "price": 29.0 + (artist_index % 4),
                    "short_blurb": "Standard artist tee with benchmark-ready sizing.",
                    "variants": [("shirt", "Tour Tee", size, "Black", 29.0 + (artist_index % 4)) for size in ["S", "M", "L", "XL"]],
                },
                {
                    "title": f"{artist_spec['name']} Carry Tote",
                    "item_type": "tote",
                    "album": second_album_slug,
                    "price": 21.0 + (artist_index % 3),
                    "short_blurb": "Canvas tote with scene-specific line work.",
                    "variants": [("tote", "Carry Tote", "Natural", "", 21.0 + (artist_index % 3)), ("tote", "Carry Tote", "Black", "", 21.0 + (artist_index % 3))],
                },
            ]

        local_merch_specs = []
        for merch_index, merch_spec in enumerate(merch_specs):
            merch_slug = make_unique_slug(slugify(merch_spec["title"]), used_merch_slugs, artist_slug)
            album_link = next((alb for alb in artist.albums if alb.slug == merch_spec.get("album")), None)
            merch = MerchItem(
                artist_id=artist.id,
                album_id=album_link.id if album_link else None,
                title=merch_spec["title"],
                slug=merch_slug,
                item_type=merch_spec["item_type"],
                description=merch_description(merch_spec["title"], album_link.title if album_link else None, artist.name, merch_spec["item_type"]),
                short_blurb=merch_spec["short_blurb"],
                image=f"images/merch/{merch_slug}.svg",
                price=merch_spec["price"],
                inventory=55 + artist_index * 2 + merch_index * 6,
                release_date=max(album.release_date for album in artist.albums) - timedelta(days=14 - merch_index * 5),
                is_featured=artist_index < 10 or merch_index == 0,
            )
            db.session.add(merch)
            db.session.flush()

            for variant_index, variant_spec in enumerate(merch_spec["variants"], start=1):
                kind, name, option_a, option_b, price = variant_spec
                db.session.add(
                    FormatVariant(
                        merch_item_id=merch.id,
                        kind=kind,
                        name=name,
                        option_a=option_a,
                        option_b=option_b,
                        price=price,
                        inventory=18 + ((artist_index + merch_index + variant_index) % 24),
                        sku=f"{merch_slug}-{kind}-{variant_index}",
                        shipping_note="Ships in 2-5 days",
                        edition_note="Locally generated merch photo and deterministic variant data.",
                        is_default=variant_index == 1,
                    )
                )
            local_merch_specs.append({"title": merch.title, "slug": merch.slug, "item_type": merch.item_type})

        create_assets_for_artist(base_dir, artist_slug, artist.name, artist.location, local_album_specs, local_merch_specs)

    db.session.commit()
