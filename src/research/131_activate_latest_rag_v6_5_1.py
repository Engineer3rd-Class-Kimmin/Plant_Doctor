#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_EXTENSIONS = {
    ".py", ".ps1", ".env", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".dart",
}

EXCLUDED_DIR_NAMES = {
    ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    ".venv", "venv", "node_modules", "build", "dist",
    "nongsaro_24crop_collector",
}

OLD_RAG_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/][^\"'\r\n]*?[\\/])?"
    r"runs[\\/]+bulk_rag_factory_[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON 객체가 아닙니다: {path}")
    return value


def metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    if isinstance(value, dict):
        return value
    value = {}
    row["metadata"] = value
    return value


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
    return str(row.get("text") or row.get("content") or "")


def derive_title(row: dict[str, Any]) -> str:
    existing = pick(
        row,
        "paper_title",
        "citation_title",
        "document_title",
        "title",
    )
    if existing:
        return existing

    meta = metadata(row)
    for key, value in meta.items():
        key_low = key.lower()
        if "title" in key_low or "논문" in key_low or "제목" in key_low:
            candidate = norm(value)
            if candidate:
                return candidate

    cid = chunk_id(row)
    prefix = cid.split("__", 1)[0] if "__" in cid else cid
    prefix = re.sub(r"[_-]+", " ", prefix).strip()
    if prefix:
        return prefix

    return "제목 미확인 문헌"


