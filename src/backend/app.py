from __future__ import annotations

from weather_api import router as weather_router

import base64
import io
import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from openai import OpenAI
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from torchvision import models, transforms
from transformers import SegformerForSemanticSegmentation
from sentence_transformers import SentenceTransformer

register_heif_opener(thumbnails=False)

load_dotenv(Path(__file__).with_name(".env"))

PROJECT_ROOT = Path(
    os.getenv("PLANT_DOCTOR_MODEL_ROOT", r"E:\EyeGuideRAG\plant_er_bootstrap")
).resolve()
CLASSIFIER_DATA_ROOT = Path(
    os.getenv(
        "PLANT_CLASSIFIER_DATA_ROOT",
        str(PROJECT_ROOT / "data" / "plantseg_lesion_classifier_v1"),
    )
).resolve()

SEGMENTATION_PATH = Path(
    os.getenv(
        "PLANT_SEGMENTATION_MODEL",
        str(
            PROJECT_ROOT
            / "runs"
            / "segformer_b3_24crops_massive_video_aug_v1"
            / "best"
        ),
    )
).resolve()

CLASSIFIER_PATH = Path(
    os.getenv(
        "PLANT_CLASSIFIER_MODEL",
        str(
            PROJECT_ROOT
            / "runs"
            / "lesion_classifier_convnext_small_24crops_v1"
            / "best"
            / "checkpoint.pt"
        ),
    )
).resolve()

RAG_ROOT = Path(
    os.getenv(
        "PLANT_DOCTOR_RAG_DIR",
        os.getenv(
            "RAG_WORK_DIR",
            os.getenv(
                "RAG_DIR",
                os.getenv(
                    "PLANT_RAG_ROOT",
                    str(PROJECT_ROOT / "runs" / "current_rag"),
                ),
            ),
        ),
    )
).resolve()
RAG_INDEX_DIR = Path(
    os.getenv("RAG_INDEX_DIR", str(RAG_ROOT / "rag_embedding_index"))
).resolve()
RAG_CHUNKS_PATH = Path(
    os.getenv("RAG_CHUNKS_PATH", str(RAG_ROOT / "rag_chunks.jsonl"))
).resolve()
RAG_EMBEDDING_DEVICE = os.getenv("RAG_EMBEDDING_DEVICE", "cpu").strip() or "cpu"
RAG_TOP_K = max(1, int(os.getenv("RAG_TOP_K", "10")))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.30"))
RAG_REQUIRE_HOST_MATCH = os.getenv("RAG_REQUIRE_HOST_MATCH", "true").strip().lower() in {
    "1", "true", "yes", "on"
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4").strip()
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1200"))
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "120"))

