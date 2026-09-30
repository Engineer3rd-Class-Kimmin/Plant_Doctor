from __future__ import annotations

import argparse
import gc
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

PURPOSES = {
    "cause": {
        "label_ko": "병변 발생 이유",
        "queries": (
            "{disease} causal pathogen cause organism etiology infection agent",
            "{disease} caused by fungus bacterium virus pathogen",
            "{disease} disease cause causal agent",
            "{disease} pathogen biology etiology",
        ),
        "keywords": ("cause", "caused by", "pathogen", "fungus", "bacter", "virus", "oomycete", "etiology", "agent"),
    },
    "conditions": {
        "label_ko": "병변 발생 조건",
        "queries": (
            "{disease} favorable environmental conditions temperature humidity rainfall moisture leaf wetness",
            "{disease} infection conditions weather humidity temperature",
            "{disease} disease development environmental factors",
            "{disease} rainfall moisture leaf wetness epidemiology",
        ),
        "keywords": ("condition", "temperature", "humidity", "rain", "moist", "wetness", "warm", "cool", "weather", "infection", "environment"),
    },
    "symptoms": {
        "label_ko": "병변 발생 현상",
        "queries": (
            "{disease} symptoms signs visual lesions leaves fruit stems appearance progression",
            "{disease} leaf symptoms fruit symptoms lesion color shape",
            "{disease} characteristic symptoms diagnosis distinguish",
            "{disease} visible disease signs affected plant parts",
        ),
        "keywords": ("symptom", "sign", "lesion", "spot", "rot", "blight", "mosaic", "yellow", "brown", "black", "olive", "scab", "leaf", "fruit", "stem", "corky", "necrotic", "chlorotic"),
    },
    "prevention": {
        "label_ko": "병변 예방법",
        "queries": (
            "{disease} prevention sanitation resistant cultivars cultural control avoid reduce risk",
            "{disease} preventive management orchard sanitation",
            "{disease} disease prevention resistant varieties monitoring",
            "{disease} reduce infection risk cultural practices",
        ),
        "keywords": ("prevent", "sanitation", "resistant", "avoid", "remove", "rotation", "monitor", "reduce", "clean", "cultural control", "pruning"),
    },
    "action": {
        "label_ko": "병변에 맞는 조치",
        "queries": (
            "{disease} management control treatment recommended actions remove infected tissue",
            "{disease} disease control fungicide bactericide treatment",
            "{disease} extension management recommendations",
            "{disease} what to do after symptoms appear",
        ),
        "keywords": ("management", "control", "treatment", "fungicide", "bactericide", "remove", "prune", "destroy", "application", "recommend", "spray"),
    },
}

OUTPUT_FIELDS = ("cause", "conditions", "symptoms", "prevention", "action")
SELECTION_PURPOSES = ("symptoms",)


GENERAL_DISEASE_ID = "__general_agriculture__"
GENERAL_PURPOSES = {"conditions", "prevention", "action"}

def normalize_label(value: str) -> str:
    value = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return re.sub(r"_+", "_", value).strip("_")


def humanize(value: str) -> str:
    return normalize_label(value).replace("_", " ")


def label_host(label: str) -> str:
    value = normalize_label(label)
    return value.split("_", 1)[0] if "_" in value else value


def candidate_label(item: dict) -> str:
    for key in ("label", "disease_id", "class_name", "name", "class"):
        if item.get(key):
            return normalize_label(item[key])
    return ""


def candidate_probability(item: dict) -> float:
    for key in ("probability", "confidence", "score", "prob", "softmax"):
        try:
            if item.get(key) is not None:
                return float(item[key])
        except (TypeError, ValueError):
            pass
    return 0.0


def softmax(values):
    if not values:
        return []
    vals = np.asarray(values, dtype=np.float64)
    vals = vals - np.max(vals)
    exps = np.exp(vals)
    return (exps / max(exps.sum(), 1e-12)).tolist()


def extract_prediction_items(data: dict):
    for key in ("all_predictions", "predictions", "all_classes", "ranked_predictions", "top_k"):
        value = data.get(key)
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            return [dict(x) for x in value], key
    labels = None
    for key in ("classes", "labels", "class_names", "disease_ids"):
        if isinstance(data.get(key), list):
            labels = data[key]
            break
    if labels:
        for key in ("probabilities", "probs", "scores", "softmax"):
            vals = data.get(key)
            if isinstance(vals, list) and len(vals) == len(labels):
                return [{"label": l, "probability": p} for l, p in zip(labels, vals)], key
        logits = data.get("logits")
        if isinstance(logits, list) and len(logits) == len(labels):
            probs = softmax(logits)
            return [{"label": l, "probability": p} for l, p in zip(labels, probs)], "logits"
    for key in ("probabilities", "scores", "probs"):
        mapping = data.get(key)
        if isinstance(mapping, dict):
            return [{"label": k, "probability": v} for k, v in mapping.items()], key
    return [], "not_found"


def load_candidates(path: Path, host: str | None, top_n: int, min_probability: float):
    data = json.loads(path.read_text(encoding="utf-8"))
    items, schema = extract_prediction_items(data)
    rows = []
    for item in items:
        label = candidate_label(item)
        prob = candidate_probability(item)
        if not label or prob < min_probability:
            continue
        if host and label_host(label) != normalize_label(host):
            continue
        rows.append({"disease_id": label, "probability": prob})
    rows.sort(key=lambda x: x["probability"], reverse=True)
    total = sum(max(0.0, x["probability"]) for x in rows[:top_n])
    for row in rows:
        row["host_normalized_probability"] = (row["probability"] / total) if total > 0 else 0.0
    return rows[:top_n], schema


