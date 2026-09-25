#!/usr/bin/env python3
"""Positive and adversarial regression tests for every Hugging Face verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact trajectory shape and the ground-truth answer the
served mirror pages yield (recorded during the reviewer's Playwright audit of
the running container — reports/huggingface/audit/), and the adversarial
cases prove the verifiers reject no-op runs, recall shortcuts, wrong answers,
foreign task ids, broken run packages, and DB writes.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB --no_llm True
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because
the repository tracks no instance assets; set WH_CONTAINER to point at the
site's container when it is not the default wh-ver-huggingface.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
TASKS_FILE = SITE_DIR / "tasks.jsonl"
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://127.0.0.1:41010"
TASKS = list(range(43))

PNG = bytes.fromhex("89504e470d0a1a0a") + b"review-evidence" * 8

# task -> (navigation paths a compliant trajectory must contain, model answer)
POSITIVE = {
    0: (["/models?q=sentiment",
         "/models?task=text-classification&updated_month=2023-03&sort=updated"],
        "cardiffnlp/twitter-xlm-roberta-base-sentiment is a multilingual sentiment "
        "analysis model (Text Classification); its card and page show it was last "
        "updated Mar 15, 2023, within March 2023."),
    1: (["/HuggingFaceH4/zephyr-7b-story-dragon-wizard"],
        "I used the Inference API widget on the HuggingFaceH4/zephyr-7b-story-"
        "dragon-wizard model page. The generated short story: 'Once upon a time, a "
        "dragon met a wizard in the enchanted forest. They decided to join forces "
        "and build a library of spells that could translate any language, "
        "summarize any book, and answer any question. Together, they trained a "
        "mighty model on the collective wisdom of the realm, and shared it openly "
        "so that every village could benefit.'"),
    2: (["/models?task=translation&sort=updated"],
        "Three new popular open-source translation models released in the past "
        "month: lemondouble/manga-translator-v3 (updated Apr 17, 2026), "
        "HuggingFaceTB/SmolLM2-Translate-360M (Apr 11, 2026), and Qwen/Qwen3-MT-3B "
        "(Apr 02, 2026)."),
    3: (["/models?license=cc-by-sa-4.0&sort=likes", "/bigscience/T0pp"],
        "bigscience/T0pp is the model with a cc-by-sa-4.0 license and the most "
        "likes: 4.20k likes, licensed CC BY-SA 4.0."),
    4: (["/models?q=conversational", "/facebook/blenderbot-3B-english-chat"],
        "facebook/blenderbot-3B-english-chat is an open-source conversational AI "
        "trained on English dialogue corpora. Main features: multi-turn dialogue, "
        "persona conditioning, safety filtering. Applications: chatbots, customer "
        "support, virtual assistants."),
    5: (["/models?q=recipe", "/flax-community/t5-recipe-generation"],
        "The recipe generation model is flax-community/t5-recipe-generation: a T5 "
        "model with 770M parameters (0.77B), tensor type FP32, disk size 3.1 GB."),
    6: (["/sentence-transformers/all-MiniLM-L6-v2"],
        "Using the Inference API widget on sentence-transformers/all-MiniLM-L6-v2, "
        "the similarity between 'Tomorrow is Sunday' and 'Eat a burger on Sunday' "
        "is 0.4743."),
    7: (["/datasets?modality=Audio&sort=downloads",
         "/datasets/mozilla-foundation/common_voice_19_0"],
        "The most downloaded audio-related dataset is mozilla-foundation/"
        "common_voice_19_0 (Common Voice 19), an Audio speech dataset with 15.8M "
        "downloads."),
    8: (["/models?q=machine+translation", "/facebook/nllb-200-distilled-600M"],
        "Example pre-trained NLP model: facebook/nllb-200-distilled-600M, a "
        "multilingual neural machine translation model covering 200+ languages; "
        "the task it is specifically designed for is Translation."),
    9: (["/models?q=en-ja&sort=downloads", "/Helsinki-NLP/opus-mt-en-ja"],
        "The most downloaded en-ja machine translation model is Helsinki-NLP/"
        "opus-mt-en-ja (5.6M downloads). The evaluation metrics stated on its page: "
        "BLEU 28.5, chrF 55.2, COMET 0.83 on the FLORES-200 en-ja test set."),
    10: (["/spaces/argilla/notux-chat-ui"],
         "The notux-chat-ui Space answered: 'The Argilla team trained me. "
         "Specifically, we (Argilla) fine-tuned this model from Mistral Instruct "
         "using DPO on our preference-labeled dataset "
         "argilla/ultrafeedback-binarized-preferences-cleaned.'"),
    11: (["/models?task=image-to-video&sort=updated", "/unsloth/LTX-2.3-GGUF"],
         "The latest updated image-to-video model is unsloth/LTX-2.3-GGUF (updated "
         "Apr 19, 2026): Unsloth GGUF quantizations of LTX-2.3 across Q4-Q8 for "
         "ComfyUI and llama.cpp-style I2V inference."),
    12: (["/models?q=error+correction&sort=updated", "/Unbabel/GEC-English"],
         "The most recently updated error-correction model is Unbabel/GEC-English "
         "(updated Apr 12, 2026): English grammatical error correction; an "
         "encoder-decoder trained on a large synthetic + curated corpus."),
    13: (["/docs/llama-tokenizer"],
         "In the LlamaTokenizer documentation, the spaces_between_special_tokens "
         "parameter has type bool and its default value is False."),
    14: (["/pricing"],
         "The Hugging Face Pro account costs $9 per month. Features: ZeroGPU "
         "priority quota, private models and datasets with unlimited storage, "
         "early access to new Hub features, PRO badge, higher Inference API rate "
         "limits, and access to PRO-only Spaces."),
    15: (["/models?library=PaddlePaddle&sort=downloads", "/PaddlePaddle/uie-base"],
         "The most downloaded model using the PaddlePaddle library is "
         "PaddlePaddle/uie-base with 3.1M downloads (updated Nov 15, 2025)."),
    16: (["/models?task=text-classification&sort=updated",
          "/microsoft/deberta-v3-large-textclassification-2026"],
         "The latest pre-trained language model suitable for text classification "
         "(as of today) is microsoft/deberta-v3-large-textclassification-2026 "
         "(updated Apr 06, 2026). Intended use case: multi-domain enterprise text "
         "classification — sentiment, topic, intent. Architecture: 24-layer "
         "DeBERTa-v3 with disentangled attention, ELECTRA-style RTD pretraining."),
    17: (["/models?q=nightly", "/huggingface/transformers-2026-nightly"],
         "The most recently updated open-source NLP project is "
         "transformers-2026-nightly, created by Hugging Face. Functionality: the "
         "latest Transformers library nightly build with a state-of-the-art NLP "
         "model zoo — tokenization, fine-tuning, and inference."),
    18: (["/docs/trl-forward-modelling"],
         "Per TRL's forward-modelling docs, to add a margin to the loss you pass "
         "`margin` in your dataset (each example may carry a 'margin' column) or "
         "via the training arguments (DPOConfig); the DPOTrainer computes "
         "loss = -log(sigmoid(beta * (chosen_logps - rejected_logps - margin)))."),
    19: (["/models?task=summarization&sort=updated", "/facebook/bart-large-cnn-2026"],
         "The most recent English text summarization model is "
         "facebook/bart-large-cnn-2026 (updated Mar 25, 2026). Features: "
         "abstractive English summarization, coverage loss for factuality, length "
         "control (min/max tokens), ROUGE-1 44.1 / ROUGE-L 41.0 on CNN/DailyMail."),
    20: (["/models?task=token-classification&updated_year=2022&sort=updated",
          "/dslim/bert-base-NER-2022"],
         "dslim/bert-base-NER-2022 is a BERT-base English NER model (token "
         "classification, CoNLL-2003: PER/LOC/ORG/MISC) that was last updated "
         "Nov 20, 2022 and has 4.2M downloads (over 1M)."),
    21: (["/docs/pipeline-tour"],
         "The pipeline quick tour states that pipeline('sentiment-analysis') "
         "without a model argument loads the default model "
         "distilbert/distilbert-base-uncased-finetuned-sst-2-english — a "
         "DistilBERT checkpoint fine-tuned on the Stanford Sentiment Treebank "
         "(SST-2)."),
    22: (["/docs/pytorch-to-tensorflow"],
         "Steps to convert a PyTorch model to TensorFlow per the docs: 1) save the "
         "PyTorch model with model.save_pretrained; 2) reload it as a TensorFlow "
         "model with TFAutoModel.from_pretrained('./bert-pt', from_pt=True); 3) "
         "save the TensorFlow weights with tf_model.save_pretrained. The loader "
         "matches layer names automatically."),
    23: (["/models?task=automatic-speech-recognition&sort=updated"],
         "Three open-source ASR models released in the past month: "
         "XiaomiMiMo/MiMo-V2.5-ASR (Apr 23, 2026), MediaTek-Research/Breeze-ASR-26 "
         "(Apr 20, 2026), and Trelis/Chorus-v1 (Apr 19, 2026)."),
    24: (["/models?license=apache-2.0&sort=likes", "/meta-llama/Llama-3-community-8B"],
         "The model with an Apache-2.0 license and the highest number of likes is "
         "meta-llama/Llama-3-community-8B with 9.80k likes (9,801), Apache 2.0."),
    25: (["/docs/peft-adapters"],
         "Per the PEFT docs: to load in 8-bit, use "
         "BitsAndBytesConfig(load_in_8bit=True) and then "
         "PeftModel.from_pretrained(base, adapter); to load in 4-bit, use "
         "BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_use_double_quant=True, "
         "bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype='bfloat16'). "
         "bitsandbytes is required first."),
    26: (["/models?q=travel", "/wanderlust/llama-travel-chat-7b"],
         "The travel chat model is wanderlust/llama-travel-chat-7b — name "
         "llama-travel-chat-7b, size 7B parameters, training framework PEFT (LoRA) "
         "on top of PyTorch + Transformers, fine-tuned on 150K travel dialogues."),
    27: (["/datasets?task=text-ranking&sort=downloads",
          "/datasets/microsoft/ms_marco_v2_retrieval"],
         "The most downloaded dataset related to Text Retrieval in NLP is "
         "microsoft/ms_marco_v2_retrieval with 18.2M downloads — MS MARCO v2, the "
         "canonical Text Ranking / passage retrieval benchmark (8.8M rows)."),
    28: (["/models?q=squad", "/deepset/xlm-roberta-large-squad2-multilingual"],
         "deepset/xlm-roberta-large-squad2-multilingual is optimized for question "
         "answering (fine-tuned on SQuAD2 with multilingual transfer). It supports "
         "English, French, German, Spanish, Italian, Dutch, Russian, Chinese, "
         "Arabic, Japanese, Korean and 20+ more languages."),
    29: (["/models?q=medical+summarization&sort=updated",
          "/microsoft/BioGPT-Large-summarization"],
         "The recent open-source medical summarization model is "
         "microsoft/BioGPT-Large-summarization (updated Apr 07, 2026): BioGPT-Large "
         "fine-tuned for biomedical literature summarization; English abstracts in, "
         "short summaries out."),
    30: (["/models?q=en-zh", "/Helsinki-NLP/opus-mt-en-zh"],
         "The most downloaded en-zh machine translation model is Helsinki-NLP/"
         "opus-mt-en-zh (6.8M downloads). Performance: BLEU 32.1 / chrF 58.4 on "
         "FLORES-200 en-zh, COMET 0.86. Usage guidelines: UTF-8 encoded English "
         "input, sentence-level segmentation for best results, up to 512 tokens "
         "per input."),
    31: (["/models?q=fake+news&sort=updated", "/jy46604790/Fake-News-Bert-Detect"],
         "The latest fake-news detection model is jy46604790/Fake-News-Bert-Detect "
         "(BERT-base, LIAR + FakeNewsNet corpora); its last update was "
         "Apr 08, 2026."),
    32: (["/models?q=GPT-J", "/EleutherAI/gpt-j-6b"],
         "In EleutherAI/gpt-j-6b's generation config parameters, the temperature "
         "parameter (float) has the default value 1.0; lower values make output "
         "more deterministic."),
    33: (["/docs", "/docs/transformers", "/docs/datasets", "/docs/tokenizers"],
         "Three Hugging Face docs and their GitHub stars so far: Transformers — "
         "136k stars; Datasets — 19.4k stars; Tokenizers — 9.2k stars."),
    34: (["/classroom"],
         "Hugging Face Classroom benefits: free access to Hugging Face courses "
         "(Transformers, Diffusion Models, Reinforcement Learning); dedicated "
         "teacher dashboards for managing up to 200 students with assignment "
         "tracking; free organization-level private Spaces and datasets for "
         "assignments; higher ZeroGPU priority; integration with Jupyter and "
         "Colab; a certification program with signed certificates; a community "
         "support channel with direct access to Hugging Face engineers and "
         "educators; and curriculum templates covering NLP, Computer Vision, "
         "Audio, Reinforcement Learning and Agentic workflows."),
    35: (["/blog", "/blog/diffusers-03-release"],
         "The latest Diffusion-related blog is 'Diffusers 0.30 — Lightning-fast "
         "Diffusion Pipelines' (2026-04-02). Overview: the release focuses on "
         "faster, more memory-efficient, easier-to-customize diffusion generation "
         "— 2x faster sampling with flow matching schedulers, a new "
         "AutoPipelineForText2Image, out-of-the-box SD3, FLUX.1 and Mochi support, "
         "an LCM (Latent Consistency Model) distillation workflow, and first-class "
         "ONNX and TensorRT export."),
    36: (["/pricing"],
         "Hugging Face pricing plans: HF Hub — Free forever: unlimited public "
         "models, datasets and Spaces, community support, free-tier Inference API, "
         "Git-based version control, CPU Spaces at no cost. PRO Account — $9 per "
         "month: ZeroGPU priority quota, private models and datasets, early access "
         "to new Hub features, PRO badge, higher Inference API rate limits, "
         "PRO-only Spaces. Enterprise Hub — $20 per user/month: SSO, SAML and "
         "audit logs, SOC2 Type II compliance, private Spaces with dedicated "
         "hardware, RBAC, dedicated support with SLAs, custom inference regions, "
         "bring-your-own-cloud deployments."),
    37: (["/papers", "/papers/2504.03275"],
         "The first daily paper is 'Scaling Chain-of-Thought Distillation Across "
         "100+ Languages' (arXiv:2504.03275) with 248 upvotes. Yes — there are "
         "related releases: models meta-llama/Llama-3.3-70B-Instruct and "
         "Qwen/Qwen2.5-72B-Instruct, and dataset HuggingFaceH4/ultrachat_200k."),
    38: (["/docs/transformers-add-tokens"],
         "Per the transformers docs: add new tokens with "
         "tokenizer.add_tokens(['[CODE]', '[EOL]', 'myspecialword']); add special "
         "tokens with tokenizer.add_special_tokens({'additional_special_tokens': "
         "['[USR]', '[SYS]']}); then resize the model's input embeddings with "
         "model.resize_token_embeddings(len(tokenizer))."),
    39: (["/docs/trainer-api"],
         "Use the Trainer API: Trainer(model=..., args=TrainingArguments("
         "output_dir, num_train_epochs, per_device_train_batch_size, "
         "learning_rate, ...), train_dataset=..., eval_dataset=..., tokenizer=..., "
         "compute_metrics=...). The configurable parameters of the Trainer class "
         "are: model, args (TrainingArguments), data_collator, train_dataset / "
         "eval_dataset, tokenizer, compute_metrics, callbacks, and optimizers."),
    40: (["/docs/text-embeddings-inference"],
         "Text Embeddings Inference (TEI) strengths: Fast — built in Rust with CUDA "
         "kernels, token-level dynamic batching and Flash Attention; Small — Docker "
         "images under 150MB with no Python runtime; Production-ready — OpenAPI "
         "spec, Prometheus metrics, safetensors support; Flexible — supports BERT, "
         "RoBERTa, DistilBERT, MPNet, GTE, BGE, E5, Jina; Scalable — gRPC and HTTP "
         "endpoints; Easy to deploy — a single docker run; Tracing — "
         "OpenTelemetry out of the box."),
    41: (["/models?task=text-to-3d&sort=downloads", "/tencent/Hunyuan3D-2-text2mesh"],
         "The Text-to-3D model with the highest downloads is "
         "tencent/Hunyuan3D-2-text2mesh with 1.4M downloads. Yes — there are "
         "Spaces that use the model: tencent/Hunyuan3D-2 and "
         "tencent/Hunyuan3D-text-to-3d."),
    42: (["/datasets/ai2lumos/lumos_complex_qa_plan_onetime",
          "/datasets/ai2lumos/lumos_complex_qa_plan_onetime/viewer"],
         "In the Dataset Viewer, the content corresponding to user in the first "
         "message is: 'Please answer the following complex question: Which actor "
         "who played in the 2005 film Pride & Prejudice was born in the same "
         "country as the director of Atonement? Break down your reasoning into "
         "subgoals and solve them step by step.'"),
}


def make_run(root: Path, task: int, paths, answer, *, task_id=None, origin=ORIGIN,
             drop_trajectory=False, break_screenshot=False):
    run = root / f"run_{task}"
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    paths = list(paths)
    steps = []
    for index, path in enumerate(paths):
        shot = f"step_{index:03d}.png"
        (shots / shot).write_bytes(PNG)
        steps.append({"step": index, "url": origin + path, "action": "click",
                      "action_result": {"success": True}, "screenshot_after": shot})
    final_shot = f"step_{len(paths):03d}.png"
    if not break_screenshot:
        (shots / final_shot).write_bytes(PNG)
    steps.append({"step": len(paths), "url": origin + (paths[-1] if paths else "/"),
                  "action": "done", "action_result": {"success": True},
                  "screenshot_after": final_shot})
    trajectory = {
        "task_id": task_id or f"Huggingface--{task}",
        "task": "fixture",
        "start_url": origin + "/",
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "steps": steps,
    }
    if not drop_trajectory:
        (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    return run


def run_verifier(task: int, run_dir: Path, initial_db: Path, after_db: Path):
    script = VERIFY_DIR / f"verify_{task}.py"
    r = subprocess.run(
        [sys.executable, str(script), "--run_dir", str(run_dir),
         "--initial_db", str(initial_db), "--after_db", str(after_db),
         "--container", "unused-container", "--no_llm", "True"],
        capture_output=True, text=True)
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[:300]}"}
    verdict["returncode"] = r.returncode
    return verdict


SEED_DB = None


def seed_db(tmp: Path) -> Path:
    global SEED_DB
    if SEED_DB is None:
        SEED_DB = verify_lib.fetch_db(
            os.environ.get("WH_CONTAINER", "wh-ver-huggingface"), "instance_seed")
    db = tmp / "seed_copy.db"
    shutil.copy2(SEED_DB, db)
    return db


class VerifierTests(unittest.TestCase):
    def execute(self, task, *, answer=None, paths=None, task_id=None,
                drop_trajectory=False, break_screenshot=False, mutate=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            if mutate:
                with sqlite3.connect(after) as connection:
                    mutate(connection)
                    connection.commit()
            good_paths, good_answer = POSITIVE[task]
            run = make_run(root, task,
                           paths if paths is not None else good_paths,
                           answer if answer is not None else good_answer,
                           task_id=task_id, drop_trajectory=drop_trajectory,
                           break_screenshot=break_screenshot)
            return run_verifier(task, run, initial, after)

    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task)
                self.assertTrue(result["pass"], f"task {task}: {result}")

    def test_noop_run_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"], answer="")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)
                self.assertEqual(result.get("reason"), "final_answer_nonempty")

    def test_shortcut_correct_answer_without_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"])
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_wrong_answer_after_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(
                    task, answer="The requested information is not available on "
                                 "this Hugging Face mirror.")
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_foreign_task_replay_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, task_id="Huggingface--999")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_missing_trajectory_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, drop_trajectory=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_missing_screenshot_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, break_screenshot=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_database_write_fails_read_only_check(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(
                    task,
                    mutate=lambda db: db.execute(
                        "UPDATE repositories SET downloads = downloads + 1 WHERE id = 1"))
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "db_state")


    def test_task2_multilingual_v2_in_window_passes(self):
        # acceptor Finding A: Helsinki-NLP/opus-mt-en-multilingual-v2 (updated
        # Mar 20, 2026, Translation) is inside the documented on/after-Mar-20
        # band; an answer naming it must PASS.
        result = self.execute(
            2, paths=["/models?task=translation&sort=updated"],
            answer="Three new popular open-source translation models released "
                   "in the past month: Helsinki-NLP/opus-mt-en-multilingual-v2 "
                   "(updated Mar 20, 2026, English-to-Multilingual), facebook/"
                   "seamless-m4t-v2-large (Mar 22, 2026), and facebook/nllb-"
                   "200-3.3B-flash (Mar 20, 2026).")
        self.assertTrue(result["pass"], result)

    def test_task2_out_of_band_models_fail(self):
        # band edge: models updated before Mar 20, 2026 (Hunyuan-MT-7B Mar 18,
        # mengzi-t5-base-mt-en-zh Mar 15, opus-mt-en-es-2026 Mar 10) stay
        # outside the accepted window.
        result = self.execute(
            2, paths=["/models?task=translation&sort=updated"],
            answer="Three new popular open-source translation models released "
                   "in the past month: tencent/Hunyuan-MT-7B (updated Mar 18, "
                   "2026), Langboat/mengzi-t5-base-mt-en-zh (Mar 15, 2026), "
                   "and Helsinki-NLP/opus-mt-en-es-2026 (Mar 10, 2026).")
        self.assertFalse(result["pass"], result)
        self.assertIn("answer_three_recent_translation_models", result["reason"])

    def test_task7_downloads_sorted_listing_passes(self):
        # D1-style regression: an agent that sorts the whole datasets catalog by
        # downloads sees the audio dataset at the top — that solve must PASS.
        result = self.execute(
            7, paths=["/datasets", "/datasets?sort=downloads"],
            answer="The most downloaded audio-related dataset is "
                   "mozilla-foundation/common_voice_19_0 (Automatic Speech "
                   "Recognition, Audio) with 15.8M downloads.")
        self.assertTrue(result["pass"], result)

    def test_task27_downloads_sorted_listing_passes(self):
        # same pattern: the downloads-sorted datasets listing surfaces ms_marco
        result = self.execute(
            27, paths=["/datasets", "/datasets?sort=downloads"],
            answer="The most downloaded dataset related to Text Retrieval in NLP "
                   "is microsoft/ms_marco_v2_retrieval with 18.2M downloads — the "
                   "canonical Text Ranking / passage retrieval benchmark.")
        self.assertTrue(result["pass"], result)

    def test_task4_chat_search_listing_passes(self):
        # a q=chat search listing is an acceptable navigation for task 4
        result = self.execute(
            4, paths=["/models?q=chat", "/facebook/blenderbot-3B-english-chat"],
            answer=POSITIVE[4][1])
        self.assertTrue(result["pass"], result)

    def test_task16_updated_sort_head_passes(self):
        # the updated-sorted listing's latest text-classifying model (Shield-82M,
        # Token Classification) is a defensible reading of task 16
        result = self.execute(
            16, paths=["/models?sort=updated", "/LH-Tech-AI/Shield-82M"],
            answer="The latest model suitable for text classification is "
                   "LH-Tech-AI/Shield-82M (updated Apr 23, 2026): a compact 82M "
                   "PII shield doing token classification for on-device privacy "
                   "redaction; intended for mobile keyboards and email clients.")
        self.assertTrue(result["pass"], result)

    def test_task17_updated_sort_head_passes(self):
        result = self.execute(
            17, paths=["/models?sort=updated", "/LH-Tech-AI/Shield-82M"],
            answer="The most recently updated open-source NLP project is "
                   "LH-Tech-AI/Shield-82M by creator LH-Tech-AI: a compact 82M "
                   "PII shield for on-device privacy redaction in mobile "
                   "keyboards and email clients (token classification).")
        self.assertTrue(result["pass"], result)

    def test_task19_updated_sort_head_passes(self):
        result = self.execute(
            19, paths=["/models?task=summarization&sort=updated",
                       "/yunu919/bart-dialogue-summ-2026"],
            answer="The most recently updated English summarization model is "
                   "yunu919/bart-dialogue-summ-2026 (updated Apr 19, 2026): a "
                   "BART-large model fine-tuned on SAMSum-XL for dialogue "
                   "summarization, with names anonymized for privacy.")
        self.assertTrue(result["pass"], result)


class ContentNegativeTests(unittest.TestCase):
    """Per-task content negatives: a plausible-but-wrong answer after honest
    navigation must FAIL on the answer-contract check."""

    NEGATIVES = {
        0: ("The sentiment analysis model cardiffnlp/twitter-xlm-roberta-base-"
            "sentiment was last updated Mar 15, 2024.", "answer_march_2023_date"),
        1: ("The Inference API generated: a dragon and a wizard became friends "
            "and opened a school of magic together.", "answer_story_dragon_wizard"),
        2: ("Three recent translation models: facebook/nllb-200-distilled-600M, "
            "Helsinki-NLP/opus-mt-en-zh, and facebook/m2m100_418M.",
            "answer_three_recent_translation_models"),
        3: ("google/flan-t5-xxl has the most likes under cc-by-sa-4.0: 3.10k "
            "likes, CC BY-SA 4.0.", "answer_names_t0pp"),
        4: ("The conversational model is facebook/blenderbot-400M-distill: a "
            "single-turn encoder with keyword retrieval.", "answer_names_blenderbot_english"),
        5: ("flax-community/t5-recipe-generation is a 220M-parameter model with "
            "tensor type int8.", "answer_model_size_770m"),
        6: ("The similarity score between the two sentences is 0.9122.",
            "answer_similarity_score"),
        7: ("The most downloaded audio dataset is openslr/librispeech_asr with "
            "9.2M downloads.", "answer_names_common_voice_19"),
        8: ("facebook/nllb-200-distilled-600M is designed for image "
            "classification.", "answer_names_visited_model_with_its_task"),
        9: ("opus-mt-en-ja's stated metrics are BLEU 12.3 and chrF 41.7 on WMT14.",
            "answer_evaluation_metrics"),
        10: ("The Space answered that the OpenAI team trained it.",
             "answer_argilla_team"),
        11: ("The latest image-to-video model is stabilityai/stable-video-"
             "diffusion-xt-2, a text-to-image generator producing 512px stills.",
             "answer_latest_i2v_model_with_features"),
        12: ("The most recently updated error-correction model is "
             "vennify/t5-base-grammar-correction, updated Nov 02, 2025.",
             "answer_error_correction_model"),
        13: ("spaces_between_special_tokens is a string parameter defaulting to "
             "' '.", "answer_type_bool"),
        14: ("The Pro account costs $25 per month with unlimited GPU hours.",
             "answer_pro_price_9"),
        15: ("The most downloaded PaddlePaddle model is PaddlePaddle/ernie-3.0-"
             "base-zh with 2.8M downloads.", "answer_names_uie_base"),
        16: ("The latest text-classification model is bert-base-uncased, a "
             "12-layer bidirectional transformer.", "answer_latest_textclass_model"),
        17: ("The latest NLP project is SmolLM2-1.7B-Instruct by HuggingFaceTB, "
             "a general chat model.", "answer_project_name"),
        18: ("TRL adds a margin by setting the learning rate of the chosen "
             "response.", "answer_dpo_trainer"),
        19: ("The recent English summarization model is google/pegasus-xsum, an "
             "extractive summarizer.", "answer_recent_english_summarizer"),
        20: ("dslim/bert-base-NER was last updated Feb 05, 2026 with 70.3k "
             "downloads.", "answer_names_2022_ner_model"),
        21: ("The default sentiment model is roberta-large fine-tuned on "
             "Twitter data.", "answer_default_model_distilbert"),
        22: ("Convert by calling transformers.load_tf_weights directly on the "
             "checkpoint folder.", "answer_conversion_steps"),
        23: ("Three recent ASR models: openai/whisper-large-v3, "
             "nvidia/parakeet-tdt-1.1b, and facebook/seamless-m4t-v2-large.",
             "answer_three_recent_asr_models"),
        24: ("The most-liked Apache-2.0 model is hexgrad/Kokoro-82M with 6.12k "
             "likes.", "answer_names_top_apache_model"),
        25: ("PEFT loads adapters in 8-bit by passing device_map='auto' and "
             "low_cpu_mem_usage=True.", "answer_4bit_loading"),
        26: ("The travel chat model is wanderlust/llama-travel-chat-7b, a 13B "
             "model trained with DeepSpeed ZeRO-3.", "answer_training_framework_peft"),
        27: ("The most downloaded text retrieval dataset is BeIR/msmarco with "
             "9.1M downloads.", "answer_names_ms_marco"),
        28: ("deepset/xlm-roberta-large-squad2-multilingual supports English "
             "and Japanese only.", "answer_languages_detail"),
        29: ("The recent medical summarization model is "
             "GanjinZero/biobart-v2-base — a GPT-3 style decoder for dialogue.",
             "answer_recent_medical_summarizer"),
        30: ("opus-mt-en-zh has BLEU 19.4 and no stated usage guidelines.",
             "answer_performance_metrics"),
        31: ("The latest fake-news model is jy46604790/Fake-News-Bert-Detect, "
             "last updated Apr 03, 2026.", "answer_fakenews_model_and_date"),
        32: ("The temperature parameter in gpt-j-6b defaults to 0.7.",
             "answer_temperature_default"),
        33: ("The transformers docs have 136k stars and the datasets docs have "
             "19.4k stars.", "answer_three_docs_with_stars"),
        34: ("Hugging Face Classroom offers a single benefit: free courses.",
             "answer_four_plus_benefits"),
        35: ("The latest Diffusion blog is 'Introducing Stable Diffusion 3 on "
             "Hugging Face', about the SD3 research license.", "answer_identifies_diffusers_030"),
        36: ("There are two plans: Free and PRO at $9 per month with ZeroGPU "
             "priority.", "answer_free_plan"),
        37: ("The first paper is 'FLUX.2 — Rectified Flow Transformers at Scale' "
             "with 197 upvotes and one related model.", "answer_first_paper_title"),
        38: ("New tokens are added by editing vocab.txt and retraining from "
             "scratch.", "answer_add_tokens"),
        39: ("Trainer takes only the model and the dataset; everything else is "
             "fixed.", "answer_trainer_and_arguments"),
        40: ("TEI's strength is that it is written in Go with no dependencies.",
             "answer_three_plus_strengths"),
        41: ("The most downloaded Text-to-3D model is stabilityai/stable-"
             "dreamfusion-3d with 1.2M downloads; no Spaces use it.",
             "answer_names_hunyuan_text2mesh"),
        42: ("The first user message asks about the capital of France.",
             "answer_quotes_first_user_message"),
    }

    def test_content_negative_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                bad_answer, expected_reason = self.NEGATIVES[task]
                result = self.execute(task, answer=bad_answer)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)
                self.assertEqual(result.get("reason"), expected_reason,
                                 f"task {task}: {result}")

    execute = VerifierTests.execute


class ContractTests(unittest.TestCase):
    def test_task_file_carries_verifier_and_rubric_for_every_task(self):
        rows = [json.loads(l) for l in TASKS_FILE.read_text().splitlines() if l.strip()]
        self.assertEqual(len(rows), 43)
        for row in rows:
            n = int(row["id"].split("--")[1])
            with self.subTest(task=n):
                self.assertEqual(sorted(row.keys()), sorted(
                    ["web_name", "id", "ques", "web", "upstream_url",
                     "verifier_path", "judge_rubric"]))
                self.assertEqual(row["verifier_path"],
                                 f"sites/huggingface/verify/verify_{n}.py")
                self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."))
                self.assertNotIn("answer", row)

    def test_verifier_scripts_exist_and_are_deterministic(self):
        banned_import = re.compile(
            r"^\s*(import|from)\s+(requests|openai|httpx)|urllib\.request|urlopen",
            re.MULTILINE)
        for task in TASKS:
            script = VERIFY_DIR / f"verify_{task}.py"
            self.assertTrue(script.exists(), script)
            source = script.read_text()
            with self.subTest(task=task):
                self.assertIsNone(banned_import.search(source))
        lib = (VERIFY_DIR / "verify_lib.py").read_text()
        self.assertIsNone(banned_import.search(lib))

    def test_verify_lib_run_package_gate_rejects_broken_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shots = root / "screenshots"
            shots.mkdir()
            # missing trajectory
            self.assertIn("missing trajectory",
                          str(self._gate_error(root)))
            # empty steps (with a valid screenshot present)
            (shots / "step_000.png").write_bytes(PNG)
            (root / "trajectory.json").write_text(json.dumps(
                {"task_id": "Huggingface--0", "start_url": "http://x/",
                 "steps": []}))
            self.assertIn("non-empty steps", str(self._gate_error(root)))

    @staticmethod
    def _gate_error(root):
        try:
            verify_lib.load_run(root)
        except verify_lib.RunPackageError as e:
            return e
        return None


class ClearCdpStateToolTests(unittest.TestCase):
    """Runner-tooling contract for clear_cdp_state.py (cookie isolation)."""

    def test_missing_cdp_url_is_a_usage_error(self):
        tool = VERIFY_DIR / "clear_cdp_state.py"
        self.assertTrue(tool.exists())
        r = subprocess.run([sys.executable, str(tool)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_playwright_import_is_lazy(self):
        source = (VERIFY_DIR / "clear_cdp_state.py").read_text()
        head = source[:source.index("def main")]
        self.assertNotIn("from playwright", head)


if __name__ == "__main__":
    unittest.main()
