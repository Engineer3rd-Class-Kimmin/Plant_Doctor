from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision.transforms import functional as TF
from transformers import SegformerForSemanticSegmentation

def load_train_module(path: Path):
    spec = importlib.util.spec_from_file_location("field_aug_v51_train", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load trainer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def parse_args():
    p = argparse.ArgumentParser(
        "Random field robustness benchmark with threshold/min-area tuning"
    )
    p.add_argument("--trainer-script", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--plantseg-root", type=Path, required=True)
    p.add_argument("--plantwild-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--image-size", type=int, default=512)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--plantseg-samples", type=int, default=200)
    p.add_argument("--plantwild-samples", type=int, default=200)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--seed", type=int, default=20260730)
    p.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=[0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
    )
    p.add_argument(
        "--min-areas",
        type=int,
        nargs="+",
        default=[0, 16, 32, 64, 128],
    )
    return p.parse_args()

def load_test_pairs(v51, root: Path, source: str):
    image_dir = root / "images" / "test"
    mask_dir = root / "annotations" / "test"
    if not image_dir.exists() or not mask_dir.exists():
        if source == "plantwild":
            image_dir = root / "images" / "val"
            mask_dir = root / "annotations" / "val"
    return v51.make_pairs(image_dir, mask_dir, source)

def read_sample(sample, size):
    with Image.open(sample.image) as f:
        image = ImageOps.exif_transpose(f).convert("RGB")
    with Image.open(sample.mask) as f:
        mask = ImageOps.exif_transpose(f).convert("L")
    image = TF.resize(
        image,
        [size, size],
        interpolation=TF.InterpolationMode.BILINEAR,
        antialias=True,
    )
    mask = TF.resize(
        mask,
        [size, size],
        interpolation=TF.InterpolationMode.NEAREST,
    )
    return (
        TF.to_tensor(image),
        (torch.from_numpy(np.asarray(mask, dtype=np.uint8).copy()) > 0).long(),
    )

def remove_small_components(binary: np.ndarray, minimum_area: int):
    if minimum_area <= 0:
        return binary
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary.astype(np.uint8),
        connectivity=8,
    )
    output = np.zeros_like(binary, dtype=np.uint8)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= minimum_area:
            output[labels == label] = 1
    return output

def add_counts(counts, pred, target):
    pred = pred.astype(bool)
    target = target.astype(bool)
    counts["tp"] += int(np.logical_and(pred, target).sum())
    counts["fp"] += int(np.logical_and(pred, ~target).sum())
    counts["fn"] += int(np.logical_and(~pred, target).sum())
    counts["tn"] += int(np.logical_and(~pred, ~target).sum())

def metrics(counts):
    tp, fp, fn, tn = (
        counts["tp"],
        counts["fp"],
        counts["fn"],
        counts["tn"],
    )
    eps = 1e-8
    return {
        "dice": (2 * tp + eps) / (2 * tp + fp + fn + eps),
        "iou": (tp + eps) / (tp + fp + fn + eps),
        "precision": (tp + eps) / (tp + fp + eps),
        "recall": (tp + eps) / (tp + fn + eps),
        "fp_rate": (fp + eps) / (fp + tn + eps),
    }

def select_samples(samples, count, rng):
    samples = list(samples)
    rng.shuffle(samples)
    return samples[: min(count, len(samples))]

def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    v51 = load_train_module(args.trainer_script)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required.")

    rng = random.Random(args.seed)
    plantseg = select_samples(
        load_test_pairs(v51, args.plantseg_root, "plantseg"),
        args.plantseg_samples,
        rng,
    )
    plantwild = select_samples(
        load_test_pairs(v51, args.plantwild_root, "plantwild"),
        args.plantwild_samples,
        rng,
    )
    samples = plantseg + plantwild

    total_inferences = len(samples) * args.repeats
    print(
        f"plantseg={len(plantseg)} plantwild={len(plantwild)} "
        f"repeats={args.repeats} total_inferences={total_inferences}"
    )

    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.set_float32_matmul_precision("high")

    model = SegformerForSemanticSegmentation.from_pretrained(
        args.model
    ).to(device).eval().to(memory_format=torch.channels_last)

    records = []
    for repeat in range(args.repeats):
        repeat_rng = random.Random(args.seed + repeat * 10007)
        ordered = list(samples)
        repeat_rng.shuffle(ordered)

        for start in range(0, len(ordered), args.batch_size):
            chunk = ordered[start : start + args.batch_size]
            loaded = [read_sample(sample, args.image_size) for sample in chunk]
            images = torch.stack([item[0] for item in loaded]).to(
                device,
                non_blocking=True,
            )
            masks = torch.stack([item[1] for item in loaded]).to(
                device,
                non_blocking=True,
            )

            random.seed(args.seed + repeat * 10007 + start)

            batch_count, _, height, width = images.shape
            matrices = []
            geom_tags = []
            light_tags = []
            for _ in range(batch_count):
                geom = random.choice(v51.GEOM)
                x_deg = random.choice(v51.TILT) if "x" in geom else 0
                y_deg = random.choice(v51.TILT) if "y" in geom else 0
                z_deg = random.choice(v51.ROLL) if "z" in geom else 0
                distance_scale = random.choice(v51.DISTANCE_SCALE)
                matrices.append(
                    v51.homography_np(
                        width,
                        height,
                        x_deg,
                        y_deg,
                        z_deg,
                        distance_scale,
                    )
                )
                geom_tags.append(
                    (geom, x_deg, y_deg, z_deg, distance_scale)
                )
                light_tags.append(random.choice(v51.LIGHT))

            homography = torch.tensor(
                np.stack(matrices),
                device=device,
                dtype=torch.float32,
            )
            images = v51.warp_batch(
                images,
                homography,
                height,
                width,
                "bilinear",
            )
            masks = v51.warp_batch(
                masks[:, None].float(),
                homography,
                height,
                width,
                "nearest",
            )[:, 0].long()

            for item_index, light_kind in enumerate(light_tags):
                images[item_index : item_index + 1] = v51.apply_realistic_light(
                    images[item_index : item_index + 1],
                    light_kind,
                )

            horizontal_flip = torch.rand(batch_count, device=device) < 0.5
            if horizontal_flip.any():
                images[horizontal_flip] = torch.flip(
                    images[horizontal_flip],
                    [-1],
                )
                masks[horizontal_flip] = torch.flip(
                    masks[horizontal_flip],
                    [-1],
                )

            images = images.contiguous(memory_format=torch.channels_last)

            with torch.inference_mode(), torch.autocast(
                "cuda",
                dtype=torch.float16,
            ):
                logits = model(pixel_values=v51.normalize(images)).logits
                logits = F.interpolate(
                    logits,
                    size=masks.shape[-2:],
                    mode="bilinear",
                    align_corners=False,
                )
                probability = logits.softmax(1)[:, 1]

            probability_np = probability.float().cpu().numpy()
            masks_np = masks.cpu().numpy().astype(np.uint8)

            for i, sample in enumerate(chunk):
                # Recreate deterministic augmentation tags for reporting only.
                # The exact random sequence is encoded by repeat and item order.
                geom, x_deg, y_deg, z_deg, distance_scale = geom_tags[i]
                records.append(
                    {
                        "repeat": repeat,
                        "source": sample.source,
                        "image": str(sample.image),
                        "geom": geom,
                        "x_deg": x_deg,
                        "y_deg": y_deg,
                        "z_deg": z_deg,
                        "distance_scale": distance_scale,
                        "light": light_tags[i],
                        "probability": probability_np[i],
                        "target": masks_np[i],
                    }
                )
            print(
                f"repeat {repeat + 1}/{args.repeats} "
                f"{min(start + len(chunk), len(ordered))}/{len(ordered)}"
            )

    summary_rows = []
    best = None
    for threshold in args.thresholds:
        for minimum_area in args.min_areas:
            by_source = {
                "plantseg": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
                "plantwild": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
            }
            for record in records:
                prediction = (record["probability"] >= threshold).astype(np.uint8)
                prediction = remove_small_components(prediction, minimum_area)
                add_counts(
                    by_source[record["source"]],
                    prediction,
                    record["target"],
                )

            plant = metrics(by_source["plantseg"])
            healthy = metrics(by_source["plantwild"])
            score = (
                plant["dice"]
                - 0.35 * healthy["fp_rate"]
                - 0.25 * max(0.0, 0.80 - plant["recall"])
            )
            row = {
                "threshold": threshold,
                "min_area": minimum_area,
                "score": score,
                "plantseg_dice": plant["dice"],
                "plantseg_iou": plant["iou"],
                "plantseg_precision": plant["precision"],
                "plantseg_recall": plant["recall"],
                "plantwild_fp_rate": healthy["fp_rate"],
            }
            summary_rows.append(row)
            if best is None or score > best["score"]:
                best = row

    summary_csv = args.output_dir / "threshold_min_area_grid.csv"
    with summary_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    # Condition-specific metrics using the selected operating point.
    condition_rows = []
    grouped = defaultdict(
        lambda: {
            "plantseg": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
            "plantwild": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
            "count": 0,
        }
    )
    for record in records:
        prediction = (
            record["probability"] >= best["threshold"]
        ).astype(np.uint8)
        prediction = remove_small_components(
            prediction,
            best["min_area"],
        )
        key = record["light"]
        add_counts(
            grouped[key][record["source"]],
            prediction,
            record["target"],
        )
        grouped[key]["count"] += 1

    for light, values in sorted(grouped.items()):
        plant = metrics(values["plantseg"])
        healthy = metrics(values["plantwild"])
        condition_rows.append(
            {
                "light": light,
                "inferences": values["count"],
                "plantseg_dice": plant["dice"],
                "plantseg_iou": plant["iou"],
                "plantseg_precision": plant["precision"],
                "plantseg_recall": plant["recall"],
                "plantwild_fp_rate": healthy["fp_rate"],
            }
        )

    condition_csv = args.output_dir / "condition_summary.csv"
    with condition_csv.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(condition_rows[0]),
        )
        writer.writeheader()
        writer.writerows(condition_rows)

    recommended = {
        "model": str(args.model),
        "plantseg_samples": len(plantseg),
        "plantwild_samples": len(plantwild),
        "repeats": args.repeats,
        "total_inferences": total_inferences,
        "recommended_threshold": best["threshold"],
        "recommended_min_area": best["min_area"],
        "recommended_metrics": best,
        "grid_csv": str(summary_csv),
        "condition_csv": str(condition_csv),
    }
    (args.output_dir / "recommended_postprocess.json").write_text(
        json.dumps(recommended, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(recommended, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
