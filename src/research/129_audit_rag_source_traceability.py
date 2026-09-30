#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []

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

            rows.append((line_no, value))

    return rows


def nested_metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def pick(row: dict[str, Any], *keys: str) -> str:
    metadata = nested_metadata(row)

    for key in keys:
        value = norm(row.get(key))
        if value:
            return value

    for key in keys:
        value = norm(metadata.get(key))
        if value:
            return value

    return ""


def chunk_id(row: dict[str, Any]) -> str:
    return pick(row, "chunk_id", "id")


def chunk_text(row: dict[str, Any]) -> str:
    return norm(row.get("text") or row.get("content"))


def content_hash(row: dict[str, Any]) -> str:
    existing = pick(row, "content_sha256")
    if existing:
        return existing

    text = chunk_text(row)
    if not text:
        return ""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAG 전체 출처·추적성·중복 감사"
    )
    parser.add_argument(
        "--rag",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_4_adp_merged"
            r"\rag_chunks.jsonl"
        ),
    )
    parser.add_argument(
        "--index-manifest",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_4_adp_merged"
            r"\rag_embedding_index\index_manifest.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_4_adp_merged"
            r"\source_audit"
        ),
    )
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="출처 추적정보 전체 누락이나 ID 중복 시 종료코드 1 반환",
    )
    args = parser.parse_args()

    rag_path = args.rag.resolve()
    index_manifest_path = args.index_manifest.resolve()
    output_dir = args.output.resolve()

    if not rag_path.exists():
        raise FileNotFoundError(
            f"rag_chunks.jsonl을 찾지 못했습니다: {rag_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(rag_path)

    source_counts = Counter()
    service_counts = Counter()
    source_type_counts = Counter()
    evidence_scope_counts = Counter()
    purpose_counts = Counter()

    missing_source: list[dict[str, Any]] = []
    missing_service: list[dict[str, Any]] = []
    missing_source_file: list[dict[str, Any]] = []
    missing_source_url: list[dict[str, Any]] = []
    missing_chunk_id: list[dict[str, Any]] = []
    missing_text: list[dict[str, Any]] = []
    missing_hash: list[dict[str, Any]] = []
    missing_all_trace: list[dict[str, Any]] = []
    metadata_mismatch: list[dict[str, Any]] = []

    id_lines: dict[str, list[int]] = defaultdict(list)
    hash_lines: dict[str, list[int]] = defaultdict(list)

    per_source_trace = defaultdict(
        lambda: Counter(
            total=0,
            source_file_present=0,
            source_url_present=0,
            chunk_id_present=0,
            hash_present=0,
        )
    )

    for line_no, row in rows:
        metadata = nested_metadata(row)

        cid = chunk_id(row)
        text = chunk_text(row)
        digest = content_hash(row)

        source = pick(row, "source", "source_database")
        service = pick(
            row,
            "source_service",
            "service_slug",
        )
        source_type = pick(row, "source_type")
        source_file = pick(row, "source_file")
        source_url = pick(row, "source_url")
        evidence_scope = pick(row, "evidence_scope", "scope")
        purpose = pick(row, "purpose")

        display_source = source or "[누락]"
        display_service = service or "[누락]"
        display_source_type = source_type or "[누락]"
        display_evidence_scope = evidence_scope or "[누락]"
        display_purpose = purpose or "[누락]"

        source_counts[display_source] += 1
        service_counts[display_service] += 1
        source_type_counts[display_source_type] += 1
        evidence_scope_counts[display_evidence_scope] += 1
        purpose_counts[display_purpose] += 1

        trace = per_source_trace[display_service]
        trace["total"] += 1
        if source_file:
            trace["source_file_present"] += 1
        if source_url:
            trace["source_url_present"] += 1
        if cid:
            trace["chunk_id_present"] += 1
        if digest:
            trace["hash_present"] += 1

        base_issue = {
            "line_no": line_no,
            "chunk_id": cid,
            "source": source,
            "source_service": service,
            "source_file": source_file,
            "source_url": source_url,
            "title": norm(row.get("title")),
            "text_preview": text[:200],
        }

        if not source:
            missing_source.append(base_issue)
        if not service:
            missing_service.append(base_issue)
        if not source_file:
            missing_source_file.append(base_issue)
        if not source_url:
            missing_source_url.append(base_issue)
        if not cid:
            missing_chunk_id.append(base_issue)
        if not text:
            missing_text.append(base_issue)
        if not digest:
            missing_hash.append(base_issue)

        if not source and not source_file and not source_url:
            missing_all_trace.append(base_issue)

        if cid:
            id_lines[cid].append(line_no)
        if digest:
            hash_lines[digest].append(line_no)

        for key in (
            "source",
            "source_service",
            "source_type",
            "source_file",
            "source_url",
            "evidence_scope",
            "scope",
            "purpose",
            "crop",
            "host",
            "disease",
            "disease_name",
            "content_sha256",
        ):
            top_value = norm(row.get(key))
            meta_value = norm(metadata.get(key))

            if top_value and meta_value and top_value != meta_value:
                metadata_mismatch.append({
                    "line_no": line_no,
                    "chunk_id": cid,
                    "field": key,
                    "top_level_value": top_value,
                    "metadata_value": meta_value,
                    "source_service": service,
                })

    duplicate_ids = [
        {
            "chunk_id": key,
            "count": len(lines),
            "line_numbers": ",".join(map(str, lines)),
        }
        for key, lines in id_lines.items()
        if len(lines) > 1
    ]

    duplicate_hashes = [
        {
            "content_sha256": key,
            "count": len(lines),
            "line_numbers": ",".join(map(str, lines)),
        }
        for key, lines in hash_lines.items()
        if len(lines) > 1
    ]

    vector_count = None
    embedding_model = ""
    embedding_dimension = None
    vector_count_matches = None

    if index_manifest_path.exists():
        manifest = json.loads(
            index_manifest_path.read_text(encoding="utf-8-sig")
        )
        vector_count = int(manifest.get("vector_count") or 0)
        embedding_model = norm(manifest.get("embedding_model"))
        embedding_dimension = int(manifest.get("dimension") or 0)
        vector_count_matches = vector_count == len(rows)

    per_service_rows: list[dict[str, Any]] = []

    for service, counts in sorted(
        per_source_trace.items(),
        key=lambda item: (-item[1]["total"], item[0]),
    ):
        total = counts["total"]

        per_service_rows.append({
            "source_service": service,
            "total_chunks": total,
            "source_file_present": counts["source_file_present"],
            "source_file_coverage_percent": round(
                counts["source_file_present"] / total * 100,
                2,
            ),
            "source_url_present": counts["source_url_present"],
            "source_url_coverage_percent": round(
                counts["source_url_present"] / total * 100,
                2,
            ),
            "chunk_id_present": counts["chunk_id_present"],
            "chunk_id_coverage_percent": round(
                counts["chunk_id_present"] / total * 100,
                2,
            ),
            "hash_present": counts["hash_present"],
            "hash_coverage_percent": round(
                counts["hash_present"] / total * 100,
                2,
            ),
        })

    summary = {
        "rag_path": str(rag_path),
        "index_manifest_path": str(index_manifest_path),
        "total_chunks": len(rows),
        "vector_count": vector_count,
        "vector_count_matches_chunks": vector_count_matches,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "missing_counts": {
            "source": len(missing_source),
            "source_service": len(missing_service),
            "source_file": len(missing_source_file),
            "source_url": len(missing_source_url),
            "chunk_id": len(missing_chunk_id),
            "text": len(missing_text),
            "content_hash": len(missing_hash),
            "all_trace_information": len(missing_all_trace),
        },
        "duplicate_counts": {
            "duplicate_chunk_ids": len(duplicate_ids),
            "duplicate_content_hashes": len(duplicate_hashes),
        },
        "metadata_mismatch_count": len(metadata_mismatch),
        "source_counts": dict(source_counts.most_common()),
        "service_counts": dict(service_counts.most_common()),
        "source_type_counts": dict(source_type_counts.most_common()),
        "evidence_scope_counts": dict(
            evidence_scope_counts.most_common()
        ),
        "purpose_counts": dict(purpose_counts.most_common()),
        "strict_pass": (
            len(missing_all_trace) == 0
            and len(missing_chunk_id) == 0
            and len(missing_text) == 0
            and len(duplicate_ids) == 0
            and vector_count_matches is not False
        ),
    }

    (
        output_dir / "source_audit_summary.json"
    ).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_csv(
        output_dir / "missing_source.csv",
        missing_source,
    )
    write_csv(
        output_dir / "missing_source_service.csv",
        missing_service,
    )
    write_csv(
        output_dir / "missing_source_file.csv",
        missing_source_file,
    )
    write_csv(
        output_dir / "missing_source_url.csv",
        missing_source_url,
    )
    write_csv(
        output_dir / "missing_chunk_id.csv",
        missing_chunk_id,
    )
    write_csv(
        output_dir / "missing_text.csv",
        missing_text,
    )
    write_csv(
        output_dir / "missing_content_hash.csv",
        missing_hash,
    )
    write_csv(
        output_dir / "missing_all_trace_information.csv",
        missing_all_trace,
    )
    write_csv(
        output_dir / "duplicate_chunk_ids.csv",
        duplicate_ids,
    )
    write_csv(
        output_dir / "duplicate_content_hashes.csv",
        duplicate_hashes,
    )
    write_csv(
        output_dir / "metadata_mismatch.csv",
        metadata_mismatch,
    )
    write_csv(
        output_dir / "source_service_coverage.csv",
        per_service_rows,
    )

    text_lines = [
        "RAG 출처 감사 결과",
        "=" * 60,
        f"RAG: {rag_path}",
        f"전체 청크: {len(rows):,}",
        f"벡터 수: {vector_count if vector_count is not None else '확인 불가'}",
        f"청크·벡터 일치: {vector_count_matches}",
        f"임베딩 모델: {embedding_model or '확인 불가'}",
        f"임베딩 차원: {embedding_dimension or '확인 불가'}",
        "",
        "[누락]",
        f"source 누락: {len(missing_source):,}",
        f"source_service 누락: {len(missing_service):,}",
        f"source_file 누락: {len(missing_source_file):,}",
        f"source_url 누락: {len(missing_source_url):,}",
        f"chunk_id 누락: {len(missing_chunk_id):,}",
        f"text/content 누락: {len(missing_text):,}",
        f"content hash 누락: {len(missing_hash):,}",
        f"출처 추적정보 전체 누락: {len(missing_all_trace):,}",
        "",
        "[중복·불일치]",
        f"중복 chunk_id: {len(duplicate_ids):,}",
        f"중복 content hash: {len(duplicate_hashes):,}",
        f"상위 필드와 metadata 불일치: {len(metadata_mismatch):,}",
        "",
        f"엄격 감사 통과: {summary['strict_pass']}",
        "",
        "[출처 서비스별 청크 수]",
    ]

    for service, count in service_counts.most_common():
        text_lines.append(f"{count:>8,}  {service}")

    text_lines.extend([
        "",
        "[서비스별 출처 파일·URL 보유율]",
    ])

    for row in per_service_rows:
        text_lines.append(
            f"{row['source_service']}: "
            f"file={row['source_file_coverage_percent']}%, "
            f"url={row['source_url_coverage_percent']}%, "
            f"id={row['chunk_id_coverage_percent']}%, "
            f"hash={row['hash_coverage_percent']}%"
        )

    (
        output_dir / "source_audit_report.txt"
    ).write_text(
        "\n".join(text_lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(text_lines))
    print("")
    print("감사 결과 폴더:", output_dir)

    if args.strict and not summary["strict_pass"]:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