def load_index(work_dir: Path):
    root = work_dir / "rag_embedding_index"
    emb_path = root / "embeddings.npy"
    meta_path = root / "metadata.jsonl"
    manifest_path = root / "index_manifest.json"
    if not emb_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"임베딩 인덱스가 없습니다: {root}")
    embeddings = np.load(emb_path, mmap_mode="r")
    metadata = []
    with meta_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                metadata.append(json.loads(line))
    if len(metadata) != embeddings.shape[0]:
        raise RuntimeError(f"벡터/메타데이터 수 불일치: {embeddings.shape[0]} != {len(metadata)}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return embeddings, metadata, manifest


def load_embedding_model(model_name: str, device: str, local_only: bool):
    from sentence_transformers import SentenceTransformer
    kwargs = {"device": device}
    if local_only:
        kwargs["local_files_only"] = True
    return SentenceTransformer(model_name, **kwargs)


def lexical_bonus(text: str, keywords) -> float:
    low = text.lower()
    hits = sum(1 for k in keywords if k in low)
    return min(0.12, hits * 0.015)


def source_key(row: dict) -> str:
    return str(row.get("source_id") or row.get("url") or row.get("source_title") or row.get("chunk_id"))


def normalize_text_key(text: str) -> str:
    return re.sub(r"\W+", " ", str(text).lower()).strip()


def reciprocal_rank_fusion(rankings: list[list[int]], rrf_k: int = 60) -> dict[int, float]:
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[int(idx)] += 1.0 / (rrf_k + rank)
    return dict(scores)


def load_reranker(model_name: str, device: str, local_only: bool):
    if not model_name:
        return None
    from sentence_transformers import CrossEncoder
    kwargs = {"device": device}
    if local_only:
        kwargs["local_files_only"] = True
    print(f"loading_reranker={model_name} device={device}")
    return CrossEncoder(model_name, **kwargs)


def retrieve_for_purpose(
    disease_id: str,
    purpose: str,
    embedder,
    reranker,
    embeddings,
    metadata,
    candidate_pool: int,
    rerank_pool: int,
    top_k: int,
    max_per_source: int,
    rrf_k: int,
    query_subject: str | None = None,
):
    spec = PURPOSES[purpose]
    subject = query_subject or humanize(disease_id)
    queries = [q.format(disease=subject) for q in spec["queries"]]
    indices = [i for i, row in enumerate(metadata) if normalize_label(row.get("disease_id")) == disease_id]
    if not indices:
        return []

    matrix = np.asarray(embeddings[indices], dtype=np.float32)
    query_texts = ["query: " + q for q in queries]
    query_vectors = embedder.encode(query_texts, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)

    rankings = []
    semantic_by_global = defaultdict(float)
    for qv in query_vectors:
        scores = matrix @ qv
        local_order = np.argsort(scores)[::-1][:candidate_pool]
        global_order = []
        for pos in local_order:
            global_idx = indices[int(pos)]
            global_order.append(global_idx)
            semantic_by_global[global_idx] = max(semantic_by_global[global_idx], float(scores[int(pos)]))
        rankings.append(global_order)

    fused = reciprocal_rank_fusion(rankings, rrf_k=rrf_k)
    fused_order = sorted(fused, key=fused.get, reverse=True)[:rerank_pool]

    rows = []
    for idx in fused_order:
        row = dict(metadata[idx])
        text = str(row.get("text", ""))
        semantic = semantic_by_global.get(idx, 0.0)
        lexical = lexical_bonus(text, spec["keywords"])
        categories = {str(x) for x in row.get("categories", [])}
        category_bonus = 0.04 if purpose in categories else 0.0
        peer_bonus = 0.015 if row.get("peer_reviewed") else 0.0
        rows.append({
            **row,
            "_global_idx": idx,
            "purpose": purpose,
            "semantic_score": semantic,
            "rrf_score": float(fused.get(idx, 0.0)),
            "lexical_bonus": lexical,
            "category_bonus": category_bonus,
            "peer_bonus": peer_bonus,
        })

    if reranker is not None and rows:
        primary_query = queries[0]
        pairs = [(primary_query, str(row.get("text", ""))) for row in rows]
        rerank_scores = reranker.predict(pairs)
        for row, score in zip(rows, rerank_scores):
            row["reranker_score"] = float(score)
        rows.sort(key=lambda row: (row["reranker_score"], row["rrf_score"], row["semantic_score"]), reverse=True)
    else:
        for row in rows:
            row["reranker_score"] = None
            row["fallback_score"] = row["semantic_score"] + row["lexical_bonus"] + row["category_bonus"] + row["peer_bonus"]
        rows.sort(key=lambda row: (row["fallback_score"], row["rrf_score"]), reverse=True)

    selected = []
    source_counts = defaultdict(int)
    seen = set()
    for row in rows:
        skey = source_key(row)
        if source_counts[skey] >= max_per_source:
            continue
        norm = normalize_text_key(row.get("text", ""))
        fingerprint = norm[:500]
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        source_counts[skey] += 1
        selected.append({
            **{k: v for k, v in row.items() if not k.startswith("_")},
            "query_variants": queries,
            "retrieval_score": round(float(row["reranker_score"] if row["reranker_score"] is not None else row["fallback_score"]), 6),
            "semantic_score": round(float(row["semantic_score"]), 6),
            "rrf_score": round(float(row["rrf_score"]), 6),
            "reranker_score": round(float(row["reranker_score"]), 6) if row["reranker_score"] is not None else None,
        })
        if len(selected) >= top_k:
            break
    return selected


def load_legacy_coverage_evidence(rag_root: Path, disease_id: str, purpose: str, top_k: int):
    """Fallback for diseases already marked RAG_READY before the embedding index was built.

    Reads approved facts from <rag_root>/raw/<disease>/extracted/*_combined_coverage.json
    and converts them to the same evidence-row schema used by vector retrieval.
    """
    extracted = rag_root / "raw" / disease_id / "extracted"
    candidates = [
        extracted / f"{disease_id}_combined_coverage.json",
        *sorted(extracted.glob("*_combined_coverage.json")),
    ]
    coverage_path = next((x for x in candidates if x.exists()), None)
    if coverage_path is None:
        return []
    try:
        data = json.loads(coverage_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    facts = data.get("approved_facts") or data.get("facts") or []
    if not isinstance(facts, list):
        return []

    category_map = {
        "cause": {"pathogen"},
        "conditions": {"favorable_conditions"},
        "symptoms": {"symptoms", "affected_parts", "differential_diagnosis"},
        "prevention": {"management", "transmission", "favorable_conditions"},
        "action": {"management"},
    }
    allowed = category_map[purpose]
    rows = []
    for idx, fact in enumerate(facts, start=1):
        if not isinstance(fact, dict):
            continue
        category = str(fact.get("category") or fact.get("fact_type") or "").strip()
        if category not in allowed:
            continue
        text = str(
            fact.get("fact_en")
            or fact.get("fact")
            or fact.get("evidence_quote")
            or fact.get("quote")
            or fact.get("text")
            or ""
        ).strip()
        if not text:
            continue
        source_url = str(fact.get("source_url") or fact.get("url") or "")
        source_id = str(fact.get("source_id") or f"{disease_id}_legacy_{idx:04d}")
        publisher = str(fact.get("publisher") or fact.get("source_publisher") or "")
        title = str(fact.get("source_title") or fact.get("title") or coverage_path.stem)
        rows.append({
            "disease_id": disease_id,
            "purpose": purpose,
            "retrieval_score": 1.0,
            "semantic_score": None,
            "rrf_score": None,
            "reranker_score": None,
            "query_variants": [f"legacy approved fact: {purpose}"],
            "chunk_id": str(fact.get("candidate_id") or f"legacy_{idx:04d}"),
            "source_id": source_id,
            "source_title": title,
            "publisher": publisher,
            "url": source_url,
            "doi": str(fact.get("doi") or ""),
            "record_id": str(fact.get("record_id") or ""),
            "text": text,
            "categories": [category],
            "legacy_coverage_fallback": True,
            "coverage_path": str(coverage_path),
        })
        if len(rows) >= top_k:
            break
    return rows


def build_stage1_selection_evidence(candidates, embedder, reranker, embeddings, metadata, rag_root, args):
    evidence = []
    candidate_payload = []
    seq = 1
    for cand in candidates:
        disease_id = cand["disease_id"]
        purpose_map = {}
        for purpose in SELECTION_PURPOSES:
            rows = retrieve_for_purpose(
                disease_id=disease_id,
                purpose=purpose,
                embedder=embedder,
                reranker=reranker,
                embeddings=embeddings,
                metadata=metadata,
                candidate_pool=args.retrieval_candidate_pool,
                rerank_pool=args.rerank_pool,
                top_k=args.selection_evidence_per_candidate,
                max_per_source=args.max_per_source,
                rrf_k=args.rrf_k,
            )
            if not rows:
                rows = load_legacy_coverage_evidence(
                    rag_root, disease_id, purpose, args.selection_evidence_per_candidate
                )
                if rows:
                    print(f"legacy_rag_fallback disease={disease_id} purpose={purpose} rows={len(rows)}")
            ids = []
            for row in rows:
                eid = f"S{seq:04d}"
                seq += 1
                ids.append(eid)
                evidence.append({
                    "evidence_id": eid,
                    "disease_id": disease_id,
                    "purpose": purpose,
                    "score": row["retrieval_score"],
                    "semantic_score": row["semantic_score"],
                    "rrf_score": row["rrf_score"],
                    "reranker_score": row["reranker_score"],
                    "query_variants": row["query_variants"],
                    "chunk_id": row.get("chunk_id", ""),
                    "source_id": row.get("source_id", ""),
                    "source_title": row.get("source_title", ""),
                    "publisher": row.get("publisher", ""),
                    "url": row.get("url", ""),
                    "doi": row.get("doi", ""),
                    "record_id": row.get("record_id", ""),
                    "text": row.get("text", ""),
                })
            purpose_map[purpose] = ids
        candidate_payload.append({**cand, "selection_evidence_by_purpose": purpose_map})
    return candidate_payload, evidence


def build_stage2_explanation_evidence(
    selected_disease_id,
    embedder,
    reranker,
    embeddings,
    metadata,
    rag_root,
    args,
):
    evidence = []
    purpose_map = {}
    seq = 1
    host = label_host(selected_disease_id)
    general_subject = " ".join(
        part for part in (host, humanize(selected_disease_id), "crop management")
        if part
    )

    for purpose in PURPOSES:
        rows = retrieve_for_purpose(
            disease_id=selected_disease_id,
            purpose=purpose,
            embedder=embedder,
            reranker=reranker,
            embeddings=embeddings,
            metadata=metadata,
            candidate_pool=args.retrieval_candidate_pool,
            rerank_pool=args.rerank_pool,
            top_k=args.evidence_per_purpose,
            max_per_source=args.max_per_source,
            rrf_k=args.rrf_k,
        )

        # General agricultural evidence is allowed only for conditions,
        # prevention and action. It never participates in diagnosis selection,
        # cause attribution or symptom matching.
        if purpose in GENERAL_PURPOSES and len(rows) < args.evidence_per_purpose:
            general_rows = retrieve_for_purpose(
                disease_id=GENERAL_DISEASE_ID,
                purpose=purpose,
                embedder=embedder,
                reranker=reranker,
                embeddings=embeddings,
                metadata=metadata,
                candidate_pool=args.retrieval_candidate_pool,
                rerank_pool=args.rerank_pool,
                top_k=args.evidence_per_purpose,
                max_per_source=args.max_per_source,
                rrf_k=args.rrf_k,
                query_subject=general_subject,
            )
            seen = {
                normalize_text_key(str(row.get("text", "")))
                for row in rows
            }
            for row in general_rows:
                key = normalize_text_key(str(row.get("text", "")))
                if not key or key in seen:
                    continue
                copied = dict(row)
                copied["evidence_scope"] = "general_agriculture"
                copied["scope_disease_id"] = GENERAL_DISEASE_ID
                rows.append(copied)
                seen.add(key)
                if len(rows) >= args.evidence_per_purpose:
                    break

        if not rows:
            rows = load_legacy_coverage_evidence(
                rag_root,
                selected_disease_id,
                purpose,
                args.evidence_per_purpose,
            )
            if rows:
                print(
                    f"legacy_rag_fallback disease={selected_disease_id} "
                    f"purpose={purpose} rows={len(rows)}"
                )

        ids = []
        for row in rows[: args.evidence_per_purpose]:
            eid = f"E{seq:04d}"
            seq += 1
            ids.append(eid)
            scope = row.get("evidence_scope") or (
                "general_agriculture"
                if normalize_label(row.get("disease_id")) == GENERAL_DISEASE_ID
                else "disease_specific"
            )
            evidence.append({
                "evidence_id": eid,
                # Keep selected disease here so same-disease citation validation
                # remains strict, while scope_disease_id preserves provenance.
                "disease_id": selected_disease_id,
                "scope_disease_id": row.get(
                    "scope_disease_id",
                    row.get("disease_id", selected_disease_id),
                ),
                "evidence_scope": scope,
                "purpose": purpose,
                "score": row["retrieval_score"],
                "semantic_score": row["semantic_score"],
                "rrf_score": row["rrf_score"],
                "reranker_score": row["reranker_score"],
                "query_variants": row["query_variants"],
                "chunk_id": row.get("chunk_id", ""),
                "source_id": row.get("source_id", ""),
                "source_title": row.get("source_title", ""),
                "publisher": row.get("publisher", ""),
                "url": row.get("url", ""),
                "doi": row.get("doi", ""),
                "record_id": row.get("record_id", ""),
                "text": row.get("text", ""),
            })
        purpose_map[purpose] = ids
    return purpose_map, evidence

def selection_prompt(candidates, evidence, host):
    ev_compact = [{
        "evidence_id": e["evidence_id"],
        "disease_id": e["disease_id"],
        "purpose": e["purpose"],
        "source_title": e["source_title"],
        "text": e["text"],
    } for e in evidence]
    schema = {
        "selected_disease": "candidate disease id or null",
        "confidence": "high|medium|low",
        "status": "SUPPORTED or INSUFFICIENT_EVIDENCE",
        "reasoning_summary": "brief Korean summary",
        "visual_findings": ["brief Korean findings"],
        "supporting_evidence_ids": ["S0001"],
        "alternatives_considered": ["candidate ids"],
    }
    return f"""
You are the diagnostic selection stage for Plant ER.
Confirmed host: {host or 'unknown'}
Task: Choose the most likely disease among the classifier candidates using the image (if provided), the classifier probabilities, and symptom-focused retrieved evidence.
Important policy:
- HOST IS IMMUTABLE. The confirmed host above is an external user input.
- You MUST choose only a disease whose disease_id host prefix exactly matches the confirmed host.
- Never replace, broaden, infer, or normalize the confirmed host into another crop.
- Do NOT choose a disease only because it has more RAG text.
- Use RAG evidence only to compare visible symptoms and distinguish candidates.
- If the image does not sufficiently support an alternative to the classifier top-1 candidate, stay conservative.
- Supporting evidence IDs must come only from the selection evidence bundle.
Classifier candidates:
{json.dumps(candidates, ensure_ascii=False)}
Selection evidence:
{json.dumps(ev_compact, ensure_ascii=False)}
Return JSON only in this schema:
{json.dumps(schema, ensure_ascii=False)}
""".strip()


def explanation_prompt(selected_disease_id: str, host: str, purpose_map: dict, evidence: list[dict], alternatives: list[str]):
    ev_compact = [{
        "evidence_id": e["evidence_id"],
        "purpose": e["purpose"],
        "evidence_scope": e.get("evidence_scope", "disease_specific"),
        "scope_disease_id": e.get("scope_disease_id", e.get("disease_id", "")),
        "source_title": e["source_title"],
        "publisher": e["publisher"],
        "doi": e["doi"],
        "url": e["url"],
        "text": e["text"],
    } for e in evidence]
    schema = {
        "status": "SUPPORTED or INSUFFICIENT_EVIDENCE",
        "disease": {"label": selected_disease_id, "name_ko": "Korean disease name", "confidence": "high|medium|low"},
        "cause": {"summary": "Korean summary or null", "evidence_ids": ["E0001"]},
        "conditions": {"summary": "Korean summary or null", "evidence_ids": ["E0002"]},
        "symptoms": {"summary": "Korean summary or null", "evidence_ids": ["E0003"]},
        "prevention": {"summary": "Korean summary or null", "evidence_ids": ["E0004"]},
        "action": {"summary": "Korean summary or null", "evidence_ids": ["E0005"]},
        "alternatives_considered": alternatives,
        "reasoning_summary": "Brief Korean summary without hidden chain-of-thought",
    }
    return f"""
You are the explanation stage for Plant ER.
Selected disease: {selected_disease_id}
Confirmed host: {host}
Use ONLY evidence for the selected disease.
Write Korean output for the six requested fields.
Rules:
1. Every non-null field cause, conditions, symptoms, prevention, action MUST include evidence_ids.
2. Only cite evidence IDs belonging to the same field purpose.
3. Evidence with evidence_scope=general_agriculture may support only conditions, prevention, or action. It must never be used to claim the disease cause or visible symptoms.
3. If evidence is indirect, incomplete, or not specific enough for that field, return null for that field.
4. Symptoms must name at least one affected plant part and at least two concrete visible descriptors such as color, shape, texture, lesion pattern, progression, or tissue change. Never write a circular sentence such as "the disease occurs on the plant."
5. Conditions must describe actual disease-favoring conditions, not merely study settings.
6. Prevention must be preventive behavior before/for risk reduction.
7. Action must be concrete management steps after disease occurrence, not just severity scoring.
8. Keep each summary limited to claims directly stated in its cited evidence. Do not combine uncited details.
Evidence by purpose map:
{json.dumps(purpose_map, ensure_ascii=False)}
Retrieved evidence:
{json.dumps(ev_compact, ensure_ascii=False)}
Return JSON only in this schema:
{json.dumps(schema, ensure_ascii=False)}
""".strip()


def load_gemma_4bit(model_path: Path, device: str = "cuda:0"):
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
    import torch.nn as nn

    if not torch.cuda.is_available():
        raise RuntimeError("4-bit Gemma 실행에는 CUDA GPU가 필요합니다.")
    try:
        device_index = int(str(device).split(":")[-1]) if ":" in str(device) else 0
    except ValueError as exc:
        raise ValueError(f"잘못된 --gemma-device 값입니다: {device}") from exc

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_storage=torch.uint8,
    )

    processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)
    print(f"loading_gemma=4bit_nf4 device=cuda:{device_index} cpu_offload=disabled")
    try:
        model = AutoModelForImageTextToText.from_pretrained(
            str(model_path),
            local_files_only=True,
            quantization_config=quantization_config,
            device_map={"": device_index},
            low_cpu_mem_usage=True,
            dtype=torch.bfloat16,
        )
    except TypeError:
        model = AutoModelForImageTextToText.from_pretrained(
            str(model_path),
            local_files_only=True,
            quantization_config=quantization_config,
            device_map={"": device_index},
            low_cpu_mem_usage=True,
            torch_dtype=torch.bfloat16,
        )

    device_map = getattr(model, "hf_device_map", {}) or {}
    forbidden = {str(v) for v in device_map.values() if str(v).lower() in {"cpu", "disk", "meta"}}
    if forbidden:
        raise RuntimeError(f"CPU/disk/meta offload 감지: {device_map}")

    vision_module = None
    candidate_paths = (("model", "embed_vision"), ("model", "vision_tower"), ("vision_tower",), ("model", "vision_model"), ("vision_model",))
    for path_parts in candidate_paths:
        current = model
        ok = True
        for part in path_parts:
            if not hasattr(current, part):
                ok = False
                break
            current = getattr(current, part)
        if ok:
            vision_module = current
            break
    if vision_module is None:
        raise RuntimeError("Gemma 비전 타워를 찾지 못했습니다.")
    count = 0
    for module in vision_module.modules():
        if isinstance(module, nn.LayerNorm):
            module.to(device=torch.device(f"cuda:{device_index}"), dtype=torch.bfloat16)
            count += 1
    if count == 0:
        raise RuntimeError("Gemma 비전 LayerNorm을 찾지 못했습니다.")

    model.eval()
    print(f"gemma_hf_device_map={device_map}")
    print(f"gemma_is_4bit={bool(getattr(model, 'is_loaded_in_4bit', False))}")
    print(f"vision_layernorm_alignment=count:{count} dtype:{torch.bfloat16} text_model_quantization:4bit_nf4")
    return processor, model, torch.device(f"cuda:{device_index}")


