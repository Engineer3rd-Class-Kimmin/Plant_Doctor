from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

KOREAN_CATEGORY_TERMS = {
    "pathogen": (
        "병원균", "병원체", "원인균", "곰팡이", "세균", "바이러스",
        "진균", "원인", "발생원인", "병원성",
    ),
    "symptoms": (
        "증상", "병징", "병반", "반점", "갈변", "황화", "시들음",
        "부패", "썩음", "괴사", "마름", "곰팡이", "변색", "점무늬",
        "잎말림", "모자이크", "궤양", "더뎅이",
    ),
    "affected_parts": (
        "잎", "과실", "열매", "줄기", "가지", "뿌리", "꽃", "꽃잎",
        "수피", "괴경", "종자", "꼬투리", "생장점",
    ),
    "favorable_conditions": (
        "발생조건", "발생 환경", "온도", "습도", "강우", "비", "수분",
        "다습", "건조", "저온", "고온", "기상", "환경조건", "발생시기",
    ),
    "transmission": (
        "전염", "전파", "감염", "포자", "빗물", "바람", "매개충",
        "토양전염", "종자전염", "월동", "확산",
    ),
    "management": (
        "방제", "예방", "관리", "처리", "약제", "농약", "살균제",
        "제거", "소각", "전정", "저항성", "윤작", "재배관리",
        "발생 후 조치", "대책",
    ),
    "differential_diagnosis": (
        "진단", "구별", "감별", "유사", "비슷", "혼동", "특징",
        "판별", "다른 병",
    ),
}

ENGLISH_CATEGORY_TERMS = {
    "pathogen": (
        "pathogen", "caused by", "causal agent", "fungus", "bacterium",
        "virus", "oomycete", "etiology",
    ),
    "symptoms": (
        "symptom", "lesion", "spot", "rot", "blight", "mosaic",
        "yellow", "brown", "black", "necrotic", "wilt", "curl", "scab",
    ),
    "affected_parts": (
        "leaf", "leaves", "fruit", "stem", "branch", "root", "flower",
        "bark", "tuber", "seed", "pod",
    ),
    "favorable_conditions": (
        "temperature", "humidity", "rain", "moisture", "wetness",
        "weather", "favorable condition",
    ),
    "transmission": (
        "spread", "transmission", "spore", "wind", "rain splash",
        "vector", "seedborne", "soilborne", "overwinter",
    ),
    "management": (
        "management", "control", "prevention", "remove", "prune",
        "sanitation", "resistant", "fungicide", "rotation", "treatment",
    ),
    "differential_diagnosis": (
        "diagnosis", "distinguish", "differentiate", "similar to",
        "confused with", "characteristic",
    ),
}

LOW_VALUE_FIELD_NAMES = {
    "resultcode", "resultmsg", "code", "value", "key", "pageindex",
    "pagesize", "pageno", "numofrows", "totalcount",
}

HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
SENTENCE_RE = re.compile(r"(?<=[.!?。！？다요임함됨])\s+|\n+")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="농사로 API 자료를 기존 evidence-gated RAG에 병합합니다."
    )
    p.add_argument(
        "--nongsaro-root",
        type=Path,
        default=Path(r".\data\rag_nongsaro_api_v2"),
    )
    p.add_argument(
        "--classes-json",
        type=Path,
        default=Path(
            r".\runs\lesion_classifier_convnext_tiny_v1\best\classes.json"
        ),
    )
    p.add_argument(
        "--base-work-dir",
        type=Path,
        default=Path(r".\runs\bulk_rag_factory"),
    )
    p.add_argument(
        "--output-work-dir",
        type=Path,
        default=Path(r".\runs\bulk_rag_factory_nongsaro"),
    )
    p.add_argument(
        "--factory-script",
        type=Path,
        default=Path(r".\84_evidence_gated_diagnostic_rag_factory.py"),
    )
    p.add_argument(
        "--rag-root",
        type=Path,
        default=Path(r".\data\rag_plant_diseases"),
    )
    p.add_argument(
        "--embedding-model",
        default=r"E:\EyeGuideRAG\models\embeddings\multilingual-e5-base",
    )
    p.add_argument("--embedding-device", default="cuda")
    p.add_argument("--embedding-batch-size", type=int, default=32)
    p.add_argument("--min-record-chars", type=int, default=100)
    p.add_argument("--chunk-target-chars", type=int, default=850)
    p.add_argument("--chunk-max-chars", type=int, default=1500)
    p.add_argument(
        "--match-threshold",
        type=float,
        default=0.62,
        help="한국어 레코드와 영문 질병 클래스 간 코사인 유사도 최소값",
    )
    p.add_argument(
        "--match-margin",
        type=float,
        default=0.035,
        help="1위와 2위 질병 유사도 차이 최소값",
    )
    p.add_argument(
        "--max-diseases-per-record",
        type=int,
        default=1,
    )
    p.add_argument(
        "--skip-embed",
        action="store_true",
        help="병합 청크만 만들고 임베딩은 실행하지 않음",
    )
    return p.parse_args()


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\\r", " ").replace("\\n", " ")
    return SPACE_RE.sub(" ", text).strip()


def load_classes(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        classes = data
    elif isinstance(data, dict):
        for key in ("classes", "class_names", "labels", "id2label"):
            if key in data:
                value = data[key]
                if isinstance(value, dict):
                    classes = [
                        value[key]
                        for key in sorted(
                            value,
                            key=lambda item: int(item)
                            if str(item).isdigit()
                            else str(item),
                        )
                    ]
                else:
                    classes = value
                break
        else:
            classes = list(data)
    else:
        raise ValueError(f"지원하지 않는 classes.json 구조: {type(data)}")

    result = []
    for item in classes:
        label = str(item).strip()
        if label and label not in result:
            result.append(label)
    if not result:
        raise RuntimeError("질병 클래스가 비어 있습니다.")
    return result


def humanize_class(label: str) -> str:
    return SPACE_RE.sub(
        " ",
        label.replace("___", " ").replace("__", " ").replace("_", " "),
    ).strip()


def load_records(root: Path) -> list[dict]:
    files = sorted((root / "services").glob("*/records.jsonl"))
    if not files:
        raise FileNotFoundError(
            f"농사로 records.jsonl을 찾지 못했습니다: {root}"
        )

    records = []
    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_records_file"] = str(path.resolve())
                records.append(row)
    return records


def record_text(row: dict) -> str:
    fields = row.get("fields") or {}
    useful = []
    if isinstance(fields, dict):
        for key, value in fields.items():
            key_clean = clean_text(key)
            value_clean = clean_text(value)
            if not value_clean:
                continue
            if key_clean.lower() in LOW_VALUE_FIELD_NAMES:
                continue
            if re.fullmatch(r"[\d,./:_-]+", value_clean):
                continue
            useful.append(f"{key_clean}: {value_clean}")

    explicit = clean_text(row.get("text"))
    if explicit and explicit not in useful:
        useful.append(explicit)

    service_name = clean_text(row.get("service_name"))
    if service_name:
        useful.insert(0, f"농사로 서비스: {service_name}")

    return "\n".join(dict.fromkeys(useful))


def categories(text: str) -> list[str]:
    low = text.lower()
    found = []
    for category in KOREAN_CATEGORY_TERMS:
        terms = (
            KOREAN_CATEGORY_TERMS[category]
            + ENGLISH_CATEGORY_TERMS[category]
        )
        if any(term.lower() in low for term in terms):
            found.append(category)
    return found


def split_units(text: str) -> list[str]:
    units = []
    for part in SENTENCE_RE.split(text):
        value = clean_text(part)
        if len(value) >= 20:
            units.append(value)
    return units


def make_chunks(text: str, target: int, maximum: int) -> list[str]:
    units = split_units(text)
    if not units and len(text) >= 20:
        units = [clean_text(text)]

    chunks = []
    current = []
    current_chars = 0
    for unit in units:
        if len(unit) > maximum:
            pieces = [
                unit[start : start + maximum]
                for start in range(0, len(unit), maximum)
            ]
        else:
            pieces = [unit]

        for piece in pieces:
            projected = current_chars + len(piece) + (1 if current else 0)
            if current and projected > maximum:
                chunks.append(" ".join(current))
                current = []
                current_chars = 0
            current.append(piece)
            current_chars += len(piece) + (1 if len(current) > 1 else 0)
            if current_chars >= target:
                chunks.append(" ".join(current))
                current = []
                current_chars = 0

    if current:
        chunks.append(" ".join(current))
    return [chunk for chunk in chunks if len(chunk) >= 60]


def load_embedding_model(model_path: str, device: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        model_path,
        device=device,
        local_files_only=True,
    )


def encode(model, texts: list[str], batch_size: int) -> np.ndarray:
    return np.asarray(
        model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ),
        dtype=np.float32,
    )


