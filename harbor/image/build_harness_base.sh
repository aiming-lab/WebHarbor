#!/usr/bin/env bash
# Build the shared WebHarbor base image containing browser-use, OpenCode and OpenWebRL harnesses.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
BASE_IMAGE="${1:-webharbor-harbor-base:0.1}"
OUTPUT_IMAGE="${2:-webharbor-harbor-base:0.2}"
CONTEXT="${REPO}/build/harness-base-context"

rm -rf "${CONTEXT}"
mkdir -p "${CONTEXT}/openwebrl_runtime"
cp "${HERE}/harnesses.Dockerfile" "${CONTEXT}/Dockerfile"
cp "${REPO}/harness/browseruse_gui.py" \
   "${REPO}/harness/opencode_capture.py" \
   "${REPO}/harness/describe_image_mcp.py" \
   "${REPO}/harness/openwebrl_eval.py" \
   "${REPO}/harness/judge_scene_assemble.py" \
   "${CONTEXT}/"
for name in __init__.py base_env.py feedback_utils.py js.py keyboard.py policy_api.py prompt_adapter.py web_env.py system_prompt_browser_env.md tool_list.json README.md; do
    cp "${REPO}/harness/openwebrl_runtime/${name}" "${CONTEXT}/openwebrl_runtime/${name}"
done

docker build \
    --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
    -t "${OUTPUT_IMAGE}" \
    -f "${CONTEXT}/Dockerfile" \
    "${CONTEXT}"

docker run --rm --entrypoint /bin/sh "${OUTPUT_IMAGE}" -c '
set -eu
for f in browseruse_gui.py opencode_capture.py describe_image_mcp.py openwebrl_eval.py judge_scene_assemble.py; do
    test -r "/opt/webharbor-harness/$f"
done
su -s /bin/sh ubuntu -c '\''PYTHONDONTWRITEBYTECODE=1 /opt/opencode-web/bin/python -c "import sys; sys.path.insert(0, \"/opt/webharbor-harness\"); import openwebrl_runtime.web_env; from openwebrl_eval import load_resources; assert len(load_resources()[1]) == 13"'\''
echo HARNESS_BASE_OK
'

echo "built ${OUTPUT_IMAGE} from ${BASE_IMAGE}"
