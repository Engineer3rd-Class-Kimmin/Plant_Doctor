from __future__ import annotations

import argparse
import atexit
import csv
import gc
import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision.transforms import functional as TF
from transformers import SegformerForSemanticSegmentation

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
TILT = (-80, -60, -40, -20, 20, 40, 60, 80)
ROLL = TILT
GEOM = ("x", "y", "z", "xy", "yz", "xz", "xyz")
DISTANCE_SCALE = (0.58, 0.70, 0.82, 0.94, 1.06, 1.18, 1.30)
LIGHT = (
    "illumination",
    "backlight",
    "dark",
    "shadow",
    "backlight_shadow",
    "dark_shadow",
)
SUPPORTED_HOST_ALIASES = {
    "rice": ("rice",),
    "soybean": ("soybean",),
    "corn": ("corn", "maize"),
    "apple": ("apple",),
    "grape": ("grape", "grapevine"),
    "peach": ("peach",),
    "plum": ("plum",),
    "cherry": ("cherry",),
    "citrus": ("citrus", "orange"),
    "potato": ("potato",),
    "tomato": ("tomato",),
    "cucumber": ("cucumber",),
    "eggplant": ("eggplant",),
    "pepper": ("bell_pepper", "bell pepper", "pepper"),
    "napa_cabbage": ("napa_cabbage", "napa cabbage", "chinese_cabbage"),
    "cabbage": ("cabbage",),
    "broccoli": ("broccoli",),
    "garlic": ("garlic",),
    "ginger": ("ginger",),
    "carrot": ("carrot",),
    "lettuce": ("lettuce",),
    "strawberry": ("strawberry",),
    "squash": ("squash", "pumpkin"),
    "blueberry": ("blueberry",),
}

@dataclass(frozen=True)
class Sample:
    image: Path
    mask: Path
    source: str