def build_class_prompts(classes: list[str]) -> list[str]:
    prompts = []
    for label in classes:
        human = humanize_class(label)
        prompts.append(
            "passage: plant crop disease diagnosis. "
            f"class id {label}. host and disease name: {human}. "
            f"symptoms pathogen favorable conditions prevention management of {human}"
        )
    return prompts


def source_url(row: dict) -> str:
    fields = row.get("fields") or {}
    for key, value in fields.items():
        key_low = str(key).lower()
        cleaned = clean_text(value)
        if (
            cleaned.startswith(("http://", "https://"))
            and any(token in key_low for token in ("url", "link", "uri"))
        ):
            return cleaned
    return "https://www.nongsaro.go.kr/"


def publisher(row: dict) -> str:
    return clean_text(row.get("publisher")) or "농촌진흥청 농사로"


def prepare_candidates(
    records: list[dict],
    minimum_chars: int,
) -> tuple[list[dict], Counter]:
    result = []
    reasons = Counter()
    seen = set()

    for row in records:
        text = record_text(row)
        if len(text) < minimum_chars:
            reasons["TOO_SHORT"] += 1
            continue

        cats = categories(text)
        if not cats:
            reasons["NO_DIAGNOSTIC_CATEGORY"] += 1
            continue

        digest = hashlib.sha256(
            SPACE_RE.sub(" ", text.lower()).encode("utf-8")
        ).hexdigest()
        if digest in seen:
            reasons["DUPLICATE_RECORD"] += 1
            continue
        seen.add(digest)

        result.append(
            {
                "row": row,
                "text": text,
                "categories": cats,
                "content_sha256": digest,
            }
        )

    return result, reasons


