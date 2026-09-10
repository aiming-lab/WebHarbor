"""Deterministic seed for the WebMD Doctor mirror.

Run directly (`PYTHONHASHSEED=0 python seed_data.py`) to rebuild
`instance_seed/webmd_doctor.db` (this is what the Docker build does).
`PYTHONHASHSEED=0 python seed_data.py --write-images` additionally regenerates
`static/images/avatars/*.png` and `static/images/posters/*.png`; those PNGs
ship through the pinned Hugging Face asset tarball, never from the image
build. Byte-reproducible: one seeded RNG, no wall-clock reads, sorted
iteration only, hard-coded password hashes, PNGs without ancillary chunks.

Every doctor, practice, hospital, address, phone, NPI, school and review is
synthetic. Real city / state / specialty / insurer names are reused only as
vocabulary.
"""
from __future__ import annotations

import importlib.util
import os
import random
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

from app import (  # noqa: E402
    AppointmentRequest,
    Award,
    Certification,
    City,
    CityZip,
    Condition,
    Doctor,
    DoctorCondition,
    DoctorExpertise,
    DoctorInsurance,
    DoctorLanguage,
    DoctorPerspective,
    DoctorProcedure,
    Education,
    ExpertiseArea,
    Hospital,
    InsurancePlan,
    Insurer,
    License,
    Location,
    PERSPECTIVE_CRITERIA,
    Practice,
    Procedure,
    Review,
    SEED_VERSION,
    SavedProvider,
    SeedMetadata,
    Specialty,
    User,
    UserReview,
    app,
    confirmation_reference,
    db,
)

SEED = 20260910
RNG = random.Random(SEED)
MIRROR_REFERENCE_DATE = date(2026, 9, 10)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "webmd_doctor.db"
INSTANCE_SEED_DIR = BASE_DIR / "instance_seed"
AVATAR_DIR = BASE_DIR / "static" / "images" / "avatars"
POSTER_DIR = BASE_DIR / "static" / "images" / "posters"

# Hard-coded werkzeug scrypt hashes of "TestPass123!" (generate_password_hash
# salts randomly, so recomputing them would break byte-identical rebuilds).
DEMO_PASSWORD_HASHES = {
    "alice.j@test.com": "scrypt:32768:8:1$x9JMG7iKsrRO1AGh$e8e195799326a6e1ff55d4d20dd2735d9d68c0ed4879bd6b263ac33fa9953b0f6c8505680f1a1d8a9fbe9b0d01ef5e88f99b77b89fc30299fda217185a3b7acf",
    "bob.c@test.com": "scrypt:32768:8:1$O14LIVdpqb3Q6D7E$4b9389cd00aad4417058fd629af5bf979b3f05bdf011791fbc65b7080fe898e50c7aedc2c22be92c71ae25a1df6922bb4ca44b386a7f17040b36888c0cdc8942",
    "carol.d@test.com": "scrypt:32768:8:1$9PGtFS6I89BOEugS$890b1c1935bb6c0c4a6f7f5ad689cc02415e4bd03b02e101f0c2095931d4f157a8504c0fa4f12c3073c94e1480fea3305ffbadc5e8540c5eaf1c16965cb47be7",
    "david.k@test.com": "scrypt:32768:8:1$luqs3gbiT1hPpw2c$09f31fef9514ae90d234cdd91a7f2c95d937e08a37fed60ce0b41755a097609040f7aa5083b94ecdd41804262dc778bd6f8d8e9f38f47f319fa8d6f3ed705d1b",
}
BENCHMARK_USERS = [
    ("alice.j@test.com", "Alice Johnson", date(1988, 4, 12)),
    ("bob.c@test.com", "Bob Chen", date(1979, 11, 3)),
    ("carol.d@test.com", "Carol Davis", date(1993, 7, 21)),
    ("david.k@test.com", "David Kim", date(1984, 2, 9)),
]
USER_CREATED_AT = datetime(2026, 6, 12, 9, 30, 0)

# Filled in from the frozen seed; ensure_seed_database refuses partial DBs.
EXPECTED_COUNTS = {
    "specialties": 10,
    "conditions": 40,
    "procedures": 30,
    "expertise_areas": 40,
    "insurers": 12,
    "insurance_plans": 28,
    "cities": 8,
    "city_zips": 24,
    "hospitals": 12,
    "practices": 30,
    "doctors": 226,
    "locations": 348,
    "doctor_conditions": 1677,
    "doctor_procedures": 1252,
    "doctor_expertise": 686,
    "doctor_insurances": 2208,
    "reviews": 1206,
    "doctor_perspectives": 1582,
    "certifications": 296,
    "licenses": 316,
    "education": 567,
    "awards": 50,
    "doctor_languages": 351,
    "users": 4,
    "saved_providers": 4,
    "appointment_requests": 1,
    "user_reviews": 1,
}
CORE_COUNT_KEYS = ("specialties", "cities", "hospitals", "practices", "doctors", "doctor_perspectives")

