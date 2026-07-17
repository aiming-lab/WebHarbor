# WebHarbor — slim, self-contained image.
# 17 Flask mirror sites + control plane on :8101.

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

COPY websyn_start.sh    /opt/websyn_start.sh
COPY control_server.py  /opt/control_server.py
COPY site_runner.py     /opt/site_runner.py
RUN chmod +x /opt/websyn_start.sh

# osu ships no frozen DB in git/HF (its data is generated deterministically from
# seed_data.py). Build its instance_seed/osu.db at image-build time so the boot
# reset (`cp -a instance_seed instance` in websyn_start.sh) and /reset/osu both
# have a seed to restore from.
RUN cd /opt/WebSyn/osu && python3 -c "\
import app; \
import os, shutil; \
os.makedirs('instance_seed', exist_ok=True); \
shutil.copy2('instance/osu.db', 'instance_seed/osu.db'); \
print('osu seed DB generated at build time.')" && rm -rf /opt/WebSyn/osu/instance

EXPOSE 8101 40000-40016

CMD ["/opt/websyn_start.sh"]
