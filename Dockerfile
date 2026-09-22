# WebHarbor — slim, self-contained image.
# 61 Flask mirror sites + control plane on :8101.

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8

COPY requirements.lock /opt/requirements.lock
RUN pip3 install --no-cache-dir --require-hashes -r /opt/requirements.lock

WORKDIR /opt/WebSyn

# Sites tree. Build context must contain the heavy assets (instance_seed/,
# static/images/, static/external_cache/) — either commit them locally or
# run scripts/fetch_assets.sh to pull them from Hugging Face first.
COPY sites/ /opt/WebSyn/
COPY scripts/check_asset_inventory.py /opt/check_asset_inventory.py
COPY .assets-revision /opt/.assets-revision
COPY assets-manifest.json /opt/assets-manifest.json
COPY scripts/asset_state.py /opt/asset_state.py
COPY scripts/check_seed_databases.py /opt/check_seed_databases.py
RUN python3 /opt/asset_state.py verify /opt/WebSyn /opt/.assets-revision /opt/assets-manifest.json

# IKEA's seed is reproducibly materialized from the tracked source catalog so code-only content fixes do not require an asset-repository write. Product images still come from the pinned asset bundle.
RUN cd /opt/WebSyn/ikea && PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# Apply tracked, idempotent data corrections to downloaded seed assets.
RUN cd /opt/WebSyn/phys_org && PYTHONHASHSEED=0 python migrate_seed.py && rm -rf instance
RUN cd /opt/WebSyn/target && PYTHONHASHSEED=0 python migrate_seed.py && rm -rf instance
RUN cd /opt/WebSyn/ted && PYTHONHASHSEED=0 python migrate_seed.py && rm -rf instance

# Compass keeps source-backed media in the pinned asset bundle and rebuilds
# its versioned deterministic SQLite seed from tracked source documents.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/compass
RUN cd /opt/WebSyn/compass && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python migrate_seed.py && rm -rf instance

# Walmart Careers validates source-backed media and rebuilds its deterministic SQLite seed from tracked source data.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/walmart_careers && \
    python3 /opt/WebSyn/walmart_careers/check_tracked_assets.py
RUN cd /opt/WebSyn/walmart_careers && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# FedEx validates its downloaded homepage media against the tracked inventory and
# rebuilds its deterministic, version-marked SQLite seed from tracked source data.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/fedex
RUN cd /opt/WebSyn/fedex && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# WebMD Doctor's generated avatars / posters come from the pinned asset bundle,
# while its SQLite seed is rebuilt deterministically from tracked source code.
# The inventory gate enforces exact coverage + per-file SHA-256 + PNG decode of
# all 317 generated images (same contract as the compass / walmart inventories).
RUN python3 /opt/WebSyn/webmd_doctor/check_generated_assets.py
RUN cd /opt/WebSyn/webmd_doctor && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance __pycache__
# Healthline's downloaded seed carries tracked corrections (image reassignment) and the
# pinned archive bundles unreferenced images; apply the deterministic migration and prune
# the unreferenced files before they are shipped.
RUN cd /opt/WebSyn/healthline && test -f instance_seed/healthline.db && \
    PYTHONHASHSEED=0 python3 migrate_seed.py && \
    python3 prune_unreferenced_images.py --apply && rm -rf instance

# Versus ships source-backed entity imagery from the pinned asset bundle.
# The generic gate enforces exact coverage, hashes, source URLs and WebP headers.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/versus
# The seed remains code-generated; the benchmark password hash is frozen so the
# SQLite output is byte-identical on every build.
RUN cd /opt/WebSyn/versus && \
    rm -rf instance instance_seed && \
    mkdir -p instance_seed && \
    python3 -c "from app import app" && \
    cp instance/versus.db instance_seed/versus.db && \
    rm -rf instance __pycache__

# Berkeley's generated imagery ships in the pinned asset bundle while its SQLite
# seed stays build-generated from tracked source — see .build-generated-seed. The
# inventory gate enforces exact coverage + per-file SHA-256 + decode at the planned
# dimensions of all 164 generated images (82 FLUX scenes + 82 Pillow avatars), the
# same contract as the webmd_doctor / compass / walmart_careers inventories.
RUN python3 /opt/WebSyn/berkeley/check_generated_assets.py
# No wall clock and no random salt reaches a row, so the artifact is
# byte-reproducible; websyn_start.sh copies it into instance/ at boot.
RUN cd /opt/WebSyn/berkeley && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# Petfinder generates its reset seed from tracked application data.
RUN cd /opt/WebSyn/petfinder && rm -rf instance instance_seed && \
    mkdir -p instance_seed && python3 -c "from app import app" && \
    cp instance/petfinder.db instance_seed/petfinder.db && rm -rf instance

# AKC ships source-backed imagery and its reviewed frozen SQLite seed.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/akc && \
    cd /opt/WebSyn/akc && test -f instance_seed/akc.db && rm -rf instance

