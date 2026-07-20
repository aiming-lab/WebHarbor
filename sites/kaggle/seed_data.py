"""Kaggle mirror — seed catalog data.

Plain Python data structures consumed by app.py's idempotent seed_*() functions.
No SQLAlchemy / Flask imports here so this module can be inspected standalone.

Kaggle's domain entities:
  User        — competitors with progression tiers + performance medals
  Competition — hosted ML challenges with prizes, leaderboards, deadlines
  Dataset     — community-uploaded datasets with usability scores
  Notebook    — public code (kernels), Python/R, optionally linked to a dataset
  Model       — pretrained models with framework + variations
  Course      — Kaggle Learn micro-courses
  Discussion  — forum threads across category forums

Everything here is deterministic — no randomness at module import or seed time,
so the byte-identical-reset invariant holds.
"""

# ----------------------------------------------------------------------------
# Controlled vocabularies
# ----------------------------------------------------------------------------
PERFORMANCE_TIERS = ["Novice", "Contributor", "Expert", "Master", "Grandmaster"]

COMPETITION_CATEGORIES = [
    "Featured", "Research", "Getting Started", "Playground",
    "Community", "Analytics",
]

DISCUSSION_FORUMS = [
    "General", "Getting Started", "Product Feedback",
    "Questions & Answers", "Competition Hosting", "Datasets",
]

ML_FRAMEWORKS = ["PyTorch", "TensorFlow", "JAX", "Keras", "scikit-learn", "Transformers"]

LICENSES = [
    "CC0: Public Domain", "CC BY-SA 4.0", "CC BY 4.0", "MIT",
    "Apache 2.0", "GPL 2", "Other (specified in description)",
    "Database: Open Database, Contents: Database Contents",
]

PROGRAMMING_LANGUAGES = ["Python", "R"]

# ----------------------------------------------------------------------------
# Users — competitors. `tiers` maps the four ranked categories to a tier.
# medals are lifetime (gold, silver, bronze) performance medals.
# The first four (alice/bob/carol/david) are the standard WebHarbor benchmark
# accounts; the rest are notable-style Grandmasters for catalog depth.
# ----------------------------------------------------------------------------
BENCHMARK_USERS = [
    {
        "email": "alice.j@test.com", "username": "alicejdata", "password": "TestPass123!",
        "display_name": "Alice Johnson", "tier": "Expert",
        "tiers": {"competitions": "Expert", "datasets": "Master", "notebooks": "Expert", "discussions": "Contributor"},
        "points": 48210, "gold": 1, "silver": 6, "bronze": 14,
        "location": "Seattle, United States", "occupation": "Data Scientist", "organization": "Cascadia Analytics",
        "bio": "ML practitioner focused on tabular modeling and feature engineering. Datasets Master.",
        "joined": "2019-03-11", "avatar": "alicejdata",
    },
    {
        "email": "bob.c@test.com", "username": "bobsmith_ml", "password": "TestPass123!",
        "display_name": "Bob Smith", "tier": "Contributor",
        "tiers": {"competitions": "Contributor", "datasets": "Contributor", "notebooks": "Novice", "discussions": "Novice"},
        "points": 9120, "gold": 0, "silver": 1, "bronze": 5,
        "location": "Manchester, United Kingdom", "occupation": "Student", "organization": "University of Manchester",
        "bio": "Learning the ropes — mostly Getting Started competitions and Kaggle Learn.",
        "joined": "2022-09-02", "avatar": "bobsmith_ml",
    },
    {
        "email": "carol.d@test.com", "username": "carolwong", "password": "TestPass123!",
        "display_name": "Carol Wong", "tier": "Master",
        "tiers": {"competitions": "Master", "datasets": "Expert", "notebooks": "Master", "discussions": "Expert"},
        "points": 102450, "gold": 4, "silver": 11, "bronze": 9,
        "location": "Singapore", "occupation": "Research Engineer", "organization": "DeepReef AI",
        "bio": "Computer vision and deep learning. Two-time competition gold medalist.",
        "joined": "2017-06-20", "avatar": "carolwong",
    },
    {
        "email": "david.k@test.com", "username": "davidtran", "password": "TestPass123!",
        "display_name": "David Tran", "tier": "Novice",
        "tiers": {"competitions": "Novice", "datasets": "Novice", "notebooks": "Novice", "discussions": "Novice"},
        "points": 320, "gold": 0, "silver": 0, "bronze": 0,
        "location": "Toronto, Canada", "occupation": "Software Engineer", "organization": "",
        "bio": "Just joined Kaggle to learn data science.",
        "joined": "2026-05-30", "avatar": "davidtran",
    },
]

NOTABLE_USERS = [
    {
        "username": "psi_grandmaster", "display_name": "Priya Sharma", "tier": "Grandmaster",
        "tiers": {"competitions": "Grandmaster", "datasets": "Master", "notebooks": "Grandmaster", "discussions": "Master"},
        "points": 312400, "gold": 19, "silver": 22, "bronze": 17, "comp_rank": 3,
        "location": "Bengaluru, India", "occupation": "Principal Data Scientist", "organization": "Helios Labs",
        "bio": "Competitions Grandmaster. Gradient boosting, stacking, and relentless cross-validation.",
        "joined": "2014-08-01", "avatar": "psi_grandmaster",
    },
    {
        "username": "kenji_cv", "display_name": "Kenji Watanabe", "tier": "Grandmaster",
        "tiers": {"competitions": "Grandmaster", "datasets": "Expert", "notebooks": "Master", "discussions": "Expert"},
        "points": 287600, "gold": 16, "silver": 25, "bronze": 12, "comp_rank": 7,
        "location": "Tokyo, Japan", "occupation": "Senior ML Engineer", "organization": "Sakura Vision",
        "bio": "Image segmentation and medical imaging specialist.",
        "joined": "2015-02-14", "avatar": "kenji_cv",
    },
    {
        "username": "datasmith_io", "display_name": "Lena Fischer", "tier": "Grandmaster",
        "tiers": {"competitions": "Master", "datasets": "Grandmaster", "notebooks": "Grandmaster", "discussions": "Grandmaster"},
        "points": 198750, "gold": 6, "silver": 14, "bronze": 31, "comp_rank": 41,
        "location": "Berlin, Germany", "occupation": "Data Engineer", "organization": "Open Data Collective",
        "bio": "Datasets & Notebooks Grandmaster. I publish clean, well-documented public datasets.",
        "joined": "2016-11-30", "avatar": "datasmith_io",
    },
    {
        "username": "marco_nlp", "display_name": "Marco Rossi", "tier": "Master",
        "tiers": {"competitions": "Master", "datasets": "Expert", "notebooks": "Master", "discussions": "Master"},
        "points": 121300, "gold": 3, "silver": 9, "bronze": 18, "comp_rank": 96,
        "location": "Milan, Italy", "occupation": "NLP Researcher", "organization": "Lingua Systems",
        "bio": "Natural language processing, transformers, and LLM fine-tuning.",
        "joined": "2018-04-22", "avatar": "marco_nlp",
    },
    {
        "username": "sara_timeseries", "display_name": "Sara Okafor", "tier": "Master",
        "tiers": {"competitions": "Master", "datasets": "Master", "notebooks": "Expert", "discussions": "Contributor"},
        "points": 88900, "gold": 2, "silver": 7, "bronze": 13, "comp_rank": 158,
        "location": "Lagos, Nigeria", "occupation": "Quantitative Analyst", "organization": "Sahel Capital",
        "bio": "Time-series forecasting and demand prediction.",
        "joined": "2018-12-05", "avatar": "sara_timeseries",
    },
    {
        "username": "tomeka_viz", "display_name": "Tomeka Banks", "tier": "Expert",
        "tiers": {"competitions": "Contributor", "datasets": "Expert", "notebooks": "Grandmaster", "discussions": "Expert"},
        "points": 76400, "gold": 1, "silver": 4, "bronze": 22, "comp_rank": 402,
        "location": "Atlanta, United States", "occupation": "Data Visualization Lead", "organization": "ClearChart",
        "bio": "Notebooks Grandmaster. I make EDA notebooks people actually read.",
        "joined": "2019-07-18", "avatar": "tomeka_viz",
    },
    {
        "username": "raul_gbm", "display_name": "Raúl Mendoza", "tier": "Grandmaster",
        "tiers": {"competitions": "Grandmaster", "datasets": "Contributor", "notebooks": "Expert", "discussions": "Master"},
        "points": 256100, "gold": 12, "silver": 19, "bronze": 21, "comp_rank": 12,
        "location": "Mexico City, Mexico", "occupation": "Kaggle Competitions Grandmaster", "organization": "",
        "bio": "Full-time competitor. LightGBM, XGBoost, and a lot of coffee.",
        "joined": "2015-09-09", "avatar": "raul_gbm",
    },
    {
        "username": "hosting_org_zindi", "display_name": "Global Health Data Initiative", "tier": "Contributor",
        "tiers": {"competitions": "Contributor", "datasets": "Master", "notebooks": "Novice", "discussions": "Contributor"},
        "points": 14200, "gold": 0, "silver": 2, "bronze": 6, "comp_rank": None,
        "location": "Geneva, Switzerland", "occupation": "Competition Host", "organization": "GHDI",
        "bio": "Non-profit hosting public-health ML challenges.",
        "joined": "2020-01-15", "avatar": "hosting_org_zindi", "is_org": True,
    },
]

