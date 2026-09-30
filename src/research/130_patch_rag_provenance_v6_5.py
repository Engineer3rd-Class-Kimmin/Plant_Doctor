#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SERVICE_RULES: dict[str, dict[str, Any]] = {
    "month": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_month_farm_tech_output"],
    },
    "monthFarmTech": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_complete_repaired"],
    },
    "pest": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_pest_occurrence_output"],
    },
    "organic": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_organic_farming_output"],
    },
    "disaster": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_disaster_prevention_output"],
    },
    "farm": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_farmWorkingPlan_output"],
    },
    "crop_ebook": {
        "source": "농촌진흥청 농사로",
        "source_database": "농사로 작목기술정보",
        "source_type": "official_public_data",
        "source_url": "https://www.nongsaro.go.kr/portal/",
        "collection_dirs": ["nongsaro_cropEbook_output"],
    },
    "ncpms_manual": {
        "source": "농촌진흥청 국가농작물병해충관리시스템",
        "source_database": "NCPMS",
        "source_type": "official_public_data",
        "source_url": "https://ncpms.rda.go.kr/npms/Main.np",
        "collection_dirs": [],
    },
}

ADP_SERVICES = {
    "adp_pesticide_registration",
    "adp_pest_monitoring",
    "adp_fertilizer_standard",
    "adp_weekly_farming",
}

ADP_PLATFORM_URL = "https://adp.rda.go.kr/portal/"


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalized_body(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"JSONL 파싱 실패: {path}:{line_no}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise RuntimeError(
                    f"JSON 객체가 아닙니다: {path}:{line_no}"
                )
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return

    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON 객체가 아닙니다: {path}")
    return value


def metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return dict(value) if isinstance(value, dict) else {}


def pick(row: dict[str, Any], *keys: str) -> str:
    meta = metadata(row)
    for key in keys:
        value = norm(row.get(key))
        if value:
            return value
    for key in keys:
        value = norm(meta.get(key))
        if value:
            return value
    return ""


def chunk_id(row: dict[str, Any]) -> str:
    return pick(row, "chunk_id", "id")


def chunk_text(row: dict[str, Any]) -> str:
    return str(row.get("text") or row.get("content") or "").strip()


def content_hash(row: dict[str, Any]) -> str:
    existing = pick(row, "content_sha256")
    if existing:
        return existing
    text = chunk_text(row)
    return sha256_text(text) if text else ""


def set_both(
    row: dict[str, Any],
    key: str,
    value: Any,
    *,
    overwrite: bool = False,
) -> None:
    meta = row.setdefault("metadata", {})
    if not isinstance(meta, dict):
        meta = {}
        row["metadata"] = meta

    if overwrite or not norm(row.get(key)):
        row[key] = value
    if overwrite or not norm(meta.get(key)):
        meta[key] = value


def sentence_fingerprints(text: str) -> list[str]:
    normalized = normalized_body(text)
    if not normalized:
        return []

    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)
    results: list[str] = []
    for part in parts:
        piece = norm(part)
        if len(piece) < 40:
            continue
        results.append(sha256_text(piece[:120]))
        if len(results) >= 8:
            break

    if not results and len(normalized) >= 40:
        results.append(sha256_text(normalized[:120]))

    return results