# --------------------------------------------------------------------------- #
# Vocabularies (real specialties / insurers / cities as vocabulary only)
# --------------------------------------------------------------------------- #
SPECIALTIES = [
    # name, slug, singular, plural, board, cert type, subspecialty cert, description
    ("Dermatology", "dermatology", "Dermatologist", "Dermatologists", "American Board of Dermatology", "Dermatology", "Pediatric Dermatology",
     "Dermatologists diagnose and treat conditions of the skin, hair and nails, from acne and eczema to skin cancer screening and cosmetic procedures."),
    ("Cardiovascular Disease", "cardiovascular-disease", "Cardiologist", "Cardiologists", "American Board of Internal Medicine", "Cardiovascular Disease", "Interventional Cardiology",
     "Cardiologists care for the heart and blood vessels, managing coronary artery disease, heart rhythm problems, heart failure and high blood pressure."),
    ("Family Medicine", "family-medicine", "Family Physician", "Family Physicians", "American Board of Family Medicine", "Family Medicine", "Geriatric Medicine",
     "Family physicians provide continuing, comprehensive care for patients of every age, from preventive visits to the management of chronic illness."),
    ("Neurology", "neurology", "Neurologist", "Neurologists", "American Board of Psychiatry and Neurology", "Neurology", "Vascular Neurology",
     "Neurologists treat disorders of the brain, spinal cord and nerves, including migraine, epilepsy, multiple sclerosis and movement disorders."),
    ("Orthopedic Surgery", "orthopedic-surgery", "Orthopedic Surgeon", "Orthopedic Surgeons", "American Board of Orthopaedic Surgery", "Orthopaedic Surgery", "Orthopaedic Sports Medicine",
     "Orthopedic surgeons treat injuries and diseases of the bones, joints, ligaments and tendons, from sports injuries to joint replacement."),
    ("Gastroenterology", "gastroenterology", "Gastroenterologist", "Gastroenterologists", "American Board of Internal Medicine", "Gastroenterology", "Transplant Hepatology",
     "Gastroenterologists diagnose and treat conditions of the digestive tract and liver, and perform screening procedures such as colonoscopy."),
    ("Psychiatry", "psychiatry", "Psychiatrist", "Psychiatrists", "American Board of Psychiatry and Neurology", "Psychiatry", "Child and Adolescent Psychiatry",
     "Psychiatrists are physicians who diagnose and treat mental health conditions such as depression, anxiety, bipolar disorder and ADHD."),
    ("Obstetrics & Gynecology", "obstetrics-gynecology", "OBGYN", "OBGYNs", "American Board of Obstetrics and Gynecology", "Obstetrics and Gynecology", "Maternal-Fetal Medicine",
     "OBGYNs provide care for pregnancy and childbirth and treat conditions of the female reproductive system across every stage of life."),
    ("Pediatrics", "pediatrics", "Pediatrician", "Pediatricians", "American Board of Pediatrics", "Pediatrics", "Pediatric Emergency Medicine",
     "Pediatricians care for infants, children and adolescents, providing well-child visits, immunizations and treatment of childhood illness."),
    ("Internal Medicine", "internal-medicine", "Internist", "Internists", "American Board of Internal Medicine", "Internal Medicine", "Geriatric Medicine",
     "Internists are primary care physicians for adults, focusing on prevention and the diagnosis and management of chronic conditions."),
]
# Specialties whose conditions / procedures a doctor may also list (cross-field consistency).
RELATED_SPECIALTIES = {
    "Dermatology": ["Internal Medicine", "Family Medicine"],
    "Cardiovascular Disease": ["Internal Medicine", "Family Medicine"],
    "Family Medicine": ["Internal Medicine", "Pediatrics", "Dermatology", "Cardiovascular Disease", "Gastroenterology", "Psychiatry", "Obstetrics & Gynecology"],
    "Neurology": ["Psychiatry", "Internal Medicine"],
    "Orthopedic Surgery": ["Family Medicine", "Internal Medicine"],
    "Gastroenterology": ["Internal Medicine", "Family Medicine"],
    "Psychiatry": ["Neurology", "Family Medicine", "Internal Medicine"],
    "Obstetrics & Gynecology": ["Family Medicine", "Internal Medicine"],
    "Pediatrics": ["Family Medicine", "Internal Medicine"],
    "Internal Medicine": ["Family Medicine", "Cardiovascular Disease", "Gastroenterology", "Dermatology", "Neurology", "Psychiatry"],
}
SECONDARY_CHOICES = {
    "Dermatology": ["Internal Medicine"],
    "Cardiovascular Disease": ["Internal Medicine"],
    "Family Medicine": ["Internal Medicine", "Pediatrics"],
    "Neurology": ["Psychiatry", "Internal Medicine"],
    "Orthopedic Surgery": ["Family Medicine"],
    "Gastroenterology": ["Internal Medicine"],
    "Psychiatry": ["Neurology", "Family Medicine"],
    "Obstetrics & Gynecology": ["Family Medicine"],
    "Pediatrics": ["Family Medicine", "Internal Medicine"],
    "Internal Medicine": ["Family Medicine", "Cardiovascular Disease", "Gastroenterology"],
}
CONDITIONS = {
    "Dermatology": ["Acne", "Eczema", "Psoriasis", "Rosacea"],
    "Cardiovascular Disease": ["Coronary Artery Disease", "Atrial Fibrillation", "Heart Failure", "Hypertension"],
    "Family Medicine": ["Type 2 Diabetes", "High Cholesterol", "Sinusitis", "Back Pain"],
    "Neurology": ["Migraine", "Epilepsy", "Multiple Sclerosis", "Parkinson's Disease"],
    "Orthopedic Surgery": ["Osteoarthritis of the Knee", "Rotator Cuff Tear", "ACL Injury", "Hip Fracture"],
    "Gastroenterology": ["Acid Reflux (GERD)", "Irritable Bowel Syndrome", "Crohn's Disease", "Celiac Disease"],
    "Psychiatry": ["Major Depressive Disorder", "Generalized Anxiety Disorder", "Bipolar Disorder", "ADHD"],
    "Obstetrics & Gynecology": ["Endometriosis", "Polycystic Ovary Syndrome", "Uterine Fibroids", "Menopause"],
    "Pediatrics": ["Asthma in Children", "Ear Infection", "Childhood Obesity", "Strep Throat"],
    "Internal Medicine": ["Anemia", "Hypothyroidism", "Chronic Kidney Disease", "Osteoporosis"],
}
PROCEDURES = {
    "Dermatology": ["Skin Biopsy", "Mohs Surgery", "Cryotherapy for Skin Lesions"],
    "Cardiovascular Disease": ["Echocardiogram", "Cardiac Catheterization", "Stress Test"],
    "Family Medicine": ["Annual Physical Exam", "Flu Vaccination", "Joint Injection"],
    "Neurology": ["EEG (Electroencephalogram)", "EMG (Electromyography)", "Lumbar Puncture"],
    "Orthopedic Surgery": ["Knee Arthroscopy", "Total Hip Replacement", "Carpal Tunnel Release"],
    "Gastroenterology": ["Colonoscopy", "Upper Endoscopy", "Capsule Endoscopy"],
    "Psychiatry": ["Psychotherapy", "Medication Management", "Transcranial Magnetic Stimulation"],
    "Obstetrics & Gynecology": ["Pap Smear", "Pelvic Ultrasound", "IUD Insertion"],
    "Pediatrics": ["Well-Child Visit", "Childhood Immunization", "Vision Screening"],
    "Internal Medicine": ["Blood Pressure Screening", "Diabetes Management", "Cholesterol Screening"],
}
EXPERTISE = {
    "Dermatology": ["Cosmetic Dermatology", "Skin Cancer Screening", "Pediatric Dermatology", "Laser Treatments"],
    "Cardiovascular Disease": ["Preventive Cardiology", "Heart Rhythm Disorders", "Cardiac Imaging", "Structural Heart Disease"],
    "Family Medicine": ["Preventive Care", "Chronic Disease Management", "Women's Health", "Sports Physicals"],
    "Neurology": ["Headache Medicine", "Movement Disorders", "Stroke Care", "Neuromuscular Disorders"],
    "Orthopedic Surgery": ["Sports Medicine", "Joint Replacement", "Hand Surgery", "Spine Care"],
    "Gastroenterology": ["Liver Disease", "Inflammatory Bowel Disease", "Colon Cancer Screening", "Motility Disorders"],
    "Psychiatry": ["Mood Disorders", "Anxiety Disorders", "Addiction Psychiatry", "Geriatric Psychiatry"],
    "Obstetrics & Gynecology": ["Prenatal Care", "Minimally Invasive Gynecologic Surgery", "Fertility Evaluation", "Menopause Management"],
    "Pediatrics": ["Newborn Care", "Adolescent Medicine", "Developmental Pediatrics", "Pediatric Asthma Care"],
    "Internal Medicine": ["Diabetes Care", "Hypertension Management", "Geriatric Medicine", "Travel Medicine"],
}
# name, slug, weight (relative acceptance), plan types
INSURERS = [
    ("Aetna", "aetna", 140, ["", "HMO", "PPO"]),
    ("Cigna", "cigna", 110, ["", "PPO"]),
    ("UnitedHealthcare", "unitedhealthcare", 130, ["", "HMO", "Medicare"]),
    ("Blue Cross Blue Shield", "blue-cross-blue-shield", 150, ["", "PPO", "HMO"]),
    ("Humana", "humana", 90, ["", "Medicare", "PPO"]),
    ("Medicare", "medicare", 160, ["", "Medicare"]),
    ("Medicaid", "medicaid", 90, ["Medicaid (Managed)"]),
    ("AmeriHealth", "amerihealth", 80, ["", "HMO", "PPO"]),
    ("Highmark", "highmark", 60, ["", "PPO"]),
    ("Horizon", "horizon", 70, ["", "HMO"]),
    ("Kaiser Permanente", "kaiser-permanente", 40, ["", "HMO"]),
    ("Tricare", "tricare", 45, ["", "Medicare"]),
]
# name, slug, state, state_name, state_slug, lat, lon, zips, doctor count, area code
CITIES = [
    ("Newark", "newark", "DE", "Delaware", "delaware", 39.6837, -75.7497, ["19711", "19702", "19713"], 52, "302"),
    ("Bear", "bear", "DE", "Delaware", "delaware", 39.6200, -75.6500, ["19701", "19706", "19720"], 22, "302"),
    ("Wilmington", "wilmington", "DE", "Delaware", "delaware", 39.7459, -75.5466, ["19801", "19803", "19805"], 34, "302"),
    ("Elkton", "elkton", "MD", "Maryland", "maryland", 39.5700, -75.9200, ["21921", "21922", "21919"], 26, "410"),
    ("Salem", "salem", "NJ", "New Jersey", "new-jersey", 39.5718, -75.4671, ["08079", "08070", "08072"], 22, "856"),
    ("West Chester", "west-chester", "PA", "Pennsylvania", "pennsylvania", 39.9607, -75.6055, ["19380", "19382", "19383"], 24, "610"),
    ("Media", "media", "PA", "Pennsylvania", "pennsylvania", 39.9200, -75.3400, ["19063", "19086", "19091"], 20, "610"),
    ("Baltimore", "baltimore", "MD", "Maryland", "maryland", 39.2904, -76.6122, ["21201", "21218", "21224"], 24, "410"),
]
IN_RADIUS_CITIES = ["Newark", "Bear", "Wilmington", "Elkton", "Salem", "West Chester", "Media"]
# (specialty, city) -> number of primary offices; cells named in tasks are >= 6.
CLUSTERS = {
    "Dermatology": {"Newark": 6, "Wilmington": 6, "Elkton": 6, "Salem": 1, "West Chester": 1},
    "Cardiovascular Disease": {"Newark": 7, "Wilmington": 6, "West Chester": 6, "Salem": 1},
    "Family Medicine": {"Newark": 8, "Bear": 6, "Elkton": 2, "Salem": 2, "Media": 2},
    "Neurology": {"West Chester": 6, "Newark": 6, "Wilmington": 3, "Elkton": 2, "Salem": 3},
    "Orthopedic Surgery": {"Elkton": 6, "Media": 6, "Newark": 3, "Bear": 3, "Salem": 2},
    "Gastroenterology": {"Newark": 6, "Wilmington": 4, "Bear": 3, "Elkton": 2, "West Chester": 2, "Salem": 3},
    "Psychiatry": {"Media": 6, "Wilmington": 6, "Newark": 4, "Elkton": 2, "Salem": 2},
    "Obstetrics & Gynecology": {"Salem": 6, "Newark": 4, "Bear": 4, "Wilmington": 3, "Media": 3},
    "Pediatrics": {"Newark": 6, "Bear": 3, "Wilmington": 3, "Elkton": 2, "West Chester": 3, "Salem": 1, "Media": 2},
    "Internal Medicine": {"Newark": 2, "Bear": 3, "Wilmington": 3, "Elkton": 4, "West Chester": 6, "Salem": 1, "Media": 1},
}
BALTIMORE_PER_SPECIALTY = {
    "Dermatology": 3, "Cardiovascular Disease": 2, "Family Medicine": 3, "Neurology": 2, "Orthopedic Surgery": 2,
    "Gastroenterology": 2, "Psychiatry": 3, "Obstetrics & Gynecology": 2, "Pediatrics": 3, "Internal Medicine": 2,
}
# Cells that need a deeper bench of highly rated physicians than the 20-per-specialty grid gives
# them (appended after the grid so the grid's own slot order is untouched).
CLUSTER_EXTRAS = [
    {"specialty": "Cardiovascular Disease", "city": "West Chester", "gender": "f", "tier": "Basic",
     "rating": 4.2, "years": 17, "new_patients": True, "virtual": False, "medicare": True, "medicaid": False},
    {"specialty": "Cardiovascular Disease", "city": "West Chester", "gender": "n", "tier": "Enhanced",
     "rating": 4.1, "years": 9, "new_patients": True, "virtual": True, "medicare": True, "medicaid": True},
]
# name, city, street, zip, phone suffix, website slug
HOSPITALS = [
    ("Christina Creek Medical Center", "Newark", "1200 Ogletown Stanton Rd", "19713", "555-0140", "christinacreekmed"),
    ("White Clay Regional Hospital", "Newark", "88 Possum Park Rd", "19711", "555-0152", "whiteclayregional"),
    ("Red Lion Community Hospital", "Bear", "2400 Pulaski Hwy", "19701", "555-0163", "redlioncommunity"),
    ("Brandywine Valley Hospital", "Wilmington", "501 W 14th St", "19801", "555-0171", "brandywinevalleyhospital"),
    ("Riverfront General Hospital", "Wilmington", "1600 Rockford Rd", "19803", "555-0184", "riverfrontgeneral"),
    ("Cecil Crossing Medical Center", "Elkton", "106 Bow St", "21921", "555-0195", "cecilcrossingmed"),
    ("Fenwick Creek Hospital", "Salem", "310 Woodstown Rd", "08079", "555-0207", "fenwickcreekhospital"),
    ("Chester Valley Medical Center", "West Chester", "701 E Marshall St", "19380", "555-0218", "chestervalleymed"),
    ("Rose Tree Medical Center", "Media", "1068 W Baltimore Pike", "19063", "555-0229", "rosetreemed"),
    ("Patapsco Harbor Medical Center", "Baltimore", "2401 W Belvedere Ave", "21218", "555-0231", "patapscoharbormed"),
    ("Chesapeake Lantern Hospital", "Baltimore", "900 S Caton Ave", "21224", "555-0242", "chesapeakelantern"),
    ("Iron Hill Surgical Hospital", "Newark", "4000 Chapman Rd", "19702", "555-0253", "ironhillsurgical"),
]
PRACTICE_NAME_BY_FOCUS = {
    "Dermatology": "{place} Dermatology Associates",
    "Cardiovascular Disease": "{place} Heart & Vascular",
    "Family Medicine": "{place} Family Health",
    "Neurology": "{place} Neurology Group",
    "Orthopedic Surgery": "{place} Orthopedics & Sports Medicine",
    "Gastroenterology": "{place} Digestive Health",
    "Psychiatry": "{place} Behavioral Health",
    "Obstetrics & Gynecology": "{place} Women's Health",
    "Pediatrics": "{place} Pediatrics",
    "Internal Medicine": "{place} Internal Medicine Associates",
    None: "{place} Medical Group",
}
# city -> list of (place name, focus specialty or None, street, zip)
PRACTICES = {
    "Newark": [
        ("Christina Creek", "Dermatology", "4735 Ogletown Stanton Rd Ste 2200", "19713"),
        ("White Clay", "Cardiovascular Disease", "620 Churchmans Rd Ste 110", "19702"),
        ("Iron Hill", "Family Medicine", "2600 Glasgow Ave Ste 116", "19702"),
        ("Glasgow Pike", "Neurology", "500 Peoples Plz Ste 230", "19702"),
        ("Deer Park", "Gastroenterology", "255 E Main St Ste 200", "19711"),
        ("Pike Creek", "Pediatrics", "3401 Papermill Rd Ste 5", "19711"),
        ("Main Street", None, "112 S Main St Fl 3", "19711"),
        ("Ogletown", None, "4051 Ogletown Rd Ste 101", "19713"),
    ],
    "Bear": [
        ("Red Lion", "Family Medicine", "1200 Pulaski Hwy Ste 1", "19701"),
        ("Fox Run", "Orthopedic Surgery", "300 Fox Hunt Dr Ste 220", "19701"),
        ("Caravel", None, "1580 Old Porter Rd Ste 3", "19720"),
    ],
    "Wilmington": [
        ("Brandywine", "Dermatology", "1401 Foulk Rd Ste 201", "19803"),
        ("Riverfront", "Cardiovascular Disease", "300 Justison St Ste 400", "19801"),
        ("Rockford Park", "Psychiatry", "1800 N Broom St Ste 2", "19805"),
        ("Trolley Square", None, "1707 Delaware Ave Ste 100", "19805"),
    ],
    "Elkton": [
        ("Cecil Crossing", "Dermatology", "142 E Main St Ste 3", "21921"),
        ("Big Elk", "Orthopedic Surgery", "9 Newark Ave Ste 210", "21921"),
        ("Elk River", None, "231 W Pulaski Hwy Ste 100", "21921"),
    ],
    "Salem": [
        ("Fenwick", "Obstetrics & Gynecology", "18 Grant St Ste 2", "08079"),
        ("Mannington", "Neurology", "119 Broadway Fl 2", "08079"),
        ("Yorke Street", None, "45 Yorke St Ste 1", "08079"),
    ],
    "West Chester": [
        ("Chester Valley", "Cardiovascular Disease", "915 Paoli Pike Ste 12", "19380"),
        ("Goose Creek", "Neurology", "1315 W Chester Pike Ste 300", "19382"),
        ("Marshall Square", "Internal Medicine", "16 N High St Ste 2", "19380"),
    ],
    "Media": [
        ("Rose Tree", "Orthopedic Surgery", "1098 W Baltimore Pike Ste 3100", "19063"),
        ("Ridley Creek", "Psychiatry", "200 E State St Ste 205", "19063"),
        ("Providence Road", None, "600 N Providence Rd Ste 101", "19063"),
    ],
    "Baltimore": [
        ("Patapsco", "Family Medicine", "3455 Wilkens Ave Ste 200", "21224"),
        ("Federal Hill", "Dermatology", "1100 Light St Ste 4", "21201"),
        ("Charles Village", None, "3100 St Paul St Ste 2A", "21218"),
    ],
}
SECONDARY_OFFICE_TAGS = ["North Office", "Medical Arts Building", "Outpatient Center", "Professional Plaza", "Annex", "Satellite Office", "Pavilion", "Wellness Center"]
SECONDARY_STREETS = ["Concord Pike", "Kirkwood Hwy", "Limestone Rd", "Marsh Rd", "Naamans Rd", "Elkton Rd", "Pulaski Hwy", "Lancaster Pike", "Baltimore Pike", "Paoli Pike", "Salem Quinton Rd", "Route 40", "Silverside Rd", "Chestnut Hill Rd", "Old Baltimore Pike", "Eastern Ave", "Falls Rd", "Harford Rd"]
STREET_TYPES = ["Ste 100", "Ste 210", "Ste 305", "Bldg B", "Fl 2", "Ste 12", "Ste 400"]
DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
HOURS_PATTERNS = [
    # (mon-fri open, close, sat open, sat close, sun open, sun close)
    ("8:00 am", "5:00 pm", None, None, None, None),
    ("8:30 am", "4:30 pm", None, None, None, None),
    ("9:00 am", "5:00 pm", "9:00 am", "12:00 pm", None, None),
    ("7:30 am", "4:00 pm", "8:00 am", "1:00 pm", None, None),
    ("8:00 am", "6:00 pm", "9:00 am", "2:00 pm", None, None),
    ("9:00 am", "4:00 pm", None, None, None, None),
    ("8:00 am", "5:30 pm", "10:00 am", "2:00 pm", None, None),
    ("7:00 am", "3:30 pm", "8:00 am", "11:30 am", None, None),
]
MEDICAL_SCHOOLS = [
    "Brandywine College of Medicine", "Chesapeake Bay School of Medicine", "Delaware Valley Medical College",
    "Susquehanna University School of Medicine", "Allegheny Ridge College of Osteopathic Medicine",
    "Harbor Point School of Medicine", "Piedmont Atlantic Medical School", "Lenape Valley College of Medicine",
    "Great Falls University School of Medicine", "Tidewater College of Osteopathic Medicine",
    "Monocacy School of Medicine", "Schuylkill Medical College", "Cumberland Gap University College of Medicine",
    "Blue Ridge Osteopathic College", "Shenandoah College of Medicine", "Pocono Highlands Medical School",
    "Cape Henlopen University School of Medicine", "Patuxent River College of Medicine", "Severn Medical College",
    "Ohio Valley Osteopathic Institute", "Wyoming Valley School of Medicine", "Juniata College of Medicine",
    "Rappahannock University School of Medicine", "Kittatinny Medical College", "Conestoga School of Osteopathic Medicine",
    "Mid-Atlantic Institute of Medicine", "Nanticoke College of Medicine", "Choptank University School of Medicine",
    "Laurel Highlands Medical College", "Tuckahoe College of Osteopathic Medicine",
]
TRAINING_HOSPITALS = [
    "Brandywine Valley Hospital", "Patapsco Harbor Medical Center", "Chester Valley Medical Center",
    "Allegheny Ridge Medical Center", "Harbor Point University Hospital", "Susquehanna General Hospital",
    "Lenape Valley Medical Center", "Great Falls University Hospital", "Tidewater Regional Medical Center",
    "Monocacy General Hospital", "Schuylkill Medical Center", "Piedmont Atlantic Hospital",
    "Cape Henlopen Medical Center", "Severn River Hospital", "Blue Ridge Regional Medical Center",
    "Christina Creek Medical Center", "Riverfront General Hospital", "Shenandoah Memorial Hospital",
    "Wyoming Valley Medical Center", "Kittatinny Regional Hospital", "Conestoga General Hospital",
    "Nanticoke Memorial Medical Center", "Laurel Highlands Hospital", "Rappahannock University Hospital",
]
LANGUAGES = ["Spanish", "Mandarin", "Hindi", "French", "Portuguese", "Arabic", "Korean", "Russian", "Tagalog", "Vietnamese", "Polish", "Greek", "Italian", "Urdu", "Haitian Creole"]
WAIT_BUCKETS = ["Under 5 minutes", "5-15 minutes", "15-30 minutes", "Over 30 minutes"]