# ----------------------------------------------------------------------------
# Competitions
# Each: slug, title, subtitle, category, host (org name), reward (display),
# reward_value (numeric USD for sorting; 0 for non-cash), metric, num_teams,
# deadline (ISO), tags, thumbnail key, description, owner_username (host acct).
# active=True means deadline in the future relative to the mirror clock.
# ----------------------------------------------------------------------------
COMPETITIONS = [
    {
        "slug": "spaceship-titanic-rescue",
        "title": "Spaceship Titanic: Predict the Rescued",
        "subtitle": "Predict which passengers were transported to an alternate dimension",
        "category": "Getting Started", "host": "Kaggle", "reward": "Knowledge", "reward_value": 0,
        "metric": "Classification Accuracy", "num_teams": 2841, "deadline": "2027-01-01",
        "tags": ["binary classification", "tabular", "beginner"], "thumbnail": "spaceship-titanic-rescue",
        "owner": "Kaggle",
        "description": "A beginner-friendly classification challenge. Given passenger records from the interstellar liner Spaceship Titanic, predict whether each passenger was transported to an alternate dimension during the disaster. Perfect for learning feature engineering and model validation.",
    },
    {
        "slug": "house-prices-advanced-regression",
        "title": "House Prices: Advanced Regression Techniques",
        "subtitle": "Predict final sale prices of residential homes in Ames, Iowa",
        "category": "Getting Started", "host": "Kaggle", "reward": "Knowledge", "reward_value": 0,
        "metric": "RMSE (log scale)", "num_teams": 4602, "deadline": "2027-01-01",
        "tags": ["regression", "tabular", "feature engineering"], "thumbnail": "house-prices-advanced-regression",
        "owner": "Kaggle",
        "description": "With 79 explanatory variables describing almost every aspect of residential homes, predict the final sale price. A classic regression competition that rewards careful feature engineering and ensembling.",
    },
    {
        "slug": "rsna-pneumonia-detection-2026",
        "title": "RSNA Pneumonia Detection Challenge 2026",
        "subtitle": "Detect pneumonia in chest radiographs",
        "category": "Featured", "host": "Radiological Society of North America", "reward": "$30,000", "reward_value": 30000,
        "metric": "Mean Average Precision (mAP)", "num_teams": 1187, "deadline": "2026-09-15",
        "tags": ["computer vision", "medical imaging", "object detection"], "thumbnail": "rsna-pneumonia-detection-2026",
        "owner": "kenji_cv",
        "description": "Build an algorithm to detect a visual signal for pneumonia in medical images. Each image may contain zero, one, or several bounding-box regions of opacity. Evaluation is mean average precision at multiple IoU thresholds.",
    },
    {
        "slug": "global-wheat-yield-forecast",
        "title": "Global Wheat Yield Forecast",
        "subtitle": "Forecast regional wheat yields from satellite and weather data",
        "category": "Research", "host": "FAO Agricultural Data Lab", "reward": "$75,000", "reward_value": 75000,
        "metric": "Root Mean Squared Error", "num_teams": 624, "deadline": "2026-08-01",
        "tags": ["regression", "time series", "geospatial", "climate"], "thumbnail": "global-wheat-yield-forecast",
        "owner": "sara_timeseries",
        "description": "Forecast end-of-season wheat yields for agricultural regions worldwide using multi-temporal satellite imagery, soil records, and weather station data. A research competition aimed at improving food-security planning.",
    },
    {
        "slug": "llm-prompt-recovery",
        "title": "LLM Prompt Recovery",
        "subtitle": "Recover the prompt used to transform a piece of text",
        "category": "Featured", "host": "Kaggle", "reward": "$50,000", "reward_value": 50000,
        "metric": "Mean Sharpened Cosine Similarity", "num_teams": 2210, "deadline": "2026-07-10",
        "tags": ["nlp", "llm", "text"], "thumbnail": "llm-prompt-recovery",
        "owner": "marco_nlp",
        "description": "Given an original text and its rewritten version, recover the natural-language instruction (prompt) that an LLM was given to perform the rewrite. Submissions are scored by sharpened cosine similarity between predicted and ground-truth prompt embeddings.",
    },
    {
        "slug": "store-sales-demand-forecasting",
        "title": "Store Sales — Time Series Forecasting",
        "subtitle": "Forecast grocery sales for thousands of product families",
        "category": "Playground", "host": "Kaggle", "reward": "Swag", "reward_value": 0,
        "metric": "Root Mean Squared Logarithmic Error", "num_teams": 1893, "deadline": "2026-12-31",
        "tags": ["time series", "regression", "retail"], "thumbnail": "store-sales-demand-forecasting",
        "owner": "Kaggle",
        "description": "Predict unit sales for thousands of items sold at different stores. Practice time-series feature engineering with promotions, holidays, and oil-price covariates. Monthly Playground-style challenge.",
    },
    {
        "slug": "malaria-cell-classification",
        "title": "Malaria Cell Image Classification",
        "subtitle": "Classify blood-smear cell images as infected or healthy",
        "category": "Featured", "host": "Global Health Data Initiative", "reward": "$25,000", "reward_value": 25000,
        "metric": "ROC AUC", "num_teams": 944, "deadline": "2026-06-30",
        "tags": ["computer vision", "medical imaging", "binary classification", "health"], "thumbnail": "malaria-cell-classification",
        "owner": "hosting_org_zindi",
        "description": "Classify segmented red-blood-cell images from thin blood smears as parasitized or uninfected. Hosted by a non-profit to accelerate low-cost malaria screening in the field.",
    },
    {
        "slug": "nyc-taxi-fare-prediction",
        "title": "New York City Taxi Fare Prediction",
        "subtitle": "Predict the fare of a NYC taxi ride",
        "category": "Playground", "host": "Kaggle", "reward": "Swag", "reward_value": 0,
        "metric": "Root Mean Squared Error", "num_teams": 1402, "deadline": "2026-11-20",
        "tags": ["regression", "tabular", "geospatial"], "thumbnail": "nyc-taxi-fare-prediction",
        "owner": "Kaggle",
        "description": "Predict taxi fare amounts in New York City from pickup/dropoff coordinates, timestamps, and passenger counts. A great playground for geospatial feature engineering.",
    },
    {
        "slug": "credit-default-risk-2026",
        "title": "Home Credit Default Risk 2026",
        "subtitle": "Predict how capable each applicant is of repaying a loan",
        "category": "Featured", "host": "Home Credit Group", "reward": "$100,000", "reward_value": 100000,
        "metric": "ROC AUC", "num_teams": 3308, "deadline": "2026-10-05",
        "tags": ["tabular", "binary classification", "finance"], "thumbnail": "credit-default-risk-2026",
        "owner": "psi_grandmaster",
        "description": "Use historical application, credit-bureau, and installment data to predict loan-repayment ability for applicants with little or no credit history. The largest cash prize on the platform this season.",
    },
    {
        "slug": "leaf-disease-segmentation",
        "title": "Plant Leaf Disease Segmentation",
        "subtitle": "Segment diseased regions on crop-leaf photographs",
        "category": "Research", "host": "FAO Agricultural Data Lab", "reward": "$40,000", "reward_value": 40000,
        "metric": "Dice Coefficient", "num_teams": 511, "deadline": "2026-09-28",
        "tags": ["computer vision", "segmentation", "agriculture"], "thumbnail": "leaf-disease-segmentation",
        "owner": "kenji_cv",
        "description": "Pixel-level segmentation of disease lesions on leaf images across 12 crop species. Helps build smartphone tools for early disease detection by smallholder farmers.",
    },
    {
        "slug": "titanic-survival",
        "title": "Titanic — Machine Learning from Disaster",
        "subtitle": "The legendary starter competition: predict survival on the Titanic",
        "category": "Getting Started", "host": "Kaggle", "reward": "Knowledge", "reward_value": 0,
        "metric": "Classification Accuracy", "num_teams": 14820, "deadline": "2027-01-01",
        "tags": ["binary classification", "tabular", "beginner"], "thumbnail": "titanic-survival",
        "owner": "Kaggle",
        "description": "The most popular Getting Started competition. Use passenger data (name, age, sex, class, fare) to predict who survived the 1912 Titanic shipwreck. Your first stop on Kaggle.",
    },
    {
        "slug": "retail-customer-churn-analytics",
        "title": "Retail Customer Churn Analytics",
        "subtitle": "Analytics challenge: explain and predict subscriber churn",
        "category": "Analytics", "host": "Streamline Retail", "reward": "$15,000", "reward_value": 15000,
        "metric": "Judged (report quality)", "num_teams": 287, "deadline": "2026-07-31",
        "tags": ["analytics", "tabular", "business"], "thumbnail": "retail-customer-churn-analytics",
        "owner": "tomeka_viz",
        "description": "An analytics competition judged on the quality of your written analysis and visualizations, not a leaderboard metric. Identify the key drivers of customer churn and recommend retention strategies.",
    },
    {
        "slug": "arctic-sea-ice-forecast",
        "title": "Arctic Sea Ice Extent Forecast",
        "subtitle": "Forecast monthly Arctic sea-ice extent",
        "category": "Research", "host": "Polar Climate Consortium", "reward": "$60,000", "reward_value": 60000,
        "metric": "Mean Absolute Error", "num_teams": 398, "deadline": "2026-08-20",
        "tags": ["time series", "climate", "regression", "geospatial"], "thumbnail": "arctic-sea-ice-forecast",
        "owner": "sara_timeseries",
        "description": "Forecast pan-Arctic and regional sea-ice extent up to six months ahead from satellite passive-microwave records and reanalysis climate fields. A research competition supporting climate science.",
    },
    {
        "slug": "handwritten-digit-recognizer",
        "title": "Digit Recognizer",
        "subtitle": "Learn computer vision fundamentals with the famous MNIST data",
        "category": "Getting Started", "host": "Kaggle", "reward": "Knowledge", "reward_value": 0,
        "metric": "Classification Accuracy", "num_teams": 5210, "deadline": "2027-01-01",
        "tags": ["computer vision", "image classification", "beginner"], "thumbnail": "handwritten-digit-recognizer",
        "owner": "Kaggle",
        "description": "Identify handwritten digits 0–9 from 28×28 grayscale images (MNIST). The standard introduction to image classification on Kaggle.",
    },
    {
        "slug": "fraud-detection-stream",
        "title": "Real-Time Fraud Detection",
        "subtitle": "Flag fraudulent transactions in a streaming feed",
        "category": "Featured", "host": "PayServe", "reward": "$80,000", "reward_value": 80000,
        "metric": "PR AUC", "num_teams": 1605, "deadline": "2026-06-26",
        "tags": ["tabular", "binary classification", "finance", "imbalanced"], "thumbnail": "fraud-detection-stream",
        "owner": "raul_gbm",
        "description": "Detect fraudulent card transactions in a highly imbalanced stream where fewer than 0.2% of records are fraud. Scored by area under the precision-recall curve. Closes soon.",
    },
    {
        "slug": "sentiment-of-product-reviews",
        "title": "Sentiment of Product Reviews",
        "subtitle": "Playground NLP: classify review sentiment into five stars",
        "category": "Playground", "host": "Kaggle", "reward": "Swag", "reward_value": 0,
        "metric": "Quadratic Weighted Kappa", "num_teams": 1021, "deadline": "2026-12-15",
        "tags": ["nlp", "text", "ordinal classification"], "thumbnail": "sentiment-of-product-reviews",
        "owner": "marco_nlp",
        "description": "Predict the 1–5 star rating implied by the text of an online product review. A monthly Playground competition for practicing text classification and ordinal targets.",
    },
    {
        "slug": "energy-load-forecasting",
        "title": "City Energy Load Forecasting",
        "subtitle": "Forecast hourly electricity demand for a metropolitan grid",
        "category": "Research", "host": "GridSense Energy", "reward": "$45,000", "reward_value": 45000,
        "metric": "Mean Absolute Percentage Error", "num_teams": 472, "deadline": "2026-10-30",
        "tags": ["time series", "regression", "energy"], "thumbnail": "energy-load-forecasting",
        "owner": "sara_timeseries",
        "description": "Forecast hourly electricity load for a large city grid using weather forecasts, calendar features, and historical consumption. Helps utilities plan generation and reduce waste.",
    },
]