def read_text_best_effort(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def build_source_index(
    collector_root: Path,
) -> tuple[
    dict[str, dict[str, list[str]]],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    """
    서비스별로 다음 인덱스를 만듭니다.
    - 전체 본문 SHA-256 -> 파일
    - 문장 fingerprint -> 파일
    - 실제 존재하는 수집 폴더 목록
    """
    exact_indexes: dict[str, dict[str, list[str]]] = {}
    sentence_indexes: dict[str, dict[str, list[str]]] = {}
    collection_roots: dict[str, list[str]] = {}

    for service, rule in SERVICE_RULES.items():
        exact: dict[str, list[str]] = defaultdict(list)
        sentences: dict[str, list[str]] = defaultdict(list)
        roots: list[str] = []

        for dirname in rule["collection_dirs"]:
            root = collector_root / dirname
            if not root.exists():
                continue
            roots.append(str(root))

            for path in root.rglob("*.txt"):
                text = read_text_best_effort(path)
                if not text.strip():
                    continue

                normalized = normalized_body(text)
                exact[sha256_text(normalized)].append(str(path))

                for fingerprint in sentence_fingerprints(text):
                    if len(sentences[fingerprint]) < 10:
                        sentences[fingerprint].append(str(path))

        exact_indexes[service] = dict(exact)
        sentence_indexes[service] = dict(sentences)
        collection_roots[service] = roots

    return exact_indexes, sentence_indexes, collection_roots


def resolve_exact_source_file(
    row: dict[str, Any],
    service: str,
    exact_indexes: dict[str, dict[str, list[str]]],
    sentence_indexes: dict[str, dict[str, list[str]]],
) -> tuple[str, str]:
    text = chunk_text(row)
    if not text:
        return "", "no_text"

    normalized = normalized_body(text)
    exact_hits = exact_indexes.get(service, {}).get(
        sha256_text(normalized),
        [],
    )
    if len(exact_hits) == 1:
        return exact_hits[0], "exact_normalized_text"
    if len(exact_hits) > 1:
        return exact_hits[0], "exact_text_multiple_first"

    candidate_counts: Counter[str] = Counter()
    for fingerprint in sentence_fingerprints(text):
        for path in sentence_indexes.get(service, {}).get(
            fingerprint,
            [],
        ):
            candidate_counts[path] += 1

    if candidate_counts:
        best_path, score = candidate_counts.most_common(1)[0]
        if score >= 1:
            return best_path, f"sentence_fingerprint_{score}"

    return "", "not_matched"


def infer_legacy_disease(row: dict[str, Any]) -> str:
    existing = pick(row, "disease", "disease_name")
    if existing:
        return existing

    cid = chunk_id(row)
    if "__" in cid:
        prefix = cid.split("__", 1)[0]
        return prefix.replace("_", " ").strip()

    return ""


def patch_row(
    row: dict[str, Any],
    line_no: int,
    base_rag_path: Path,
    collector_root: Path,
    exact_indexes: dict[str, dict[str, list[str]]],
    sentence_indexes: dict[str, dict[str, list[str]]],
    collection_roots: dict[str, list[str]],
    counters: Counter,
    unresolved_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    patched = json.loads(json.dumps(row, ensure_ascii=False))
    meta = patched.setdefault("metadata", {})
    if not isinstance(meta, dict):
        meta = {}
        patched["metadata"] = meta

    cid = chunk_id(patched)
    service = pick(
        patched,
        "source_service",
        "service_slug",
    )
    source = pick(patched, "source", "source_database")
    source_file = pick(patched, "source_file")
    source_url = pick(patched, "source_url")

    # 기존 정상 메타데이터는 유지하고 공통 추적 필드만 보강합니다.
    set_both(patched, "provenance_patch_version", "v6_5")
    set_both(patched, "provenance_audited", True)

    if service in SERVICE_RULES:
        rule = SERVICE_RULES[service]

        if not source:
            set_both(patched, "source", rule["source"])
            set_both(
                patched,
                "source_database",
                rule["source_database"],
            )
            counters["restored_source_by_service"] += 1

        if not pick(patched, "source_type"):
            set_both(
                patched,
                "source_type",
                rule["source_type"],
            )

        if not source_url:
            set_both(
                patched,
                "source_url",
                rule["source_url"],
            )
            set_both(
                patched,
                "source_url_granularity",
                "official_service_homepage",
            )
            counters["restored_service_url"] += 1

        if not source_file:
            resolved, method = resolve_exact_source_file(
                patched,
                service,
                exact_indexes,
                sentence_indexes,
            )

            if resolved:
                set_both(patched, "source_file", resolved)
                set_both(
                    patched,
                    "source_file_resolution",
                    method,
                )
                set_both(
                    patched,
                    "provenance_granularity",
                    "exact_or_best_effort_file",
                )
                set_both(
                    patched,
                    "provenance_status",
                    "resolved",
                )
                counters["resolved_exact_or_best_effort_file"] += 1
            else:
                roots = collection_roots.get(service, [])
                if roots:
                    fallback = " | ".join(roots)
                elif service == "ncpms_manual":
                    fallback = (
                        "collection://NCPMS/manual_import/"
                        f"{base_rag_path.name}#line={line_no}"
                    )
                else:
                    fallback = (
                        "collection://legacy_service/"
                        f"{service}/{base_rag_path.name}#line={line_no}"
                    )

                set_both(patched, "source_file", fallback)
                set_both(
                    patched,
                    "source_file_resolution",
                    "collection_root_fallback",
                )
                set_both(
                    patched,
                    "provenance_granularity",
                    "collection_folder",
                )
                set_both(
                    patched,
                    "provenance_status",
                    "partially_resolved",
                )
                counters["collection_root_fallback"] += 1

    elif service in ADP_SERVICES:
        # V6.4 ADP 데이터는 기관 및 원본 파일이 이미 존재합니다.
        if not source_url:
            set_both(patched, "source_url", ADP_PLATFORM_URL)
            set_both(
                patched,
                "source_url_granularity",
                "official_platform_homepage",
            )
            counters["restored_adp_platform_url"] += 1

        set_both(
            patched,
            "provenance_status",
            "resolved_official_download",
        )
        set_both(
            patched,
            "provenance_granularity",
            "download_file",
        )

    elif service == "korean_plant_disease_catalog":
        set_both(
            patched,
            "provenance_status",
            "resolved_official_catalog",
        )
        set_both(
            patched,
            "provenance_granularity",
            "record_file_and_url",
        )

    elif not service:
        # 원 출처를 추측하지 않습니다. 현재까지 확인 가능한 계보만 기록합니다.
        legacy_service = "legacy_literature_evidence"
        legacy_source = "Plant Doctor 초기 문헌 근거 코퍼스"

        set_both(
            patched,
            "source_service",
            legacy_service,
        )
        if not norm(patched.get("service_slug")):
            patched["service_slug"] = legacy_service

        set_both(patched, "source", legacy_source)
        set_both(
            patched,
            "source_database",
            "legacy_bootstrap_corpus",
        )
        set_both(
            patched,
            "source_type",
            "legacy_literature_import",
        )
        set_both(
            patched,
            "source_file",
            f"{base_rag_path}#line={line_no}",
        )
        set_both(
            patched,
            "source_file_resolution",
            "current_rag_lineage_only",
        )
        set_both(
            patched,
            "provenance_status",
            "original_source_unresolved",
        )
        set_both(
            patched,
            "provenance_granularity",
            "legacy_rag_line",
        )
        set_both(
            patched,
            "requires_manual_source_resolution",
            True,
        )

        disease = infer_legacy_disease(patched)
        if disease:
            set_both(patched, "disease", disease)
            set_both(patched, "disease_name", disease)

        unresolved_rows.append({
            "line_no": line_no,
            "chunk_id": cid,
            "inferred_disease": disease,
            "text_preview": norm(chunk_text(patched))[:300],
            "current_lineage": (
                f"{base_rag_path}#line={line_no}"
            ),
            "resolution_status": "original_source_unresolved",
        })
        counters["legacy_original_source_unresolved"] += 1

    else:
        # 알려지지 않은 서비스도 현재 계보를 잃지 않도록 기록합니다.
        if not source:
            set_both(
                patched,
                "source",
                f"기존 RAG 서비스: {service}",
            )
        if not source_file:
            set_both(
                patched,
                "source_file",
                f"{base_rag_path}#line={line_no}",
            )
        set_both(
            patched,
            "provenance_status",
            "service_known_original_file_unresolved",
        )
        set_both(
            patched,
            "provenance_granularity",
            "legacy_rag_line",
        )
        counters["unknown_service_lineage_fallback"] += 1

    # 모든 청크에 공통 계보와 해시를 보장합니다.
    set_both(
        patched,
        "lineage_parent_rag",
        str(base_rag_path),
    )
    set_both(
        patched,
        "lineage_parent_line",
        line_no,
    )

    digest = content_hash(patched)
    if digest:
        set_both(patched, "content_sha256", digest)

    return patched


def validate(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(before) != len(after):
        raise RuntimeError(
            f"청크 수 변경 감지: before={len(before)}, after={len(after)}"
        )

    changed_text = 0
    changed_ids = 0
    missing_trace = 0
    missing_service = 0
    duplicate_ids: Counter[str] = Counter()

    for old, new in zip(before, after):
        old_id = chunk_id(old)
        new_id = chunk_id(new)
        if old_id != new_id:
            changed_ids += 1

        if chunk_text(old) != chunk_text(new):
            changed_text += 1

        source = pick(new, "source", "source_database")
        source_file = pick(new, "source_file")
        source_url = pick(new, "source_url")
        service = pick(new, "source_service", "service_slug")

        if not source and not source_file and not source_url:
            missing_trace += 1
        if not service:
            missing_service += 1

        if new_id:
            duplicate_ids[new_id] += 1

    duplicate_count = sum(
        1 for count in duplicate_ids.values() if count > 1
    )

    result = {
        "chunk_count_before": len(before),
        "chunk_count_after": len(after),
        "changed_chunk_ids": changed_ids,
        "changed_texts": changed_text,
        "missing_all_trace_after": missing_trace,
        "missing_source_service_after": missing_service,
        "duplicate_chunk_ids_after": duplicate_count,
    }

    if changed_ids:
        raise RuntimeError(
            f"chunk_id가 {changed_ids}개 변경됐습니다."
        )
    if changed_text:
        raise RuntimeError(
            f"본문이 {changed_text}개 변경됐습니다."
        )
    if missing_trace:
        raise RuntimeError(
            f"출처 추적정보 전체 누락이 {missing_trace}개 남았습니다."
        )
    if missing_service:
        raise RuntimeError(
            f"source_service 누락이 {missing_service}개 남았습니다."
        )
    if duplicate_count:
        raise RuntimeError(
            f"중복 chunk_id가 {duplicate_count}개 생겼습니다."
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "V6.4 RAG의 기존 7,190개 출처 메타데이터를 "
            "정직한 계보 방식으로 보강하고 V6.5를 생성합니다."
        )
    )
    parser.add_argument(
        "--base-work-dir",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_4_adp_merged"
        ),
    )
    parser.add_argument(
        "--output-work-dir",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_5_provenance_patched"
        ),
    )
    parser.add_argument(
        "--collector-root",
        type=Path,
        default=Path(r".\nongsaro_24crop_collector"),
    )
    parser.add_argument(
        "--embed-script",
        type=Path,
        default=Path(r".\84_evidence_gated_diagnostic_rag_factory.py"),
    )
    parser.add_argument(
        "--audit-script",
        type=Path,
        default=Path(r".\129_audit_rag_source_traceability.py"),
    )
    parser.add_argument(
        "--rag-root",
        type=Path,
        default=Path(r".\data\rag_plant_diseases"),
    )
    parser.add_argument("--embedding-device", default="cuda")
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    base_dir = (root / args.base_work_dir).resolve()
    output_dir = (root / args.output_work_dir).resolve()
    collector_root = (root / args.collector_root).resolve()
    embed_script = (root / args.embed_script).resolve()
    audit_script = (root / args.audit_script).resolve()
    rag_root = (root / args.rag_root).resolve()

    base_rag_path = base_dir / "rag_chunks.jsonl"
    base_index_manifest_path = (
        base_dir / "rag_embedding_index" / "index_manifest.json"
    )

    required = [
        base_rag_path,
        base_index_manifest_path,
        collector_root,
        embed_script,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "필수 경로가 없습니다:\n" + "\n".join(missing)
        )

    base_rows = read_jsonl(base_rag_path)
    base_manifest = read_manifest(base_index_manifest_path)

    base_vector_count = int(base_manifest.get("vector_count") or 0)
    embedding_model = norm(base_manifest.get("embedding_model"))
    embedding_dimension = int(base_manifest.get("dimension") or 0)

    if len(base_rows) != base_vector_count:
        raise RuntimeError(
            "기존 청크와 벡터 수가 다릅니다: "
            f"chunks={len(base_rows)}, vectors={base_vector_count}"
        )
    if not embedding_model or not embedding_dimension:
        raise RuntimeError(
            "기존 임베딩 모델 또는 차원을 확인할 수 없습니다."
        )

    print("원본 파일 인덱스 생성 중...")
    (
        exact_indexes,
        sentence_indexes,
        collection_roots,
    ) = build_source_index(collector_root)

    counters = Counter()
    unresolved_rows: list[dict[str, Any]] = []
    patched_rows: list[dict[str, Any]] = []

    for line_no, row in enumerate(base_rows, 1):
        patched_rows.append(
            patch_row(
                row=row,
                line_no=line_no,
                base_rag_path=base_rag_path,
                collector_root=collector_root,
                exact_indexes=exact_indexes,
                sentence_indexes=sentence_indexes,
                collection_roots=collection_roots,
                counters=counters,
                unresolved_rows=unresolved_rows,
            )
        )

    validation = validate(base_rows, patched_rows)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    patched_rag_path = output_dir / "rag_chunks.jsonl"
    patch_only_path = output_dir / "v6_5_provenance_patch_records.jsonl"
    unresolved_path = output_dir / "v6_5_unresolved_legacy_sources.csv"
    manifest_path = output_dir / "v6_5_provenance_patch_manifest.json"

    write_jsonl(patched_rag_path, patched_rows)

    changed_rows: list[dict[str, Any]] = []
    for before, after in zip(base_rows, patched_rows):
        if before != after:
            changed_rows.append(after)
    write_jsonl(patch_only_path, changed_rows)
    write_csv(unresolved_path, unresolved_rows)

    manifest = {
        "update_version": "v6_5_provenance_patched",
        "implementation": "independent_metadata_patch_preserve_text_and_ids",
        "compatibility_base": str(base_dir),
        "base_chunks": len(base_rows),
        "base_vector_count": base_vector_count,
        "patched_chunks": len(changed_rows),
        "final_chunks": len(patched_rows),
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "embedding_device": args.embedding_device,
        "embedding_batch_size": args.embedding_batch_size,
        "collector_root": str(collector_root),
        "output_work_dir": str(output_dir),
        "existing_base_overwritten": False,
        "validation": validation,
        "counts": dict(sorted(counters.items())),
        "unresolved_legacy_original_sources": len(unresolved_rows),
        "unresolved_report": str(unresolved_path),
        "provenance_policy": {
            "no_original_source_fabrication": True,
            "exact_file_match_when_available": True,
            "collection_folder_fallback_is_labeled": True,
            "legacy_literature_unresolved_is_labeled": True,
            "text_unchanged": True,
            "chunk_ids_unchanged": True,
        },
    }
    write_json(manifest_path, manifest)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if args.skip_embed:
        print("RAG_PROVENANCE_V6_5_CHUNKS_READY")
        return

    embed_command = [
        sys.executable,
        str(embed_script),
        "embed",
        "--rag-root",
        str(rag_root),
        "--work-dir",
        str(output_dir),
        "--embedding-model",
        embedding_model,
        "--embedding-device",
        args.embedding_device,
        "--embedding-batch-size",
        str(args.embedding_batch_size),
        "--embedding-local-files-only",
    ]
    print("running_embed=", " ".join(embed_command))
    subprocess.run(embed_command, check=True)

    new_index_manifest_path = (
        output_dir / "rag_embedding_index" / "index_manifest.json"
    )
    if not new_index_manifest_path.exists():
        raise RuntimeError(
            "임베딩 후 index_manifest.json이 생성되지 않았습니다."
        )

    new_manifest = read_manifest(new_index_manifest_path)
    new_vector_count = int(new_manifest.get("vector_count") or 0)
    new_dimension = int(new_manifest.get("dimension") or 0)
    new_model = norm(new_manifest.get("embedding_model"))

    if new_vector_count != len(patched_rows):
        raise RuntimeError(
            "최종 벡터 수 불일치: "
            f"vectors={new_vector_count}, chunks={len(patched_rows)}"
        )
    if new_dimension != embedding_dimension:
        raise RuntimeError(
            "임베딩 차원 불일치: "
            f"base={embedding_dimension}, new={new_dimension}"
        )
    if new_model != embedding_model:
        raise RuntimeError(
            "임베딩 모델 불일치: "
            f"base={embedding_model}, new={new_model}"
        )

    if not args.skip_audit:
        if not audit_script.exists():
            raise FileNotFoundError(
                f"감사 스크립트가 없습니다: {audit_script}"
            )

        audit_output = output_dir / "source_audit"
        audit_command = [
            sys.executable,
            str(audit_script),
            "--rag",
            str(patched_rag_path),
            "--index-manifest",
            str(new_index_manifest_path),
            "--output",
            str(audit_output),
            "--strict",
        ]
        print("running_audit=", " ".join(audit_command))
        subprocess.run(audit_command, check=True)

    print("RAG_PROVENANCE_V6_5_BUILD_COMPLETE")
    print("final_chunks=", len(patched_rows))
    print("final_vectors=", new_vector_count)
    print("legacy_original_sources_unresolved=", len(unresolved_rows))
    print("new_work_dir=", output_dir)
    print("existing_base_preserved=", base_dir)


if __name__ == "__main__":
    main()
