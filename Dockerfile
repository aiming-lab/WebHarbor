# WebHarbor — slim, self-contained image.
# 25 Flask mirror sites + control plane on :8101.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8

RUN pip3 install --no-cache-dir \
    Flask==3.1.0 \
    Flask-SQLAlchemy==3.1.1 \
    Flask-Login==0.6.3 \
    Flask-WTF==1.2.2 \
    Flask-Bcrypt==1.0.1 \
    bcrypt==5.0.0 \
    Werkzeug==3.1.3 \
    Jinja2==3.1.4 \
    SQLAlchemy==2.0.36 \
    WTForms==3.2.1 \
    email-validator==2.2.0 \
    Pillow==11.0.0

WORKDIR /opt/WebSyn

# Sites tree. Build context must contain the heavy assets (instance_seed/,
# static/images/, static/external_cache/) — either commit them locally or
# run scripts/fetch_assets.sh to pull them from Hugging Face first.
COPY sites/ /opt/WebSyn/
COPY scripts/check_asset_inventory.py /opt/check_asset_inventory.py

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

# WebMD Doctor ships no HF assets: the deterministic SQLite seed, the Pillow
# initials avatars and the video poster frames are all generated here.
RUN cd /opt/WebSyn/webmd_doctor && rm -rf instance instance_seed && \
    PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

COPY websyn_start.sh    /opt/websyn_start.sh
COPY control_server.py  /opt/control_server.py
COPY site_runner.py     /opt/site_runner.py
RUN chmod +x /opt/websyn_start.sh

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

EXPOSE 8101 40000-40024

CMD ["/opt/websyn_start.sh"]