# Leaderboard submissions per competition slug. Each tuple:
# (rank, team_name, owner_username, score, submitted_at). Scores ordered by rank.
LEADERBOARDS = {
    "credit-default-risk-2026": [
        (1, "Gradient Surfers", "psi_grandmaster", 0.81342, "2026-06-18"),
        (2, "Boosted Beavers", "raul_gbm", 0.81197, "2026-06-19"),
        (3, "Reef Net", "carolwong", 0.80955, "2026-06-15"),
        (4, "Data Mavens", "datasmith_io", 0.80610, "2026-06-17"),
        (5, "alicejdata", "alicejdata", 0.80288, "2026-06-16"),
        (6, "Mendoza Solo", "marco_nlp", 0.79944, "2026-06-12"),
    ],
    "fraud-detection-stream": [
        (1, "Boosted Beavers", "raul_gbm", 0.91205, "2026-06-21"),
        (2, "Gradient Surfers", "psi_grandmaster", 0.90880, "2026-06-20"),
        (3, "Sahel Signals", "sara_timeseries", 0.89712, "2026-06-19"),
        (4, "alicejdata", "alicejdata", 0.88450, "2026-06-18"),
    ],
    "rsna-pneumonia-detection-2026": [
        (1, "Sakura Vision", "kenji_cv", 0.26412, "2026-06-10"),
        (2, "Reef Net", "carolwong", 0.25988, "2026-06-14"),
        (3, "PixelMedics", "tomeka_viz", 0.24501, "2026-06-09"),
    ],
    "llm-prompt-recovery": [
        (1, "Lingua Systems", "marco_nlp", 0.74129, "2026-06-20"),
        (2, "Gradient Surfers", "psi_grandmaster", 0.73004, "2026-06-19"),
        (3, "carolwong", "carolwong", 0.71880, "2026-06-17"),
    ],
}