IMAGE_SIZE = int(os.getenv("PLANT_SEGMENTATION_IMAGE_SIZE", "512"))
MASK_THRESHOLD = float(os.getenv("PLANT_SEGMENTATION_THRESHOLD", "0.5"))
REQUIRE_ALL_MODELS = os.getenv("PLANT_REQUIRE_ALL_MODELS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

MEAN = torch.tensor([0.485, 0.456, 0.406])[None, :, None, None]
STD = torch.tensor([0.229, 0.224, 0.225])[None, :, None, None]
SOURCE_SUFFIXES = {"google", "bing", "baidu", "yahoo", "flickr", "duckduckgo", "ddg"}

HOST_ALIASES: dict[str, list[str]] = {
    "eggplant": ["eggplant"],
    "citrus": ["citrus", "orange"],
    "potato": ["potato"],
    "pepper": ["pepper", "bell_pepper"],
    "carrot": ["carrot"],
    "strawberry": ["strawberry"],
    "garlic": ["garlic"],
    "napa_cabbage": ["napa_cabbage", "chinese_cabbage", "cabbage"],
    "rice": ["rice"],
    "peach": ["peach"],
    "broccoli": ["broccoli"],
    "blueberry": ["blueberry"],
    "apple": ["apple"],
    "lettuce": ["lettuce"],
    "ginger": ["ginger"],
    "cabbage": ["cabbage"],
    "cucumber": ["cucumber"],
    "corn": ["corn", "maize"],
    "plum": ["plum"],
    "cherry": ["cherry"],
    "soybean": ["soybean", "bean"],
    "tomato": ["tomato"],
    "grape": ["grape"],
    "squash": ["squash", "pumpkin"],
}



HOST_KO_ALIASES: dict[str, list[str]] = {
    "eggplant": ["가지"],
    "citrus": ["감귤", "귤"],
    "potato": ["감자"],
    "pepper": ["고추", "파프리카", "단고추"],
    "carrot": ["당근"],
    "strawberry": ["딸기"],
    "garlic": ["마늘"],
    "napa_cabbage": ["배추"],
    "rice": ["벼", "논벼"],
    "peach": ["복숭아"],
    "broccoli": ["브로콜리", "꽃양배추"],
    "blueberry": ["블루베리"],
    "apple": ["사과"],
    "lettuce": ["상추"],
    "ginger": ["생강"],
    "cabbage": ["양배추"],
    "cucumber": ["오이"],
    "corn": ["옥수수"],
    "plum": ["자두"],
    "cherry": ["체리", "양앵두"],
    "soybean": ["콩", "대두"],
    "tomato": ["토마토"],
    "grape": ["포도"],
    "squash": ["호박", "애호박", "단호박"],
}


def _meta_value(row: dict[str, Any], *keys: str) -> Any:
    nested = row.get("metadata")
    metadata = nested if isinstance(nested, dict) else {}
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    for key in keys:
        value = metadata.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


class RagVectorStore:
    def __init__(self) -> None:
        self.root = RAG_ROOT
        self.index_dir = RAG_INDEX_DIR
        self.chunks_path = RAG_CHUNKS_PATH
        self.embeddings_path = self.index_dir / "embeddings.npy"
        self.metadata_path = self.index_dir / "metadata.jsonl"
        self.manifest_path = self.index_dir / "index_manifest.json"
        self.embedding_model_name = ""
        self.dimension = 0
        self.vector_count = 0
        self.normalized = False
        self.embeddings: np.ndarray | None = None
        self.records: list[dict[str, Any]] = []
        self.search_model: SentenceTransformer | None = None
        self.loaded_ms = 0.0
        self.lock = threading.RLock()

    def load(self) -> None:
        started = time.perf_counter()
        required = [
            self.root,
            self.embeddings_path,
            self.metadata_path,
            self.manifest_path,
            self.chunks_path,
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError(
                "최신 RAG 필수 파일이 없습니다:\n" + "\n".join(missing)
            )

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8-sig"))
        self.embedding_model_name = str(
            manifest.get("embedding_model") or "intfloat/multilingual-e5-base"
        ).strip()
        self.dimension = int(manifest.get("dimension") or 0)
        self.vector_count = int(manifest.get("vector_count") or 0)
        self.normalized = bool(manifest.get("normalized", True))

        self.embeddings = np.load(self.embeddings_path, mmap_mode="r")
        if self.embeddings.ndim != 2:
            raise RuntimeError(f"RAG embeddings shape 오류: {self.embeddings.shape}")
        if self.embeddings.shape[0] != self.vector_count:
            raise RuntimeError(
                f"RAG 벡터 수 불일치: npy={self.embeddings.shape[0]}, "
                f"manifest={self.vector_count}"
            )
        if self.dimension and self.embeddings.shape[1] != self.dimension:
            raise RuntimeError(
                f"RAG 차원 불일치: npy={self.embeddings.shape[1]}, "
                f"manifest={self.dimension}"
            )

        self.records = []
        with self.metadata_path.open("r", encoding="utf-8-sig") as handle:
            for line_no, raw in enumerate(handle, 1):
                line = raw.strip()
                if not line:
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(
                        f"RAG metadata JSON 객체 오류: {self.metadata_path}:{line_no}"
                    )
                self.records.append(value)

        if len(self.records) != self.vector_count:
            raise RuntimeError(
                f"RAG metadata 수 불일치: metadata={len(self.records)}, "
                f"vectors={self.vector_count}"
            )

        chunk_rows: list[dict[str, Any]] = []
        with self.chunks_path.open("r", encoding="utf-8-sig") as handle:
            for line_no, raw in enumerate(handle, 1):
                line = raw.strip()
                if not line:
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(
                        f"RAG chunk JSON 객체 오류: {self.chunks_path}:{line_no}"
                    )
                chunk_rows.append(value)
        if len(chunk_rows) != self.vector_count:
            raise RuntimeError(
                f"RAG chunk 수 불일치: chunks={len(chunk_rows)}, "
                f"vectors={self.vector_count}"
            )

        # 인덱스 metadata에 본문이 빠진 구조도 지원합니다.
        merged_records: list[dict[str, Any]] = []
        for index, (meta_row, chunk_row) in enumerate(
            zip(self.records, chunk_rows, strict=True)
        ):
            meta_id = str(_meta_value(meta_row, "chunk_id", "id") or "")
            chunk_id_value = str(_meta_value(chunk_row, "chunk_id", "id") or "")
            if meta_id and chunk_id_value and meta_id != chunk_id_value:
                raise RuntimeError(
                    f"RAG 순서 불일치 index={index}: "
                    f"metadata={meta_id}, chunk={chunk_id_value}"
                )
            merged = dict(chunk_row)
            merged_meta = merged.get("metadata")
            if not isinstance(merged_meta, dict):
                merged_meta = {}
            index_meta = meta_row.get("metadata")
            if isinstance(index_meta, dict):
                merged_meta.update(index_meta)
            for key, value in meta_row.items():
                if key != "metadata" and value not in (None, "", [], {}):
                    merged[key] = value
            merged["metadata"] = merged_meta
            merged_records.append(merged)
        self.records = merged_records

        print(
            f"[startup] loading RAG query encoder: {self.embedding_model_name} "
            f"device={RAG_EMBEDDING_DEVICE}"
        )
        self.search_model = SentenceTransformer(
            self.embedding_model_name,
            device=RAG_EMBEDDING_DEVICE,
            local_files_only=True,
        )
        self.loaded_ms = (time.perf_counter() - started) * 1000
        print(
            f"[startup] vector RAG ready vectors={self.vector_count} "
            f"dim={self.embeddings.shape[1]} normalized={self.normalized} "
            f"root={self.root} load_ms={self.loaded_ms:.1f}"
        )

    def _record_host_values(self, row: dict[str, Any]) -> set[str]:
        values: set[str] = set()
        for key in ("host", "crop", "crop_names_ko", "host_ko"):
            for item in _string_values(_meta_value(row, key)):
                normalized = normalize_label(item)
                if normalized:
                    values.add(normalized)
                values.add(item.strip().lower())
        return values

    def _host_matches(self, row: dict[str, Any], host: str, host_ko: str) -> bool:
        record_values = self._record_host_values(row)
        if not record_values:
            # 병명 사전이나 일반 근거는 host 필드가 없을 수 있으므로 허용합니다.
            service = str(_meta_value(row, "source_service", "service_slug") or "")
            return service in {
                "korean_plant_disease_catalog",
                "legacy_literature_evidence",
            }

        candidates: set[str] = {
            normalize_label(host),
            normalize_label(host_ko),
            host.strip().lower(),
            host_ko.strip().lower(),
        }
        for alias in HOST_ALIASES.get(normalize_label(host), []):
            candidates.add(normalize_label(alias))
            candidates.add(alias.lower())
        for alias in HOST_KO_ALIASES.get(normalize_label(host), []):
            candidates.add(normalize_label(alias))
            candidates.add(alias.lower())
        candidates.discard("")
        return bool(record_values & candidates)

    def _display_source(self, row: dict[str, Any]) -> str:
        service = str(_meta_value(row, "source_service", "service_slug") or "")
        if service == "legacy_literature_evidence":
            return str(
                _meta_value(
                    row,
                    "paper_title",
                    "citation_title",
                    "display_source",
                    "title",
                )
                or "제목 미확인 문헌"
            ).strip()
        return str(
            _meta_value(row, "display_source", "source_title", "source")
            or service
            or "출처 미상"
        ).strip()

    def search(
        self,
        *,
        disease_id: str,
        host: str,
        host_ko: str,
        top_k: int = RAG_TOP_K,
        min_score: float = RAG_MIN_SCORE,
    ) -> list[dict[str, Any]]:
        if self.search_model is None or self.embeddings is None:
            raise RuntimeError("RAG vector store is not loaded.")

        disease_human = humanize_label(disease_id)
        query = (
            f"query: 작물 {host_ko} ({host}), 질병 후보 {disease_human} "
            f"({disease_id})의 증상, 원인, 감별, 관리, 예방, 등록 농약 근거"
        )
        with self.lock:
            query_vector = self.search_model.encode(
                [query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )[0].astype(np.float32, copy=False)

        # embeddings.npy가 정규화되어 있으므로 내적이 코사인 유사도입니다.
        scores = np.asarray(self.embeddings @ query_vector, dtype=np.float32)
        candidate_count = min(max(top_k * 25, 250), len(scores))
        if candidate_count >= len(scores):
            candidate_ids = np.argsort(scores)[::-1]
        else:
            partition = np.argpartition(scores, -candidate_count)[-candidate_count:]
            candidate_ids = partition[np.argsort(scores[partition])[::-1]]

        selected: list[dict[str, Any]] = []
        for index in candidate_ids:
            score = float(scores[int(index)])
            if score < min_score:
                continue
            row = self.records[int(index)]
            if RAG_REQUIRE_HOST_MATCH and not self._host_matches(row, host, host_ko):
                continue

            text = str(_meta_value(row, "text", "content") or "").strip()
            if not text:
                continue
            selected.append(
                {
                    "rank": len(selected) + 1,
                    "score": round(score, 6),
                    "chunk_id": str(_meta_value(row, "chunk_id", "id") or ""),
                    "text": text[:1400],
                    "source": self._display_source(row),
                    "source_service": str(
                        _meta_value(row, "source_service", "service_slug") or ""
                    ),
                    "source_url": str(_meta_value(row, "source_url") or ""),
                    "purpose": str(_meta_value(row, "purpose") or ""),
                    "crop": str(_meta_value(row, "crop", "host") or ""),
                }
            )
            if len(selected) >= top_k:
                break
        return selected

    def status(self) -> dict[str, Any]:
        return {
            "rag_loaded": self.search_model is not None and self.embeddings is not None,
            "rag_root": str(self.root),
            "rag_root_exists": self.root.exists(),
            "rag_index_dir": str(self.index_dir),
            "rag_chunks_path": str(self.chunks_path),
            "rag_embedding_model": self.embedding_model_name,
            "rag_embedding_device": RAG_EMBEDDING_DEVICE,
            "rag_vector_count": self.vector_count,
            "rag_dimension": self.dimension,
            "rag_normalized": self.normalized,
            "rag_load_ms": round(self.loaded_ms, 2),
            "rag_top_k": RAG_TOP_K,
            "rag_min_score": RAG_MIN_SCORE,
            "rag_require_host_match": RAG_REQUIRE_HOST_MATCH,
        }


def _cuda_memory() -> dict[str, float]:
    if not torch.cuda.is_available():
        return {}
    return {
        "allocated_gb": round(torch.cuda.memory_allocated() / 1024**3, 3),
        "reserved_gb": round(torch.cuda.memory_reserved() / 1024**3, 3),
        "max_allocated_gb": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
    }


class ModelRegistry:
    def __init__(self) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError(
                "RTX 3090 CUDA가 감지되지 않았습니다. PyTorch CUDA 설치와 NVIDIA 드라이버를 확인하세요."
            )

        self.device = torch.device("cuda:0")
        self.segmentation_model: SegformerForSemanticSegmentation | None = None
        self.classifier_model: torch.nn.Module | None = None
        self.classifier_classes: list[str] = []
        self.classifier_image_size = 384
        self.host_names: list[str] = []
        self.host_to_ids: dict[str, list[int]] = {}

        self.openai_client: OpenAI | None = None
        self.rag_store = RagVectorStore()

        self.segmentation_warmup_ms = 0.0
        self.classifier_warmup_ms = 0.0
        self.openai_ready_ms = 0.0

        self.gpu_lock = threading.RLock()

    def load_all(self) -> None:
        torch.set_float32_matmul_precision("high")
        torch.backends.cudnn.benchmark = True
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

        self._load_segmentation()
        self._load_classifier()
        self._load_openai()
        self._load_rag()
        self._warmup_all()

        missing = []
        if self.segmentation_model is None:
            missing.append("segmentation")
        if self.classifier_model is None:
            missing.append("classifier")
        if self.openai_client is None:
            missing.append("openai")
        if self.rag_store.search_model is None:
            missing.append("rag")

        if REQUIRE_ALL_MODELS and missing:
            raise RuntimeError("필수 모델 로드 실패: " + ", ".join(missing))

        print(f"[startup] all models ready | cuda={_cuda_memory()}")

    def _load_segmentation(self) -> None:
        if not SEGMENTATION_PATH.exists():
            raise FileNotFoundError(f"SegFormer model not found: {SEGMENTATION_PATH}")

        print(f"[startup] loading SegFormer: {SEGMENTATION_PATH}")
        self.segmentation_model = (
            SegformerForSemanticSegmentation.from_pretrained(
                SEGMENTATION_PATH,
                local_files_only=True,
            )
            .to(self.device)
            .eval()
        )

    def _load_classifier(self) -> None:
        if not CLASSIFIER_PATH.exists():
            raise FileNotFoundError(f"Classifier checkpoint not found: {CLASSIFIER_PATH}")

        print(f"[startup] loading ConvNeXt-Small: {CLASSIFIER_PATH}")
        checkpoint = torch.load(CLASSIFIER_PATH, map_location="cpu", weights_only=False)

        self.classifier_classes = list(checkpoint.get("classes") or checkpoint.get("class_names") or [])
        if not self.classifier_classes:
            raise RuntimeError("분류 체크포인트에 classes/class_names가 없습니다.")

        self.classifier_image_size = int(checkpoint.get("image_size", 384))

        checkpoint_model_name = str(checkpoint.get("model_name", "convnext_small"))
        if checkpoint_model_name != "convnext_small":
            raise RuntimeError(
                f"Unsupported classifier architecture: {checkpoint_model_name}"
            )

        classifier = models.convnext_small(weights=None)
        in_features = classifier.classifier[2].in_features
        classifier.classifier[2] = torch.nn.Linear(in_features, len(self.classifier_classes))

        state = checkpoint.get("model_state_dict") or checkpoint.get("state_dict") or checkpoint
        classifier.load_state_dict(state)

        self.classifier_model = classifier.to(self.device).to(memory_format=torch.channels_last).eval()

        self.host_to_ids = {}
        for idx, label in enumerate(self.classifier_classes):
            self.host_to_ids.setdefault(label_host(label), []).append(idx)
        self.host_names = sorted(self.host_to_ids)

    def _load_openai(self) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 없습니다. server/.env 파일에 API 키를 입력하세요.")
        started = time.perf_counter()
        self.openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=2,
        )
        self.openai_ready_ms = (time.perf_counter() - started) * 1000
        print(f"[startup] OpenAI client ready model={OPENAI_MODEL}")

    def _load_rag(self) -> None:
        self.rag_store.load()

    def _warmup_all(self) -> None:
        self._warmup_segmentation()
        self._warmup_classifier()

    def _warmup_segmentation(self) -> None:
        assert self.segmentation_model is not None
        dummy = torch.zeros(1, 3, IMAGE_SIZE, IMAGE_SIZE, device=self.device)

        started = time.perf_counter()
        with self.gpu_lock, torch.inference_mode():
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                _ = self.segmentation_model(pixel_values=dummy).logits
            torch.cuda.synchronize()
        self.segmentation_warmup_ms = (time.perf_counter() - started) * 1000
        print(f"[startup] SegFormer ready {self.segmentation_warmup_ms:.1f} ms")

    def _warmup_classifier(self) -> None:
        assert self.classifier_model is not None
        dummy = torch.zeros(
            1,
            3,
            self.classifier_image_size,
            self.classifier_image_size,
            device=self.device,
        ).to(memory_format=torch.channels_last)

        started = time.perf_counter()
        with self.gpu_lock, torch.inference_mode():
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                _ = self.classifier_model(dummy)
            torch.cuda.synchronize()
        self.classifier_warmup_ms = (time.perf_counter() - started) * 1000
        print(f"[startup] ConvNeXt-Small ready {self.classifier_warmup_ms:.1f} ms")

    def status(self) -> dict[str, Any]:
        return {
            "device": str(self.device),
            "segmentation_loaded": self.segmentation_model is not None,
            "segmentation_path": str(SEGMENTATION_PATH),
            "segmentation_warmup_ms": round(self.segmentation_warmup_ms, 2),
            "classifier_loaded": self.classifier_model is not None,
            "classifier_path": str(CLASSIFIER_PATH),
            "classifier_classes": len(self.classifier_classes),
            "classifier_architecture": "convnext_small",
            "classifier_hosts": len(self.host_names),
            "classifier_warmup_ms": round(self.classifier_warmup_ms, 2),
            "llm_provider": "openai",
            "openai_loaded": self.openai_client is not None,
            "openai_model": OPENAI_MODEL,
            "openai_max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
            "openai_client_ready_ms": round(self.openai_ready_ms, 2),
            **self.rag_store.status(),
            "cuda_memory": _cuda_memory(),
        }


registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    if registry is None:
        raise RuntimeError("Model registry is not initialized.")
    return registry


def normalize_label(value: str) -> str:
    value = re.sub(r"[_-]?\d+$", "", value).strip("_- ").replace("-", "_")
    value = re.sub(r"_+", "_", value)
    parts = value.split("_") if value else []
    while parts and parts[-1].lower() in SOURCE_SUFFIXES:
        parts.pop()
    return "_".join(parts).lower()


def label_host(label: str) -> str:
    normalized = normalize_label(label)
    # Preserve compound crop names used by the trained checkpoint.  Also fold
    # the dataset's "grapevine" spelling into the application's grape host.
    if normalized.startswith("bell_pepper_"):
        return "bell_pepper"
    if normalized.startswith("grapevine_"):
        return "grape"
    return normalized.split("_", 1)[0].strip().lower()


def humanize_label(label: str) -> str:
    clean = normalize_label(label)
    if not clean:
        return "알 수 없음"
    return " ".join(part.capitalize() for part in clean.split("_"))


def open_rgb(data: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            return ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported or damaged image. "
                "Capture the photo again or upload a valid JPEG, PNG, or WebP image."
            ),
        ) from exc


def segmentation_tensor(image: Image.Image) -> torch.Tensor:
    reg = get_registry()
    resized = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
    return ((tensor - MEAN) / STD).to(reg.device)


def run_segmentation(image: Image.Image) -> tuple[np.ndarray, float]:
    reg = get_registry()
    if reg.segmentation_model is None:
        raise RuntimeError("Segmentation model is not loaded.")

    tensor = segmentation_tensor(image)
    with reg.gpu_lock, torch.inference_mode():
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            logits = reg.segmentation_model(pixel_values=tensor).logits
            logits = F.interpolate(logits, size=(IMAGE_SIZE, IMAGE_SIZE), mode="bilinear", align_corners=False)
            probability = logits.softmax(dim=1)[0, 1]
        mask = (probability >= MASK_THRESHOLD).byte().cpu().numpy()

    return mask, float(mask.mean())


def mask_png(mask: np.ndarray, output_size: tuple[int, int]) -> bytes:
    image = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    image = image.resize(output_size, Image.Resampling.NEAREST)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_focus_crop(
    image: Image.Image,
    mask: np.ndarray,
    padding_ratio: float = 0.20,
    outside_dim: float = 0.35,
) -> tuple[Image.Image, list[int] | None]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return image, None

    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    scale_x = image.width / IMAGE_SIZE
    scale_y = image.height / IMAGE_SIZE

    x1 = int(x1 * scale_x)
    x2 = int(x2 * scale_x)
    y1 = int(y1 * scale_y)
    y2 = int(y2 * scale_y)

    pad_x = max(8, int((x2 - x1) * padding_ratio))
    pad_y = max(8, int((y2 - y1) * padding_ratio))

    left = max(0, x1 - pad_x)
    top = max(0, y1 - pad_y)
    right = min(image.width, x2 + pad_x)
    bottom = min(image.height, y2 + pad_y)

    resized_mask = Image.fromarray((mask * 255).astype(np.uint8), mode="L").resize(image.size, Image.Resampling.NEAREST)
    mask_array = (np.asarray(resized_mask, dtype=np.float32) / 255.0)[:, :, None]
    image_array = np.asarray(image, dtype=np.float32)
    dimmed = image_array * (mask_array + (1.0 - mask_array) * outside_dim)
    focused = Image.fromarray(np.clip(dimmed, 0, 255).astype(np.uint8))
    return focused.crop((left, top, right, bottom)), [left, top, right, bottom]


def run_classifier(image: Image.Image) -> tuple[str, float, list[dict[str, float | str]], torch.Tensor]:
    reg = get_registry()
    if reg.classifier_model is None or not reg.classifier_classes:
        raise RuntimeError("Classifier model is not loaded.")

    preprocess = transforms.Compose(
        [
            transforms.Resize((reg.classifier_image_size, reg.classifier_image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    tensor = preprocess(image).unsqueeze(0).to(reg.device)
    tensor = tensor.to(memory_format=torch.channels_last)

    with reg.gpu_lock, torch.inference_mode():
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            logits = reg.classifier_model(tensor)
            probabilities = logits.softmax(dim=1)[0].float().detach().cpu()

    top_k = min(5, len(reg.classifier_classes))
    values, indices = probabilities.topk(top_k)
    predictions = [
        {"label": reg.classifier_classes[int(index)], "probability": float(value)}
        for value, index in zip(values, indices)
    ]

    return str(predictions[0]["label"]), float(predictions[0]["probability"]), predictions, probabilities


def resolve_classifier_hosts(requested_host: str) -> list[str]:
    normalized = normalize_label(requested_host)
    aliases = HOST_ALIASES.get(normalized, [normalized])
    reg = get_registry()
    return [alias for alias in aliases if alias in reg.host_to_ids]


def constrain_predictions_to_host(
    probabilities: torch.Tensor,
    requested_host: str | None,
) -> tuple[list[dict[str, float | str]], float, bool]:
    reg = get_registry()
    if not requested_host:
        return [], 0.0, False

    resolved_hosts = resolve_classifier_hosts(requested_host)
    if not resolved_hosts:
        return [], 0.0, False

    host_ids: list[int] = []
    for host in resolved_hosts:
        host_ids.extend(reg.host_to_ids.get(host, []))
    host_ids = sorted(set(host_ids))
    if not host_ids:
        return [], 0.0, False

    host_probabilities = probabilities[host_ids]
    host_mass = float(host_probabilities.sum().item())
    host_probabilities = host_probabilities / host_probabilities.sum().clamp_min(1e-12)
    host_k = min(5, len(host_ids))
    selected_probs, selected_local_ids = host_probabilities.topk(host_k)

    predictions = []
    for probability, local_id in zip(selected_probs, selected_local_ids):
        global_id = host_ids[int(local_id)]
        predictions.append(
            {
                "label": reg.classifier_classes[global_id],
                "probability": float(probability),
            }
        )
    return predictions, host_mass, True


def _image_data_url(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _extract_json(text: str) -> dict[str, Any]:
    content = text.strip()
    if not content:
        return {}
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def call_gpt_json(system_prompt: str, user_prompt: str, image: Image.Image | None = None) -> dict[str, Any]:
    reg = get_registry()
    if reg.openai_client is None:
        raise RuntimeError("OpenAI API client is not initialized.")

    content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
    if image is not None:
        content.append({"type": "input_image", "image_url": _image_data_url(image)})

    response = reg.openai_client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": content},
        ],
        max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
    )
    return _extract_json((response.output_text or "").strip())


def _is_korean_locale(locale: str) -> bool:
    return str(locale).lower().replace("_", "-").split("-", 1)[0] == "ko"


def _contains_hangul(value: Any) -> bool:
    return bool(re.search(r"[가-힣]", json.dumps(value, ensure_ascii=False)))


def _enforce_output_locale(payload: dict[str, Any], locale: str, context: str) -> dict[str, Any]:
    """Translate residual Korean fallbacks without changing JSON structure."""
    if not payload or _is_korean_locale(locale) or not _contains_hangul(payload):
        return payload
    try:
        translated = call_gpt_json(
            (
                "You are a strict JSON localization validator. Return JSON only. "
                f"Translate every user-visible string into BCP-47 locale {locale}. "
                "Do not leave any Korean/Hangul in user-visible values. Preserve all keys, "
                "IDs, URLs, numbers, booleans, nulls, arrays, and interpolation tokens."
            ),
            f"Context: {context}\nLocalize this JSON:\n{json.dumps(payload, ensure_ascii=False)}",
        )
        if translated and not _contains_hangul(translated):
            return translated
    except Exception as error:
        print(f"[locale] cleanup failed locale={locale} context={context}: {error}")
    return payload


def _localize_values(values: list[str], locale: str, context: str) -> list[str]:
    if _is_korean_locale(locale):
        return values
    result: list[str | None] = [None] * len(values)
    missing_indexes: list[int] = []
    for index, source in enumerate(values):
        cached = LOCALIZATION_CACHE.get((locale, source))
        if cached and not _contains_hangul(cached):
            result[index] = cached
        else:
            missing_indexes.append(index)
    if missing_indexes:
        missing = [values[index] for index in missing_indexes]
        try:
            payload = call_gpt_json(
                (
                    "You localize short plant-health labels and source titles for a mobile app. Return strict JSON only. "
                    f"Write every item naturally in BCP-47 locale {locale}. Never leave Hangul. "
                    "Preserve scientific names and disease meaning."
                ),
                f"Context: {context}\nReturn {{\"translations\":[...]}} in identical order for:\n"
                + json.dumps(missing, ensure_ascii=False),
            )
            translated = payload.get("translations")
            if isinstance(translated, list) and len(translated) == len(missing):
                for index, value in zip(missing_indexes, translated, strict=True):
                    clean = str(value).strip()
                    if clean and not _contains_hangul(clean):
                        result[index] = clean
                        LOCALIZATION_CACHE[(locale, values[index])] = clean
        except Exception as error:
            print(f"[locale] names failed locale={locale} context={context}: {error}")
    return [str(value if value is not None else source) for value, source in zip(result, values, strict=True)]


def infer_host_with_gpt(image: Image.Image) -> dict[str, Any]:
    reg = get_registry()
    allowed_hosts = ", ".join(reg.host_names)
    system_prompt = (
        "You identify the plant host/crop from a leaf photo. "
        "Return strict JSON only. Never add markdown."
    )
    user_prompt = f"""
아래 이미지를 보고 잎의 작물(식물 host)을 추정하세요.
반드시 아래 host 목록 중 하나만 선택하거나, 확실하지 않으면 unknown으로 답하세요.

허용 host 목록:
{allowed_hosts}

반환 JSON 스키마:
{{
  "host": "one_of_allowed_hosts_or_unknown",
  "confidence": "high|medium|low",
  "reason": "짧은 한국어 이유"
}}

규칙:
- host 목록 밖의 값을 만들지 마세요.
- 이미지에서 확실히 보이지 않으면 unknown.
- 잎만 보고 가능한 수준으로만 추정하세요.
""".strip()
    payload = call_gpt_json(system_prompt, user_prompt, image)
    host = normalize_label(str(payload.get("host", "unknown")))
    if host not in reg.host_to_ids and host != "unknown":
        host = "unknown"
    confidence = str(payload.get("confidence", "low")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    reason = str(payload.get("reason", "")).strip()
    return {"host": host, "confidence": confidence, "reason": reason}


def _flatten_candidate_text(predictions: list[dict[str, float | str]]) -> str:
    lines = []
    for row in predictions:
        label = str(row.get("label", ""))
        probability = float(row.get("probability", 0.0)) * 100
        lines.append(f"- {label}: {probability:.2f}%")
    return "\n".join(lines)


def load_rag_facts(
    disease_id: str,
    host: str,
    host_ko: str,
    max_items: int = 8,
) -> tuple[list[str], list[dict[str, Any]]]:
    results = get_registry().rag_store.search(
        disease_id=disease_id,
        host=host,
        host_ko=host_ko,
        top_k=max_items,
    )
    facts = [
        f"[출처: {item['source']}] {item['text']}"
        for item in results
    ]
    sources = [
        {
            "rank": item["rank"],
            "score": item["score"],
            "chunk_id": item["chunk_id"],
            "source": item["source"],
            "source_service": item["source_service"],
            "source_url": item["source_url"],
            "purpose": item["purpose"],
        }
        for item in results
    ]
    return facts, sources

def summarize_diagnosis_with_gpt(
    full_image: Image.Image,
    focused_image: Image.Image,
    selected_label: str,
    selected_confidence: float,
    mask_ratio: float,
    raw_predictions: list[dict[str, float | str]],
    host_info: dict[str, Any],
    host_locked_predictions: list[dict[str, float | str]],
    rag_facts: list[str],
    locale: str = "ko-KR",
) -> dict[str, Any]:
    rag_text = "\n".join(f"- {fact}" for fact in rag_facts) if rag_facts else "- 사용 가능한 RAG 근거 없음"
    raw_text = _flatten_candidate_text(raw_predictions)
    locked_text = _flatten_candidate_text(host_locked_predictions) if host_locked_predictions else "- host 고정 후보 없음"

    system_prompt = (
        "You are Plant Doctor, a plant disease explanation assistant. "
        f"Return strict JSON only. Write every user-visible value in locale {locale}. "
        "Do not dump raw RAG text verbatim."
    )

    user_prompt = f"""
식물 병해 진단 결과를 일반인이 이해하기 쉽게 요약하세요.
반드시 다음 휴대폰 언어로 작성하세요: {locale}
아래 정보는 모델 후보, 병변 면적, host 고정 정보, 그리고 RAG 근거 요약입니다.

최종 선택 disease_id: {selected_label}
최종 신뢰도: {selected_confidence * 100:.2f}%
병변 면적 비율: {mask_ratio * 100:.2f}%
추정 host: {host_info.get('host', 'unknown')}
host 추정 신뢰도: {host_info.get('confidence', 'low')}
host 추정 이유: {host_info.get('reason', '')}

원본 분류 후보:
{raw_text}

host 고정 후보:
{locked_text}

RAG 근거 요약:
{rag_text}

반환 JSON 스키마:
{{
  "disease_name": "{locale} 언어로 쓴 질병명",
  "disease_name_ko": "한국어 질병명(내부 호환용)",
  "disease_name_en": "영문 질병명 또는 null",
  "headline": "한 줄 요약",
  "short_summary": "2문장 이내 짧은 요약",
  "observation_summary": "이미지에서 보이는 핵심 관찰 1~2문장",
  "disease_info": "질병 정보 요약 2~4문장",
  "management_steps": ["짧은 행동 1 > 행동 1에만 해당하는 구체적 실행 설명", "짧은 행동 2 > 행동 2에만 해당하는 구체적 실행 설명", "짧은 행동 3 > 행동 3에만 해당하는 구체적 실행 설명"],
  "prevention_steps": ["예방 1", "예방 2", "예방 3", "예방 4"],
  "additional_checks": ["추가 확인 1", "추가 확인 2", "추가 확인 3"],
  "caution_note": "오진 가능성, 주의점, 전문가 확인 필요 조건",
  "confidence_message": "신뢰도 설명 한 문장",
  "host_reason": "{locale} 언어로 쓴 작물 선택 또는 판단 근거 한 문장",
  "severity_label": "관찰 필요|주의 단계|위험 가능성",
  "needs_expert_check": true,
  "source_note": "예: AI 분석 + RAG 요약 / AI 분석 기반"
}}

규칙:
- 전문 용어를 줄이고 {locale} 사용자가 읽기 쉬운 자연스러운 언어를 사용하세요.
- disease_name을 포함한 사용자 표시값에는 {locale} 이외의 언어를 섞지 마세요.
- RAG 내용을 그대로 길게 복붙하지 말고 핵심만 쉬운 말로 재구성하세요.
- 이미지에서 확인되지 않는 특징은 단정하지 마세요.
- 최종 확정 진단처럼 쓰지 말고, 참고용이라는 뉘앙스를 유지하세요.
- 관리 방법은 사용자가 바로 행동할 수 있게 짧고 구체적으로 쓰세요.
- management_steps는 최대 3개, prevention_steps는 최대 4개, additional_checks는 최대 3개만 작성하세요.
- management_steps의 각 항목은 반드시 `짧은 행동 > 해당 행동만의 구체적인 상세 설명` 형식으로 작성하고, 서로 같은 상세 설명을 반복하지 마세요.
""".strip()

    payload = call_gpt_json(system_prompt, user_prompt, full_image)
    payload.setdefault("disease_name", humanize_label(selected_label))
    payload.setdefault("disease_name_ko", humanize_label(selected_label))
    payload.setdefault("disease_name_en", humanize_label(selected_label))
    payload.setdefault("headline", "식물 잎에서 병징이 의심됩니다.")
    payload.setdefault("short_summary", "AI 분석 결과를 바탕으로 병해 가능성을 안내합니다.")
    payload.setdefault("observation_summary", "잎에서 병변이 의심되는 부위가 확인되었습니다.")
    payload.setdefault("disease_info", payload.get("short_summary"))
    payload.setdefault("management_steps", ["병든 부위를 우선 관찰하고 상태를 기록하세요."])
    payload.setdefault("prevention_steps", ["통풍이 잘 되도록 관리하세요."])
    payload.setdefault("additional_checks", ["새 잎에도 비슷한 반점이 생기는지 확인하세요."])
    payload.setdefault("caution_note", "모델 결과는 참고용이며, 증상이 빠르게 번지면 전문가 확인이 필요합니다.")
    payload.setdefault("confidence_message", "AI 신뢰도는 참고 지표이며 실제 상태와 다를 수 있습니다.")
    payload.setdefault("host_reason", str(host_info.get("reason") or ""))
    payload.setdefault("severity_label", "주의 단계")
    payload.setdefault("needs_expert_check", True)
    payload.setdefault("source_note", "Plant Doctor AI 분석 기반")

    for key in ("management_steps", "prevention_steps", "additional_checks"):
        value = payload.get(key)
        if not isinstance(value, list):
            payload[key] = []
        else:
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            limits = {"management_steps": 3, "prevention_steps": 4, "additional_checks": 3}
            payload[key] = cleaned[: limits[key]]

    protected_ko_name = payload.pop("disease_name_ko", None)
    payload = _enforce_output_locale(payload, locale, "plant diagnosis result")
    if protected_ko_name:
        payload["disease_name_ko"] = protected_ko_name

    return payload


def build_legacy_text(summary: dict[str, Any], disease_id: str, confidence: float, mask_ratio: float) -> str:
    management_steps = summary.get("management_steps") or []
    additional_checks = summary.get("additional_checks") or []
    prevention_steps = summary.get("prevention_steps") or []
    # This compatibility field is assembled only from already localized GPT
    # values. Hard-coded Korean headings previously leaked into foreign UIs.
    sections = [
        str(summary.get("disease_name") or humanize_label(disease_id)),
        str(summary.get("short_summary") or ""),
        str(summary.get("observation_summary") or ""),
        "\n".join(f"- {item}" for item in management_steps),
        "\n".join(f"- {item}" for item in additional_checks),
        "\n".join(f"- {item}" for item in prevention_steps),
        str(summary.get("caution_note") or ""),
    ]
    return "\n\n".join(section for section in sections if section.strip())


DICTIONARY_CATEGORY_LABELS = {
    "symptoms": "주요 증상",
    "affected_parts": "발생 부위",
    "pathogen": "원인",
    "favorable_conditions": "잘 발생하는 환경",
    "transmission": "전염과 확산",
    "management": "관리와 예방",
    "differential_diagnosis": "비슷한 증상과 구별",
}
DICTIONARY_SUMMARY_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
LOCALIZATION_CACHE: dict[tuple[str, str], str] = {}
DISEASE_NAME_KO = {
    "alternaria_leaf_blight": "알터나리아잎마름병", "alternaria_leaf_spot": "알터나리아잎반점병",
    "angular_leaf_spot": "각진잎반점병", "anthracnose": "탄저병", "bacterial_blight": "세균성잎마름병",
    "bacterial_leaf_spot": "세균성잎반점병", "bacterial_spot": "세균성반점병", "bacterial_wilt": "세균성시들음병",
    "black_rot": "검은썩음병", "blast": "도열병", "blossom_end_rot": "배꼽썩음병", "brown_rot": "갈색썩음병",
    "brown_spot": "갈색반점병", "canker": "궤양병", "cavity_spot": "공동반점병",
    "cercospora_leaf_spot": "세르코스포라잎반점병", "downy_mildew": "노균병", "early_blight": "겹둥근무늬병",
    "frog_eye_leaf_spot": "개구리눈무늬병", "gray_leaf_spot": "회색잎반점병", "greening_disease": "감귤그리닝병",
    "late_blight": "역병", "leaf_blight": "잎마름병", "leaf_curl": "잎말림병", "leaf_mold": "잎곰팡이병",
    "leaf_scorch": "잎마름증", "leaf_spot": "잎반점병", "mosaic": "모자이크병", "mosaic_virus": "모자이크바이러스병",
    "mummy_berry": "미라열매병", "northern_leaf_blight": "북방잎마름병", "phomopsis_fruit_rot": "포모프시스열매썩음병",
    "pocket_disease": "주머니병", "powdery_mildew": "흰가루병", "rust": "녹병", "scab": "검은별무늬병",
    "scorch": "스코치병", "septoria_leaf_spot": "셉토리아잎반점병", "sheath_blight": "잎집무늬마름병",
    "smut": "깜부기병", "yellow_leaf_curl_virus": "황화잎말림바이러스병",
    "grapevine_leafroll_disease": "포도나무잎말림병",
}


def disease_name_ko(disease_id: str) -> str:
    normalized = normalize_label(disease_id)
    prefixes = sorted(
        {alias for aliases in HOST_ALIASES.values() for alias in aliases} | set(HOST_ALIASES),
        key=len,
        reverse=True,
    )
    suffix = normalized
    for prefix in prefixes:
        marker = f"{prefix}_"
        if normalized.startswith(marker):
            suffix = normalized[len(marker):]
            break
    return DISEASE_NAME_KO.get(suffix, humanize_label(normalized))


def _dictionary_row_disease(row: dict[str, Any]) -> str:
    disease_id = normalize_label(str(_meta_value(row, "disease_id") or ""))
    scope_id = normalize_label(str(_meta_value(row, "scope_disease_id") or ""))
    if disease_id in {"", "general_agriculture"} and scope_id not in {"", "general_agriculture"}:
        return scope_id
    return disease_id


def _dictionary_host_rows(host: str) -> list[dict[str, Any]]:
    normalized_host = normalize_label(host)
    aliases = set(HOST_ALIASES.get(normalized_host, [normalized_host]))
    return [
        row
        for row in get_registry().rag_store.records
        if normalize_label(str(_meta_value(row, "host", "crop") or "")) in aliases
    ]


def _dictionary_records(host: str, disease_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _dictionary_host_rows(host):
        row_disease = _dictionary_row_disease(row)
        if row_disease == "general_agriculture":
            continue
        if disease_id is not None and row_disease != normalize_label(disease_id):
            continue
        rows.append(row)
    return rows


def _dictionary_disease_name(rows: list[dict[str, Any]], disease_id: str) -> str:
    for row in rows:
        name = str(_meta_value(row, "strict_source_disease_ko", "disease_name_ko") or "").strip()
        if name:
            return re.split(r"\s*한문명\s*", name, maxsplit=1)[0].strip()
    return disease_name_ko(disease_id)


def _dictionary_evidence(rows: list[dict[str, Any]], limit_per_category: int = 2) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    seen: set[str] = set()
    for row in rows:
        text_value = re.sub(r"\s+", " ", str(row.get("text") or "")).strip()
        if len(text_value) < 45:
            continue
        fingerprint = str(row.get("content_sha256") or text_value[:180])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        publisher = str(row.get("publisher") or _meta_value(row, "source") or "")
        score = 0.0
        score += 4.0 if row.get("evidence_quality") == "A" else 0.0
        score += 3.0 if row.get("strict_diagnostic") else 0.0
        score += 3.0 if re.search(r"[가-힣]", text_value) else 0.0
        score += 2.0 if any(key in publisher for key in ("농촌진흥청", "NCPMS", "농사로")) else 0.0
        score += 1.0 if 100 <= len(text_value) <= 1200 else 0.0
        ranked.append((score, row))

    selected: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for _, row in sorted(ranked, key=lambda item: item[0], reverse=True):
        categories = [str(value) for value in (row.get("categories") or ["general"])]
        category = next(
            (value for value in categories if category_counts.get(value, 0) < limit_per_category),
            None,
        )
        if category is None:
            continue
        category_counts[category] = category_counts.get(category, 0) + 1
        selected.append(
            {
                "category": category,
                "category_label": DICTIONARY_CATEGORY_LABELS.get(category, "참고 정보"),
                "text": re.sub(r"\s+", " ", str(row.get("text") or "")).strip()[:1100],
                "source": str(row.get("source_title") or row.get("publisher") or "Plant Doctor RAG 원문"),
                "url": str(row.get("url") or _meta_value(row, "source_url") or ""),
                "safe_fallback": bool(re.search(r"[가-힣]", str(row.get("text") or ""))),
            }
        )
    return selected[:14]


def _dictionary_summary(host: str, disease_id: str, disease_name: str, evidence: list[dict[str, Any]], locale: str) -> dict[str, Any]:
    evidence_text = "\n".join(
        f"[{item['category_label']}] {item['text']} (출처: {item['source']})"
        for item in evidence
    )
    prompt = f"""
작물 질병 백과사전 항목을 일반인이 읽기 쉬운 언어로 작성하세요.
출력 언어(locale): {locale}
작물 ID: {host}
질병 ID: {disease_id}
표시 질병명: {disease_name}

선별된 로컬 RAG 원문 근거:
{evidence_text or '근거가 부족합니다.'}

반환 JSON:
{{
  "headline": "질병을 한 문장으로 설명",
  "overview": "쉬운 말로 쓴 2~4문장 설명",
  "symptoms": ["관찰할 증상"],
  "causes": ["원인과 발생 환경"],
  "spread": ["전염 또는 확산 정보"],
  "management": ["실천 가능한 관리 방법"],
  "prevention": ["예방 방법"],
  "caution": "농약 사용과 확정 진단에 관한 주의 문장"
}}

규칙: 원문에 없는 내용을 만들지 말고, 단정적 확정 진단을 피하세요. 각 목록은 최대 5개이며 짧고 구체적으로 작성하세요.
""".strip()
    try:
        payload = call_gpt_json(
            f"You turn plant-disease evidence into a concise, safe encyclopedia. Write every user-visible value in locale {locale}. Return strict JSON only.",
            prompt,
        )
    except Exception as error:
        print(f"[dictionary] GPT summary fallback disease={disease_id}: {error}")
        payload = {}

    category_keys = {
        "symptoms": "symptoms",
        "affected_parts": "symptoms",
        "pathogen": "causes",
        "favorable_conditions": "causes",
        "transmission": "spread",
        "management": "management",
        "differential_diagnosis": "symptoms",
    }
    fallback_lists: dict[str, list[str]] = {
        "symptoms": [], "causes": [], "spread": [], "management": [], "prevention": []
    }
    for item in evidence:
        if not item.get("safe_fallback"):
            continue
        target = category_keys.get(str(item.get("category")), "")
        text_value = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        if target and text_value:
            fallback_lists[target].append(text_value[:320])

    payload.setdefault("headline", f"{disease_name} 관련 증상과 관리 정보를 확인하세요.")
    payload.setdefault("overview", "Plant Doctor 로컬 근거 자료를 작물과 질병별로 정리한 참고 정보입니다.")
    payload.setdefault("symptoms", fallback_lists["symptoms"][:5])
    payload.setdefault("causes", fallback_lists["causes"][:5])
    payload.setdefault("spread", fallback_lists["spread"][:5])
    payload.setdefault("management", fallback_lists["management"][:5])
    payload.setdefault("prevention", fallback_lists["prevention"][:5])
    payload.setdefault("caution", "이 안내는 참고용이며, 피해가 빠르게 번지면 농업기술센터나 전문가에게 확인하세요.")
    for key in ("symptoms", "causes", "spread", "management", "prevention"):
        value = payload.get(key)
        payload[key] = [str(item).strip() for item in value[:5] if str(item).strip()] if isinstance(value, list) else []
    return _enforce_output_locale(payload, locale, "plant disease encyclopedia")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global registry
    registry = ModelRegistry()
    registry.load_all()
    yield
    registry = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(title="Plant Doctor segmentation/classifier + OpenAI inference", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return get_registry().status()


@app.post("/v1/localize")
def localize_ui(payload: dict[str, Any]) -> dict[str, Any]:
    locale = str(payload.get("locale") or "ko-KR").strip()[:35]
    raw_strings = payload.get("strings")
    if not isinstance(raw_strings, list):
        raise HTTPException(400, "strings must be a list")
    strings = list(dict.fromkeys(str(value)[:500] for value in raw_strings if str(value).strip()))[:40]
    translations: dict[str, str] = {}
    missing: list[str] = []
    for source in strings:
        cached = LOCALIZATION_CACHE.get((locale, source))
        if cached:
            translations[source] = cached
        else:
            missing.append(source)

    if missing and not locale.lower().startswith("ko"):
        prompt = f"""
Translate the following mobile app UI strings from Korean into locale {locale}.
Keep Plant Doctor, disease IDs, numbers, units, placeholders, punctuation, and line breaks intact.
Use short natural wording suitable for buttons and phone screens.
Return strict JSON only in this form:
{{"items":[{{"source":"exact original","translated":"translation"}}]}}

Strings:
{json.dumps(missing, ensure_ascii=False)}
""".strip()
        try:
            result = call_gpt_json(
                "You are a professional mobile-app localization engine. Return strict JSON only.",
                prompt,
            )
            items = result.get("items") if isinstance(result, dict) else None
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    source = str(item.get("source") or "")
                    translated = str(item.get("translated") or "").strip()
                    if source in missing and translated:
                        LOCALIZATION_CACHE[(locale, source)] = translated
                        translations[source] = translated
        except Exception as error:
            print(f"[localize] locale={locale} fallback: {error}")

    for source in strings:
        translations.setdefault(source, source)
    return {"locale": locale, "translations": translations}


@app.get("/v1/dictionary/{host}")
def dictionary_diseases(host: str, locale: str = "ko-KR") -> dict[str, Any]:
    normalized_host = normalize_label(host)
    if normalized_host not in HOST_ALIASES:
        raise HTTPException(404, "지원하지 않는 작물입니다.")
    rows = _dictionary_records(normalized_host)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        disease_id = _dictionary_row_disease(row)
        if disease_id:
            grouped.setdefault(disease_id, []).append(row)
    aliases = set(HOST_ALIASES.get(normalized_host, [normalized_host]))
    for classifier_label in get_registry().classifier_classes:
        if label_host(classifier_label) in aliases:
            grouped.setdefault(normalize_label(classifier_label), [])
    diseases = []
    for disease_id, disease_rows in grouped.items():
        categories = sorted(
            {str(category) for row in disease_rows for category in (row.get("categories") or [])}
        )
        diseases.append(
            {
                "disease_id": disease_id,
                "name": _dictionary_disease_name(disease_rows, disease_id),
                "evidence_count": len(disease_rows),
                "categories": categories,
                "has_image": any(
                    (CLASSIFIER_DATA_ROOT / split / disease_id).is_dir()
                    for split in ("test", "val", "train")
                ),
            }
        )
    diseases.sort(key=lambda item: (str(item["name"]), str(item["disease_id"])))
    localized_names = _localize_values(
        [str(item["name"]) for item in diseases], locale, f"{normalized_host} disease list"
    )
    for item, localized_name in zip(diseases, localized_names, strict=True):
        item["name"] = (
            humanize_label(str(item["disease_id"]))
            if not _is_korean_locale(locale) and _contains_hangul(localized_name)
            else localized_name
        )
    return {
        "host": normalized_host,
        "locale": locale,
        "source_record_count": len(_dictionary_host_rows(normalized_host)),
        "disease_evidence_count": len(rows),
        "disease_count": len(diseases),
        "diseases": diseases,
    }


@app.get("/v1/dictionary/{host}/{disease_id}")
def dictionary_detail(host: str, disease_id: str, locale: str = "ko-KR") -> dict[str, Any]:
    normalized_host = normalize_label(host)
    normalized_disease = normalize_label(disease_id)
    if normalized_host not in HOST_ALIASES:
        raise HTTPException(404, "지원하지 않는 작물입니다.")
    rows = _dictionary_records(normalized_host, normalized_disease)
    aliases = set(HOST_ALIASES.get(normalized_host, [normalized_host]))
    is_classifier_disease = any(
        normalize_label(label) == normalized_disease and label_host(label) in aliases
        for label in get_registry().classifier_classes
    )
    if not rows and not is_classifier_disease:
        raise HTTPException(404, "해당 작물의 질병 자료가 없습니다.")
    disease_name = _dictionary_disease_name(rows, normalized_disease)
    localized_disease_name = _localize_values(
        [disease_name], locale, f"{normalized_host} disease detail"
    )[0]
    if not _is_korean_locale(locale) and _contains_hangul(localized_disease_name):
        localized_disease_name = humanize_label(normalized_disease)
    evidence = _dictionary_evidence(rows)
    cache_key = (normalized_host, normalized_disease, locale)
    summary = DICTIONARY_SUMMARY_CACHE.get(cache_key)
    if summary is None and evidence:
        summary = _dictionary_summary(normalized_host, normalized_disease, localized_disease_name, evidence, locale)
        DICTIONARY_SUMMARY_CACHE[cache_key] = summary
    if summary is None:
        summary = {
            "headline": f"{localized_disease_name} 질병 항목입니다.",
            "overview": "분류 모델이 학습한 질병이지만 현재 연결된 RAG 설명 자료는 없습니다.",
            "symptoms": [],
            "causes": [],
            "spread": [],
            "management": [],
            "prevention": [],
            "caution": "설명 근거가 부족하므로 증상을 단정하지 말고 전문가에게 확인하세요.",
        }
        summary = _enforce_output_locale(summary, locale, "plant disease encyclopedia without RAG evidence")
    sources: list[dict[str, str]] = []
    seen_sources: set[tuple[str, str]] = set()
    for item in evidence:
        key = (item["source"], item["url"])
        if key in seen_sources:
            continue
        seen_sources.add(key)
        sources.append({"title": item["source"], "url": item["url"]})
    localized_source_titles = _localize_values(
        [item["title"] for item in sources[:8]], locale, "agricultural reference source titles"
    )
    for item, localized_title in zip(sources[:8], localized_source_titles, strict=True):
        item["title"] = localized_title
    return {
        "host": normalized_host,
        "disease_id": normalized_disease,
        "name": localized_disease_name,
        "evidence_count": len(rows),
        "summary": summary,
        "sources": sources[:8],
    }


@app.get("/v1/dictionary/{host}/{disease_id}/image")
def dictionary_image(host: str, disease_id: str) -> FileResponse:
    normalized_host = normalize_label(host)
    normalized_disease = normalize_label(disease_id)
    aliases = set(HOST_ALIASES.get(normalized_host, [normalized_host]))
    if normalized_host not in HOST_ALIASES or label_host(normalized_disease) not in aliases:
        raise HTTPException(404, "해당 작물의 질병 이미지가 없습니다.")
    candidates: list[Path] = []
    for split in ("test", "val", "train"):
        folder = CLASSIFIER_DATA_ROOT / split / normalized_disease
        if folder.is_dir():
            candidates.extend(
                path for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            )
        if candidates:
            break
    if not candidates:
        raise HTTPException(404, "해당 질병의 원본 이미지가 없습니다.")
    selected = max(candidates, key=lambda path: path.stat().st_size)
    media_type = "image/png" if selected.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(selected, media_type=media_type, filename=selected.name)


@app.post("/v1/segment", response_class=Response)
async def segment(image: UploadFile = File(...)) -> Response:
    data = await image.read()
    if not data:
        raise HTTPException(400, "Empty image.")

    rgb = open_rgb(data)
    mask, ratio = run_segmentation(rgb)
    png = mask_png(mask, rgb.size)

    return Response(
        content=png,
        media_type="image/png",
        headers={"X-Mask-Ratio": f"{ratio:.8f}", "X-Mask-Threshold": str(MASK_THRESHOLD)},
    )


@app.post("/v1/diagnose")
async def diagnose(
    image: UploadFile = File(...),
    host: str = Form(...),
    host_ko: str = Form(...),
    locale: str = Form("ko-KR"),
) -> JSONResponse:
    data = await image.read()
    if not data:
        raise HTTPException(400, "Empty image.")

    started = time.perf_counter()
    rgb = open_rgb(data)

    mask, ratio = run_segmentation(rgb)
    if ratio <= 0:
        raise HTTPException(422, "No lesion was detected in the captured image.")

    focused_crop, crop_box = build_focus_crop(rgb, mask)
    raw_label, raw_confidence, raw_predictions, probabilities = run_classifier(focused_crop)

    requested_host = normalize_label(host)
    if requested_host not in HOST_ALIASES:
        raise HTTPException(400, f"Unsupported host: {host}")

    resolved_hosts = resolve_classifier_hosts(requested_host)
    if not resolved_hosts:
        raise HTTPException(
            422,
            f"선택한 작물({host_ko})에 해당하는 분류 클래스가 현재 모델에 없습니다. "
            "다른 작물 병으로 바꾸지 않고 진단을 중단했습니다.",
        )

    host_info = {
        "host": requested_host,
        "host_ko": host_ko,
        "confidence": "user_selected",
        "reason": f"사용자가 진단 시작 전에 {host_ko} 작물을 선택했습니다.",
        "resolved_classifier_hosts": resolved_hosts,
    }
    host_locked_predictions, host_mass, host_constraint_available = constrain_predictions_to_host(
        probabilities, requested_host
    )

    if not host_constraint_available or not host_locked_predictions:
        raise HTTPException(
            422,
            f"선택한 작물({host_ko}) 범위에서 질병 후보를 만들 수 없습니다. "
            "교차 작물 진단은 수행하지 않았습니다.",
        )

    final_label = str(host_locked_predictions[0]["label"])
    final_confidence = float(host_locked_predictions[0]["probability"])
    selected_predictions = host_locked_predictions
    selection_strategy = "user_host_locked"
    use_host_locked = True

    rag_facts, rag_sources = load_rag_facts(
        final_label,
        host=requested_host,
        host_ko=host_ko,
        max_items=RAG_TOP_K,
    )
    localized_rag_titles = _localize_values(
        [str(item.get("source") or item.get("source_service") or "참고 출처") for item in rag_sources],
        locale,
        "diagnosis reference source titles",
    )
    for item, localized_title in zip(rag_sources, localized_rag_titles, strict=True):
        item["source"] = localized_title
    summary = summarize_diagnosis_with_gpt(
        full_image=rgb,
        focused_image=focused_crop,
        selected_label=final_label,
        selected_confidence=final_confidence,
        mask_ratio=ratio,
        raw_predictions=raw_predictions,
        host_info=host_info,
        host_locked_predictions=host_locked_predictions,
        rag_facts=rag_facts,
        locale=locale,
    )
    gpt_output = build_legacy_text(summary, final_label, final_confidence, ratio)
    elapsed_ms = (time.perf_counter() - started) * 1000

    return JSONResponse(
        {
            "disease_name": final_label,
            "display_name": str(summary.get("disease_name") or summary.get("disease_name_en") or humanize_label(final_label)),
            "display_name_en": str(summary.get("disease_name_en") or humanize_label(final_label)),
            "classifier_label": final_label,
            "confidence": final_confidence,
            "mask_ratio": ratio,
            "all_predictions": raw_predictions,
            "host_locked_predictions": host_locked_predictions,
            "host_detection": {
                "host": host_info.get("host", "unknown"),
                "host_ko": host_info.get("host_ko", host_ko),
                "confidence": host_info.get("confidence", "user_selected"),
                "reason": summary.get("host_reason") or host_info.get("reason", ""),
                "host_probability_mass": host_mass,
                "constraint_available": host_constraint_available,
                "used_host_lock": use_host_locked,
            },
            "selection_strategy": selection_strategy,
            "crop_box": crop_box,
            "rag_fact_count": len(rag_facts),
            "rag_sources": rag_sources,
            "active_rag": str(RAG_ROOT),
            "rag_vector_count": get_registry().rag_store.vector_count,
            "summary": summary,
            "gpt_output": gpt_output,
            "gemma_output": gpt_output,
            "elapsed_ms": round(elapsed_ms, 2),
            "runtime": "openai_gpt_host_locked_vector_rag_v6_5_1",
        }
    )

app.include_router(weather_router)