def run_gemma(processor, model, input_device, prompt: str, image_path: Path | None, max_new_tokens: int):
    import torch
    content = []
    if image_path:
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        content.append({"type": "image", "image": image})
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]
    inputs = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt")
    prepared = {}
    for key, value in inputs.items():
        if not hasattr(value, "to"):
            prepared[key] = value
            continue
        value = value.to(input_device)
        if key == "pixel_values":
            value = value.to(dtype=torch.bfloat16)
        prepared[key] = value
    inputs = prepared
    input_dtypes = {k: str(v.dtype) for k, v in inputs.items() if hasattr(v, "dtype")}
    print(f"gemma_input_dtypes={input_dtypes}")
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, use_cache=True)
    generated = output[0, inputs["input_ids"].shape[-1]:]
    return processor.decode(generated, skip_special_tokens=True)


def parse_json_object(text: str):
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise RuntimeError("Gemma 출력에서 JSON 객체를 찾지 못했습니다.")
    return json.loads(match.group(0))


def candidate_map(candidates: list[dict]):
    return {normalize_label(c["disease_id"]): c for c in candidates}


def validate_selection(selection: dict, candidates: list[dict], selection_evidence: list[dict], args, locked_host: str):
    cmap = candidate_map(candidates)
    evidence_map = {e["evidence_id"]: e for e in selection_evidence}
    top1 = candidates[0]
    top2 = candidates[1] if len(candidates) > 1 else None
    top1_norm = float(top1.get("host_normalized_probability", 0.0))
    top1_ratio = float(top1["probability"]) / max(float(top2["probability"]) if top2 else 1e-12, 1e-12)

    selected = normalize_label(selection.get("selected_disease")) if selection.get("selected_disease") else ""
    if selected not in cmap:
        selected = normalize_label(top1["disease_id"])

    host_violation_detected = label_host(selected) != locked_host
    if host_violation_detected:
        selected = normalize_label(top1["disease_id"])
    sel_row = cmap[selected]
    sel_norm = float(sel_row.get("host_normalized_probability", 0.0))

    valid_ids = []
    for eid in selection.get("supporting_evidence_ids", []):
        ev = evidence_map.get(str(eid))
        if ev and normalize_label(ev["disease_id"]) == selected and ev["purpose"] == "symptoms":
            valid_ids.append(str(eid))

    fallback_reason = None
    if not valid_ids:
        fallback_reason = "NO_VALID_SELECTION_EVIDENCE"
        selected = normalize_label(top1["disease_id"])
    elif selected != normalize_label(top1["disease_id"]):
        if top1_norm >= args.top1_lock_norm_probability and top1_ratio >= args.top1_lock_probability_ratio:
            fallback_reason = "TOP1_LOCKED_BY_CLASSIFIER"
            selected = normalize_label(top1["disease_id"])
        elif sel_norm < args.min_overrule_normalized_probability:
            fallback_reason = "ALTERNATIVE_PROBABILITY_TOO_LOW"
            selected = normalize_label(top1["disease_id"])

    out = {
        "selected_disease": selected,
        "status": selection.get("status", "SUPPORTED") if selected else "INSUFFICIENT_EVIDENCE",
        "confidence": selection.get("confidence", "medium"),
        "reasoning_summary": str(selection.get("reasoning_summary", "")).strip(),
        "visual_findings": selection.get("visual_findings", []) if isinstance(selection.get("visual_findings"), list) else [],
        "supporting_evidence_ids": valid_ids,
        "alternatives_considered": [normalize_label(x) for x in selection.get("alternatives_considered", []) if normalize_label(x) in cmap],
        "selection_fallback_reason": fallback_reason,
        "top1_classifier_candidate": top1,
        "locked_host": locked_host,
        "host_invariant_ok": label_host(selected) == locked_host,
        "host_violation_detected": host_violation_detected,
    }
    if fallback_reason:
        out["status"] = "SUPPORTED"
        out["confidence"] = "medium" if top1_norm < 0.9 else "high"
    if not out["alternatives_considered"]:
        out["alternatives_considered"] = [c["disease_id"] for c in candidates if normalize_label(c["disease_id"]) != selected]
    return out