# ----------------------------------------------------------------------------
# Datasets
# slug, title, subtitle, owner_username, size (display), size_bytes (sort),
# file_count, file_types, usability (0-10 one decimal), upvotes, downloads,
# views, license, tags, last_updated (ISO), thumbnail, description
# ----------------------------------------------------------------------------
DATASETS = [
    {
        "slug": "global-co2-emissions-1960-2025", "owner": "datasmith_io",
        "title": "Global CO₂ Emissions 1960–2025",
        "subtitle": "Per-country annual CO₂ emissions, GDP, and population",
        "size": "44 MB", "size_bytes": 46137344, "file_count": 3, "file_types": "CSV",
        "usability": 10.0, "upvotes": 1842, "downloads": 39120, "views": 210400,
        "license": "CC0: Public Domain", "tags": ["climate", "economics", "environment", "tabular"],
        "last_updated": "2026-05-28", "thumbnail": "global-co2-emissions-1960-2025",
        "description": "A tidy, country-level panel of annual CO₂ emissions (total and per-capita) joined with GDP and population from 1960 to 2025. Cleaned, de-duplicated, and ready for analysis.",
    },
    {
        "slug": "imdb-50k-movie-reviews", "owner": "marco_nlp",
        "title": "IMDB 50K Movie Reviews",
        "subtitle": "Balanced binary sentiment classification corpus",
        "size": "66 MB", "size_bytes": 69206016, "file_count": 1, "file_types": "CSV",
        "usability": 9.4, "upvotes": 3201, "downloads": 88210, "views": 402100,
        "license": "Other (specified in description)", "tags": ["nlp", "text", "sentiment", "binary classification"],
        "last_updated": "2025-11-12", "thumbnail": "imdb-50k-movie-reviews",
        "description": "50,000 highly polar movie reviews labeled positive or negative, split 25k/25k for training and testing. The standard benchmark for binary sentiment classification.",
    },
    {
        "slug": "nyc-airbnb-2026", "owner": "alicejdata",
        "title": "New York City Airbnb Listings 2026",
        "subtitle": "Listing prices, locations, availability, and host details",
        "size": "18 MB", "size_bytes": 18874368, "file_count": 2, "file_types": "CSV, GeoJSON",
        "usability": 9.1, "upvotes": 1204, "downloads": 28740, "views": 150300,
        "license": "CC BY-SA 4.0", "tags": ["geospatial", "tabular", "tourism", "pricing"],
        "last_updated": "2026-04-02", "thumbnail": "nyc-airbnb-2026",
        "description": "Every active Airbnb listing in NYC's five boroughs as of Q1 2026, with nightly price, room type, neighborhood, review counts, and host data. Includes a GeoJSON of neighborhood boundaries.",
    },
    {
        "slug": "chest-xray-pneumonia", "owner": "kenji_cv",
        "title": "Chest X-Ray Images (Pneumonia)",
        "subtitle": "5,863 labeled pediatric chest radiographs",
        "size": "1.2 GB", "size_bytes": 1288490188, "file_count": 5863, "file_types": "JPEG",
        "usability": 8.8, "upvotes": 5420, "downloads": 142300, "views": 610200,
        "license": "CC BY 4.0", "tags": ["computer vision", "medical imaging", "health", "image classification"],
        "last_updated": "2025-09-30", "thumbnail": "chest-xray-pneumonia",
        "description": "Anterior-posterior chest X-ray images of pediatric patients, organized into NORMAL and PNEUMONIA folders for train/val/test. Widely used to benchmark medical-image classifiers.",
    },
    {
        "slug": "world-happiness-report-2026", "owner": "datasmith_io",
        "title": "World Happiness Report 2026",
        "subtitle": "National happiness scores and their six explanatory factors",
        "size": "2 MB", "size_bytes": 2097152, "file_count": 1, "file_types": "CSV",
        "usability": 10.0, "upvotes": 2987, "downloads": 61200, "views": 288700,
        "license": "CC0: Public Domain", "tags": ["economics", "social science", "tabular", "survey"],
        "last_updated": "2026-03-20", "thumbnail": "world-happiness-report-2026",
        "description": "Ladder-of-life happiness scores for 150+ countries with the six contributing factors (GDP per capita, social support, healthy life expectancy, freedom, generosity, perceptions of corruption).",
    },
    {
        "slug": "credit-card-fraud-transactions", "owner": "raul_gbm",
        "title": "Credit Card Fraud Transactions",
        "subtitle": "Anonymized European card transactions, highly imbalanced",
        "size": "150 MB", "size_bytes": 157286400, "file_count": 1, "file_types": "CSV",
        "usability": 9.7, "upvotes": 8810, "downloads": 233400, "views": 901200,
        "license": "Database: Open Database, Contents: Database Contents", "tags": ["finance", "tabular", "binary classification", "imbalanced"],
        "last_updated": "2025-12-01", "thumbnail": "credit-card-fraud-transactions",
        "description": "284,807 card transactions over two days, 492 of them fraudulent (0.172%). Features are PCA-transformed for privacy except Time and Amount. The canonical imbalanced-classification dataset.",
    },
    {
        "slug": "spotify-tracks-audio-features", "owner": "tomeka_viz",
        "title": "Spotify Tracks — Audio Features",
        "subtitle": "114k tracks with danceability, energy, valence, and more",
        "size": "20 MB", "size_bytes": 20971520, "file_count": 1, "file_types": "CSV",
        "usability": 9.4, "upvotes": 2110, "downloads": 47800, "views": 199600,
        "license": "CC0: Public Domain", "tags": ["music", "tabular", "audio", "eda"],
        "last_updated": "2026-01-18", "thumbnail": "spotify-tracks-audio-features",
        "description": "114,000 Spotify tracks across 125 genres with audio features (tempo, energy, danceability, valence, acousticness) and popularity. Great for EDA, clustering, and recommendation.",
    },
    {
        "slug": "global-wheat-satellite-imagery", "owner": "sara_timeseries",
        "title": "Global Wheat Satellite Imagery",
        "subtitle": "Multi-temporal Sentinel-2 patches over wheat-growing regions",
        "size": "3.4 GB", "size_bytes": 3650722201, "file_count": 21840, "file_types": "GeoTIFF, CSV",
        "usability": 8.5, "upvotes": 742, "downloads": 9120, "views": 51200,
        "license": "CC BY 4.0", "tags": ["geospatial", "computer vision", "agriculture", "climate", "time series"],
        "last_updated": "2026-05-10", "thumbnail": "global-wheat-satellite-imagery",
        "description": "Cloud-free Sentinel-2 image patches sampled across global wheat belts at five growth stages, paired with end-of-season yield labels. The companion dataset to the Global Wheat Yield Forecast competition.",
    },
    {
        "slug": "us-used-car-listings-2026", "owner": "alicejdata",
        "title": "US Used Car Listings 2026",
        "subtitle": "400k listings with price, mileage, make, model, and condition",
        "size": "92 MB", "size_bytes": 96468992, "file_count": 1, "file_types": "CSV",
        "usability": 9.2, "upvotes": 1533, "downloads": 35600, "views": 162900,
        "license": "CC BY-SA 4.0", "tags": ["tabular", "pricing", "regression", "automotive"],
        "last_updated": "2026-04-25", "thumbnail": "us-used-car-listings-2026",
        "description": "Roughly 400,000 used-car listings scraped from US dealer sites in early 2026, with asking price, odometer, year, make, model, trim, fuel type, and condition. A solid regression playground.",
    },
    {
        "slug": "handwritten-digits-mnist", "owner": "Kaggle",
        "title": "MNIST Handwritten Digits",
        "subtitle": "70,000 labeled 28×28 grayscale digit images",
        "size": "11 MB", "size_bytes": 11534336, "file_count": 4, "file_types": "CSV, IDX",
        "usability": 10.0, "upvotes": 4290, "downloads": 178200, "views": 720100,
        "license": "CC0: Public Domain", "tags": ["computer vision", "image classification", "beginner"],
        "last_updated": "2025-08-14", "thumbnail": "handwritten-digits-mnist",
        "description": "The classic MNIST dataset of handwritten digits 0–9 as flattened pixel CSVs and original IDX files. The 'hello world' of computer vision.",
    },
    {
        "slug": "amazon-product-reviews-electronics", "owner": "marco_nlp",
        "title": "Amazon Product Reviews — Electronics",
        "subtitle": "1.2M reviews with star ratings and helpfulness votes",
        "size": "480 MB", "size_bytes": 503316480, "file_count": 1, "file_types": "JSON",
        "usability": 8.9, "upvotes": 2670, "downloads": 58900, "views": 244300,
        "license": "Other (specified in description)", "tags": ["nlp", "text", "sentiment", "ecommerce"],
        "last_updated": "2025-10-22", "thumbnail": "amazon-product-reviews-electronics",
        "description": "1.2 million electronics-category product reviews with 1–5 star ratings, review text, summary, and helpfulness votes. Use for sentiment, ordinal regression, or recommendation.",
    },
    {
        "slug": "world-cities-population", "owner": "datasmith_io",
        "title": "World Cities Population & Coordinates",
        "subtitle": "47k cities with population, country, and lat/long",
        "size": "6 MB", "size_bytes": 6291456, "file_count": 1, "file_types": "CSV",
        "usability": 9.8, "upvotes": 1920, "downloads": 51000, "views": 233100,
        "license": "CC BY 4.0", "tags": ["geospatial", "tabular", "reference"],
        "last_updated": "2026-02-09", "thumbnail": "world-cities-population",
        "description": "47,000 world cities with population estimates, country and admin region, time zone, and latitude/longitude. A handy reference table for joining and mapping.",
    },
    {
        "slug": "retail-store-sales-history", "owner": "sara_timeseries",
        "title": "Retail Store Sales History",
        "subtitle": "Five years of daily sales across 54 stores and 33 families",
        "size": "120 MB", "size_bytes": 125829120, "file_count": 6, "file_types": "CSV",
        "usability": 9.3, "upvotes": 1340, "downloads": 31200, "views": 142800,
        "license": "CC0: Public Domain", "tags": ["time series", "retail", "regression", "tabular"],
        "last_updated": "2026-05-15", "thumbnail": "retail-store-sales-history",
        "description": "Daily unit sales for 54 stores and 33 product families over five years, with promotions, holidays, oil prices, and store metadata. Companion data for the Store Sales forecasting competition.",
    },
    {
        "slug": "plant-leaf-disease-images", "owner": "kenji_cv",
        "title": "Plant Leaf Disease Images",
        "subtitle": "54k annotated leaf photos across 12 crop species",
        "size": "2.1 GB", "size_bytes": 2254857830, "file_count": 54306, "file_types": "JPEG, PNG masks",
        "usability": 8.7, "upvotes": 1108, "downloads": 17400, "views": 78200,
        "license": "CC BY-SA 4.0", "tags": ["computer vision", "segmentation", "agriculture", "image classification"],
        "last_updated": "2026-05-05", "thumbnail": "plant-leaf-disease-images",
        "description": "54,306 leaf images spanning healthy and 26 disease classes across 12 crops, each with a pixel mask of the diseased region. Companion to the Plant Leaf Disease Segmentation competition.",
    },
    {
        "slug": "global-temperature-anomalies", "owner": "datasmith_io",
        "title": "Global Temperature Anomalies 1880–2025",
        "subtitle": "Monthly land+ocean temperature anomalies",
        "size": "4 MB", "size_bytes": 4194304, "file_count": 2, "file_types": "CSV",
        "usability": 9.9, "upvotes": 2240, "downloads": 49800, "views": 211000,
        "license": "CC0: Public Domain", "tags": ["climate", "time series", "environment", "tabular"],
        "last_updated": "2026-03-01", "thumbnail": "global-temperature-anomalies",
        "description": "Monthly global land and ocean temperature anomalies relative to the 1951–1980 baseline, 1880 to present. Tidy and ready for time-series and trend analysis.",
    },
    {
        "slug": "student-performance-factors", "owner": "bobsmith_ml",
        "title": "Student Performance Factors",
        "subtitle": "Exam scores with study habits and background features",
        "size": "1 MB", "size_bytes": 1048576, "file_count": 1, "file_types": "CSV",
        "usability": 9.0, "upvotes": 980, "downloads": 22100, "views": 96500,
        "license": "CC BY 4.0", "tags": ["education", "tabular", "regression", "beginner"],
        "last_updated": "2026-06-01", "thumbnail": "student-performance-factors",
        "description": "Synthetic-but-realistic records of student exam scores with study hours, attendance, parental involvement, sleep, and tutoring. A clean beginner regression dataset.",
    },
]