MALE_FIRST = ["Aaron", "Adrian", "Alan", "Andre", "Anthony", "Arjun", "Benjamin", "Brandon", "Caleb", "Carlos", "Charles", "Christopher", "Colin", "Damian", "Daniel", "Darius", "Dean", "Derek", "Dmitri", "Douglas", "Elijah", "Emmanuel", "Eric", "Ethan", "Evan", "Felix", "Gabriel", "Gregory", "Harold", "Hector", "Henry", "Ian", "Isaac", "Jamal", "Jared", "Jerome", "Joel", "Jonah", "Joseph", "Julian", "Keith", "Kenji", "Kevin", "Leon", "Luis", "Malik", "Marcus", "Martin", "Mateo", "Matthew", "Miguel", "Nathan", "Neil", "Nikhil", "Oliver", "Omar", "Patrick", "Peter", "Rafael", "Raymond", "Ricardo", "Robert", "Roland", "Russell", "Samir", "Sean", "Simon", "Stephen", "Tariq", "Theodore", "Timothy", "Tobias", "Victor", "Vincent", "Warren", "Wesley", "Xavier", "Zachary"]
FEMALE_FIRST = ["Abigail", "Adriana", "Aisha", "Alexandra", "Alicia", "Amara", "Amelia", "Ana", "Angela", "Anita", "Beatriz", "Bianca", "Bridget", "Camila", "Carmen", "Caroline", "Catherine", "Celeste", "Claire", "Dana", "Deborah", "Denise", "Diana", "Elena", "Eleanor", "Emily", "Erin", "Esther", "Fatima", "Fiona", "Gabriela", "Grace", "Hannah", "Helen", "Ingrid", "Irene", "Isabel", "Jasmine", "Jennifer", "Joanna", "Julia", "Karen", "Kavya", "Laila", "Laura", "Leah", "Lillian", "Linda", "Lucia", "Madeline", "Margaret", "Maria", "Marisol", "Mei", "Melissa", "Miriam", "Monica", "Naomi", "Natalie", "Nicole", "Nora", "Olivia", "Patricia", "Priya", "Rachel", "Rebecca", "Renee", "Rosa", "Ruth", "Sabrina", "Samantha", "Sarah", "Simone", "Sofia", "Stephanie", "Tamara", "Teresa", "Valerie", "Vanessa", "Veronica", "Yasmin"]
NEUTRAL_FIRST = ["Alex", "Avery", "Blake", "Cameron", "Casey", "Dakota", "Drew", "Elliot", "Emerson", "Finley", "Harper", "Hayden", "Jesse", "Jordan", "Kai", "Lane", "Morgan", "Parker", "Quinn", "Reese", "Riley", "Rowan", "Sage", "Skyler", "Taylor"]
SURNAMES = ["Abernathy", "Achebe", "Adler", "Aguilar", "Ahmadi", "Alvarado", "Anand", "Archer", "Ashworth", "Baptiste", "Barlow", "Bassett", "Beckett", "Bellamy", "Benitez", "Bergstrom", "Blackwood", "Bouchard", "Brennan", "Calloway", "Carvalho", "Castellano", "Chandra", "Choudhury", "Cisneros", "Clemente", "Coleman", "Conway", "Cordova", "Crawford", "Dalton", "Danforth", "DeLuca", "Desai", "Devereaux", "Dimitriou", "Donnelly", "Draper", "Dubois", "Ellison", "Emerson", "Escobar", "Fairbanks", "Farrell", "Ferreira", "Fitzgerald", "Fontaine", "Forsythe", "Gallagher", "Galloway", "Garrison", "Gilchrist", "Goldberg", "Grantham", "Greenwood", "Guzman", "Hadley", "Halloran", "Hargrove", "Harrington", "Hastings", "Hawthorne", "Henderson", "Holloway", "Huang", "Ibarra", "Ingram", "Iyer", "Jacobsen", "Jankowski", "Jimenez", "Kaminski", "Kapoor", "Kearney", "Keller", "Kennedy", "Kimura", "Kirkland", "Kowalski", "Lachance", "Landry", "Larkin", "Lindqvist", "Lockhart", "Lombardi", "Macallister", "Maddox", "Mahoney", "Marchetti", "Matsuda", "McAllister", "Mendoza", "Merriweather", "Molina", "Montgomery", "Moreau", "Nakamura", "Navarro", "Nguyen", "Nordstrom", "Novak", "Nwachukwu", "Oduya", "Okafor", "Oliveira", "Olsen", "Ortega", "Osei", "Padilla", "Pappas", "Patel", "Pemberton", "Pereira", "Petrov", "Prescott", "Quintero", "Radcliffe", "Ramsey", "Rashid", "Redmond", "Reyes", "Rocha", "Rutherford", "Saito", "Salazar", "Sandoval", "Sattler", "Schaefer", "Sinclair", "Solano", "Soriano", "Stanton", "Sterling", "Sullivan", "Tanaka", "Thackeray", "Thornton", "Tolliver", "Trask", "Underwood", "Valdez", "Vance", "Varga", "Velasquez", "Villanueva", "Wakefield", "Waller", "Warrick", "Weatherly", "Whitaker", "Whitfield", "Winslow", "Wolcott", "Yamamoto", "Yilmaz", "Zamora", "Zhang", "Abbott", "Acosta", "Ainsley", "Alcott", "Amundsen", "Baird", "Banerjee", "Barrera", "Bishop", "Boland", "Bradshaw", "Burgess", "Cahill", "Camacho", "Carrington", "Chaudhry", "Cheng", "Costa", "Cunningham", "Dawson", "Delgado", "Doyle", "Duarte", "Eldridge", "Faulkner", "Fischer", "Flores", "Gaines", "Garza", "Gomes", "Haddad", "Hakim", "Hansen", "Hoffman", "Holt", "Hutchinson", "Jensen", "Kaur", "Khoury", "Lawson", "Lindsey", "Lowery", "Marlowe", "Mbeki", "Meyer", "Nash", "Nielsen", "Ochoa", "Pace", "Peralta", "Quigley", "Ramirez", "Rowe", "Sato", "Serrano", "Shah", "Tahir", "Torres", "Ueda", "Vasquez", "Walsh", "Wexler", "Yoon", "Zielinski", "Ashby", "Brandt", "Corwin", "Dunmore", "Ellery", "Farrow", "Gaskell", "Hollis", "Ivanova", "Joubert", "Kessler", "Lattimer"]
# Surname collision pairs: (specialty, city A, city B). The B doctor takes A's surname.
SURNAME_COLLISIONS = [
    ("Dermatology", "Newark", "Newark"),
    ("Dermatology", "Wilmington", "Elkton"),
    ("Cardiovascular Disease", "Wilmington", "Newark"),
    ("Neurology", "West Chester", "Newark"),
    ("Psychiatry", "Media", "Wilmington"),
    ("Orthopedic Surgery", "Elkton", "Media"),
]

