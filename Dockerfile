# WebHarbor — slim, self-contained image.
# 25 Flask mirror sites + control plane on :8101.

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
COPY .assets-revision /opt/.assets-revision
COPY assets-manifest.json /opt/assets-manifest.json
COPY scripts/check_asset_inventory.py /opt/check_asset_inventory.py
COPY scripts/check_seed_databases.py /opt/check_seed_databases.py
COPY scripts/asset_state.py /opt/asset_state.py
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

# Drugs.com uses database-backed inline pill renderings and rebuilds its versioned deterministic SQLite seed from tracked source data without network access.
RUN python3 /opt/check_asset_inventory.py /opt/WebSyn/drugs_com
RUN cd /opt/WebSyn/drugs_com && rm -rf instance instance_seed && \
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

# Final fail-closed package gate after every tracked seed generator and migration.
RUN python3 /opt/check_seed_databases.py /opt/WebSyn

EXPOSE 8101 40000-40024

CMD ["/opt/websyn_start.sh"]