# ----------------------------------------------------------------------------
# Notebooks (Kernels / Code)
# slug, title, author_username, language, votes, comments, medal (or None),
# best_score (display or None), runtime, last_run (ISO), linked_competition,
# linked_dataset, thumbnail, description, tags
# ----------------------------------------------------------------------------
NOTEBOOKS = [
    {
        "slug": "eda-credit-default-deep-dive", "author": "psi_grandmaster",
        "title": "Home Credit — Full EDA & Feature Factory",
        "language": "Python", "votes": 1842, "comments": 214, "medal": "gold",
        "best_score": None, "runtime": "428.6s", "last_run": "2026-06-15",
        "linked_competition": "credit-default-risk-2026", "linked_dataset": None,
        "thumbnail": "eda-credit-default-deep-dive", "tags": ["eda", "feature engineering", "lightgbm", "tabular"],
        "description": "An end-to-end exploratory analysis of the Home Credit Default Risk data plus a reusable feature-engineering pipeline that joins all auxiliary tables and produces 700+ aggregated features.",
    },
    {
        "slug": "lgbm-baseline-fraud", "author": "raul_gbm",
        "title": "LightGBM Baseline for Real-Time Fraud Detection",
        "language": "Python", "votes": 1204, "comments": 138, "medal": "gold",
        "best_score": "0.91205", "runtime": "92.4s", "last_run": "2026-06-21",
        "linked_competition": "fraud-detection-stream", "linked_dataset": "credit-card-fraud-transactions",
        "thumbnail": "lgbm-baseline-fraud", "tags": ["lightgbm", "imbalanced", "tabular", "baseline"],
        "description": "A clean, well-commented LightGBM baseline for the Real-Time Fraud Detection competition, with class-weighting, threshold tuning on the PR curve, and out-of-fold validation. Reproduces a 0.912 leaderboard score.",
    },
    {
        "slug": "unet-pneumonia-segmentation", "author": "kenji_cv",
        "title": "U-Net Pneumonia Detection — Training Pipeline",
        "language": "Python", "votes": 932, "comments": 96, "medal": "gold",
        "best_score": "0.264", "runtime": "3h 12m", "last_run": "2026-06-10",
        "linked_competition": "rsna-pneumonia-detection-2026", "linked_dataset": "chest-xray-pneumonia",
        "thumbnail": "unet-pneumonia-segmentation", "tags": ["pytorch", "computer vision", "segmentation", "medical imaging"],
        "description": "A PyTorch U-Net with an EfficientNet encoder for the RSNA Pneumonia Detection Challenge, including augmentation, mixed-precision training, and a mAP evaluation harness.",
    },
    {
        "slug": "titanic-top-3-percent", "author": "carolwong",
        "title": "Titanic — Top 3% Solution Walkthrough",
        "language": "Python", "votes": 2610, "comments": 311, "medal": "gold",
        "best_score": "0.81100", "runtime": "44.1s", "last_run": "2026-05-22",
        "linked_competition": "titanic-survival", "linked_dataset": None,
        "thumbnail": "titanic-top-3-percent", "tags": ["beginner", "feature engineering", "ensemble", "tabular"],
        "description": "A friendly, fully explained Titanic solution that reaches the top 3% of the leaderboard with thoughtful feature engineering (titles, family size, fare bins) and a soft-voting ensemble.",
    },
    {
        "slug": "spotify-genre-clustering", "author": "tomeka_viz",
        "title": "Spotify Audio Features — Clustering & Viz",
        "language": "Python", "votes": 884, "comments": 73, "medal": "silver",
        "best_score": None, "runtime": "61.2s", "last_run": "2026-02-01",
        "linked_competition": None, "linked_dataset": "spotify-tracks-audio-features",
        "thumbnail": "spotify-genre-clustering", "tags": ["eda", "clustering", "visualization", "music"],
        "description": "Interactive UMAP + K-Means clustering of 114k Spotify tracks by audio features, with beautiful Plotly charts that reveal how genres separate in feature space.",
    },
    {
        "slug": "imdb-sentiment-transformers", "author": "marco_nlp",
        "title": "IMDB Sentiment with DistilBERT (94% acc)",
        "language": "Python", "votes": 1410, "comments": 152, "medal": "gold",
        "best_score": "0.9412", "runtime": "27m 8s", "last_run": "2025-11-15",
        "linked_competition": None, "linked_dataset": "imdb-50k-movie-reviews",
        "thumbnail": "imdb-sentiment-transformers", "tags": ["nlp", "transformers", "pytorch", "sentiment"],
        "description": "Fine-tunes DistilBERT on the IMDB 50K reviews dataset to 94% test accuracy, with a clean Hugging Face Trainer loop, learning-rate schedule, and confusion-matrix analysis.",
    },
    {
        "slug": "house-prices-stacked-regression", "author": "alicejdata",
        "title": "House Prices — Stacked Regression (Top 5%)",
        "language": "Python", "votes": 1190, "comments": 134, "medal": "silver",
        "best_score": "0.11892", "runtime": "118.7s", "last_run": "2026-04-30",
        "linked_competition": "house-prices-advanced-regression", "linked_dataset": None,
        "thumbnail": "house-prices-stacked-regression", "tags": ["regression", "stacking", "feature engineering", "tabular"],
        "description": "A stacked ensemble (Lasso, ElasticNet, Gradient Boosting, XGBoost) with careful skew correction and target encoding that lands in the top 5% of the House Prices leaderboard.",
    },
    {
        "slug": "r-timeseries-store-sales", "author": "sara_timeseries",
        "title": "Store Sales Forecasting in R (fable + tsibble)",
        "language": "R", "votes": 612, "comments": 58, "medal": "silver",
        "best_score": "0.41203", "runtime": "204.9s", "last_run": "2026-05-18",
        "linked_competition": "store-sales-demand-forecasting", "linked_dataset": "retail-store-sales-history",
        "thumbnail": "r-timeseries-store-sales", "tags": ["r", "time series", "forecasting", "tidyverse"],
        "description": "A tidyverts (fable + tsibble) workflow for the Store Sales competition in R: seasonal decomposition, exponential smoothing, and an ensemble of ETS and ARIMA per product family.",
    },
    {
        "slug": "mnist-cnn-from-scratch", "author": "bobsmith_ml",
        "title": "MNIST CNN from Scratch (99.2% acc)",
        "language": "Python", "votes": 421, "comments": 39, "medal": "bronze",
        "best_score": "0.99214", "runtime": "12m 3s", "last_run": "2026-06-03",
        "linked_competition": "handwritten-digit-recognizer", "linked_dataset": "handwritten-digits-mnist",
        "thumbnail": "mnist-cnn-from-scratch", "tags": ["computer vision", "keras", "beginner", "cnn"],
        "description": "A beginner-friendly Keras CNN for MNIST that reaches 99.2% with data augmentation and dropout, explained layer by layer.",
    },
    {
        "slug": "co2-emissions-trends-eda", "author": "datasmith_io",
        "title": "Global CO₂ Emissions — Trends & Storytelling",
        "language": "Python", "votes": 1056, "comments": 91, "medal": "silver",
        "best_score": None, "runtime": "38.5s", "last_run": "2026-05-29",
        "linked_competition": None, "linked_dataset": "global-co2-emissions-1960-2025",
        "thumbnail": "co2-emissions-trends-eda", "tags": ["eda", "climate", "visualization", "storytelling"],
        "description": "A narrative EDA of 65 years of global CO₂ emissions: who emits the most per capita, how emissions track GDP, and which countries have decoupled growth from carbon.",
    },
    {
        "slug": "wheat-yield-lgbm-geospatial", "author": "sara_timeseries",
        "title": "Wheat Yield — Geospatial Features + LightGBM",
        "language": "Python", "votes": 388, "comments": 44, "medal": "bronze",
        "best_score": "1.0423", "runtime": "266.0s", "last_run": "2026-05-12",
        "linked_competition": "global-wheat-yield-forecast", "linked_dataset": "global-wheat-satellite-imagery",
        "thumbnail": "wheat-yield-lgbm-geospatial", "tags": ["geospatial", "lightgbm", "feature engineering", "agriculture"],
        "description": "Extracts NDVI time-series and weather aggregates from the satellite patches, then trains a LightGBM regressor to forecast end-of-season wheat yield. Strong public-LB baseline.",
    },
    {
        "slug": "happiness-report-regression", "author": "bobsmith_ml",
        "title": "What Makes Countries Happy? A Regression Study",
        "language": "Python", "votes": 503, "comments": 47, "medal": "bronze",
        "best_score": None, "runtime": "21.7s", "last_run": "2026-03-22",
        "linked_competition": None, "linked_dataset": "world-happiness-report-2026",
        "thumbnail": "happiness-report-regression", "tags": ["eda", "regression", "social science", "beginner"],
        "description": "Explores which factors best predict national happiness using linear and tree models, with partial-dependence plots that quantify the contribution of GDP, social support, and freedom.",
    },
]