def load_existing_chunks(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"기존 RAG 청크가 없습니다: {path}")
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    args.nongsaro_root = args.nongsaro_root.resolve()
    args.classes_json = args.classes_json.resolve()
    args.base_work_dir = args.base_work_dir.resolve()
    args.output_work_dir = args.output_work_dir.resolve()
    args.factory_script = args.factory_script.resolve()
    args.rag_root = args.rag_root.resolve()

    args.output_work_dir.mkdir(parents=True, exist_ok=True)

    classes = load_classes(args.classes_json)
    records = load_records(args.nongsaro_root)
    candidates, rejection_counts = prepare_candidates(
        records,
        args.min_record_chars,
    )

    print(f"classes={len(classes)}")
    print(f"nongsaro_records={len(records)}")
    print(f"diagnostic_candidates={len(candidates)}")
    print(f"prefilter_rejections={dict(rejection_counts)}")

    if not candidates:
        raise RuntimeError(
            "진단용으로 사용할 수 있는 농사로 레코드가 없습니다. "
            "현재 다운로드가 코드 목록 중심인지 확인하세요."
        )

    model = load_embedding_model(
        args.embedding_model,
        args.embedding_device,
    )
    class_vectors = encode(
        model,
        build_class_prompts(classes),
        args.embedding_batch_size,
    )
    record_vectors = encode(
        model,
        [
            "query: Korean agricultural disease evidence. "
            + candidate["text"]
            for candidate in candidates
        ],
        args.embedding_batch_size,
    )

    scores = record_vectors @ class_vectors.T
    accepted_chunks = []
    mapping_rows = []
    matching_rejections = Counter()
    seen_chunk_hashes = set()

    for index, candidate in enumerate(candidates):
        order = np.argsort(-scores[index])
        best_idx = int(order[0])
        second_idx = int(order[1]) if len(order) > 1 else best_idx
        best_score = float(scores[index, best_idx])
        second_score = float(scores[index, second_idx])
        margin = best_score - second_score
        row = candidate["row"]

        mapping = {
            "record_id": row.get("record_id", ""),
            "service_name": row.get("service_name", ""),
            "endpoint": row.get("endpoint", ""),
            "matched_disease_id": classes[best_idx],
            "best_score": best_score,
            "second_disease_id": classes[second_idx],
            "second_score": second_score,
            "margin": margin,
            "categories": "|".join(candidate["categories"]),
            "text_preview": candidate["text"][:350],
            "status": "",
        }

        if best_score < args.match_threshold:
            mapping["status"] = "REJECT_LOW_SIMILARITY"
            matching_rejections["LOW_SIMILARITY"] += 1
            mapping_rows.append(mapping)
            continue

        if margin < args.match_margin:
            mapping["status"] = "REJECT_AMBIGUOUS"
            matching_rejections["AMBIGUOUS"] += 1
            mapping_rows.append(mapping)
            continue

        disease_id = classes[best_idx]
        chunks = make_chunks(
            candidate["text"],
            args.chunk_target_chars,
            args.chunk_max_chars,
        )
        if not chunks:
            mapping["status"] = "REJECT_NO_CHUNK"
            matching_rejections["NO_CHUNK"] += 1
            mapping_rows.append(mapping)
            continue

        kept = 0
        for chunk_index, chunk in enumerate(chunks, 1):
            chunk_categories = categories(chunk)
            if not chunk_categories:
                continue
            digest = hashlib.sha256(
                SPACE_RE.sub(" ", chunk.lower()).encode("utf-8")
            ).hexdigest()
            if digest in seen_chunk_hashes:
                continue
            seen_chunk_hashes.add(digest)
            kept += 1

            source_id = (
                "nongsaro_"
                + hashlib.sha1(
                    (
                        str(row.get("service_slug", ""))
                        + str(row.get("endpoint", ""))
                        + str(row.get("record_id", ""))
                    ).encode("utf-8")
                ).hexdigest()[:16]
            )
            accepted_chunks.append(
                {
                    "chunk_id": (
                        f"{disease_id}__{source_id}__{chunk_index:04d}"
                    ),
                    "disease_id": disease_id,
                    "host": humanize_class(disease_id).split(" ", 1)[0],
                    "source_id": source_id,
                    "source_title": (
                        f"농사로 {row.get('service_name', '')} "
                        f"{row.get('endpoint', '')}"
                    ).strip(),
                    "publisher": publisher(row),
                    "url": source_url(row),
                    "doi": "",
                    "record_id": row.get("record_id", ""),
                    "peer_reviewed": False,
                    "local_file": row.get("_records_file", ""),
                    "text_path": row.get("_records_file", ""),
                    "categories": chunk_categories,
                    "char_count": len(chunk),
                    "content_sha256": digest,
                    "strict_diagnostic": True,
                    "paragraph_grounded": True,
                    "sentence_grounded": True,
                    "evidence_gated": True,
                    "language": "ko",
                    "source_type": "nongsaro_openapi",
                    "service_slug": row.get("service_slug", ""),
                    "service_name": row.get("service_name", ""),
                    "endpoint": row.get("endpoint", ""),
                    "class_match_score": best_score,
                    "class_match_margin": margin,
                    "text": chunk,
                }
            )

        if kept:
            mapping["status"] = f"ACCEPTED_{kept}_CHUNKS"
        else:
            mapping["status"] = "REJECT_NO_DIAGNOSTIC_CHUNK"
            matching_rejections["NO_DIAGNOSTIC_CHUNK"] += 1
        mapping_rows.append(mapping)

    print(f"accepted_nongsaro_chunks={len(accepted_chunks)}")
    print(f"matching_rejections={dict(matching_rejections)}")

    mapping_csv = args.output_work_dir / "nongsaro_class_mapping.csv"
    write_csv(
        mapping_csv,
        mapping_rows,
        [
            "record_id",
            "service_name",
            "endpoint",
            "matched_disease_id",
            "best_score",
            "second_disease_id",
            "second_score",
            "margin",
            "categories",
            "status",
            "text_preview",
        ],
    )

    nongsaro_jsonl = args.output_work_dir / "nongsaro_chunks.jsonl"
    with nongsaro_jsonl.open("w", encoding="utf-8") as fh:
        for chunk in accepted_chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    existing_path = args.base_work_dir / "rag_chunks.jsonl"
    existing_chunks = load_existing_chunks(existing_path)

    combined = []
    combined_hashes = set()
    duplicate_existing = 0
    duplicate_nongsaro = 0

    for source_name, rows in (
        ("existing", existing_chunks),
        ("nongsaro", accepted_chunks),
    ):
        for row in rows:
            digest = row.get("content_sha256") or hashlib.sha256(
                SPACE_RE.sub(
                    " ",
                    str(row.get("text", "")).lower(),
                ).encode("utf-8")
            ).hexdigest()
            key = (row.get("disease_id", ""), digest)
            if key in combined_hashes:
                if source_name == "existing":
                    duplicate_existing += 1
                else:
                    duplicate_nongsaro += 1
                continue
            combined_hashes.add(key)
            combined.append(row)

    combined_path = args.output_work_dir / "rag_chunks.jsonl"
    with combined_path.open("w", encoding="utf-8") as fh:
        for row in combined:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    disease_counts = Counter(
        row.get("disease_id", "")
        for row in accepted_chunks
    )
    service_counts = Counter(
        row.get("service_name", "")
        for row in accepted_chunks
    )
    category_counts = Counter(
        category
        for row in accepted_chunks
        for category in row.get("categories", [])
    )

    manifest = {
        "base_chunks": len(existing_chunks),
        "nongsaro_input_records": len(records),
        "nongsaro_diagnostic_candidates": len(candidates),
        "nongsaro_accepted_chunks": len(accepted_chunks),
        "combined_chunks": len(combined),
        "duplicate_existing": duplicate_existing,
        "duplicate_nongsaro": duplicate_nongsaro,
        "prefilter_rejections": dict(rejection_counts),
        "matching_rejections": dict(matching_rejections),
        "disease_counts": dict(disease_counts.most_common()),
        "service_counts": dict(service_counts.most_common()),
        "category_counts": dict(category_counts.most_common()),
        "match_threshold": args.match_threshold,
        "match_margin": args.match_margin,
        "base_chunks_path": str(existing_path),
        "combined_chunks_path": str(combined_path),
        "nongsaro_chunks_path": str(nongsaro_jsonl),
        "mapping_csv": str(mapping_csv),
    }
    (args.output_work_dir / "nongsaro_merge_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if args.skip_embed:
        print("embed_skipped=True")
        return

    command = [
        sys.executable,
        str(args.factory_script),
        "embed",
        "--rag-root",
        str(args.rag_root),
        "--work-dir",
        str(args.output_work_dir),
        "--embedding-model",
        str(args.embedding_model),
        "--embedding-device",
        args.embedding_device,
        "--embedding-batch-size",
        str(args.embedding_batch_size),
        "--embedding-local-files-only",
    ]
    print("running_embed=", subprocess.list2cmdline(command))
    subprocess.run(command, check=True)

    print("RAG_BUILD_COMPLETE")
    print(
        "new_index=",
        args.output_work_dir / "rag_embedding_index",
    )


if __name__ == "__main__":
    main()
