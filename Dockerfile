# WebHarbor — slim, self-contained image.
# 19 Flask mirror sites + control plane on :8101.

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

# IKEA's seed is reproducibly materialized from the tracked source catalog so code-only content fixes do not require an asset-repository write. Product images still come from the pinned asset bundle.
RUN cd /opt/WebSyn/ikea && PYTHONHASHSEED=0 python seed_data.py && rm -rf instance

# Apply tracked, idempotent Phys.org data corrections to the pinned seed asset.
RUN cd /opt/WebSyn/phys_org && PYTHONHASHSEED=0 python migrate_seed.py && rm -rf instance

# Rebuild Compass's source-backed catalog and benchmark state from tracked data.
RUN cd /opt/WebSyn/compass && python migrate_seed.py && rm -rf instance

COPY websyn_start.sh    /opt/websyn_start.sh
COPY control_server.py  /opt/control_server.py
COPY site_runner.py     /opt/site_runner.py
RUN chmod +x /opt/websyn_start.sh

EXPOSE 8101 40000-40018

CMD ["/opt/websyn_start.sh"]