# ----------------------------------------------------------------------------
# Models
# slug, title, owner_username, framework, variations, downloads, upvotes,
# license, tags, last_updated, thumbnail, description
# ----------------------------------------------------------------------------
MODELS = [
    {
        "slug": "resnet50-chestxray", "owner": "kenji_cv",
        "title": "ResNet-50 Chest X-Ray Classifier",
        "framework": "PyTorch", "variations": 3, "downloads": 41200, "upvotes": 612,
        "license": "Apache 2.0", "tags": ["computer vision", "medical imaging", "classification"],
        "last_updated": "2026-04-18", "thumbnail": "resnet50-chestxray",
        "description": "A ResNet-50 fine-tuned on the Chest X-Ray Pneumonia dataset, with fp16 and int8 variations for edge deployment. Reaches 0.97 ROC AUC on the held-out test split.",
    },
    {
        "slug": "distilbert-imdb-sentiment", "owner": "marco_nlp",
        "title": "DistilBERT IMDB Sentiment",
        "framework": "Transformers", "variations": 2, "downloads": 88700, "upvotes": 901,
        "license": "MIT", "tags": ["nlp", "sentiment", "text classification"],
        "last_updated": "2025-11-16", "thumbnail": "distilbert-imdb-sentiment",
        "description": "DistilBERT fine-tuned on IMDB 50K reviews for binary sentiment, 94% accuracy. Includes base and quantized ONNX variations.",
    },
    {
        "slug": "lightgbm-fraud-detector", "owner": "raul_gbm",
        "title": "LightGBM Fraud Detector",
        "framework": "scikit-learn", "variations": 1, "downloads": 22300, "upvotes": 388,
        "license": "Apache 2.0", "tags": ["tabular", "finance", "classification", "imbalanced"],
        "last_updated": "2026-06-21", "thumbnail": "lightgbm-fraud-detector",
        "description": "A serialized LightGBM model + preprocessing pipeline for card-fraud scoring, trained on the Credit Card Fraud Transactions dataset. PR-AUC 0.91.",
    },
    {
        "slug": "unet-leaf-segmentation", "owner": "kenji_cv",
        "title": "U-Net Leaf Disease Segmenter",
        "framework": "PyTorch", "variations": 2, "downloads": 9800, "upvotes": 201,
        "license": "CC BY 4.0", "tags": ["computer vision", "segmentation", "agriculture"],
        "last_updated": "2026-05-06", "thumbnail": "unet-leaf-segmentation",
        "description": "U-Net with a ResNet-34 encoder trained on the Plant Leaf Disease Images dataset for pixel-level lesion segmentation. Dice 0.88 on validation.",
    },
    {
        "slug": "tabnet-credit-risk", "owner": "psi_grandmaster",
        "title": "TabNet Credit Risk Model",
        "framework": "PyTorch", "variations": 1, "downloads": 15600, "upvotes": 277,
        "license": "Apache 2.0", "tags": ["tabular", "finance", "classification", "deep learning"],
        "last_updated": "2026-06-16", "thumbnail": "tabnet-credit-risk",
        "description": "An attention-based TabNet model for the Home Credit Default Risk problem, with feature-importance masks for interpretability. ROC AUC 0.80.",
    },
    {
        "slug": "prophet-energy-forecaster", "owner": "sara_timeseries",
        "title": "Prophet City Energy Forecaster",
        "framework": "scikit-learn", "variations": 1, "downloads": 7400, "upvotes": 142,
        "license": "MIT", "tags": ["time series", "energy", "forecasting"],
        "last_updated": "2026-05-20", "thumbnail": "prophet-energy-forecaster",
        "description": "A tuned Prophet model with custom holiday and weather regressors for hourly metropolitan electricity-load forecasting. MAPE 3.1% on the validation horizon.",
    },
    {
        "slug": "efficientnet-leaf-classifier", "owner": "datasmith_io",
        "title": "EfficientNet-B3 Plant Leaf Classifier",
        "framework": "TensorFlow", "variations": 2, "downloads": 12800, "upvotes": 188,
        "license": "Apache 2.0", "tags": ["computer vision", "agriculture", "image classification"],
        "last_updated": "2026-03-28", "thumbnail": "efficientnet-leaf-classifier",
        "description": "An EfficientNet-B3 image classifier trained on the Plant Leaf Disease Images dataset to recognise 26 disease classes across 12 crops. TensorFlow SavedModel and TFLite variations included.",
    },
    {
        "slug": "yolov8-traffic-detector", "owner": "carolwong",
        "title": "YOLOv8 Urban Traffic Object Detector",
        "framework": "PyTorch", "variations": 3, "downloads": 33100, "upvotes": 421,
        "license": "GPL 2", "tags": ["computer vision", "object detection", "geospatial"],
        "last_updated": "2026-06-02", "thumbnail": "yolov8-traffic-detector",
        "description": "A YOLOv8 detector fine-tuned to spot cars, buses, cyclists, and pedestrians in dashcam and CCTV frames. Nano, small, and medium variations for different latency budgets.",
    },
    {
        "slug": "bert-ner-finance", "owner": "marco_nlp",
        "title": "BERT Financial NER",
        "framework": "Transformers", "variations": 1, "downloads": 19400, "upvotes": 256,
        "license": "MIT", "tags": ["nlp", "named entity recognition", "finance"],
        "last_updated": "2026-04-09", "thumbnail": "bert-ner-finance",
        "description": "A BERT-base token-classification model that tags companies, tickers, monetary amounts, and dates in financial news and filings.",
    },
    {
        "slug": "xgboost-churn-predictor", "owner": "psi_grandmaster",
        "title": "XGBoost Customer Churn Predictor",
        "framework": "scikit-learn", "variations": 1, "downloads": 10250, "upvotes": 174,
        "license": "Apache 2.0", "tags": ["tabular", "business", "classification"],
        "last_updated": "2026-05-31", "thumbnail": "xgboost-churn-predictor",
        "description": "A gradient-boosted churn classifier with SHAP explanations, trained on telco-style subscriber data. Ships with a calibrated probability head.",
    },
]