def cleanup_runtime_caches(output_dir: Path) -> None:
    report = {
        "python_gc_objects": gc.collect(),
        "cuda_available": torch.cuda.is_available(),
        "removed_paths": [],
    }
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except RuntimeError:
            pass

    script_cache = Path(__file__).resolve().parent / "__pycache__"
    if script_cache.exists():
        warnings = []
        for cached_file in script_cache.glob(f"{Path(__file__).stem}.*.pyc"):
            try:
                cached_file.unlink()
                report["removed_paths"].append(str(cached_file))
            except OSError as exc:
                warnings.append(str(exc))
        if warnings:
            report["cache_cleanup_warning"] = warnings

    try:
        (output_dir / "cache_cleanup_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

def parse_args():
    p = argparse.ArgumentParser(
        "SegFormer field augmentation v5.1: realistic augmentation-only fine-tuning"
    )
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--plantseg-root", type=Path, required=True)
    p.add_argument("--plantwild-root", type=Path, required=True)
    p.add_argument("--failure-root", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--image-size", type=int, default=512)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--lr", type=float, default=7e-7)
    p.add_argument("--weight-decay", type=float, default=1e-2)
    p.add_argument("--patience", type=int, default=2)
    p.add_argument("--seed", type=int, default=20260730)
    p.add_argument(
        "--allowed-hosts",
        nargs="+",
        choices=sorted(SUPPORTED_HOST_ALIASES),
        default=None,
    )
    p.add_argument("--plantseg-weight", type=float, default=0.82)
    p.add_argument("--plantwild-weight", type=float, default=0.18)
    p.add_argument("--failure-weight", type=float, default=0.0)
    p.add_argument("--samples-per-epoch-multiplier", type=float, default=1.0)
    p.add_argument("--plantseg-val-ratio", type=float, default=0.15)
    p.add_argument("--aug-val-max-plantseg", type=int, default=400)
    p.add_argument("--aug-val-max-healthy", type=int, default=400)
    p.add_argument("--fp-penalty", type=float, default=0.35)
    p.add_argument("--recall-floor", type=float, default=0.80)
    p.add_argument("--compile", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--channels-last", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--tf32", action=argparse.BooleanOptionalAction, default=True)
    return p.parse_args()

def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def file_map(folder: Path):
    return {
        p.stem.lower(): p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    }

def make_pairs(image_dir: Path, mask_dir: Path, source: str):
    images, masks = file_map(image_dir), file_map(mask_dir)
    keys = sorted(set(images) & set(masks))
    if not keys:
        raise RuntimeError(f"paired data missing: {image_dir} / {mask_dir}")
    return [Sample(images[k], masks[k], source) for k in keys]

def stable_fraction(sample: Sample, seed: int):
    raw = hashlib.sha1(
        f"{seed}:{sample.image}".encode("utf-8", errors="ignore")
    ).digest()[:8]
    return int.from_bytes(raw, "big") / 2**64

def load_plantseg(args, split: str):
    explicit_images = args.plantseg_root / "images" / split
    explicit_masks = args.plantseg_root / "annotations" / split
    if split == "val" and explicit_images.exists() and explicit_masks.exists():
        return make_pairs(explicit_images, explicit_masks, "plantseg")

    all_samples = make_pairs(
        args.plantseg_root / "images" / "train",
        args.plantseg_root / "annotations" / "train",
        "plantseg",
    )
    return [
        s
        for s in all_samples
        if (stable_fraction(s, args.seed) >= args.plantseg_val_ratio)
        == (split == "train")
    ]

def load_optional(root: Path | None, split: str, source: str):
    if root is None:
        return []
    image_dir = root / "images" / split
    mask_dir = next(
        (
            path
            for path in (
                root / "annotations" / split,
                root / "masks" / split,
            )
            if path.exists()
        ),
        None,
    )
    if not image_dir.exists() or mask_dir is None:
        print(
            f"[warning] missing source={source} split={split} "
            f"image={image_dir} mask={mask_dir}"
        )
        return []
    result = make_pairs(image_dir, mask_dir, source)
    print(f"[loaded] {source} {split}: {len(result)} pairs")
    return result

def load_samples(args, split: str):
    samples = (
        load_plantseg(args, split)
        + load_optional(args.plantwild_root, split, "plantwild")
        + load_optional(args.failure_root, split, "failure")
    )
    if not args.allowed_hosts:
        return samples

    aliases = {
        host: tuple(alias.lower() for alias in SUPPORTED_HOST_ALIASES[host])
        for host in args.allowed_hosts
    }

    def matches(sample: Sample) -> bool:
        name = sample.image.stem.lower().replace("-", "_")
        padded = f"_{name}_"
        for host_aliases in aliases.values():
            for alias in host_aliases:
                normalized = alias.replace(" ", "_")
                if padded.startswith(f"_{normalized}_") or f"_{normalized}_" in padded:
                    return True
        return False

    filtered = [sample for sample in samples if matches(sample)]
    print(
        f"[host-filter] split={split} allowed={list(args.allowed_hosts)} "
        f"before={len(samples)} after={len(filtered)}"
    )
    return filtered

class SegDataset(Dataset):
    def __init__(self, samples: Sequence[Sample], size: int):
        self.samples = list(samples)
        self.size = size

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        sample = self.samples[index]
        with Image.open(sample.image) as f:
            image = ImageOps.exif_transpose(f).convert("RGB")
        with Image.open(sample.mask) as f:
            mask = ImageOps.exif_transpose(f).convert("L")

        if image.size != mask.size:
            if image.size == (mask.height, mask.width):
                mask = mask.transpose(Image.Transpose.TRANSPOSE)
            else:
                raise RuntimeError(
                    f"size mismatch: {sample.image} {image.size} {mask.size}"
                )

        image = TF.resize(
            image,
            [self.size, self.size],
            interpolation=TF.InterpolationMode.BILINEAR,
            antialias=True,
        )
        mask = TF.resize(
            mask,
            [self.size, self.size],
            interpolation=TF.InterpolationMode.NEAREST,
        )
        return (
            TF.to_tensor(image),
            (torch.from_numpy(np.asarray(mask, dtype=np.uint8).copy()) > 0).long(),
            sample.source,
        )

def build_sampler(samples, args):
    configured = {
        "plantseg": args.plantseg_weight,
        "plantwild": args.plantwild_weight,
        "failure": args.failure_weight,
    }
    counts = {
        key: sum(sample.source == key for sample in samples)
        for key in configured
    }
    active = {
        key: weight
        for key, weight in configured.items()
        if counts[key] > 0 and weight > 0
    }
    total_weight = sum(active.values())
    ratios = {key: value / total_weight for key, value in active.items()}
    weights = [ratios[s.source] / counts[s.source] for s in samples]
    num_samples = max(
        1,
        int(round(len(samples) * args.samples_per_epoch_multiplier)),
    )
    print(
        "source counts=", counts,
        "sampler ratios=", ratios,
        "samples_per_epoch=", num_samples,
    )
    if counts["plantwild"] == 0:
        raise RuntimeError(
            "PlantWildHealthy was not loaded. Healthy data is mandatory."
        )
    return WeightedRandomSampler(weights, num_samples, replacement=True)

def homography_np(width, height, x_deg, y_deg, z_deg, distance_scale=0.94):
    w, h = float(width), float(height)
    corners = np.array(
        [
            [-w / 2, -h / 2, 0],
            [w / 2, -h / 2, 0],
            [w / 2, h / 2, 0],
            [-w / 2, h / 2, 0],
        ],
        dtype=np.float64,
    )
    rx, ry, rz = np.deg2rad([x_deg, y_deg, z_deg])
    rx_m = np.array(
        [[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]]
    )
    ry_m = np.array(
        [[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]]
    )
    rz_m = np.array(
        [[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]]
    )
    rotated = corners @ (rz_m @ ry_m @ rx_m).T
    focal = max(w, h) * 1.35
    distance = focal * 2.25
    depth = rotated[:, 2] + distance
    projected = np.c_[
        focal * rotated[:, 0] / depth,
        focal * rotated[:, 1] / depth,
    ]
    projected -= projected.mean(0)
    span = np.ptp(projected, axis=0)
    projected *= min(
        w * 0.96 / max(span[0], 1e-6),
        h * 0.96 / max(span[1], 1e-6),
    ) * distance_scale
    projected += np.array([w / 2, h / 2])
    source = np.array(
        [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(source, projected.astype(np.float32))

def random_homographies(batch, height, width, device):
    matrices = []
    for _ in range(batch):
        mode = random.choice(GEOM)
        x_deg = random.choice(TILT) if "x" in mode else 0
        y_deg = random.choice(TILT) if "y" in mode else 0
        z_deg = random.choice(ROLL) if "z" in mode else 0
        distance_scale = random.choice(DISTANCE_SCALE)
        matrices.append(
            homography_np(
                width,
                height,
                x_deg,
                y_deg,
                z_deg,
                distance_scale,
            )
        )
    return torch.tensor(
        np.stack(matrices),
        device=device,
        dtype=torch.float32,
    )

def warp_batch(tensor, homography, out_h, out_w, mode):
    batch = tensor.shape[0]
    inverse = torch.linalg.inv(homography)
    yy, xx = torch.meshgrid(
        torch.arange(out_h, device=tensor.device, dtype=torch.float32),
        torch.arange(out_w, device=tensor.device, dtype=torch.float32),
        indexing="ij",
    )
    destination = torch.stack((xx, yy, torch.ones_like(xx)), -1)
    destination = destination.reshape(1, -1, 3).expand(batch, -1, -1)
    source = destination @ inverse.transpose(1, 2)
    sx = source[..., 0] / source[..., 2].clamp_min(1e-6)
    sy = source[..., 1] / source[..., 2].clamp_min(1e-6)
    gx = 2 * sx / max(out_w - 1, 1) - 1
    gy = 2 * sy / max(out_h - 1, 1) - 1
    grid = torch.stack((gx, gy), -1).reshape(batch, out_h, out_w, 2)
    return F.grid_sample(
        tensor,
        grid,
        mode=mode,
        padding_mode="reflection" if mode == "bilinear" else "zeros",
        align_corners=True,
    )

def apply_realistic_light(image, kind: str):
    _, _, h, w = image.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, h, device=image.device),
        torch.linspace(-1, 1, w, device=image.device),
        indexing="ij",
    )

    if kind == "illumination":
        gain = random.uniform(0.78, 1.28)
        gamma = random.uniform(0.84, 1.18)
        return ((image.clamp(1e-5, 1) ** gamma) * gain).clamp(0, 1)

    if kind == "dark":
        gain = random.uniform(0.46, 0.74)
        gamma = random.uniform(1.08, 1.42)
        noise = torch.randn_like(image) * random.uniform(0.0, 0.012)
        return ((image.clamp(1e-5, 1) ** gamma) * gain + noise).clamp(0, 1)

    if kind == "backlight":
        cx, cy = random.choice(
            ((-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9), (0.9, 0.9), (0, -1), (0, 1))
        )
        radius = torch.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        glow = torch.exp(-(radius**2) / random.uniform(0.28, 0.62))[None, None]
        return (
            image * random.uniform(0.68, 0.88)
            + glow * random.uniform(0.22, 0.52)
        ).clamp(0, 1)

    if kind == "shadow":
        angle = random.uniform(0, 2 * math.pi)
        offset = random.uniform(-0.45, 0.45)
        width = random.uniform(0.16, 0.42)
        soft = random.uniform(0.08, 0.20)
        distance = xx * math.cos(angle) + yy * math.sin(angle) - offset
        band = (
            torch.sigmoid((distance + width) / soft)
            - torch.sigmoid((distance - width) / soft)
        )
        return (image * (1 - band[None, None] * random.uniform(0.22, 0.52))).clamp(0, 1)

    if kind == "backlight_shadow":
        return apply_realistic_light(
            apply_realistic_light(image, "backlight"),
            "shadow",
        )

    if kind == "dark_shadow":
        return apply_realistic_light(
            apply_realistic_light(image, "dark"),
            "shadow",
        )

    raise ValueError(f"unknown lighting kind: {kind}")

def light_batch(images):
    output = images.clone()
    kinds = []
    for i in range(images.shape[0]):
        kind = random.choice(LIGHT)
        output[i : i + 1] = apply_realistic_light(output[i : i + 1], kind)
        kinds.append(kind)
    return output, kinds

def gpu_augment(images, masks):
    batch, _, height, width = images.shape
    homography = random_homographies(batch, height, width, images.device)
    images = warp_batch(images, homography, height, width, "bilinear")
    masks = warp_batch(
        masks[:, None].float(),
        homography,
        height,
        width,
        "nearest",
    )[:, 0].long()
    images, _ = light_batch(images)
    if random.random() < 0.30:
        images = (
            images
            + torch.randn_like(images) * random.uniform(0.004, 0.025)
        ).clamp(0, 1)
    if random.random() < 0.18:
        kernel = random.choice((3, 5))
        images = F.avg_pool2d(
            images,
            kernel_size=kernel,
            stride=1,
            padding=kernel // 2,
        )
    horizontal_flip = torch.rand(batch, device=images.device) < 0.5
    if horizontal_flip.any():
        images[horizontal_flip] = torch.flip(images[horizontal_flip], [-1])
        masks[horizontal_flip] = torch.flip(masks[horizontal_flip], [-1])
    return images, masks

def normalize(images):
    mean = torch.tensor(
        [0.485, 0.456, 0.406],
        device=images.device,
    )[None, :, None, None]
    std = torch.tensor(
        [0.229, 0.224, 0.225],
        device=images.device,
    )[None, :, None, None]
    return (images - mean) / std

def focal_tversky_loss(logits, target, alpha=0.30, beta=0.70, gamma=1.33):
    probability = logits.softmax(1)[:, 1]
    target_float = target.float()
    dims = (1, 2)
    tp = (probability * target_float).sum(dims)
    fp = (probability * (1 - target_float)).sum(dims)
    fn = ((1 - probability) * target_float).sum(dims)
    tversky = (tp + 1.0) / (tp + alpha * fp + beta * fn + 1.0)
    return ((1 - tversky) ** gamma).mean()

def segmentation_loss(logits, target):
    ce = F.cross_entropy(
        logits,
        target,
        weight=torch.tensor([0.65, 1.35], device=logits.device),
    )
    focal_tversky = focal_tversky_loss(logits, target)
    return 0.55 * ce + 0.45 * focal_tversky

def add_counts(counts, prediction, target):
    prediction = prediction.bool()
    target = target.bool()
    counts["tp"] += int((prediction & target).sum())
    counts["fp"] += int((prediction & ~target).sum())
    counts["fn"] += int((~prediction & target).sum())
    counts["tn"] += int((~prediction & ~target).sum())

def metrics(counts):
    tp, fp, fn, tn = (
        counts["tp"],
        counts["fp"],
        counts["fn"],
        counts["tn"],
    )
    eps = 1e-8
    return {
        **counts,
        "dice": (2 * tp + eps) / (2 * tp + fp + fn + eps),
        "iou": (tp + eps) / (tp + fp + fn + eps),
        "precision": (tp + eps) / (tp + fp + eps),
        "recall": (tp + eps) / (tp + fn + eps),
        "fp_rate": (fp + eps) / (fp + tn + eps),
    }

def run_model(model, images, target_size):
    logits = model(pixel_values=normalize(images)).logits
    return F.interpolate(
        logits,
        size=target_size,
        mode="bilinear",
        align_corners=False,
    )

def evaluate_original(model, loader, device, channels_last):
    model.eval()
    counts = {
        key: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for key in ("plantseg", "plantwild", "failure")
    }
    with torch.inference_mode(), torch.autocast(
        "cuda",
        dtype=torch.float16,
        enabled=device.type == "cuda",
    ):
        for images, masks, sources in loader:
            images = images.to(device, non_blocking=True)
            masks = masks.to(device, non_blocking=True)
            if channels_last:
                images = images.contiguous(memory_format=torch.channels_last)
            prediction = run_model(model, images, masks.shape[-2:]).argmax(1)
            for i, source in enumerate(sources):
                add_counts(counts[source], prediction[i], masks[i])
    return {key: metrics(value) for key, value in counts.items()}

def limited_indices(sources, max_plantseg, max_healthy, seed):
    rng = random.Random(seed)
    plantseg = [i for i, s in enumerate(sources) if s.source == "plantseg"]
    healthy = [i for i, s in enumerate(sources) if s.source != "plantseg"]
    rng.shuffle(plantseg)
    rng.shuffle(healthy)
    return set(plantseg[:max_plantseg] + healthy[:max_healthy])

def evaluate_augmented(model, samples, dataset, args, device, epoch_seed):
    chosen = limited_indices(
        samples,
        args.aug_val_max_plantseg,
        args.aug_val_max_healthy,
        epoch_seed,
    )
    subset = torch.utils.data.Subset(dataset, sorted(chosen))
    loader_kwargs = dict(
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=True,
        persistent_workers=args.workers > 0,
    )
    if args.workers:
        loader_kwargs["prefetch_factor"] = 4
    loader = DataLoader(subset, **loader_kwargs)

    counts = {
        key: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for key in ("plantseg", "plantwild", "failure")
    }
    seed_all(epoch_seed)
    model.eval()
    with torch.inference_mode(), torch.autocast(
        "cuda",
        dtype=torch.float16,
        enabled=device.type == "cuda",
    ):
        for images, masks, sources in loader:
            images = images.to(device, non_blocking=True)
            masks = masks.to(device, non_blocking=True)
            images, masks = gpu_augment(images, masks)
            if args.channels_last:
                images = images.contiguous(memory_format=torch.channels_last)
            prediction = run_model(model, images, masks.shape[-2:]).argmax(1)
            for i, source in enumerate(sources):
                add_counts(counts[source], prediction[i], masks[i])
    return {key: metrics(value) for key, value in counts.items()}

def healthy_fp(metrics_by_source):
    values = []
    for key in ("plantwild", "failure"):
        item = metrics_by_source[key]
        if sum(item[q] for q in ("tp", "fp", "fn", "tn")):
            values.append(item["fp_rate"])
    return float(np.mean(values)) if values else 0.0

def composite_score(original, augmented, args):
    orig_plant = original["plantseg"]
    aug_plant = augmented["plantseg"]
    orig_fp = healthy_fp(original)
    aug_fp = healthy_fp(augmented)

    recall_penalty = (
        max(0.0, args.recall_floor - orig_plant["recall"])
        + max(0.0, args.recall_floor - aug_plant["recall"])
    )
    return (
        0.35 * orig_plant["dice"]
        + 0.65 * aug_plant["dice"]
        - args.fp_penalty * (0.35 * orig_fp + 0.65 * aug_fp)
        - 0.25 * recall_penalty
    )

def main():
    args = parse_args()
    seed_all(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atexit.register(cleanup_runtime_caches, args.output_dir)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required.")

    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = args.tf32
    torch.backends.cudnn.allow_tf32 = args.tf32
    torch.set_float32_matmul_precision("high")
    device = torch.device("cuda")
    print("device=", torch.cuda.get_device_name(0))

    train_samples = load_samples(args, "train")
    val_samples = load_samples(args, "val")
    train_dataset = SegDataset(train_samples, args.image_size)
    val_dataset = SegDataset(val_samples, args.image_size)
    sampler = build_sampler(train_samples, args)

    samples_per_epoch = max(
        1,
        int(round(len(train_samples) * args.samples_per_epoch_multiplier)),
    )
    augmentation_plan = {
        "model": str(args.checkpoint),
        "task": "binary_lesion_segmentation",
        "object_mask_used": False,
        "allowed_hosts": args.allowed_hosts,
        "unique_train_images": len(train_samples),
        "train_source_counts": {
            source: sum(sample.source == source for sample in train_samples)
            for source in ("plantseg", "plantwild", "failure")
        },
        "epochs_requested": args.epochs,
        "samples_per_epoch": samples_per_epoch,
        "maximum_augmented_presentations": samples_per_epoch * args.epochs,
        "rotation_axes": list(GEOM),
        "rotation_degrees": list(TILT),
        "distance_scales": list(DISTANCE_SCALE),
        "lighting_modes": list(LIGHT),
        "core_discrete_combinations": 728 * len(DISTANCE_SCALE) * len(LIGHT),
        "evaluation": {
            "validation_original_each_epoch": True,
            "validation_augmented_each_epoch": True,
            "official_test_reserved_for_post_training": True,
        },
    }
    (args.output_dir / "training_plan.json").write_text(
        json.dumps(augmentation_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(augmentation_plan, ensure_ascii=False, indent=2))

    common = dict(
        batch_size=args.batch_size,
        num_workers=args.workers,
        pin_memory=True,
        persistent_workers=args.workers > 0,
    )
    if args.workers:
        common["prefetch_factor"] = 2

    train_loader = DataLoader(
        train_dataset,
        sampler=sampler,
        drop_last=True,
        **common,
    )
    val_loader = DataLoader(
        val_dataset,
        shuffle=False,
        drop_last=False,
        **common,
    )

    model = SegformerForSemanticSegmentation.from_pretrained(
        args.checkpoint,
        num_labels=2,
        id2label={0: "background", 1: "lesion"},
        label2id={"background": 0, "lesion": 1},
        ignore_mismatched_sizes=True,
    ).to(device)

    if args.channels_last:
        model = model.to(memory_format=torch.channels_last)

    if args.compile and hasattr(torch, "compile"):
        try:
            model = torch.compile(model, mode="default")
            print("[speed] torch.compile enabled")
        except Exception as exc:
            print("[warning] torch.compile disabled:", exc)

    optimizer = AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
        fused=True,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(1, len(train_loader) * args.epochs),
    )

    best_score = -1e9
    stale = 0
    best_dir = args.output_dir / "best"
    fields = [
        "epoch",
        "train_loss",
        "score",
        "original_dice",
        "original_iou",
        "original_recall",
        "original_healthy_fp",
        "augmented_dice",
        "augmented_iou",
        "augmented_recall",
        "augmented_healthy_fp",
        "lr",
        "seconds",
    ]

    with (args.output_dir / "history.csv").open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for epoch in range(1, args.epochs + 1):
            model.train()
            running_loss = 0.0
            start_time = time.time()

            for step, (images, masks, _) in enumerate(train_loader, 1):
                images = images.to(device, non_blocking=True)
                masks = masks.to(device, non_blocking=True)
                images, masks = gpu_augment(images, masks)

                if args.channels_last:
                    images = images.contiguous(memory_format=torch.channels_last)

                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=torch.float16):
                    logits = run_model(model, images, masks.shape[-2:])
                    loss = segmentation_loss(logits, masks)

                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()

                running_loss += loss.detach().item()
                if step % 50 == 0 or step == len(train_loader):
                    print(
                        f"epoch {epoch}/{args.epochs} "
                        f"step {step}/{len(train_loader)} "
                        f"loss={running_loss / step:.5f}"
                    )

            original = evaluate_original(
                model,
                val_loader,
                device,
                args.channels_last,
            )
            augmented = evaluate_augmented(
                model,
                val_samples,
                val_dataset,
                args,
                device,
                args.seed + epoch * 1009,
            )
            score = composite_score(original, augmented, args)

            original_plant = original["plantseg"]
            augmented_plant = augmented["plantseg"]
            row = {
                "epoch": epoch,
                "train_loss": running_loss / max(1, len(train_loader)),
                "score": score,
                "original_dice": original_plant["dice"],
                "original_iou": original_plant["iou"],
                "original_recall": original_plant["recall"],
                "original_healthy_fp": healthy_fp(original),
                "augmented_dice": augmented_plant["dice"],
                "augmented_iou": augmented_plant["iou"],
                "augmented_recall": augmented_plant["recall"],
                "augmented_healthy_fp": healthy_fp(augmented),
                "lr": optimizer.param_groups[0]["lr"],
                "seconds": time.time() - start_time,
            }
            writer.writerow(row)
            f.flush()
            print(json.dumps(row, ensure_ascii=False, indent=2))

            raw_model = model._orig_mod if hasattr(model, "_orig_mod") else model
            torch.save(
                {
                    "epoch": epoch,
                    "model": raw_model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "scaler": scaler.state_dict(),
                    "best_score": best_score,
                },
                args.output_dir / "last_training_state.pt",
            )

            if score > best_score:
                best_score = score
                stale = 0
                best_dir.mkdir(parents=True, exist_ok=True)
                raw_model.save_pretrained(best_dir)
                (best_dir / "best_metrics.json").write_text(
                    json.dumps(
                        {
                            "epoch": epoch,
                            "score": score,
                            "original": original,
                            "augmented": augmented,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                performance_table = "\n".join(
                    [
                        "# SegFormer-B3 validation performance",
                        "",
                        "| Evaluation | Dice | IoU | Recall | Healthy FP rate |",
                        "|---|---:|---:|---:|---:|",
                        (
                            f"| Original | {original_plant['dice']:.4f} | "
                            f"{original_plant['iou']:.4f} | "
                            f"{original_plant['recall']:.4f} | "
                            f"{healthy_fp(original):.4f} |"
                        ),
                        (
                            f"| Augmented | {augmented_plant['dice']:.4f} | "
                            f"{augmented_plant['iou']:.4f} | "
                            f"{augmented_plant['recall']:.4f} | "
                            f"{healthy_fp(augmented):.4f} |"
                        ),
                        "",
                        f"Best epoch: {epoch}",
                        f"Composite score: {score:.6f}",
                    ]
                )
                (best_dir / "performance_table.md").write_text(
                    performance_table,
                    encoding="utf-8",
                )
                print(f"[BEST] epoch={epoch} score={score:.6f}")
            else:
                stale += 1
                print(f"no improvement {stale}/{args.patience}")
                if stale >= args.patience:
                    print("[EARLY STOP]")
                    break

    print("done best=", best_dir)

if __name__ == "__main__":
    main()
