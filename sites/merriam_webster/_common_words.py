"""Common everyday vocabulary added to the Merriam-Webster mirror catalog.

The original WORDS list (142 entries) is skewed toward advanced/literary
vocabulary, so any off-script lookup of an everyday word dead-ended. These
common words give the dictionary real coverage and provide real distractors.
Data (part of speech, definition, first-known-use, etymology) follows
Merriam-Webster's published entries; pronunciation uses MW-style respelling.
Seed combines these with WORDS via seed_data.ALL_WORDS.
"""

COMMON_WORDS = [
    {
        "headword": "water",
        "slug": "water",
        "pos": "noun",
        "pronunciation": "ˈwȯ-tər",
        "syllables": "wa-ter",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English wæter; akin to Old High German wazzar water, Greek hydōr water, Latin unda wave",
        "definitions": [
            {"sense_num": 1, "text": "the liquid that descends from the clouds as rain and forms streams, lakes, and seas", "examples": ["a glass of cold water", "the water in the lake was clear"]},
            {"sense_num": 2, "text": "a body of water (as a sea, lake, or river)", "examples": ["the ship was still in open water"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "dog",
        "slug": "dog",
        "pos": "noun",
        "pronunciation": "ˈdȯg",
        "syllables": "dog",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English docga; akin to Old English docga a powerful dog",
        "definitions": [
            {"sense_num": 1, "text": "a highly variable domestic mammal (Canis familiaris) closely related to the gray wolf", "examples": ["the family dog", "a stray dog followed us home"]},
            {"sense_num": 2, "text": "a worthless or contemptible person", "examples": ["you lucky dog"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "run",
        "slug": "run",
        "pos": "verb",
        "pronunciation": "ˈrən",
        "syllables": "run",
        "first_known_use": "before 12th century",
        "etymology": "Middle English ronnen, alteration of Old English irnan, eornan; akin to Old High German rinnan to run, Greek orcheus",
        "definitions": [
            {"sense_num": 1, "text": "to go faster than a walk; to move at a pace faster than walking", "examples": ["run to the store", "she had to run to catch the bus"]},
            {"sense_num": 2, "text": "to flow steadily", "examples": ["the river runs to the sea"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "baby",
        "slug": "baby",
        "pos": "noun",
        "pronunciation": "ˈbā-bē",
        "syllables": "ba-by",
        "first_known_use": "14th century",
        "etymology": "Middle English, from baby baby; diminutive of babe",
        "definitions": [
            {"sense_num": 1, "text": "an extremely young child; especially one not yet able to walk or talk", "examples": ["a baby crying in the next room", "rock the baby to sleep"]},
            {"sense_num": 2, "text": "the youngest member of a group", "examples": ["the baby of the family"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "cry",
        "slug": "cry",
        "pos": "verb",
        "pronunciation": "ˈkrī",
        "syllables": "cry",
        "first_known_use": "13th century",
        "etymology": "Middle English crien, from Anglo-French crier, from Latin quiritare to cry out",
        "definitions": [
            {"sense_num": 1, "text": "to call loudly; to weep or shed tears", "examples": ["cry for help", "the baby began to cry"]},
            {"sense_num": 2, "text": "to require or call for urgently", "examples": ["the matter cries for attention"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "book",
        "slug": "book",
        "pos": "noun",
        "pronunciation": "ˈbu̇k",
        "syllables": "book",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English bōc; akin to Old High German buoh book, Gothic boka letter",
        "definitions": [
            {"sense_num": 1, "text": "a set of printed sheets of paper bound together along one edge", "examples": ["read a good book", "a book of poems"]},
            {"sense_num": 2, "text": "a set of rules or records", "examples": ["he threw the book at them"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "tree",
        "slug": "tree",
        "pos": "noun",
        "pronunciation": "ˈtrē",
        "syllables": "tree",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English trēow; akin to Old High German triu tree, Greek drys oak",
        "definitions": [
            {"sense_num": 1, "text": "a woody perennial plant having a single usually elongate main stem generally standing erect", "examples": ["climb a tree", "an old oak tree"]},
            {"sense_num": 2, "text": "something branching out from a stem", "examples": ["a family tree"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "house",
        "slug": "house",
        "pos": "noun",
        "pronunciation": "ˈhau̇s",
        "syllables": "house",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English hūs; akin to Old High German hūs house",
        "definitions": [
            {"sense_num": 1, "text": "a building that serves as living quarters for one or a few families", "examples": ["buy a new house", "a house on the hill"]},
            {"sense_num": 2, "text": "a household", "examples": ["the whole house was asleep"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "food",
        "slug": "food",
        "pos": "noun",
        "pronunciation": "ˈfüd",
        "syllables": "food",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English fōda; akin to Old High German fuotar food, Latin panis bread",
        "definitions": [
            {"sense_num": 1, "text": "material consisting essentially of protein, carbohydrate, and fat used in the body of an organism to sustain growth, repair, and vital processes", "examples": ["good food", "a steady supply of food"]},
            {"sense_num": 2, "text": "nutriment in solid form", "examples": ["gave the dog its food"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "money",
        "slug": "money",
        "pos": "noun",
        "pronunciation": "ˈmə-nē",
        "syllables": "mon-ey",
        "first_known_use": "14th century",
        "etymology": "Middle English, from Anglo-French moneie, from Latin moneta mint, money, from Moneta, epithet of Juno",
        "definitions": [
            {"sense_num": 1, "text": "something generally accepted as a medium of exchange, a measure of value, or a means of payment", "examples": ["save up money", "spend money wisely"]},
            {"sense_num": 2, "text": "wealth reckoned in terms of money", "examples": ["made money on the deal"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "school",
        "slug": "school",
        "pos": "noun",
        "pronunciation": "ˈskül",
        "syllables": "school",
        "first_known_use": "before 12th century",
        "etymology": "Middle English scole, from Old English scōl; from Latin schola, from Greek scholē leisure, discussion, lecture",
        "definitions": [
            {"sense_num": 1, "text": "an organization that provides instruction; an institution for the teaching of children", "examples": ["go to school", "a new school was built"]},
            {"sense_num": 2, "text": "a group of persons who hold a common doctrine or follow the same teacher", "examples": ["the Stoic school"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "friend",
        "slug": "friend",
        "pos": "noun",
        "pronunciation": "ˈfrend",
        "syllables": "friend",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English frēond; akin to Old High German friunt friend, Old English frēon to love",
        "definitions": [
            {"sense_num": 1, "text": "a person you know well and like who is not a member of your family", "examples": ["a close friend", "meet a friend for coffee"]},
            {"sense_num": 2, "text": "one that favors or promotes something", "examples": ["a friend of the arts"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "smile",
        "slug": "smile",
        "pos": "verb",
        "pronunciation": "ˈsmī(-ə)l",
        "syllables": "smile",
        "first_known_use": "14th century",
        "etymology": "Middle English, from Old English smerian; akin to Old English smearwian to smear",
        "definitions": [
            {"sense_num": 1, "text": "to have or show a pleased expression on the face", "examples": ["smile at the camera", "she began to smile"]},
            {"sense_num": 2, "text": "to express by a smile", "examples": ["smiled her thanks"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
    {
        "headword": "light",
        "slug": "light",
        "pos": "noun",
        "pronunciation": "ˈlīt",
        "syllables": "light",
        "first_known_use": "before 12th century",
        "etymology": "Middle English, from Old English lēoht; akin to Old High German lioht light, Latin luc-, lux light, Greek leukos white",
        "definitions": [
            {"sense_num": 1, "text": "something that makes vision possible; electromagnetic radiation of any wavelength that travels in a vacuum", "examples": ["a beam of light", "turn on the light"]},
            {"sense_num": 2, "text": "a source of light (as a lamp or the sun)", "examples": ["stand in the light"]}
        ],
        "synonyms": [],
        "difficulty": "common",
    },
]