# ----------------------------------------------------------------------------
# Kaggle Learn courses
# slug, title, lessons, hours, level, icon, tags, description, lesson_titles
# ----------------------------------------------------------------------------
COURSES = [
    {
        "slug": "intro-to-machine-learning", "title": "Intro to Machine Learning",
        "lessons": 7, "hours": 3, "level": "Beginner", "icon": "🤖",
        "tags": ["machine learning", "beginner", "scikit-learn"],
        "description": "Learn the core ideas in machine learning and build your first models. Decision trees, model validation, underfitting vs overfitting, and random forests.",
        "lesson_titles": ["How Models Work", "Basic Data Exploration", "Your First Machine Learning Model",
                          "Model Validation", "Underfitting and Overfitting", "Random Forests", "Machine Learning Competitions"],
    },
    {
        "slug": "pandas", "title": "Pandas",
        "lessons": 6, "hours": 4, "level": "Beginner", "icon": "🐼",
        "tags": ["pandas", "data manipulation", "python"],
        "description": "Solve short hands-on challenges to perfect your data-manipulation skills with pandas — the most important Python library for working with tabular data.",
        "lesson_titles": ["Creating, Reading and Writing", "Indexing, Selecting & Assigning", "Summary Functions and Maps",
                          "Grouping and Sorting", "Data Types and Missing Values", "Renaming and Combining"],
    },
    {
        "slug": "intro-to-deep-learning", "title": "Intro to Deep Learning",
        "lessons": 6, "hours": 4, "level": "Intermediate", "icon": "🧠",
        "tags": ["deep learning", "keras", "neural networks"],
        "description": "Use TensorFlow and Keras to build and train neural networks for structured data. Stochastic gradient descent, overfitting, dropout, and batch normalization.",
        "lesson_titles": ["A Single Neuron", "Deep Neural Networks", "Stochastic Gradient Descent",
                          "Overfitting and Underfitting", "Dropout and Batch Normalization", "Binary Classification"],
    },
    {
        "slug": "computer-vision", "title": "Computer Vision",
        "lessons": 6, "hours": 4, "level": "Intermediate", "icon": "👁️",
        "tags": ["computer vision", "cnn", "keras", "deep learning"],
        "description": "Build convolutional neural networks with TensorFlow and Keras. Learn about convolution, pooling, data augmentation, and transfer learning for image classification.",
        "lesson_titles": ["The Convolutional Classifier", "Convolution and ReLU", "Maximum Pooling",
                          "The Sliding Window", "Custom Convnets", "Data Augmentation"],
    },
    {
        "slug": "feature-engineering", "title": "Feature Engineering",
        "lessons": 6, "hours": 5, "level": "Intermediate", "icon": "🛠️",
        "tags": ["feature engineering", "machine learning", "tabular"],
        "description": "Better features make better models. Discover how to engineer features, measure mutual information, create features, and use target encoding and clustering.",
        "lesson_titles": ["What Is Feature Engineering", "Mutual Information", "Creating Features",
                          "Clustering With K-Means", "Principal Component Analysis", "Target Encoding"],
    },
    {
        "slug": "intro-to-sql", "title": "Intro to SQL",
        "lessons": 6, "hours": 3, "level": "Beginner", "icon": "🗄️",
        "tags": ["sql", "bigquery", "data"],
        "description": "Learn SQL for working with databases using Google BigQuery. SELECT, GROUP BY, ORDER BY, joins, and how to keep your queries under control.",
        "lesson_titles": ["Getting Started With SQL and BigQuery", "Select, From & Where", "Group By, Having & Count",
                          "Order By", "As & With", "Joining Data"],
    },
    {
        "slug": "data-visualization", "title": "Data Visualization",
        "lessons": 7, "hours": 4, "level": "Beginner", "icon": "📊",
        "tags": ["visualization", "seaborn", "eda"],
        "description": "Make great data visualizations with seaborn. Line, bar, and scatter charts, distributions, and choosing the right plot for your data and story.",
        "lesson_titles": ["Hello, Seaborn", "Line Charts", "Bar Charts and Heatmaps", "Scatter Plots",
                          "Distributions", "Choosing Plot Types and Custom Styles", "Final Project"],
    },
    {
        "slug": "intro-to-deep-learning-nlp", "title": "Natural Language Processing",
        "lessons": 4, "hours": 3, "level": "Advanced", "icon": "💬",
        "tags": ["nlp", "transformers", "text", "deep learning"],
        "description": "Distinguish yourself by learning to work with text data. Text classification, word vectors, and building NLP pipelines with spaCy and transformers.",
        "lesson_titles": ["Intro to NLP", "Text Classification", "Word Vectors", "Transformers and Beyond"],
    },
    {
        "slug": "time-series", "title": "Time Series",
        "lessons": 6, "hours": 4, "level": "Intermediate", "icon": "📈",
        "tags": ["time series", "forecasting", "regression"],
        "description": "Apply machine learning to real-world forecasting tasks. Trend and seasonality, time-series features, hybrid models, and forecasting with ML.",
        "lesson_titles": ["Linear Regression With Time Series", "Trend", "Seasonality",
                          "Time Series as Features", "Hybrid Models", "Forecasting With Machine Learning"],
    },
    {
        "slug": "intro-to-ai-ethics", "title": "Intro to AI Ethics",
        "lessons": 5, "hours": 4, "level": "Beginner", "icon": "⚖️",
        "tags": ["ai ethics", "fairness", "responsible ai"],
        "description": "Explore practical tools to guide the moral design of AI systems. Human-centered design, bias, fairness, model cards, and AI fairness metrics.",
        "lesson_titles": ["Introduction", "Human-Centered Design for AI", "Identifying Bias in AI",
                          "AI Fairness", "Model Cards"],
    },
]