OVERVIEW_TEMPLATES = [
    "{full} is a {specialty_lower} physician practicing at {practice} in {city}, {state}. With {years} years of experience, {pronoun} sees patients at the {city} office throughout the week.",
    "{full} practices {specialty} at {practice}, based in {city}, {state}. {Pronoun} has {years} years of experience caring for patients in the {city} area.",
    "Practicing {specialty} for {years} years, {full} is part of the team at {practice} in {city}, {state}, where {pronoun} welcomes patients from across the region.",
    "{full} is a {specialty} specialist with {practice} in {city}, {state}. {Pronoun} brings {years} years of clinical experience to every visit.",
    "Based at {practice} in {city}, {state}, {full} has practiced {specialty} for {years} years and is known in {city} for an unhurried, patient-first approach.",
    "{full} joined {practice} in {city}, {state}, and has {years} years of experience in {specialty}. Patients describe the {city} office as calm and well organized.",
    "With {years} years in {specialty}, {full} cares for patients at {practice} in {city}, {state}, combining thorough evaluations with clear, practical guidance.",
    "{full} is a {specialty_lower} physician at {practice} in {city}, {state}, with {years} years of experience. {Pronoun} focuses on building long-term relationships with the patients {pronoun} serves.",
]
BIO_PHILOSOPHY = [
    "{Short} believes the best care starts with listening. Every visit begins with time to understand what brought the patient in, what has already been tried, and what a good outcome would look like for them.",
    "{Short} takes an evidence-based, conservative approach: the least invasive option that will work is always considered first, and every treatment plan is written down so patients leave knowing exactly what happens next.",
    "Patients of {short} can expect a plain-language explanation of every finding. {Pronoun_cap} keeps visits unhurried and encourages families to take part in decisions.",
    "{Short} coordinates closely with each patient's other physicians so that treatment fits into the bigger picture of their health, and follows up after every significant change in care.",
]
BIO_CLOSING = [
    "{Short} is {accepting} and offers {visit_style}. Same-week appointments are usually available at the {city} office.",
    "The {city} office of {practice} offers {visit_style}, and {short} is {accepting}.",
    "{Short} is {accepting}. The practice offers {visit_style} and evening scheduling on request.",
]
REVIEW_TEMPLATES = {
    5: [
        "{doctor} took the time to explain my {topic} in plain language and answered every question. Wait was {wait} and the staff at {practice} were {staff}.",
        "Best {visit} I have had in years. {doctor} listened carefully, laid out the options for my {topic}, and never rushed me. The {city} office runs on time.",
        "I was nervous going in, but {doctor} was calm, thorough and kind. My {topic} is finally under control after {n} months of trying elsewhere.",
        "{doctor} is exactly the kind of physician you hope to find: {staff} staff, {wait} wait, and a clear plan for my {topic} before I left the room.",
        "Highly recommend {doctor}. The {practice} team was {staff}, the check-in was easy, and I felt genuinely heard about my {topic}.",
        "Five stars for {doctor}. Follow-up call came the next day as promised, and the instructions for managing my {topic} were easy to follow.",
        "After {n} years with the same {topic}, {doctor} found an approach that actually works. Wait time was {wait}. Could not be happier.",
        "{doctor} explained the results of every test and made sure I understood the treatment for my {topic}. The {city} office is clean and well run.",
        "Wonderful experience at {practice}. {doctor} is knowledgeable, patient and {staff}; my {topic} appointment felt thorough rather than rushed.",
        "From scheduling to the {visit} itself, everything was smooth. {doctor} gave me a written plan for my {topic} and the staff were {staff}.",
    ],
    4: [
        "{doctor} was knowledgeable and thorough about my {topic}. The only downside was a {wait} wait past my appointment time.",
        "Good {visit} overall. {doctor} answered my questions about {topic} and the staff at {practice} were {staff}. Parking at the {city} office is tight.",
        "Solid, careful physician. {doctor} recommended a sensible plan for my {topic}; I just wish the follow-up call had come sooner than {n} days later.",
        "I like {doctor}: direct, {staff} and clearly experienced with {topic}. Scheduling the next visit took a couple of phone calls.",
        "Very good care for my {topic}. {doctor} explained things well. The waiting room at {practice} was busy and the wait was {wait}.",
        "{doctor} took my concerns about {topic} seriously and ordered the right tests. Four stars only because the office phone line is hard to reach.",
        "Professional and reassuring. {doctor} walked me through my {topic} treatment step by step. Check-in at the {city} office was a little slow.",
        "Happy with {doctor} after {n} visits for my {topic}. Staff are {staff}; the portal for results could be easier to use.",
    ],
    3: [
        "{doctor} seems competent and the plan for my {topic} was reasonable, but the visit felt rushed and I waited {wait} to be seen.",
        "Mixed experience at {practice}. {doctor} was fine, though I had to ask twice before my questions about {topic} were answered.",
        "Average {visit}. {doctor} addressed my {topic} but did not explain the medication side effects until I asked. Staff were {staff}.",
        "The care for my {topic} was adequate. Getting a follow-up appointment with {doctor} at the {city} office took {n} weeks.",
        "{doctor} was polite and the exam was thorough, but the front desk at {practice} lost my paperwork and the wait was {wait}.",
        "Okay overall. {doctor} knows {topic} well; communication between visits could be much better.",
    ],
    2: [
        "Disappointed. {doctor} spent under ten minutes with me and my questions about {topic} went mostly unanswered. Wait was {wait}.",
        "The staff at {practice} were {staff}, but {doctor} dismissed my concerns about {topic} and I left without a clear plan.",
        "Two stars. {doctor} may be a fine physician but the {city} office is disorganized: {n} calls to get my {topic} results.",
        "I did not feel listened to. {doctor} interrupted several times while I described my {topic}, and the follow-up never came.",
        "Long wait ({wait}) and a hurried {visit}. {doctor} did not explain the next steps for my {topic}.",
    ],
    1: [
        "Would not return. {doctor} was dismissive about my {topic} and the office at {practice} never returned {n} phone calls.",
        "Terrible experience. Waited {wait} past my appointment, then {doctor} spent five minutes on my {topic} and left.",
        "One star. My {topic} got worse under the plan {doctor} gave me, and nobody at the {city} office would schedule a follow-up.",
        "Rude front desk, {wait} wait, and {doctor} did not review my chart before discussing my {topic}. Went elsewhere.",
    ],
}
REVIEW_STAFF = ["friendly", "courteous", "helpful", "welcoming", "efficient", "patient", "attentive", "professional"]
REVIEW_WAIT = ["under five minutes", "about ten minutes", "close to twenty minutes", "roughly half an hour", "over forty minutes", "just a few minutes"]
REVIEW_VISIT = ["first visit", "follow-up", "annual checkup", "consultation", "second opinion", "new-patient appointment"]
REVIEW_TAILS = [" Recommended to my neighbors.", " Booked my next visit before leaving.", " My spouse now sees the same office.", " Worth the drive.", " Sharing so others know what to expect.", " Updated after my second visit.", " Still the same opinion a year later.", " Posting at my family's request."]
HOSPITAL_OVERVIEW = "{name} is a Hospital with 1 Location. Currently {name}'s {n} physicians cover {s} specialty areas of medicine."
PRACTICE_OVERVIEW = "{name} is a Group Practice with 1 Location. Currently {name}'s {n} physicians cover {s} specialty areas of medicine."


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def slugify(value: str) -> str:
    out = []
    for char in value.lower():
        if char.isalnum():
            out.append(char)
        elif char in " -&/'":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def multiset(spec: list[tuple[object, int]]) -> list:
    """Expand [(value, count), ...] into a list and shuffle it with the RNG."""
    values = [value for value, count in spec for _ in range(count)]
    RNG.shuffle(values)
    return values


def weighted_sample(population: list, weights: list[int], k: int) -> list:
    """Weighted sampling without replacement (deterministic via RNG)."""
    chosen = []
    pool = list(zip(population, weights))
    for _ in range(min(k, len(pool))):
        total = sum(weight for _item, weight in pool)
        pick = RNG.random() * total
        cumulative = 0.0
        for index, (item, weight) in enumerate(pool):
            cumulative += weight
            if pick <= cumulative:
                chosen.append(item)
                pool.pop(index)
                break
    return chosen


def jitter(lat: float, lon: float) -> tuple[float, float]:
    return round(lat + RNG.uniform(-0.012, 0.012), 6), round(lon + RNG.uniform(-0.015, 0.015), 6)


def phone(area: str, used: set[str]) -> str:
    while True:
        number = f"({area}) 555-{RNG.randint(100, 999):03d}{RNG.randint(0, 9)}"
        if number not in used:
            used.add(number)
            return number


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=RNG.randint(0, (end - start).days))


def apply_hours(target, pattern) -> None:
    open_wd, close_wd, sat_open, sat_close, sun_open, sun_close = pattern
    for key in ("mon", "tue", "wed", "thu", "fri"):
        setattr(target, f"{key}_open", open_wd)
        setattr(target, f"{key}_close", close_wd)
    target.sat_open, target.sat_close = sat_open, sat_close
    target.sun_open, target.sun_close = sun_open, sun_close


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _build_vocabulary() -> dict:
    specialties: dict[str, Specialty] = {}
    for order, (name, slug, singular, plural, board, _cert, _sub, description) in enumerate(SPECIALTIES):
        row = Specialty(name=name, slug=slug, singular=singular, plural=plural, description=description, board_name=board, display_order=order)
        db.session.add(row)
        specialties[name] = row
    db.session.flush()
    conditions: dict[str, list[Condition]] = {}
    procedures: dict[str, list[Procedure]] = {}
    areas: dict[str, list[ExpertiseArea]] = {}
    for name, *_rest in SPECIALTIES:
        conditions[name] = [Condition(name=c, slug=slugify(c), specialty_id=specialties[name].id) for c in CONDITIONS[name]]
        procedures[name] = [Procedure(name=p, slug=slugify(p), specialty_id=specialties[name].id) for p in PROCEDURES[name]]
        areas[name] = [ExpertiseArea(name=a, specialty_id=specialties[name].id) for a in EXPERTISE[name]]
        db.session.add_all(conditions[name] + procedures[name] + areas[name])
    db.session.flush()
    insurers: list[tuple[Insurer, int, list[InsurancePlan]]] = []
    for name, slug, weight, plan_types in INSURERS:
        insurer = Insurer(name=name, slug=slug)
        db.session.add(insurer)
        db.session.flush()
        plans = [InsurancePlan(insurer_id=insurer.id, plan_type=plan_type) for plan_type in plan_types]
        db.session.add_all(plans)
        insurers.append((insurer, weight, plans))
    db.session.flush()
    cities: dict[str, City] = {}
    for name, slug, state, state_name, state_slug, lat, lon, zips, _count, _area in CITIES:
        city = City(name=name, slug=slug, state=state, state_name=state_name, state_slug=state_slug, lat=lat, lon=lon)
        db.session.add(city)
        db.session.flush()
        db.session.add_all([CityZip(city_id=city.id, zip=zip_code) for zip_code in zips])
        cities[name] = city
    db.session.flush()
    return {"specialties": specialties, "conditions": conditions, "procedures": procedures, "areas": areas, "insurers": insurers, "cities": cities}


