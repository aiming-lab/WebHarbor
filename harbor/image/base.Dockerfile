# webharbor-harbor-base: one image for every WebHarbor-in-Harbor website.
#
# Two identities, one container:
#   - root    owns the site tree (/opt/WebSyn, 0700), the site DB, and the
#             root-only access log; the per-website entrypoint runs as root.
#   - ubuntu is the agent user: owns /workspace, /state, /logs/agent and the
#             shared chromium; cannot read any root-owned site or verifier
#             artifact.
#
# Agent runtime is the WildAWM pinned toolchain, copied verbatim from the
# digest-pinned image battalion7244/wildawm-opencode-web@ea888860:
#   opencode 1.17.7 (binary sha256 c67c8602...), browser-use 0.11.13
#   (with the AWMEVAL_CDP_URL attach patch), Playwright 1.61.0,
#   Playwright MCP 0.0.78, chromium 1228.
#
# Build: harbor/image/build_base.sh (assembles the context and runs docker build).

ARG AGENT_RUNTIME=battalion7244/wildawm-opencode-web@sha256:ea8888608db77f427b7f2fe30d3bd9853c39a6c0e9dc563bd43456d270a938d3
FROM ${AGENT_RUNTIME} AS agent-runtime

# WebHarbor's own base: pinned python 3.12 slim.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

USER root

# System packages: curl (guard target + healthcheck), libexpat1 (python3.11),
# and the full Chromium runtime dependency set from the pinned Playwright.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libexpat1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    OPENCODE_DISABLE_AUTOUPDATE=1 \
    OPENCODE_DISABLE_MODELS_FETCH=true \
    OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER=true \
    PATH=/opt/guards/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/opencode-web/bin

# ---- Site runtime (root side): the full WebHarbor Flask stack ----
COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --require-hashes -r /tmp/requirements.lock && rm /tmp/requirements.lock

# ---- Agent runtime (ubuntu side): pinned opencode/browser-use/playwright ----
COPY --from=agent-runtime /opt/opencode-web /opt/opencode-web
COPY --from=agent-runtime /opt/pw-browsers /opt/pw-browsers
COPY --from=agent-runtime /opt/playwright-mcp /opt/playwright-mcp
COPY --from=agent-runtime /usr/local/bin/node /usr/local/bin/node
# The venv's interpreters symlink /usr/bin/python3.11; bring them along so the
# copied venv actually runs in this image.
COPY --from=agent-runtime /usr/bin/python3.11 /usr/bin/python3.11
COPY --from=agent-runtime /usr/lib/python3.11 /usr/lib/python3.11
# opencode 1.17.7 from its official release; both the archive and the binary are pinned.
RUN curl -fsSL -o /tmp/opencode.tar.gz https://github.com/anomalyco/opencode/releases/download/v1.17.7/opencode-linux-x64.tar.gz \
    && echo "60fe5a92dc9af64ec079348fedde17e12da6a867efe7e8353be8038480607924  /tmp/opencode.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin opencode \
    && echo "c67c8602154a18729cb80b4fca2669911f558347d76599f7ef45dee76c806613  /usr/local/bin/opencode" | sha256sum -c - \
    && rm /tmp/opencode.tar.gz
# browser-use 0.11.13 CDP-attach patch: AWMEVAL_CDP_URL / AWMEVAL_START_URL.
# The venv's bin/python points at /usr/bin/python3 which this slim image lacks;
# retarget it at the copied python3.11.
COPY patch-browser-use-cdp.py /tmp/patch-browser-use-cdp.py
RUN ln -sfn /usr/bin/python3.11 /opt/opencode-web/bin/python \
    && /opt/opencode-web/bin/python /tmp/patch-browser-use-cdp.py && rm /tmp/patch-browser-use-cdp.py \
    && ln -sfn /opt/playwright-mcp/node_modules/@playwright/mcp/cli.js /usr/local/bin/playwright-mcp \
    && chmod 0555 /usr/local/bin/opencode /opt/opencode-web/bin/browser-use \
    && test "$(/usr/local/bin/opencode --version)" = "1.17.7" \
    && /opt/opencode-web/bin/python -c 'import importlib.metadata as m; assert m.version("browser-use") == "0.11.13"; assert m.version("playwright") == "1.61.0"' \
    && node -e 'if(require("/opt/playwright-mcp/node_modules/@playwright/mcp/package.json").version!=="0.0.78") process.exit(1)' \
    && test -x /opt/pw-browsers/chromium-1228/chrome-linux64/chrome \
    && /opt/opencode-web/bin/python -m playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R a+rX /opt/pw-browsers /opt/playwright-mcp

# ---- Guards (PATH-fronted shims; real binaries stay at original paths) ----
COPY guards/curl-guard.py guards/browser-use-guard.py /opt/guards/
COPY site_entrypoint.sh site_launcher.py access_log.py browseruse_gui.py opencode_capture.py /opt/webharbor-harness/
RUN mkdir -p /opt/guards/bin \
    && printf '#!/bin/sh\nexec /usr/local/bin/python3 /opt/guards/curl-guard.py "$@"\n' > /opt/guards/bin/curl \
    && printf '#!/bin/sh\nexec /opt/opencode-web/bin/python /opt/guards/browser-use-guard.py "$@"\n' > /opt/guards/bin/browser-use \
    && chmod 0555 /opt/guards/bin/curl /opt/guards/bin/browser-use /opt/guards/*.py \
    && chmod 0755 /opt/webharbor-harness/site_entrypoint.sh \
    && chmod 0555 /opt/webharbor-harness/*.py

# ---- Identities and filesystem boundaries ----
RUN useradd --create-home --shell /bin/bash ubuntu \
    && mkdir -p /opt/WebSyn /workspace /state /var/lib/webharbor /var/log/webharbor \
    && chmod 0700 /opt/WebSyn \
    && chown ubuntu:ubuntu /workspace /state \
    && rm -rf /home/ubuntu/.cache /home/ubuntu/.config

# The site tree stays root-only; per-website images COPY into /opt/WebSyn/<site>.
# Agent phase execs run as ubuntu via task.toml [agent] user.
WORKDIR /workspace