# ----------------------------------------------------------------------------
# Discussions (forum threads)
# slug, title, author_username, forum, votes, comments, pinned, created_at, body
# ----------------------------------------------------------------------------
DISCUSSIONS = [
    {
        "slug": "welcome-to-kaggle-getting-started", "author": "Kaggle",
        "title": "Welcome to Kaggle! Start here", "forum": "Getting Started",
        "votes": 5210, "comments": 642, "pinned": True, "created_at": "2025-01-05",
        "body": "New to Kaggle? This thread links the essentials: pick a Getting Started competition like Titanic, take the Intro to Machine Learning course on Kaggle Learn, and don't be afraid to fork a public notebook. Welcome aboard!",
    },
    {
        "slug": "fraud-detection-pr-auc-vs-roc-auc", "author": "raul_gbm",
        "title": "Why PR-AUC, not ROC-AUC, for the fraud comp?", "forum": "Questions & Answers",
        "votes": 412, "comments": 58, "pinned": False, "created_at": "2026-06-08",
        "body": "With fraud at 0.17% prevalence, ROC-AUC looks great even for weak models because true negatives dominate. PR-AUC focuses on the positive (fraud) class, so it's the honest metric here. Curious how others are calibrating their thresholds.",
    },
    {
        "slug": "credit-default-leak-warning", "author": "psi_grandmaster",
        "title": "Heads up: potential target leak via SK_ID ordering", "forum": "Competition Hosting",
        "votes": 388, "comments": 71, "pinned": True, "created_at": "2026-06-11",
        "body": "If you sort by SK_ID_CURR you'll notice the default rate drifts. That's an artifact of how the data was exported, not signal. Using row order as a feature will overfit the public LB and collapse on private. Don't do it.",
    },
    {
        "slug": "best-gpu-for-kaggle-2026", "author": "bobsmith_ml",
        "title": "Best free GPU setup for training in 2026?", "forum": "General",
        "votes": 244, "comments": 89, "pinned": False, "created_at": "2026-05-19",
        "body": "Kaggle gives 30 GPU hours/week on T4s and P100s. For the chest X-ray comp that's tight. Anyone splitting training across sessions or using gradient checkpointing to fit U-Net at higher resolution?",
    },
    {
        "slug": "feature-request-dark-mode", "author": "tomeka_viz",
        "title": "Feature request: dark mode for notebooks", "forum": "Product Feedback",
        "votes": 1820, "comments": 203, "pinned": False, "created_at": "2026-04-12",
        "body": "Please ship a real dark mode for the notebook editor. My eyes during a 2am competition crunch would appreciate it. Upvote if you agree!",
    },
    {
        "slug": "sharing-co2-dataset-v3", "author": "datasmith_io",
        "title": "[Dataset] Global CO₂ Emissions updated through 2025", "forum": "Datasets",
        "votes": 302, "comments": 41, "pinned": False, "created_at": "2026-05-28",
        "body": "Just pushed v3 of the Global CO₂ Emissions dataset with 2025 figures and a cleaned per-capita column. Usability is back to 10.0. Let me know if you spot any country-code mismatches.",
    },
    {
        "slug": "wheat-yield-ndvi-features", "author": "sara_timeseries",
        "title": "What NDVI aggregation works best for wheat yield?", "forum": "Questions & Answers",
        "votes": 156, "comments": 34, "pinned": False, "created_at": "2026-05-13",
        "body": "I'm getting the best CV from max-NDVI in the heading stage plus the integral of NDVI over the season. Mean NDVI alone underperforms. What growth-stage windows are working for you?",
    },
    {
        "slug": "titanic-feature-ideas", "author": "carolwong",
        "title": "Underrated Titanic features that actually help", "forum": "Getting Started",
        "votes": 921, "comments": 167, "pinned": False, "created_at": "2026-05-22",
        "body": "Beyond the obvious: extracting the title from Name (Mr/Mrs/Master/Rare), family size = SibSp+Parch+1, and a 'deck' letter from the cabin all move the needle. Ticket-group survival is the sneaky strong one.",
    },
]

# Comments attached to discussions. slug -> list of (author_username, body, votes, created_at)
DISCUSSION_COMMENTS = {
    "fraud-detection-pr-auc-vs-roc-auc": [
        ("psi_grandmaster", "Exactly. I tune the threshold to maximize F1 on out-of-fold predictions, then sanity-check the PR curve.", 41, "2026-06-08"),
        ("alicejdata", "Class weights in LightGBM plus PR-AUC early stopping got me to 0.88. Thanks for the writeup!", 22, "2026-06-09"),
    ],
    "titanic-feature-ideas": [
        ("bobsmith_ml", "The title extraction alone bumped me from 0.76 to 0.79. Wild how much a regex helps.", 58, "2026-05-23"),
        ("davidtran", "Total beginner here — thank you, the family-size feature finally got me off 0.62.", 12, "2026-05-24"),
    ],
}