def _build_hospitals(cities: dict[str, City], used_phones: set[str]) -> dict[str, list[Hospital]]:
    by_city: dict[str, list[Hospital]] = {}
    area_by_city = {row[0]: row[9] for row in CITIES}
    for name, city_name, street, zip_code, suffix, site in HOSPITALS:
        area = area_by_city[city_name]
        number = f"({area}) {suffix}"
        used_phones.add(number)
        hospital = Hospital(
            name=name,
            slug=slugify(name),
            city_id=cities[city_name].id,
            street=street,
            zip=zip_code,
            phone=number,
            website=f"https://www.{site}.example",
            overview_text="",
            avg_rating=None,
            ratings_count=0,
        )
        db.session.add(hospital)
        by_city.setdefault(city_name, []).append(hospital)
    db.session.flush()
    return by_city


def _build_practices(cities: dict[str, City], used_phones: set[str]) -> dict[str, list[tuple[Practice, str | None]]]:
    by_city: dict[str, list[tuple[Practice, str | None]]] = {}
    area_by_city = {row[0]: row[9] for row in CITIES}
    for city_name in [row[0] for row in CITIES]:
        for place, focus, street, zip_code in PRACTICES[city_name]:
            name = PRACTICE_NAME_BY_FOCUS[focus].format(place=place)
            slug = slugify(name)
            practice = Practice(
                name=name,
                slug=slug,
                city_id=cities[city_name].id,
                street=street,
                zip=zip_code,
                phone=phone(area_by_city[city_name], used_phones),
                website=f"https://www.{slug.replace('-', '')}.example",
                overview_text="",
                avg_rating=None,
                ratings_count=0,
            )
            apply_hours(practice, RNG.choice(HOURS_PATTERNS))
            db.session.add(practice)
            by_city.setdefault(city_name, []).append((practice, focus))
    db.session.flush()
    return by_city


def _doctor_slots() -> list[dict]:
    """Deterministic list of (specialty, city, gender, tier) slots — 200 in radius + 24 Baltimore + cluster extras."""
    slots: list[dict] = []
    for spec_name, *_rest in SPECIALTIES:
        cells = CLUSTERS[spec_name]
        assert sum(cells.values()) == 20, spec_name
        genders = multiset([("m", 9), ("f", 9), ("n", 2)])
        tiers = multiset([("Basic", 12), ("Enhanced", 8)])
        cursor = 0
        for city_name in IN_RADIUS_CITIES:
            for _ in range(cells.get(city_name, 0)):
                slots.append({"specialty": spec_name, "city": city_name, "gender": genders[cursor], "tier": tiers[cursor]})
                cursor += 1
    baltimore_genders = multiset([("m", 13), ("f", 11)])
    baltimore_tiers = multiset([("Basic", 14), ("Enhanced", 10)])
    cursor = 0
    for spec_name, *_rest in SPECIALTIES:
        for _ in range(BALTIMORE_PER_SPECIALTY[spec_name]):
            slots.append({"specialty": spec_name, "city": "Baltimore", "gender": baltimore_genders[cursor], "tier": baltimore_tiers[cursor]})
            cursor += 1
    for extra in CLUSTER_EXTRAS:
        slots.append(dict(extra))
    assert len(slots) == 224 + len(CLUSTER_EXTRAS)
    return slots


def _assign_quotas(slots: list[dict]) -> None:
    """Attach the quota-controlled attributes to each slot (in-radius multisets first)."""
    in_radius = [slot for slot in slots if slot["city"] != "Baltimore" and "rating" not in slot]
    baltimore = [slot for slot in slots if slot["city"] == "Baltimore"]
    ratings = multiset([(5.0, 24)] + [(None, 6)])
    ratings += multiset([(round(4.0 + 0.1 * i, 1), 9) for i in range(10)])
    ratings += multiset([(round(3.0 + 0.2 * i, 1), 10) for i in range(5)])
    ratings += multiset([(round(2.0 + 0.3 * i, 1), 5) for i in range(4)])
    ratings += multiset([(round(1.0 + 0.4 * i, 1), 5) for i in range(2)])
    ratings = ratings[:24] + ratings[24:30] + ratings[30:]
    RNG.shuffle(ratings)
    years = multiset([(RNG.randint(1, 4), 1) for _ in range(22)] + [(RNG.randint(5, 14), 1) for _ in range(50)]
                     + [(RNG.randint(15, 19), 1) for _ in range(36)] + [(RNG.randint(20, 24), 1) for _ in range(34)]
                     + [(RNG.randint(25, 29), 1) for _ in range(30)] + [(RNG.randint(30, 42), 1) for _ in range(28)])
    new_patients = multiset([(True, 150), (False, 50)])
    virtual = multiset([(True, 70), (False, 130)])
    medicare = multiset([(True, 130), (False, 70)])
    medicaid = multiset([(True, 90), (False, 110)])
    for index, slot in enumerate(in_radius):
        slot.update(rating=ratings[index], years=years[index], new_patients=new_patients[index], virtual=virtual[index], medicare=medicare[index], medicaid=medicaid[index])
    b_ratings = multiset([(5.0, 3), (4.2, 3), (4.5, 3), (4.8, 3), (4.0, 2), (3.4, 3), (3.8, 3), (2.6, 2), (2.1, 1), (1.7, 1)])
    b_years = multiset([(RNG.randint(2, 40), 1) for _ in range(24)])
    b_new = multiset([(True, 18), (False, 6)])
    b_virtual = multiset([(True, 9), (False, 15)])
    b_medicare = multiset([(True, 16), (False, 8)])
    b_medicaid = multiset([(True, 11), (False, 13)])
    for index, slot in enumerate(baltimore):
        slot.update(rating=b_ratings[index], years=b_years[index], new_patients=b_new[index], virtual=b_virtual[index], medicare=b_medicare[index], medicaid=b_medicaid[index])


def _assign_names(slots: list[dict]) -> None:
    surnames = list(SURNAMES)
    RNG.shuffle(surnames)
    males, females, neutrals = list(MALE_FIRST), list(FEMALE_FIRST), list(NEUTRAL_FIRST)
    RNG.shuffle(males)
    RNG.shuffle(females)
    RNG.shuffle(neutrals)
    cursors = {"m": 0, "f": 0, "n": 0}
    pools = {"m": males, "f": females, "n": neutrals}
    for index, slot in enumerate(slots):
        pool = pools[slot["gender"]]
        slot["first"] = pool[cursors[slot["gender"]] % len(pool)]
        cursors[slot["gender"]] += 1
        slot["last"] = surnames[index]
    # deliberate surname collisions (same specialty, different city or first name)
    for spec_name, city_a, city_b in SURNAME_COLLISIONS:
        a_candidates = [s for s in slots if s["specialty"] == spec_name and s["city"] == city_a]
        b_candidates = [s for s in slots if s["specialty"] == spec_name and s["city"] == city_b and s is not a_candidates[0]]
        doctor_a = a_candidates[0]
        doctor_b = b_candidates[-1]
        doctor_b["last"] = doctor_a["last"]
    # make sure the same first+last never repeats
    seen: set[tuple[str, str]] = set()
    for slot in slots:
        key = (slot["first"], slot["last"])
        while key in seen:
            pool = pools[slot["gender"]]
            slot["first"] = pool[cursors[slot["gender"]] % len(pool)]
            cursors[slot["gender"]] += 1
            key = (slot["first"], slot["last"])
        seen.add(key)


