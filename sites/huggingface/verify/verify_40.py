#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--40.

Task: Check out Text Embeddings Inference in Hugging face's Doc to summarise the strengths of the toolkit.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/text-embeddings-inference — TEI strengths: Fast (built in Rust,
    CUDA kernels, token-level dynamic batching, Flash Attention); Small
    (Docker images under 150MB, no Python runtime); Production-ready (OpenAPI
    spec, Prometheus metrics, safetensors support); Flexible (BERT, RoBERTa,
    DistilBERT, MPNet, GTE, BGE, E5, Jina and many more); Scalable
    (horizontal scaling, gRPC and HTTP endpoints); Easy to deploy (single
    docker run); Tracing (OpenTelemetry).
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts. Input/Output: verify_lib.parse_args / Judge.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, listing_step,
                        visited_model, visited_dataset, visited_space,
                        visited_model_slugs, contains_all, contains_any,
                        big_number_in, decimal_in, date_token_in, count_named,
                        Judge, parse_args)



def main():
    a = parse_args()
    j = Judge('Huggingface--40', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_tei_doc",
            navigated_any(t, ["text-embeddings-inference", "text embeddings inference",
                              "tei"]),
            "the TEI doc page")
    j.check("answer_names_tei",
            contains_any(fa, ["text embeddings inference", "tei"]),
            f"final={fa[:200]!r}")
    strengths = count_named(fa, ["rust", "cuda", "flash attention", "dynamic batching",
                                "150mb", "no python", "openapi", "prometheus",
                                "safetensors", "grpc", "docker", "opentelemetry",
                                "tracing", "bert", "roberta", "distilbert", "mpnet",
                                "gte", "bge", "e5", "jina", "scalable", "horizontal"])
    j.check("answer_three_plus_strengths", strengths >= 3,
            f"strength_hits={strengths}; final={fa[:300]!r}")

    j.emit()


if __name__ == "__main__":
    main()