def patch_literature_display(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    patched: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []

    for line_no, original in enumerate(rows, 1):
        row = json.loads(json.dumps(original, ensure_ascii=False))
        meta = metadata(row)
        service = pick(row, "source_service", "service_slug")

        if service == "legacy_literature_evidence":
            title = derive_title(row)

            row["citation_title"] = title
            row["display_source"] = title
            row["source_display"] = title
            row["user_visible_source"] = title
            row["paper_title"] = title

            meta["citation_title"] = title
            meta["display_source"] = title
            meta["source_display"] = title
            meta["user_visible_source"] = title
            meta["paper_title"] = title
            meta["citation_display_policy"] = "paper_title_only"
            meta["hide_internal_provenance_from_user"] = True

            # 내부 계보는 그대로 남겨 감사 가능성을 보존합니다.
            report.append({
                "line_no": line_no,
                "chunk_id": chunk_id(row),
                "paper_title": title,
                "provenance_status": pick(row, "provenance_status"),
                "internal_source_file_preserved": bool(
                    pick(row, "source_file")
                ),
            })

        patched.append(row)

    return patched, report


def validate_unchanged(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> None:
    if len(before) != len(after):
        raise RuntimeError("청크 수가 변경됐습니다.")

    changed_ids = 0
    changed_texts = 0

    for old, new in zip(before, after):
        if chunk_id(old) != chunk_id(new):
            changed_ids += 1
        if chunk_text(old) != chunk_text(new):
            changed_texts += 1

    if changed_ids:
        raise RuntimeError(
            f"chunk_id가 {changed_ids}개 변경됐습니다."
        )
    if changed_texts:
        raise RuntimeError(
            f"본문이 {changed_texts}개 변경됐습니다."
        )


def create_current_junction(
    current_path: Path,
    target_path: Path,
) -> str:
    if current_path.exists() or current_path.is_symlink():
        try:
            if current_path.is_symlink():
                current_path.unlink()
            elif current_path.is_dir():
                # Windows junction은 rmdir로 링크만 제거됩니다.
                subprocess.run(
                    ["cmd", "/c", "rmdir", str(current_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                current_path.unlink()
        except Exception as exc:
            raise RuntimeError(
                f"기존 current_rag 제거 실패: {current_path}: {exc}"
            ) from exc

    current_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        result = subprocess.run(
            [
                "cmd", "/c", "mklink", "/J",
                str(current_path), str(target_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "current_rag junction 생성 실패:\n"
                + result.stdout
                + "\n"
                + result.stderr
            )
        return "windows_junction"

    current_path.symlink_to(target_path, target_is_directory=True)
    return "directory_symlink"


def should_scan(path: Path, project_root: Path) -> bool:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return False

    if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
        return False
    if relative.parts and relative.parts[0].lower() == "runs":
        return False
    if path.suffix.lower() not in RUNTIME_EXTENSIONS:
        return False
    if path.name.lower().startswith(("readme", "license")):
        return False
    if re.match(r"^\d{2,3}_", path.name):
        # 과거 생성·수집 스크립트는 재현성을 위해 변경하지 않습니다.
        return False
    return True


def patch_runtime_references(
    project_root: Path,
    backup_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    patched_files: list[dict[str, Any]] = []
    remaining_refs: list[dict[str, Any]] = []

    for path in project_root.rglob("*"):
        if not path.is_file() or not should_scan(path, project_root):
            continue

        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue

        matches = list(OLD_RAG_PATTERN.finditer(text))
        if not matches:
            continue

        def replacement(match: re.Match[str]) -> str:
            matched = match.group(0)
            slash = "\\" if "\\" in matched else "/"

            absolute_match = re.match(
                r"^[A-Za-z]:[\\/]", matched
            )
            if absolute_match:
                return str(
                    project_root / "runs" / "current_rag"
                )
            return f"runs{slash}current_rag"

        new_text = OLD_RAG_PATTERN.sub(replacement, text)

        if new_text != text:
            relative = path.relative_to(project_root)
            backup = backup_root / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)

            encoding = "utf-8-sig" if path.suffix.lower() == ".ps1" else "utf-8"
            path.write_text(new_text, encoding=encoding)

            patched_files.append({
                "file": str(path),
                "backup": str(backup),
                "replacement_count": len(matches),
            })

    # 수정 후 남은 실제 런타임 참조를 다시 검색합니다.
    for path in project_root.rglob("*"):
        if not path.is_file() or not should_scan(path, project_root):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        found = OLD_RAG_PATTERN.findall(text)
        if found:
            remaining_refs.append({
                "file": str(path),
                "references": found,
            })

    return patched_files, remaining_refs


def update_env_file(
    project_root: Path,
    current_rag: Path,
    backup_root: Path,
) -> dict[str, Any]:
    env_path = project_root / ".env"
    env_values = {
        "PLANT_DOCTOR_RAG_DIR": str(current_rag),
        "RAG_WORK_DIR": str(current_rag),
        "RAG_DIR": str(current_rag),
        "RAG_INDEX_DIR": str(current_rag / "rag_embedding_index"),
        "RAG_CHUNKS_PATH": str(current_rag / "rag_chunks.jsonl"),
    }

    original = ""
    if env_path.exists():
        original = env_path.read_text(encoding="utf-8-sig")
        backup = backup_root / ".env"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(env_path, backup)

    lines = original.splitlines()
    existing_keys: set[str] = set()
    output_lines: list[str] = []

    for line in lines:
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and match.group(1) in env_values:
            key = match.group(1)
            output_lines.append(f"{key}={env_values[key]}")
            existing_keys.add(key)
        else:
            output_lines.append(line)

    if output_lines and output_lines[-1].strip():
        output_lines.append("")

    output_lines.append("# Plant Doctor active RAG")
    for key, value in env_values.items():
        if key not in existing_keys:
            output_lines.append(f"{key}={value}")

    env_path.write_text(
        "\n".join(output_lines).rstrip() + "\n",
        encoding="utf-8",
    )

    return {
        "env_file": str(env_path),
        "keys": env_values,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "V6.5 문헌 표시를 제목 전용으로 패치하고 "
            "프로그램이 최신 RAG를 보도록 current_rag를 활성화합니다."
        )
    )
    parser.add_argument(
        "--base-work-dir",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_5_provenance_patched"
        ),
    )
    parser.add_argument(
        "--output-work-dir",
        type=Path,
        default=Path(
            r".\runs\bulk_rag_factory_nongsaro_v2_ncpms_strict_v6_5_1_active"
        ),
    )
    parser.add_argument(
        "--current-rag",
        type=Path,
        default=Path(r".\runs\current_rag"),
    )
    parser.add_argument(
        "--embed-script",
        type=Path,
        default=Path(r".\84_evidence_gated_diagnostic_rag_factory.py"),
    )
    parser.add_argument(
        "--rag-root",
        type=Path,
        default=Path(r".\data\rag_plant_diseases"),
    )
    parser.add_argument("--embedding-device", default="cuda")
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--skip-runtime-patch", action="store_true")
    args = parser.parse_args()

    project_root = Path.cwd().resolve()
    base_dir = (project_root / args.base_work_dir).resolve()
    output_dir = (project_root / args.output_work_dir).resolve()
    current_rag = (project_root / args.current_rag).resolve()
    embed_script = (project_root / args.embed_script).resolve()
    rag_root = (project_root / args.rag_root).resolve()

    base_rag = base_dir / "rag_chunks.jsonl"
    base_manifest_path = (
        base_dir / "rag_embedding_index" / "index_manifest.json"
    )

    required = [base_rag, base_manifest_path, embed_script]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "필수 파일이 없습니다:\n" + "\n".join(missing)
        )

    before = read_jsonl(base_rag)
    base_manifest = read_manifest(base_manifest_path)

    vector_count = int(base_manifest.get("vector_count") or 0)
    model = norm(base_manifest.get("embedding_model"))
    dimension = int(base_manifest.get("dimension") or 0)

    if len(before) != vector_count:
        raise RuntimeError(
            f"기존 청크·벡터 수 불일치: {len(before)} != {vector_count}"
        )

    after, literature_report = patch_literature_display(before)
    validate_unchanged(before, after)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(output_dir / "rag_chunks.jsonl", after)
    write_jsonl(
        output_dir / "literature_title_display_report.jsonl",
        literature_report,
    )

    preliminary = {
        "update_version": "v6_5_1_active",
        "base_work_dir": str(base_dir),
        "output_work_dir": str(output_dir),
        "total_chunks": len(after),
        "literature_title_only_records": len(literature_report),
        "embedding_model": model,
        "embedding_dimension": dimension,
        "text_unchanged": True,
        "chunk_ids_unchanged": True,
    }
    (
        output_dir / "v6_5_1_activation_manifest.json"
    ).write_text(
        json.dumps(preliminary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(preliminary, ensure_ascii=False, indent=2))

    if args.skip_embed:
        print("RAG_V6_5_1_CHUNKS_READY")
        return

    command = [
        sys.executable,
        str(embed_script),
        "embed",
        "--rag-root",
        str(rag_root),
        "--work-dir",
        str(output_dir),
        "--embedding-model",
        model,
        "--embedding-device",
        args.embedding_device,
        "--embedding-batch-size",
        str(args.embedding_batch_size),
        "--embedding-local-files-only",
    ]
    print("running_embed=", " ".join(command))
    subprocess.run(command, check=True)

    new_manifest_path = (
        output_dir / "rag_embedding_index" / "index_manifest.json"
    )
    new_manifest = read_manifest(new_manifest_path)

    new_vectors = int(new_manifest.get("vector_count") or 0)
    new_dimension = int(new_manifest.get("dimension") or 0)
    new_model = norm(new_manifest.get("embedding_model"))

    if new_vectors != len(after):
        raise RuntimeError(
            f"최종 벡터 수 불일치: {new_vectors} != {len(after)}"
        )
    if new_dimension != dimension:
        raise RuntimeError(
            f"임베딩 차원 불일치: {new_dimension} != {dimension}"
        )
    if new_model != model:
        raise RuntimeError(
            f"임베딩 모델 불일치: {new_model} != {model}"
        )

    link_type = create_current_junction(current_rag, output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = (
        project_root / "runtime_rag_path_backups" / timestamp
    )

    patched_files: list[dict[str, Any]] = []
    remaining_refs: list[dict[str, Any]] = []
    env_report: dict[str, Any] = {}

    if not args.skip_runtime_patch:
        patched_files, remaining_refs = patch_runtime_references(
            project_root,
            backup_root,
        )
        env_report = update_env_file(
            project_root,
            current_rag,
            backup_root,
        )

    final_report = {
        **preliminary,
        "final_vector_count": new_vectors,
        "current_rag": str(current_rag),
        "current_rag_target": str(output_dir),
        "current_rag_link_type": link_type,
        "runtime_files_patched": len(patched_files),
        "patched_files": patched_files,
        "remaining_old_runtime_references": remaining_refs,
        "backup_root": str(backup_root),
        "environment": env_report,
    }

    (
        output_dir / "v6_5_1_activation_manifest.json"
    ).write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(final_report, ensure_ascii=False, indent=2))
    print("RAG_V6_5_1_ACTIVATION_COMPLETE")
    print("active_rag=", current_rag)
    print("active_target=", output_dir)
    print("final_vectors=", new_vectors)


if __name__ == "__main__":
    main()