def _build_doctors(vocab: dict, hospitals: dict[str, list[Hospital]], practices: dict[str, list[tuple[Practice, str | None]]], used_phones: set[str]) -> list[Doctor]:
    specialties = vocab["specialties"]
    cities = vocab["cities"]
    slots = _doctor_slots()
    _assign_quotas(slots)
    _assign_names(slots)
    area_by_city = {row[0]: row[9] for row in CITIES}
    used_npis: set[str] = set()
    used_slugs: set[str] = set()
    practice_load: dict[int, int] = {}
    secondary_load: dict[int, int] = {}
    hospital_load: dict[int, int] = {}
    doctors: list[Doctor] = []
    for slot in slots:
        spec_name = slot["specialty"]
        city_name = slot["city"]
        specialty = specialties[spec_name]
        years = slot["years"]
        graduation_year = MIRROR_REFERENCE_DATE.year - years - RNG.randint(0, 1)
        degree = "DO" if RNG.random() < 0.2 else "MD"
        secondary = None
        if RNG.random() < 0.3:
            secondary = specialties[RNG.choice(SECONDARY_CHOICES[spec_name])]
        hospital = None
        if RNG.random() < 0.75:
            hospital = min(hospitals[city_name], key=lambda h: (hospital_load.get(h.id, 0), h.id))
            hospital_load[hospital.id] = hospital_load.get(hospital.id, 0) + 1
        while True:
            npi = "1" + "".join(str(RNG.randint(0, 9)) for _ in range(9))
            if npi not in used_npis:
                used_npis.add(npi)
                break
        while True:
            slug = f"{slugify(slot['first'])}-{slugify(slot['last'])}-{RNG.getrandbits(32):08x}"
            if slug not in used_slugs:
                used_slugs.add(slug)
                break
        # practice: prefer a focus-matching practice with room, else the least-loaded general one
        options = practices[city_name]
        focus_matches = [p for p, focus in options if focus == spec_name and practice_load.get(p.id, 0) < 10]
        if focus_matches:
            practice = focus_matches[0]
        else:
            general = [p for p, focus in options if focus is None and practice_load.get(p.id, 0) < 12]
            candidates = general or [p for p, _f in options]
            practice = min(candidates, key=lambda p: (practice_load.get(p.id, 0), p.id))
        practice_load[practice.id] = practice_load.get(practice.id, 0) + 1
        enhanced = slot["tier"] == "Enhanced"
        doctor = Doctor(
            slug=slug,
            prefix="Dr.",
            first_name=slot["first"],
            last_name=slot["last"],
            degree=degree,
            gender=slot["gender"],
            profile_type=slot["tier"],
            primary_specialty_id=specialty.id,
            secondary_specialty_id=secondary.id if secondary else None,
            hospital_id=hospital.id if hospital else None,
            avg_rating=slot["rating"],
            ratings_count=0,
            text_review_count=0,
            years_experience=years,
            graduation_year=graduation_year,
            medical_school=RNG.choice(MEDICAL_SCHOOLS),
            accepting_new_patients=slot["new_patients"],
            virtual_visit=slot["virtual"],
            npi=npi,
            overview_text="",
            bio_html=None,
            avg_wait_minutes=RNG.choice([5, 10, 15, 20, 25, 30, 35, 40, 45]) if enhanced else None,
            callout_label=None,
            video_poster_file=f"images/posters/{slug}.png" if enhanced else None,
            next_available_label=f"{RNG.choice(['Thu, Sep 10', 'Fri, Sep 11', 'Mon, Sep 14', 'Tue, Sep 15'])} @ {RNG.choice(['9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM', '11:00 AM'])}" if enhanced else None,
            website_url=practice.website if enhanced else None,
        )
        db.session.add(doctor)
        db.session.flush()
        doctor._slot = slot  # transient, seed-time only
        doctor._practice = practice
        # primary location
        city = cities[city_name]
        lat, lon = jitter(city.lat, city.lon)
        primary = Location(
            doctor_id=doctor.id,
            practice_id=practice.id,
            name=practice.name,
            street=practice.street,
            city_id=city.id,
            zip=practice.zip,
            lat=lat,
            lon=lon,
            phone=practice.phone,
            is_primary=True,
            medicare=slot["medicare"],
            medicaid=slot["medicaid"],
            new_patients=slot["new_patients"],
        )
        apply_hours(primary, RNG.choice(HOURS_PATTERNS))
        db.session.add(primary)
        # secondary locations (0 / 1 / 2) in another seeded city of the same state
        extra = 0
        roll = RNG.random()
        if roll < 0.10:
            extra = 2
        elif roll < 0.40:
            extra = 1
        same_state = [name for name, *_rest in CITIES if cities[name].state == city.state and name != city_name] or [city_name]
        for _ in range(extra):
            other_name = RNG.choice(same_state)
            other_city = cities[other_name]
            other_options = practices[other_name]
            other_focus = [p for p, focus in other_options if focus == spec_name and secondary_load.get(p.id, 0) < 6]
            other_general = [p for p, focus in other_options if focus is None and secondary_load.get(p.id, 0) < 8]
            candidates = other_focus or other_general or [p for p, _f in other_options]
            other_practice = min(candidates, key=lambda p: (secondary_load.get(p.id, 0), p.id))
            secondary_load[other_practice.id] = secondary_load.get(other_practice.id, 0) + 1
            o_lat, o_lon = jitter(other_city.lat, other_city.lon)
            location = Location(
                doctor_id=doctor.id,
                practice_id=other_practice.id,
                name=f"{other_practice.name} - {RNG.choice(SECONDARY_OFFICE_TAGS)}",
                street=f"{RNG.randint(100, 4999)} {RNG.choice(SECONDARY_STREETS)} {RNG.choice(STREET_TYPES)}",
                city_id=other_city.id,
                zip=RNG.choice([z.zip for z in other_city.zips]),
                lat=o_lat,
                lon=o_lon,
                phone=phone(area_by_city[other_name], used_phones),
                is_primary=False,
                medicare=RNG.random() < 0.6,
                medicaid=RNG.random() < 0.4,
                new_patients=RNG.random() < 0.7,
            )
            apply_hours(location, RNG.choice(HOURS_PATTERNS))
            db.session.add(location)
        doctors.append(doctor)
    db.session.flush()
    return doctors