def text_has_any(text: str, patterns):
    low = str(text or "").lower()
    return any(p in low for p in patterns)


def count_term_hits(text: str, patterns) -> int:
    low = str(text or "").lower()
    return sum(1 for p in patterns if p in low)


def field_supports_summary(field: str, summary: str, evidence_rows: list[dict]):
    """
    Bilingual/mixed-language validation.

    - Korean, English, and Latin scientific names are all allowed.
    - English keywords are NOT required in the Korean summary.
    - Keywords are auxiliary signals, never the sole pass/fail condition.
    - The primary gate is: valid same-disease/same-purpose evidence exists,
      the summary is non-empty and non-circular, and the cited evidence
      contains concrete information appropriate to the field.
    """
    summary_text = str(summary or "").strip()
    if not summary_text or not evidence_rows:
        return False

    summary_low = summary_text.lower()
    evidence_text = "\n".join(str(ev.get("text", "")) for ev in evidence_rows).strip()
    evidence_low = evidence_text.lower()
    if not evidence_low:
        return False

    # Very short or circular summaries are not useful even when cited.
    generic_only = (
        "질병이 발생", "병이 발생", "증상이 나타납니다", "발생합니다.",
        "disease occurs", "disease is present", "symptoms occur",
        "this disease occurs", "infection occurs",
    )
    if any(p in summary_low for p in generic_only) and len(summary_text) < 80:
        return False

    # Bilingual field vocabularies. These are used as supporting signals.
    vocab = {
        "cause": (
            "원인", "병원균", "균", "곰팡이", "세균", "바이러스", "감염",
            "cause", "caused by", "causal", "pathogen", "fungus", "fungal",
            "bacter", "virus", "oomycete", "etiology", "agent", "infection",
        ),
        "conditions": (
            "온도", "기온", "습도", "강우", "비", "습윤", "수분", "환경",
            "가뭄", "상처", "스트레스", "젖", "조건",
            "temperature", "humidity", "rain", "rainfall", "moisture",
            "wetness", "wet", "weather", "environment", "drought", "wound",
            "stress", "favorable", "condition",
        ),
        "symptoms": (
            "증상", "병징", "병반", "반점", "변색", "부패", "썩", "괴사",
            "잎", "과실", "열매", "가지", "줄기", "꽃", "수피", "미라",
            "검은", "갈색", "보라", "붉", "노란", "원형", "동심", "함몰", "균열",
            "symptom", "sign", "lesion", "spot", "discolor", "rot", "necrot",
            "leaf", "fruit", "stem", "branch", "blossom", "bark", "mumm",
            "black", "brown", "purple", "red", "yellow", "circular",
            "concentric", "sunken", "crack", "corky", "chlorotic",
        ),
        "prevention": (
            "예방", "위생", "청소", "제거", "저항성", "회피", "모니터링", "전정",
            "발생 전", "위험 감소", "재배 관리",
            "prevent", "prevention", "sanitation", "clean", "remove", "resistant",
            "avoid", "monitor", "prune", "cultural control", "reduce risk",
        ),
        "action": (
            "조치", "방제", "처리", "관리", "살균제", "세균제", "제거", "폐기",
            "전정", "살포", "치료", "감염 후",
            "action", "management", "control", "treatment", "fungicide",
            "bactericide", "remove", "destroy", "prune", "spray", "application",
        ),
    }

    field_terms = vocab[field]
    evidence_hits = count_term_hits(evidence_low, field_terms)
    summary_hits = count_term_hits(summary_low, field_terms)

    # The evidence must contain at least one concrete field-relevant signal.
    # The summary may be Korean, English, or mixed, so summary keyword absence
    # alone never causes rejection when the evidence and structure are sound.
    if evidence_hits == 0:
        return False

    if field == "symptoms":
        part_terms = (
            "잎", "과실", "열매", "가지", "줄기", "꽃", "수피",
            "leaf", "fruit", "stem", "branch", "blossom", "bark",
        )
        descriptor_terms = (
            "검은", "갈색", "보라", "붉", "노란", "원형", "동심", "썩",
            "함몰", "괴사", "반점", "병반", "미라", "균열", "변색",
            "black", "brown", "purple", "red", "yellow", "circular",
            "concentric", "rot", "sunken", "necrot", "spot", "lesion",
            "mumm", "crack", "corky", "chlorotic", "discolor",
        )
        # Require concrete visible content in the summary itself. Mixed-language
        # phrases such as "과실의 black lesion" are fully accepted.
        if not text_has_any(summary_low, part_terms):
            return False
        if count_term_hits(summary_low, descriptor_terms) < 2:
            return False
        return True

    # For non-symptom fields, valid purpose-aligned evidence plus a meaningful
    # non-empty summary is sufficient. A bilingual keyword hit strengthens the
    # signal but is not mandatory because scientific names can carry the key fact.
    if len(summary_text) < 8:
        return False
    if summary_hits == 0:
        # Accept Latin/scientific names or numeric environmental facts even when
        # ordinary Korean/English cue words are absent.
        has_scientific_name = bool(re.search(r"\b[A-Z][a-z]{2,}\s+[a-z][a-z-]{2,}\b", summary_text))
        has_numeric_fact = bool(re.search(r"\d+(?:\.\d+)?\s*(?:°?[CF]|℃|℉|%|시간|hours?|days?)", summary_text, flags=re.I))
        if not (has_scientific_name or has_numeric_fact or len(summary_text) >= 20):
            return False
    return True