COPY websyn_start.sh    /opt/websyn_start.sh
COPY control_server.py  /opt/control_server.py
COPY site_runner.py     /opt/site_runner.py
RUN sed -i 's/\r$//' /opt/websyn_start.sh && chmod +x /opt/websyn_start.sh

# OSU's real-site image bundle is required, while its database is generated
# deterministically from tracked source data.
RUN test -n "$(ls -A /opt/WebSyn/osu/static/images)"
RUN cd /opt/WebSyn/osu && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python3 migrate_seed.py && rm -rf instance

# Rotten Tomatoes keeps source-backed media in the asset bundle and rebuilds
# its deterministic SQLite seed from tracked, validated source documents.
RUN test -n "$(ls -A /opt/WebSyn/rotten_tomatoes/static/images)" && \
    test -n "$(ls -A /opt/WebSyn/rotten_tomatoes/static/external_cache)"
RUN cd /opt/WebSyn/rotten_tomatoes && rm -rf instance instance_seed && python3 -c "\
import app; \
import os, shutil; \
os.makedirs('instance_seed', exist_ok=True); \
shutil.copy2('instance/rotten_tomatoes.db', 'instance_seed/rotten_tomatoes.db'); \
print('Rotten Tomatoes seed DB generated at build time.')" && rm -rf /opt/WebSyn/rotten_tomatoes/instance

# B&H's asset bundle contains images; generate the reset seed from its tracked
# catalog in the image so a fresh checkout needs no locally prepared database.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/bh_photo
RUN cd /opt/WebSyn/bh_photo && rm -rf instance instance_seed && PYTHONHASHSEED=0 python3 -c "\
import app; \
import os, shutil; \
os.makedirs('instance_seed', exist_ok=True); \
shutil.copy2('instance/bh_photo.db', 'instance_seed/bh_photo.db'); \
print('B&H Photo seed DB generated at build time.')" && rm -rf instance

# AccuWeather uses genuine captured UI assets and freezes its deterministic seed.
RUN test -n "$(ls -A /opt/WebSyn/accuweather/static/images)" && \
    cd /opt/WebSyn/accuweather && rm -rf instance instance_seed && python3 -c "\
import app; \
import os, shutil; \
os.makedirs('instance_seed', exist_ok=True); \
shutil.copy2('instance/accuweather.db', 'instance_seed/accuweather.db'); \
print('AccuWeather seed DB generated at build time.')" && rm -rf /opt/WebSyn/accuweather/instance

# Upgrade the pinned Recreation.gov seed before it becomes the reset fixture.
RUN cd /opt/WebSyn/recreation_gov && python3 migrate_seed.py

# Keep the downloaded BabyCenter seed aligned with tracked source corrections.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/babycenter && \
    python3 /opt/WebSyn/babycenter/migrate_seed.py

# Verify every Cookpad source-backed image before shipping the pinned seed.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/cookpad

# Craigslist ships its reviewed seed and authentic listing photos/provenance.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/craigslist && \
    cd /opt/WebSyn/craigslist && python3 -c "import app" && rm -rf instance

# Drugs.com: verify source-backed DailyMed assets and generate the deterministic seed.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/drugs_com && \
    cd /opt/WebSyn/drugs_com && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# Y Combinator ships upstream-sourced media in the pinned asset bundle and
# rebuilds its deterministic SQLite seed from the tracked source_data.json.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/y_combinator
RUN cd /opt/WebSyn/y_combinator && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# Adopt-a-Pet builds its synthetic catalog; representative photos come from HF.
RUN test -n "$(ls -A /opt/WebSyn/adopt_a_pet/static/images)" && \
    cd /opt/WebSyn/adopt_a_pet && rm -rf instance instance_seed && python3 -c "\
import app; \
import os, shutil; \
os.makedirs('instance_seed', exist_ok=True); \
shutil.copy2('instance/adopt_a_pet.db', 'instance_seed/adopt_a_pet.db'); \
print('Adopt-a-Pet seed DB generated at build time.')" && rm -rf /opt/WebSyn/adopt_a_pet/instance

# Preserve the downloaded MEGA archive and migrate its seed at build time.
RUN cd /opt/WebSyn/mega && python3 migrate_seed.py

# Preserve the original 4shared archive and add deterministic rename history.
RUN cd /opt/WebSyn/4shared && python3 migrate_seed.py

# Preserve the 9GAG archive; curated benchmark stories have no matching source photos.
RUN cd /opt/WebSyn/9gag && python3 migrate_seed.py


# CA.gov mirrors the live https://www.ca.gov/ directory; upstream-sourced
# media ships in the pinned asset bundle and the deterministic SQLite seed is
# rebuilt from the committed scrape-derived literals.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/california_gov && \
    cd /opt/WebSyn/california_gov && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# Fail closed after all registered-site seed migrations/generators.
RUN python3 /opt/check_seed_databases.py /opt/WebSyn

EXPOSE 8101 40000-40064

CMD ["/opt/websyn_start.sh"]