def _build_doctor_children(doctors: list[Doctor], vocab: dict) -> None:
    specialties = vocab["specialties"]
    spec_by_id = {row.id: name for name, row in specialties.items()}
    conditions = vocab["conditions"]
    procedures = vocab["procedures"]
    areas = vocab["areas"]
    insurers = vocab["insurers"]
    other_specs = {name: list(RELATED_SPECIALTIES[name]) for name, *_rest in SPECIALTIES}
    tiers = ["Similar", "More Often", "More Than Most"]
    used_review_texts: set[str] = set()
    for doctor in doctors:
        spec_name = spec_by_id[doctor.primary_specialty_id]
        slot = doctor._slot
        practice = doctor._practice
        city_name = slot["city"]
        # conditions: 2 own + 4-8 from other specialties
        own = RNG.sample(conditions[spec_name], 2)
        related_pool = [c for other in other_specs[spec_name] for c in conditions[other]]
        extras = RNG.sample(related_pool, RNG.randint(4, min(7, len(related_pool))))
        ordered = own + extras
        for position, condition in enumerate(ordered, start=1):
            tier = RNG.choices(tiers, weights=[35, 35, 30])[0]
            db.session.add(DoctorCondition(doctor_id=doctor.id, condition_id=condition.id, tier=tier, position=position))
        # procedures: 1-2 own + 3-5 other
        own_procs = RNG.sample(procedures[spec_name], RNG.randint(1, 2))
        related_procs = [q for other in other_specs[spec_name] for q in procedures[other]]
        other_procs = RNG.sample(related_procs, RNG.randint(3, min(5, len(related_procs))))
        for position, procedure in enumerate(own_procs + other_procs, start=1):
            tier = RNG.choices(tiers, weights=[35, 35, 30])[0]
            db.session.add(DoctorProcedure(doctor_id=doctor.id, procedure_id=procedure.id, tier=tier, position=position))
        # expertise 2-4 own areas
        for position, area in enumerate(RNG.sample(areas[spec_name], RNG.randint(2, 4)), start=1):
            db.session.add(DoctorExpertise(doctor_id=doctor.id, area_id=area.id, position=position))
        # insurers 4-9 (weighted), base plan always + 40 % of the extra plans
        count = RNG.randint(4, 9)
        chosen = weighted_sample(insurers, [weight for _i, weight, _p in insurers], count)
        chosen.sort(key=lambda entry: entry[0].id)
        for _insurer, _weight, plans in chosen:
            db.session.add(DoctorInsurance(doctor_id=doctor.id, plan_id=plans[0].id, is_verified=True))
            for plan in plans[1:]:
                if RNG.random() < 0.4:
                    db.session.add(DoctorInsurance(doctor_id=doctor.id, plan_id=plan.id, is_verified=RNG.random() < 0.85))
        # reviews
        review_count = 0 if doctor.avg_rating is None else RNG.randint(3, 8)
        review_dates: set[date] = set()
        reviews: list[Review] = []
        topic_pool = [c.name for c in ordered[:4]]
        for _ in range(review_count):
            base = doctor.avg_rating
            rating = int(min(5, max(1, round(base + RNG.choice([-1, -0.5, 0, 0, 0, 0.5, 1])))))
            while True:
                review_date = random_date(date(2022, 1, 4), date(2026, 8, 28))
                if review_date not in review_dates:
                    review_dates.add(review_date)
                    break
            text_value = _unique_review_text(rating, doctor, practice, city_name, topic_pool, used_review_texts)
            good = rating >= 4
            criteria = {f"c{i}": (1 if (good or RNG.random() < 0.5) else 0) for i in range(1, 8)}
            reviews.append(Review(
                doctor_id=doctor.id,
                rating=rating,
                text=text_value,
                review_date=review_date,
                helpful_count=RNG.randint(0, 12),
                wait_bucket=RNG.choice(WAIT_BUCKETS),
                is_featured=False,
                **criteria,
            ))
        reviews.sort(key=lambda r: r.review_date)
        if len(reviews) >= 2 and RNG.random() < 0.6:
            candidates = [r for r in reviews[1:] if r.rating >= 4]
            if candidates:
                candidates[-1].is_featured = True
        db.session.add_all(reviews)
        doctor.text_review_count = review_count
        doctor.ratings_count = 0 if doctor.avg_rating is None else review_count + RNG.randint(0, 120)
        # patients' perspective
        best_label = None
        best_value = -1
        for criterion in range(1, 8):
            if doctor.ratings_count == 0:
                did_well, needs = 0, 0
            else:
                did_well = RNG.randint(max(0, doctor.ratings_count - 40), doctor.ratings_count)
                needs = RNG.randint(0, max(0, int(doctor.ratings_count * (1 - (doctor.avg_rating or 3) / 5.5))))
            db.session.add(DoctorPerspective(doctor_id=doctor.id, criterion=criterion, did_well=did_well, needs_improvement=needs))
            if did_well > best_value:
                best_value, best_label = did_well, PERSPECTIVE_CRITERIA[criterion - 1]
        doctor.callout_label = best_label if doctor.is_enhanced and doctor.ratings_count else None
        # certifications, licenses, education, languages
        spec_row = next(row for row in SPECIALTIES if row[0] == spec_name)
        residency_year = min(doctor.graduation_year + RNG.randint(3, 5), MIRROR_REFERENCE_DATE.year)
        cert_year = min(residency_year + RNG.randint(0, 2), MIRROR_REFERENCE_DATE.year)
        db.session.add(Certification(doctor_id=doctor.id, issuer=spec_row[4], cert_type=spec_row[5], year=cert_year))
        if RNG.random() < 0.3:
            db.session.add(Certification(doctor_id=doctor.id, issuer=spec_row[4], cert_type=spec_row[6], year=min(cert_year + RNG.randint(1, 6), MIRROR_REFERENCE_DATE.year)))
        state_name = doctor.primary_location.city.state_name
        license_type = "Doctor of Osteopathic Medicine" if doctor.degree == "DO" else "Doctor of Medicine"
        db.session.add(License(doctor_id=doctor.id, license_type=license_type, state=state_name, expiry_date=random_date(date(2026, 10, 1), date(2031, 12, 31)), status="Active"))
        if RNG.random() < 0.35:
            other_state = RNG.choice([n for n in ("Delaware", "Maryland", "Pennsylvania", "New Jersey") if n != state_name])
            db.session.add(License(doctor_id=doctor.id, license_type=license_type, state=other_state, expiry_date=random_date(date(2026, 10, 1), date(2031, 12, 31)), status="Active"))
        db.session.add(Education(doctor_id=doctor.id, kind="Medical School", institution=doctor.medical_school, year=doctor.graduation_year))
        db.session.add(Education(doctor_id=doctor.id, kind="Residency", institution=RNG.choice(TRAINING_HOSPITALS), year=residency_year))
        if RNG.random() < 0.5:
            db.session.add(Education(doctor_id=doctor.id, kind="Fellowship", institution=RNG.choice(TRAINING_HOSPITALS), year=min(residency_year + RNG.randint(1, 3), MIRROR_REFERENCE_DATE.year)))
        db.session.add(DoctorLanguage(doctor_id=doctor.id, language="English", position=1))
        if RNG.random() < 0.45:
            db.session.add(DoctorLanguage(doctor_id=doctor.id, language=RNG.choice(LANGUAGES), position=2))
        # overview + bio (vocabulary-restricted opener)
        doctor.overview_text = _overview_text(doctor, spec_name, practice, city_name)
        if doctor.is_enhanced:
            doctor.bio_html = _bio_html(doctor, spec_name, practice, city_name, ordered[:6], own_procs + other_procs, [a.name for a in areas[spec_name]])
        # satisfaction poll counts (display-only)
        for index in range(1, 6):
            yes = RNG.randint(0, max(0, doctor.ratings_count // 3))
            no = RNG.randint(0, max(0, yes // 4))
            setattr(doctor, f"poll_q{index}_yes", yes)
            setattr(doctor, f"poll_q{index}_no", no)
    db.session.flush()


def _unique_review_text(rating: int, doctor: Doctor, practice: Practice, city_name: str, topics: list[str], used: set[str]) -> str:
    for attempt in range(40):
        template = RNG.choice(REVIEW_TEMPLATES[rating])
        text_value = template.format(
            doctor=doctor.short_name,
            practice=practice.name,
            city=city_name,
            topic=RNG.choice(topics).lower() if topics else "condition",
            wait=RNG.choice(REVIEW_WAIT),
            staff=RNG.choice(REVIEW_STAFF),
            visit=RNG.choice(REVIEW_VISIT),
            n=RNG.randint(2, 9),
        )
        if attempt >= 20:
            text_value += RNG.choice(REVIEW_TAILS)
        if text_value not in used:
            used.add(text_value)
            return text_value
    raise RuntimeError("could not produce a unique review text")


def _overview_text(doctor: Doctor, spec_name: str, practice: Practice, city_name: str) -> str:
    template = RNG.choice(OVERVIEW_TEMPLATES)
    pronoun = doctor.pronoun
    return template.format(
        full=doctor.full_name,
        specialty=spec_name,
        specialty_lower=spec_name.lower(),
        practice=practice.name,
        city=city_name,
        state=doctor.primary_location.city.state,
        years=doctor.years_experience,
        pronoun=pronoun,
        Pronoun=pronoun.capitalize(),
    )


def _bio_html(doctor: Doctor, spec_name: str, practice: Practice, city_name: str, conditions, procedures, areas: list[str]) -> str:
    pronoun = doctor.pronoun
    focus = RNG.sample(areas, 2)
    paragraphs = [
        f"<p><strong>Meet {doctor.full_name}:</strong></p>",
        f"<p>{doctor.overview_text}</p>",
        f"<p>{doctor.possessive.capitalize()} clinical interests include {focus[0].lower()} and {focus[1].lower()}, with a particular focus on {conditions[0].name.lower()} and {conditions[1].name.lower()}.</p>",
        "<p>" + RNG.choice(BIO_PHILOSOPHY).format(Short=doctor.short_name, short=doctor.short_name, Pronoun_cap=pronoun.capitalize()) + "</p>",
        f"<p><strong>{doctor.short_name} sees patients for</strong></p>",
        "<ul>" + "".join(f"<li>{c.name}</li>" for c in conditions[:5]) + "".join(f"<li>{p.name}</li>" for p in procedures[:2]) + "</ul>",
        "<p>" + RNG.choice(BIO_CLOSING).format(
            Short=doctor.short_name,
            short=doctor.short_name,
            city=city_name,
            practice=practice.name,
            accepting="currently accepting new patients" if doctor.accepting_new_patients else "not currently accepting new patients",
            visit_style="in-person and video visits" if doctor.virtual_visit else "in-person visits",
        ) + "</p>",
    ]
    return "\n".join(paragraphs)


def _ensure_similar_tiers() -> None:
    """Every condition / procedure facet keeps at least two doctors tiered "Similar"."""
    for model, key in ((DoctorCondition, "condition_id"), (DoctorProcedure, "procedure_id")):
        rows = model.query.order_by(model.id).all()
        by_target: dict[int, list] = {}
        for row in rows:
            by_target.setdefault(getattr(row, key), []).append(row)
        for target_id in sorted(by_target):
            linked = by_target[target_id]
            similar = [row for row in linked if row.tier == "Similar"]
            for row in linked:
                if len(similar) >= 2:
                    break
                if row.tier != "Similar" and row.position > 5:
                    row.tier = "Similar"
                    similar.append(row)
            for row in linked:
                if len(similar) >= 2:
                    break
                if row.tier != "Similar":
                    row.tier = "Similar"
                    similar.append(row)
    db.session.flush()


def _build_awards(doctors: list[Doctor], vocab: dict) -> None:
    """Patient's Choice = highest-rated doctor of each (specialty, city) cell with >= 6 doctors;
    Elite / Provider drawn from the remaining highly rated doctors."""
    spec_by_id = {row.id: name for name, row in vocab["specialties"].items()}
    cells: dict[tuple[str, str], list[Doctor]] = {}
    for doctor in doctors:
        key = (spec_by_id[doctor.primary_specialty_id], doctor._slot["city"])
        cells.setdefault(key, []).append(doctor)
    awarded: set[int] = set()
    years = [2024, 2025, 2026]
    for key in sorted(cells):
        members = [d for d in cells[key] if d.avg_rating is not None and d._slot["city"] != "Baltimore"]
        if len(cells[key]) < 6:
            continue
        best = sorted(members, key=lambda d: (-d.avg_rating, -d.ratings_count, d.id))[0]
        db.session.add(Award(doctor_id=best.id, award_class="Patient", year=RNG.choice(years)))
        awarded.add(best.id)
    remaining = [d for d in doctors if d.id not in awarded and d.avg_rating is not None and d.avg_rating >= 4.3]
    remaining.sort(key=lambda d: d.id)
    elite = RNG.sample(remaining, 16)
    for doctor in elite:
        db.session.add(Award(doctor_id=doctor.id, award_class="Elite", year=RNG.choice(years)))
        awarded.add(doctor.id)
    remaining = [d for d in doctors if d.id not in awarded and d.avg_rating is not None and d.avg_rating >= 4.0]
    remaining.sort(key=lambda d: d.id)
    for doctor in RNG.sample(remaining, 16):
        db.session.add(Award(doctor_id=doctor.id, award_class="Provider", year=RNG.choice(years)))
    db.session.flush()


def _finish_hubs(hospital_rows: list[Hospital], practice_rows: list[Practice]) -> None:
    for hospital in hospital_rows:
        doctors = list(hospital.doctors)
        specialties = {d.primary_specialty_id for d in doctors}
        hospital.overview_text = HOSPITAL_OVERVIEW.format(name=hospital.name, n=len(doctors), s=len(specialties))
        rated = [d.avg_rating for d in doctors if d.avg_rating is not None]
        if rated and RNG.random() < 0.7:
            hospital.avg_rating = round(sum(rated) / len(rated), 1)
            hospital.ratings_count = RNG.randint(1, 40)
        for index in range(1, 6):
            yes = RNG.randint(0, 25)
            setattr(hospital, f"poll_q{index}_yes", yes)
            setattr(hospital, f"poll_q{index}_no", RNG.randint(0, max(0, yes // 3)))
    for practice in practice_rows:
        doctor_ids = sorted({loc.doctor_id for loc in practice.locations})
        doctors = [db.session.get(Doctor, doctor_id) for doctor_id in doctor_ids]
        specialties = {d.primary_specialty_id for d in doctors}
        practice.overview_text = PRACTICE_OVERVIEW.format(name=practice.name, n=len(doctors), s=len(specialties))
        rated = [d.avg_rating for d in doctors if d.avg_rating is not None]
        if rated and RNG.random() < 0.6:
            practice.avg_rating = round(sum(rated) / len(rated), 1)
            practice.ratings_count = RNG.randint(1, 30)
        for index in range(1, 6):
            yes = RNG.randint(0, 15)
            setattr(practice, f"poll_q{index}_yes", yes)
            setattr(practice, f"poll_q{index}_no", RNG.randint(0, max(0, yes // 3)))
    db.session.flush()


# --------------------------------------------------------------------------- #
# Seed entry points (whole-function gates)
# --------------------------------------------------------------------------- #
def _topup_languages(doctors: list[Doctor]) -> None:
    """Physicians who cover three offices are seeded as multilingual (English + two more).
    Deterministic in the doctor id — consumes no RNG, so it can run after every other builder."""
    for doctor in doctors:
        if len(doctor.locations) < 3:
            continue
        spoken = {row.language for row in doctor.languages}
        position = len(doctor.languages) + 1
        for offset in (7, 11):
            language = LANGUAGES[(doctor.id * offset + offset) % len(LANGUAGES)]
            if language in spoken or position > 3:
                continue
            db.session.add(DoctorLanguage(doctor_id=doctor.id, language=language, position=position))
            spoken.add(language)
            position += 1
    db.session.flush()


def _sync_public_payer_rows(doctors: list[Doctor]) -> None:
    """The Medicare / Medicaid entries of the profile's Insurance card follow the primary office's
    Accepts-Medicare / Accepts-Medicaid flags (the values the results filter and the practice page
    use). Deterministic, consumes no RNG, so it runs after every other builder."""
    payer_plans = {}
    for insurer in Insurer.query.filter(Insurer.slug.in_(("medicare", "medicaid"))).order_by(Insurer.id).all():
        payer_plans[insurer.slug] = InsurancePlan.query.filter_by(insurer_id=insurer.id).order_by(InsurancePlan.id).all()
    for doctor in doctors:
        primary = next(location for location in doctor.locations if location.is_primary)
        for slug, accepted in (("medicare", primary.medicare), ("medicaid", primary.medicaid)):
            plan_ids = {plan.id for plan in payer_plans[slug]}
            rows = [row for row in doctor.insurances if row.plan_id in plan_ids]
            if accepted and not rows:
                db.session.add(DoctorInsurance(doctor_id=doctor.id, plan_id=payer_plans[slug][0].id, is_verified=True))
            elif not accepted:
                for row in rows:
                    db.session.delete(row)
    db.session.flush()


def _assign_office_lines(doctors: list[Doctor]) -> None:
    """Every office gets its own direct line: primary offices were seeded with the practice's main
    number, which would surface a Basic doctor's office phone on colleagues' cards. Deterministic
    in the location id (no RNG); numbers stay unique across hospitals, practices and offices."""
    used = {row.phone for row in Hospital.query.all()} | {row.phone for row in Practice.query.all()}
    used |= {row.phone for row in Location.query.all()}
    for location in Location.query.order_by(Location.id).all():
        practice = location.practice
        if location.phone != practice.phone:
            continue
        area, last4 = practice.phone[1:4], int(practice.phone[-4:])
        step = 0
        while True:
            candidate = f"({area}) 555-{(last4 + 37 * location.id + 101 * step) % 9000 + 1000:04d}"
            if candidate not in used:
                break
            step += 1
        used.add(candidate)
        location.phone = candidate
    db.session.flush()


def _unify_practice_hours() -> None:
    """A practice publishes one schedule and every office located at it posts the same hours.
    The site schedule is the longest weekly schedule among the offices at the practice (ties by
    location id), so a practice never contradicts its own offices. No RNG."""
    def minutes(value: str | None) -> int:
        if not value:
            return 0
        clock, meridiem = value.split(" ")
        hours, mins = (int(part) for part in clock.split(":"))
        return (hours % 12 + (12 if meridiem == "pm" else 0)) * 60 + mins

    def weekly(target) -> int:
        return sum(max(0, minutes(getattr(target, f"{key}_close")) - minutes(getattr(target, f"{key}_open"))) for key in DAY_KEYS)

    def pattern(target) -> tuple:
        return tuple(getattr(target, f"{key}_{edge}") for key in DAY_KEYS for edge in ("open", "close"))

    for practice in Practice.query.order_by(Practice.id).all():
        offices = sorted(practice.locations, key=lambda row: row.id)
        if not offices:
            continue
        site = max(offices, key=lambda row: (weekly(row), -row.id))
        values = pattern(site)
        for target in [practice, *offices]:
            for (key, edge), value in zip(((key, edge) for key in DAY_KEYS for edge in ("open", "close")), values):
                setattr(target, f"{key}_{edge}", value)
    db.session.flush()


def _bound_perspective_votes(doctors: list[Doctor]) -> None:
    """Patients' Perspective votes are bounded by the doctor's ratings: per criterion,
    did-well + needs-improvement <= ratings_count, and each side is at least the number of
    visible reviews that marked it that way. No RNG."""
    for doctor in doctors:
        total = doctor.ratings_count
        for row in doctor.perspectives:
            marks = [getattr(review, f"c{row.criterion}") for review in doctor.reviews]
            visible_yes = sum(1 for mark in marks if mark == 1)
            visible_no = len(marks) - visible_yes
            row.did_well = max(visible_yes, min(row.did_well, total - visible_no))
            row.needs_improvement = max(visible_no, min(row.needs_improvement, total - row.did_well))
    db.session.flush()


def seed_database(force: bool = False) -> None:
    if Doctor.query.count() > 0 and not force:
        return
    RNG.seed(SEED)
    used_phones: set[str] = set()
    vocab = _build_vocabulary()
    hospitals = _build_hospitals(vocab["cities"], used_phones)
    practices = _build_practices(vocab["cities"], used_phones)
    doctors = _build_doctors(vocab, hospitals, practices, used_phones)
    _build_doctor_children(doctors, vocab)
    _ensure_similar_tiers()
    _build_awards(doctors, vocab)
    _finish_hubs(Hospital.query.order_by(Hospital.id).all(), Practice.query.order_by(Practice.id).all())
    _topup_languages(doctors)
    _sync_public_payer_rows(doctors)
    _assign_office_lines(doctors)
    _unify_practice_hours()
    _bound_perspective_votes(doctors)
    for doctor in doctors:
        del doctor._slot
        del doctor._practice


def seed_benchmark_users(force: bool = False) -> None:
    if User.query.count() > 0 and not force:
        return
    users: dict[str, User] = {}
    for email, display, dob in BENCHMARK_USERS:
        user = User(email=email, password_hash=DEMO_PASSWORD_HASHES[email], dob=dob, display_name=display, created_at=USER_CREATED_AT)
        db.session.add(user)
        users[email] = user
    db.session.flush()
    specialties = {row.name: row for row in Specialty.query.all()}

    def nth_doctor(spec_name: str, n: int, **filters) -> Doctor:
        rows = Doctor.query.filter_by(primary_specialty_id=specialties[spec_name].id, **filters).order_by(Doctor.id).all()
        return rows[n]

    alice = users["alice.j@test.com"]
    # exactly one Dermatologist among Alice's three saved providers
    alice_saved = [
        (nth_doctor("Dermatology", 4), datetime(2026, 7, 2, 18, 5, 0)),
        (nth_doctor("Family Medicine", 6), datetime(2026, 7, 19, 8, 41, 0)),
        (nth_doctor("Neurology", 3), datetime(2026, 8, 6, 12, 27, 0)),
    ]
    for doctor, saved_at in alice_saved:
        db.session.add(SavedProvider(user_id=alice.id, doctor_id=doctor.id, saved_at=saved_at))
    bob = users["bob.c@test.com"]
    db.session.add(SavedProvider(user_id=bob.id, doctor_id=nth_doctor("Cardiovascular Disease", 2).id, saved_at=datetime(2026, 8, 11, 16, 48, 0)))
    enhanced = nth_doctor("Gastroenterology", 1, profile_type="Enhanced")
    booking = AppointmentRequest(
        user_id=alice.id,
        doctor_id=enhanced.id,
        location_id=enhanced.primary_location.id,
        patient_type="Returning Patient",
        slot_date=date(2026, 9, 11),
        slot_time="9:30 AM",
        reference="pending",
        created_at=datetime(2026, 8, 20, 9, 12, 0),
    )
    db.session.add(booking)
    db.session.flush()
    booking.reference = confirmation_reference(booking.id)
    reviewed = nth_doctor("Family Medicine", 6)
    db.session.add(UserReview(
        user_id=alice.id,
        doctor_id=reviewed.id,
        rating=4,
        c1=1, c2=1, c3=0, c4=1, c5=1, c6=1, c7=0,
        text="Thorough annual visit and clear answers about my lab results; scheduling the follow-up took two calls.",
        status="Pending review",
        created_at=datetime(2026, 8, 22, 14, 3, 0),
    ))
    db.session.flush()


# --------------------------------------------------------------------------- #
# Build-time invariant checks (gitignored scripts_dev/assert_distractors.py)
# --------------------------------------------------------------------------- #
def _load_distractor_checks():
    path = BASE_DIR / "scripts_dev" / "assert_distractors.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("webmd_doctor_assert_distractors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assert_distractors


def _current_counts() -> dict[str, int]:
    models = {
        "specialties": Specialty, "conditions": Condition, "procedures": Procedure, "expertise_areas": ExpertiseArea,
        "insurers": Insurer, "insurance_plans": InsurancePlan, "cities": City, "city_zips": CityZip,
        "hospitals": Hospital, "practices": Practice, "doctors": Doctor, "locations": Location,
        "doctor_conditions": DoctorCondition, "doctor_procedures": DoctorProcedure, "doctor_expertise": DoctorExpertise,
        "doctor_insurances": DoctorInsurance, "reviews": Review, "doctor_perspectives": DoctorPerspective,
        "certifications": Certification, "licenses": License, "education": Education, "awards": Award,
        "doctor_languages": DoctorLanguage, "users": User, "saved_providers": SavedProvider,
        "appointment_requests": AppointmentRequest, "user_reviews": UserReview,
    }
    return {key: model.query.count() for key, model in models.items()}


def _seed_is_complete() -> bool:
    marker = db.session.get(SeedMetadata, "version")
    counts = _current_counts()
    core_match = all(counts[key] == EXPECTED_COUNTS[key] for key in CORE_COUNT_KEYS)
    benchmark_emails = {email for email, _d, _b in BENCHMARK_USERS}
    present = {row.email for row in User.query.filter(User.email.in_(benchmark_emails)).all()}
    return marker is not None and marker.value == SEED_VERSION and core_match and present == benchmark_emails


def _database_has_seed_rows() -> bool:
    return any(_current_counts().values()) or SeedMetadata.query.count() > 0


def _validate_seed() -> None:
    counts = _current_counts()
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"seed row counts differ: expected={EXPECTED_COUNTS}, actual={counts}")
    violations = db.session.execute(text("PRAGMA foreign_key_check")).all()
    if violations:
        raise RuntimeError(f"seed foreign-key violations: {violations[:5]}")


def ensure_seed_database() -> None:
    if _seed_is_complete():
        return
    if _database_has_seed_rows():
        raise RuntimeError("webmd_doctor database is partial, unversioned, or from another seed version")
    try:
        seed_database(force=True)
        seed_benchmark_users(force=True)
        _validate_seed()
        db.session.add(SeedMetadata(key="version", value=SEED_VERSION))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# --------------------------------------------------------------------------- #
# Generated images (deterministic PNG bytes, no text chunks). Local freezer
# only (`seed_data.py --write-images`): the Docker build never calls this;
# the PNGs are fetched from the pinned Hugging Face tarball.
# --------------------------------------------------------------------------- #
AVATAR_PALETTE = [
    (0, 21, 124), (53, 87, 255), (14, 116, 144), (99, 64, 178), (27, 94, 32), (150, 63, 122),
    (180, 83, 9), (0, 105, 92), (71, 85, 105), (120, 40, 40), (34, 64, 140), (88, 110, 40),
]


def _initials_font(size: int):
    from PIL import ImageFont

    return ImageFont.load_default(size=size)


def _save_png(image, path: Path) -> None:
    # Fixed compression, no tIME / tEXt / zTXt chunks: the bytes depend only on the pixels.
    image.save(path, format="PNG", optimize=False, compress_level=9, pnginfo=None)


def write_images(doctors: list[Doctor]) -> None:
    from PIL import Image, ImageDraw

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    for stale in sorted(AVATAR_DIR.glob("*.png")) + sorted(POSTER_DIR.glob("*.png")):
        stale.unlink()
    font_large = _initials_font(58)
    font_poster = _initials_font(72)
    for doctor in sorted(doctors, key=lambda d: d.id):
        initials = (doctor.first_name[:1] + doctor.last_name[:1]).upper()
        colour = AVATAR_PALETTE[doctor.id % len(AVATAR_PALETTE)]
        image = Image.new("RGB", (150, 150), (241, 246, 250))
        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, 149, 149), fill=colour)
        box = draw.textbbox((0, 0), initials, font=font_large)
        width, height = box[2] - box[0], box[3] - box[1]
        draw.text(((150 - width) / 2 - box[0], (150 - height) / 2 - box[1]), initials, fill=(255, 255, 255), font=font_large)
        _save_png(image, AVATAR_DIR / f"{doctor.slug}.png")
        if doctor.is_enhanced:
            poster = Image.new("RGB", (640, 360), (0, 6, 37))
            pdraw = ImageDraw.Draw(poster)
            for y in range(360):
                shade = int(6 + (y / 360) * 40)
                pdraw.line((0, y, 639, y), fill=(0, shade, 37 + shade))
            pdraw.ellipse((245, 105, 395, 255), fill=colour)
            box = pdraw.textbbox((0, 0), initials, font=font_poster)
            width, height = box[2] - box[0], box[3] - box[1]
            pdraw.text((320 - width / 2 - box[0], 180 - height / 2 - box[1]), initials, fill=(255, 255, 255), font=font_poster)
            pdraw.ellipse((560, 280, 620, 340), fill=(53, 87, 255))
            pdraw.polygon([(582, 296), (582, 324), (606, 310)], fill=(255, 255, 255))
            _save_png(poster, POSTER_DIR / f"{doctor.slug}.png")


def build_seed_database(write_images_too: bool = False) -> None:
    INSTANCE_SEED_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    destination = INSTANCE_SEED_DIR / "webmd_doctor.db"
    checks = _load_distractor_checks()
    try:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()
        with app.app_context():
            db.create_all()
            ensure_seed_database()
            if checks is not None:
                checks()
            if write_images_too:
                write_images(Doctor.query.order_by(Doctor.id).all())
            db.session.remove()
            with db.engine.connect() as connection:
                connection.execute(text("VACUUM"))
            db.engine.dispose()
        temporary = destination.with_suffix(".db.tmp")
        shutil.copyfile(DB_PATH, temporary)
        os.replace(temporary, destination)
    except Exception:
        destination.with_suffix(".db.tmp").unlink(missing_ok=True)
        DB_PATH.unlink(missing_ok=True)
        raise
    if checks is None:
        print("scripts_dev/assert_distractors.py not present - skipping the build-time task invariants.")


def build_images() -> None:
    """Local freezer entry point: regenerate the avatar / poster PNGs from the seed."""
    with app.app_context():
        db.create_all()
        ensure_seed_database()
        write_images(Doctor.query.order_by(Doctor.id).all())
        db.session.remove()
        db.engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild the deterministic WebMD Doctor seed.")
    parser.add_argument("--write-images", action="store_true",
                        help="also regenerate static/images/{avatars,posters}/ (local freezer only; "
                             "the Docker build ships them from the Hugging Face tarball)")
    args = parser.parse_args()
    build_seed_database(write_images_too=args.write_images)
    if args.write_images:
        print("Seed database, avatars and posters generated for WebMD Doctor.")
    else:
        print("Seed database generated for WebMD Doctor (images come from the HF asset tarball).")
