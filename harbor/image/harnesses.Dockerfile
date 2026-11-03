ARG BASE_IMAGE=webharbor-harbor-base:0.1
FROM ${BASE_IMAGE}

USER root

# One immutable harness directory, shared by all per-site images. Harbor runs
# every agent harness as task.toml [agent].user (ubuntu); root owns these files
# so the evaluated agent cannot replace its own policy or evidence recorder.
COPY browseruse_gui.py opencode_capture.py describe_image_mcp.py openwebrl_eval.py judge_scene_assemble.py /opt/webharbor-harness/
COPY openwebrl_runtime/ /opt/webharbor-harness/openwebrl_runtime/

RUN chown root:root \
        /opt/webharbor-harness/browseruse_gui.py \
        /opt/webharbor-harness/opencode_capture.py \
        /opt/webharbor-harness/describe_image_mcp.py \
        /opt/webharbor-harness/openwebrl_eval.py \
        /opt/webharbor-harness/judge_scene_assemble.py \
    && chown -R root:root /opt/webharbor-harness/openwebrl_runtime \
    && chmod 0555 \
        /opt/webharbor-harness/browseruse_gui.py \
        /opt/webharbor-harness/opencode_capture.py \
        /opt/webharbor-harness/describe_image_mcp.py \
        /opt/webharbor-harness/openwebrl_eval.py \
        /opt/webharbor-harness/judge_scene_assemble.py \
    && find /opt/webharbor-harness/openwebrl_runtime -type d -exec chmod 0555 {} + \
    && find /opt/webharbor-harness/openwebrl_runtime -type f -exec chmod 0444 {} + \
    && su -s /bin/sh ubuntu -c 'PYTHONDONTWRITEBYTECODE=1 /opt/opencode-web/bin/python -c "import sys; sys.path.insert(0, \"/opt/webharbor-harness\"); import httpx, playwright; import openwebrl_runtime.web_env, openwebrl_runtime.policy_api; from openwebrl_eval import load_resources; policy, tools = load_resources(); assert \"<think>\" in policy and len(tools) == 13"'

LABEL webharbor.harnesses="browseruse,opencode,openwebrl"
LABEL webharbor.openwebrl.config="browser_env,native_prompt_serialization=true,user_request=task_description,assistant_prefill=auto_from_chat_template,tool_response=1,turn_level=true,max_steps=30,context_screenshots=1,temp=0.6,top_p=0.95,top_k=20,max_response=4096,max_context=32768"

WORKDIR /workspace