def build_repair_prompt(selected_disease: str, invalid_fields: list[str], evidence: list[dict]):
    relevant = [e for e in evidence if e.get("purpose") in invalid_fields]
    schema = {field: {"summary": "Korean summary or null", "evidence_ids": ["E0001"]} for field in invalid_fields}
    return f"""
You are repairing weak evidence-grounded fields for Plant ER.
Selected disease: {selected_disease}
Repair only these fields: {json.dumps(invalid_fields, ensure_ascii=False)}
Evidence:
{json.dumps(relevant, ensure_ascii=False)}
Rules:
- Use only the supplied evidence.
- Every non-null field must cite evidence IDs from the same purpose.
- For symptoms, include an affected plant part and at least two concrete visible descriptors. Do not write a circular statement that merely says the disease occurs.
- For conditions, state actual favorable environmental or host-stress conditions.
- For prevention and action, state concrete plant-management behavior.
- Return JSON only:
{json.dumps(schema, ensure_ascii=False)}
""".strip()



def normalize_evidence_ids(value) -> list[str]:
    """Return a safe list of evidence IDs from unreliable model JSON."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []

    cleaned = []
    seen = set()
    for item in value:
        if item is None:
            continue
        evidence_id = str(item).strip()
        if not evidence_id or evidence_id.lower() in {"null", "none"}:
            continue
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        cleaned.append(evidence_id)
    return cleaned


def normalize_explanation_fields(payload: dict) -> dict:
    """Normalize nullable or malformed factual fields before validation."""
    if not isinstance(payload, dict):
        return {}

    for field in ("cause", "conditions", "symptoms", "prevention", "action"):
        value = payload.get(field)

        if value is None:
            payload[field] = None
            continue

        if not isinstance(value, dict):
            payload[field] = None
            continue

        summary = value.get("summary")
        if summary is not None:
            summary = str(summary).strip()
        evidence_ids = normalize_evidence_ids(value.get("evidence_ids"))

        if not summary:
            payload[field] = None
            continue

        payload[field] = {
            **value,
            "summary": summary,
            "evidence_ids": evidence_ids,
        }

    alternatives = payload.get("alternatives_considered")
    if alternatives is None:
        payload["alternatives_considered"] = []
    elif isinstance(alternatives, str):
        payload["alternatives_considered"] = [alternatives]
    elif not isinstance(alternatives, list):
        payload["alternatives_considered"] = []

    return payload

def validate_explanation(payload: dict, evidence: list[dict], selected_disease: str, alternatives: list[str]):
    payload = normalize_explanation_fields(payload)
    evidence_map = {e["evidence_id"]: e for e in evidence}
    used_ids = []
    validation = {}

    disease = payload.get("disease") if isinstance(payload.get("disease"), dict) else {}
    model_selected = normalize_label(disease.get("label")) if disease.get("label") else ""
    final_selected = selected_disease if selected_disease else model_selected
    payload["status"] = payload.get("status", "SUPPORTED") if final_selected else "INSUFFICIENT_EVIDENCE"
    payload["disease"] = {
        "label": final_selected or None,
        "name_ko": disease.get("name_ko") or disease.get("label") or humanize(final_selected) if final_selected else None,
        "confidence": disease.get("confidence") or payload.get("confidence") or "medium",
    }

    for field in OUTPUT_FIELDS:
        value = payload.get(field)
        valid = []
        if final_selected and isinstance(value, dict):
            for eid in normalize_evidence_ids(value.get("evidence_ids")):
                ev = evidence_map.get(str(eid))
                if ev and normalize_label(ev["disease_id"]) == final_selected and ev["purpose"] == field:
                    valid.append(str(eid))
        summary = value.get("summary") if isinstance(value, dict) else ""
        supporting_rows = [evidence_map[eid] for eid in valid if eid in evidence_map]
        if not valid or not str(summary or "").strip() or not field_supports_summary(field, summary, supporting_rows):
            payload[field] = None
            validation[field] = "NULL_NO_DIRECT_VALID_CITATION"
        else:
            payload[field] = {"summary": str(summary).strip(), "evidence_ids": list(dict.fromkeys(valid))}
            validation[field] = "CITED"
            used_ids.extend(payload[field]["evidence_ids"])

    missing_fields = [field for field in OUTPUT_FIELDS if payload.get(field) is None]
    if not final_selected:
        payload["status"] = "INSUFFICIENT_EVIDENCE"
    elif missing_fields:
        # A missing descriptive field does not erase a diagnosis selected from
        # image + classifier + symptom-comparison evidence. Preserve every
        # independently cited field and expose exactly what is missing.
        payload["status"] = "SUPPORTED_WITH_MISSING_FIELDS"
    else:
        payload["status"] = "SUPPORTED"
    payload["missing_fields"] = missing_fields

    seen = set()
    sources = []
    for eid in used_ids:
        ev = evidence_map[eid]
        key = str(ev.get("source_id") or ev.get("url") or ev.get("doi") or ev.get("source_title") or eid)
        if key in seen:
            continue
        seen.add(key)
        source_eids = [
            x for x in used_ids
            if str(evidence_map[x].get("source_id") or evidence_map[x].get("url") or evidence_map[x].get("doi") or evidence_map[x].get("source_title") or x) == key
        ]
        sources.append({
            "source_id": ev.get("source_id", ""),
            "title": ev.get("source_title", ""),
            "publisher": ev.get("publisher", ""),
            "url": ev.get("url", ""),
            "doi": ev.get("doi", ""),
            "record_id": ev.get("record_id", ""),
            "evidence_ids": source_eids,
        })

    payload["alternatives_considered"] = alternatives
    payload["citation_validation"] = validation
    payload["sources"] = sources
    payload["citation_policy"] = (
        "Every non-null factual field is backed by same-purpose evidence. "
        "Disease-specific evidence is required for cause and symptoms. "
        "General 농사로 agricultural evidence is allowed only for conditions, "
        "prevention, and action, and its original scope is preserved in "
        "scope_disease_id/evidence_scope."
    )
    return payload


def main():
    p = argparse.ArgumentParser(description="Plant ER host-locked two-stage cited diagnosis harness with 4-bit Gemma")
    p.add_argument("--classifier-json", type=Path, required=True)
    p.add_argument("--work-dir", type=Path, default=Path(r".\runs\bulk_rag_factory"))
    p.add_argument("--rag-root", type=Path, default=Path(r".\data\rag_plant_diseases"))
    p.add_argument("--gemma-model", type=Path, default=Path(r"E:\EyeGuideRAG\models\gemma4\gemma-4-12B-it"))
    p.add_argument("--image", type=Path)
    p.add_argument("--host", required=True, help="Immutable user-selected host.")
    p.add_argument("--top-candidates", type=int, default=3)
    p.add_argument("--min-candidate-probability", type=float, default=0.0)
    p.add_argument("--embedding-model", default="intfloat/multilingual-e5-base")
    p.add_argument("--embedding-device", default="cuda")
    p.add_argument("--embedding-local-files-only", action="store_true")
    p.add_argument("--retrieval-candidate-pool", type=int, default=30)
    p.add_argument("--rerank-pool", type=int, default=20)
    p.add_argument("--rrf-k", type=int, default=60)
    p.add_argument("--reranker-model", default="BAAI/bge-reranker-v2-m3")
    p.add_argument("--reranker-device", default="cuda")
    p.add_argument("--reranker-local-files-only", action="store_true")
    p.add_argument("--disable-reranker", action="store_true")
    p.add_argument("--selection-evidence-per-candidate", type=int, default=3)
    p.add_argument("--evidence-per-purpose", type=int, default=4)
    p.add_argument("--max-per-source", type=int, default=2)
    p.add_argument("--max-new-tokens", type=int, default=2048)
    p.add_argument("--gemma-device", default="cuda:0")
    p.add_argument("--top1-lock-norm-probability", type=float, default=0.65)
    p.add_argument("--top1-lock-probability-ratio", type=float, default=3.0)
    p.add_argument("--min-overrule-normalized-probability", type=float, default=0.15)
    p.add_argument("--output", type=Path, default=Path(r".\runs\plant_er_cited_diagnosis\diagnosis.json"))
    p.add_argument("--retrieval-output", type=Path, default=Path(r".\runs\plant_er_cited_diagnosis\retrieval_bundle.json"))
    args = p.parse_args()

    args.classifier_json = args.classifier_json.resolve()
    args.work_dir = args.work_dir.resolve()
    args.rag_root = args.rag_root.resolve()
    args.gemma_model = args.gemma_model.resolve()
    args.output = args.output.resolve()
    args.retrieval_output = args.retrieval_output.resolve()
    if args.image:
        args.image = args.image.resolve()

    input_host = str(args.host).strip()
    locked_host = normalize_label(input_host)
    if not locked_host:
        raise RuntimeError("--host 값이 비어 있습니다.")

    candidates, schema = load_candidates(
        args.classifier_json,
        locked_host,
        args.top_candidates,
        args.min_candidate_probability,
    )
    if not candidates:
        raise RuntimeError(
            f"입력 host={input_host!r}에 해당하는 classifier 후보가 없습니다."
        )

    cross_host_candidates = [
        row["disease_id"]
        for row in candidates
        if label_host(row["disease_id"]) != locked_host
    ]
    if cross_host_candidates:
        raise RuntimeError(
            f"HOST_INVARIANT_BROKEN: host={input_host!r}, "
            f"cross_host_candidates={cross_host_candidates}"
        )

    args.host = input_host

    embeddings, metadata, manifest = load_index(args.work_dir)
    embedding_model_name = manifest.get("embedding_model") or args.embedding_model
    if args.embedding_model != embedding_model_name:
        print(f"[warning] index model={embedding_model_name}, requested={args.embedding_model}")
    embedder = load_embedding_model(args.embedding_model, args.embedding_device, args.embedding_local_files_only)
    reranker = None
    if not args.disable_reranker:
        reranker = load_reranker(args.reranker_model, args.reranker_device, args.reranker_local_files_only)

    stage1_candidates, stage1_evidence = build_stage1_selection_evidence(candidates, embedder, reranker, embeddings, metadata, args.rag_root, args)
    print(f"selection_candidates={len(stage1_candidates)} selection_evidence={len(stage1_evidence)}")

    if reranker is not None:
        del reranker
    del embedder
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    processor, gemma, gemma_input_device = load_gemma_4bit(args.gemma_model, args.gemma_device)

    stage1_prompt = selection_prompt(stage1_candidates, stage1_evidence, locked_host)
    raw_stage1 = run_gemma(processor, gemma, gemma_input_device, stage1_prompt, args.image, min(args.max_new_tokens, 1024))
    parsed_stage1 = parse_json_object(raw_stage1)
    validated_stage1 = validate_selection(parsed_stage1, candidates, stage1_evidence, args, locked_host)
    selected_disease = validated_stage1["selected_disease"]
    if label_host(selected_disease) != locked_host:
        raise RuntimeError(
            f"HOST_INVARIANT_BROKEN_AFTER_SELECTION: "
            f"input_host={input_host!r}, selected_disease={selected_disease!r}"
        )
    print(
        f"locked_host={input_host} selected_disease={selected_disease} "
        f"selection_fallback_reason={validated_stage1.get('selection_fallback_reason')}"
    )

    embedder = load_embedding_model(args.embedding_model, args.embedding_device, args.embedding_local_files_only)
    reranker = None
    if not args.disable_reranker:
        reranker = load_reranker(args.reranker_model, args.reranker_device, args.reranker_local_files_only)
    purpose_map, stage2_evidence = build_stage2_explanation_evidence(selected_disease, embedder, reranker, embeddings, metadata, args.rag_root, args)
    print(f"explanation_evidence={len(stage2_evidence)}")
    del embedder
    if reranker is not None:
        del reranker
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    alternatives = [
        c["disease_id"]
        for c in candidates
        if normalize_label(c["disease_id"]) != normalize_label(selected_disease)
        and label_host(c["disease_id"]) == locked_host
    ]
    stage2_prompt = explanation_prompt(selected_disease, locked_host, purpose_map, stage2_evidence, alternatives)
    raw_stage2 = run_gemma(processor, gemma, gemma_input_device, stage2_prompt, args.image, args.max_new_tokens)
    parsed_stage2 = parse_json_object(raw_stage2)
    preliminary = validate_explanation(dict(parsed_stage2), stage2_evidence, selected_disease, alternatives)
    invalid_fields = [field for field in OUTPUT_FIELDS if preliminary.get(field) is None]
    raw_repair = None
    if invalid_fields and stage2_evidence:
        print(f"repair_fields={invalid_fields} (only missing fields)")
        repair_prompt = build_repair_prompt(selected_disease, invalid_fields, stage2_evidence)
        raw_repair = run_gemma(processor, gemma, gemma_input_device, repair_prompt, None, min(args.max_new_tokens, 1024))
        repaired = parse_json_object(raw_repair)
        for field in invalid_fields:
            if field in repaired:
                parsed_stage2[field] = repaired[field]
    parsed_stage2 = normalize_explanation_fields(parsed_stage2)
    final = validate_explanation(parsed_stage2, stage2_evidence, selected_disease, alternatives)

    if label_host(selected_disease) != locked_host:
        raise RuntimeError(
            f"HOST_INVARIANT_BROKEN_BEFORE_OUTPUT: "
            f"input_host={input_host!r}, selected_disease={selected_disease!r}"
        )
    if not isinstance(final.get("disease"), dict):
        final["disease"] = {}
    final["disease"]["label"] = selected_disease
    final["host"] = input_host
    final["locked_host"] = input_host
    final["host_normalized"] = locked_host
    final["host_invariant_ok"] = True

    retrieval_bundle = {
        "classifier_json": str(args.classifier_json),
        "rag_root": str(args.rag_root),
        "classifier_schema": schema,
        "host": input_host,
        "locked_host": input_host,
        "host_normalized": locked_host,
        "host_invariant_ok": True,
        "classifier_candidates": candidates,
        "selection_stage": {
            "candidates": stage1_candidates,
            "evidence": stage1_evidence,
            "validated_selection": validated_stage1,
            "raw_model_output": raw_stage1,
        },
        "explanation_stage": {
            "selected_disease": selected_disease,
            "purpose_map": purpose_map,
            "evidence": stage2_evidence,
            "raw_model_output": raw_stage2,
            "raw_repair_output": raw_repair,
        },
        "index_manifest": manifest,
        "retrieval_strategy": {
            "multi_query_count": 4,
            "fusion": "reciprocal_rank_fusion",
            "rrf_k": args.rrf_k,
            "reranker": None if args.disable_reranker else args.reranker_model,
            "rerank_pool": args.rerank_pool,
            "two_stage": True,
            "legacy_coverage_fallback": True,
        },
    }
    args.retrieval_output.parent.mkdir(parents=True, exist_ok=True)
    args.retrieval_output.write_text(json.dumps(retrieval_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    final["selection_stage"] = validated_stage1
    final["classifier_candidates"] = candidates
    final["host"] = input_host
    final["locked_host"] = input_host
    final["host_normalized"] = locked_host
    final["host_invariant_ok"] = True
    final["image"] = str(args.image) if args.image else None
    final["retrieval_bundle"] = str(args.retrieval_output)
    final["raw_model_output"] = {"selection_stage": raw_stage1, "explanation_stage": raw_stage2, "repair_stage": raw_repair}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(final, ensure_ascii=False, indent=2))
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
