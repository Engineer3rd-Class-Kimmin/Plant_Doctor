import argparse
import csv
import importlib.util
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from torchvision.transforms import InterpolationMode

SUPPORTED_HOST_ALIASES = {
    "rice": ("rice",), "soybean": ("soybean",), "corn": ("corn", "maize"),
    "apple": ("apple",), "grape": ("grape", "grapevine"), "peach": ("peach",),
    "plum": ("plum",), "cherry": ("cherry",), "citrus": ("citrus", "orange"),
    "potato": ("potato",), "tomato": ("tomato",), "cucumber": ("cucumber",),
    "eggplant": ("eggplant",), "pepper": ("bell_pepper", "pepper"),
    "napa_cabbage": ("napa_cabbage", "chinese_cabbage"), "cabbage": ("cabbage",),
    "broccoli": ("broccoli",), "garlic": ("garlic",), "ginger": ("ginger",),
    "carrot": ("carrot",), "lettuce": ("lettuce",), "strawberry": ("strawberry",),
    "squash": ("squash", "pumpkin"), "blueberry": ("blueberry",),
}


def class_matches_host(class_name: str, allowed_hosts) -> bool:
    if not allowed_hosts:
        return True
    return any(
        class_name == alias or class_name.startswith(alias + "_")
        for host in allowed_hosts
        for alias in SUPPORTED_HOST_ALIASES[host]
    )


class FilteredImageFolder(datasets.ImageFolder):
    def __init__(self, root, transform, allowed_hosts):
        self.allowed_hosts = allowed_hosts
        super().__init__(root, transform=transform)

    def find_classes(self, directory):
        classes, _ = super().find_classes(directory)
        classes = [c for c in classes if class_matches_host(c, self.allowed_hosts)]
        if not classes:
            raise RuntimeError(f"No selected crop classes found in {directory}")
        return classes, {name: index for index, name in enumerate(classes)}


def load_augmentation_module(path: Path):
    spec = importlib.util.spec_from_file_location("seg_video_aug", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load augmentation module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_transforms(image_size: int):
    train_transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size), interpolation=InterpolationMode.BICUBIC),
            transforms.ToTensor(),
        ]
    )

    eval_transform = transforms.Compose(
        [
            transforms.Resize(
                int(image_size * 1.08),
                interpolation=InterpolationMode.BICUBIC,
            ),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    return train_transform, eval_transform


def compute_class_weights(dataset, num_classes: int):
    counts = Counter(dataset.targets)
    total = len(dataset)

    weights = []
    for class_id in range(num_classes):
        count = max(1, counts.get(class_id, 1))
        # 완전 역빈도보다 완만한 sqrt 역빈도
        weight = math.sqrt(total / (num_classes * count))
        weights.append(weight)

    weights = torch.tensor(weights, dtype=torch.float32)
    weights = weights / weights.mean()
    return weights, counts


def topk_correct(logits, targets, topk=(1, 3)):
    max_k = min(max(topk), logits.shape[1])
    _, pred = logits.topk(max_k, dim=1, largest=True, sorted=True)
    pred = pred.t()
    correct = pred.eq(targets.view(1, -1).expand_as(pred))

    result = {}
    for k in topk:
        k = min(k, logits.shape[1])
        result[k] = int(correct[:k].reshape(-1).float().sum().item())
    return result


def train_one_epoch(
    model,
    loader,
    optimizer,
    criterion,
    device,
    scaler,
    use_bf16,
    grad_clip,
    augmentation,
):
    model.train()

    running_loss = 0.0
    total = 0
    correct1 = 0
    correct3 = 0

    for images, targets in loader:
        images = images.to(
            device,
            non_blocking=True,
            memory_format=torch.channels_last,
        )
        targets = targets.to(device, non_blocking=True)

        dummy_masks = torch.zeros(
            images.shape[0], images.shape[2], images.shape[3],
            dtype=torch.long, device=device,
        )
        images, _ = augmentation.gpu_augment(images, dummy_masks)
        images = augmentation.normalize(images)

        optimizer.zero_grad(set_to_none=True)

        with autocast(
            device_type="cuda",
            dtype=torch.bfloat16 if use_bf16 else torch.float16,
            enabled=device.type == "cuda",
        ):
            logits = model(images)
            loss = criterion(logits, targets)

        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()

        batch_size = targets.size(0)
        running_loss += loss.item() * batch_size
        total += batch_size

        correct = topk_correct(logits.detach(), targets, topk=(1, 3))
        correct1 += correct[1]
        correct3 += correct[3]

    return {
        "loss": running_loss / max(1, total),
        "top1": correct1 / max(1, total),
        "top3": correct3 / max(1, total),
    }


@torch.inference_mode()
def evaluate(
    model,
    loader,
    criterion,
    device,
    use_bf16,
):
    model.eval()

    running_loss = 0.0
    total = 0
    correct1 = 0
    correct3 = 0

    class_total = Counter()
    class_correct = Counter()

    for images, targets in loader:
        images = images.to(
            device,
            non_blocking=True,
            memory_format=torch.channels_last,
        )
        targets = targets.to(device, non_blocking=True)

        with autocast(
            device_type="cuda",
            dtype=torch.bfloat16 if use_bf16 else torch.float16,
            enabled=device.type == "cuda",
        ):
            logits = model(images)
            loss = criterion(logits, targets)

        batch_size = targets.size(0)
        running_loss += loss.item() * batch_size
        total += batch_size

        correct = topk_correct(logits, targets, topk=(1, 3))
        correct1 += correct[1]
        correct3 += correct[3]

        predictions = logits.argmax(dim=1)
        for target, prediction in zip(
            targets.cpu().tolist(),
            predictions.cpu().tolist(),
        ):
            class_total[target] += 1
            if target == prediction:
                class_correct[target] += 1

    recalls = []
    for class_id, count in class_total.items():
        recalls.append(class_correct[class_id] / max(1, count))

    return {
        "loss": running_loss / max(1, total),
        "top1": correct1 / max(1, total),
        "top3": correct3 / max(1, total),
        "macro_recall": float(np.mean(recalls)) if recalls else 0.0,
    }


def save_checkpoint(
    output_dir,
    model,
    optimizer,
    scheduler,
    epoch,
    metrics,
    classes,
    args,
):
    best_dir = output_dir / "best"
    best_dir.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "metrics": metrics,
            "classes": classes,
            "model_name": "convnext_small",
            "image_size": args.image_size,
        },
        best_dir / "checkpoint.pt",
    )

    with (best_dir / "classes.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "classes": classes,
                "class_to_id": {
                    name: idx for idx, name in enumerate(classes)
                },
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    with (best_dir / "config.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            vars(args),
            file,
            ensure_ascii=False,
            indent=2,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        default=r".\data\plantseg_lesion_classifier_v1",
    )
    parser.add_argument(
        "--output-dir",
        default=r".\runs\lesion_classifier_convnext_tiny_v1",
    )
    parser.add_argument("--image-size", type=int, default=384)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=0.05)
    parser.add_argument("--label-smoothing", type=float, default=0.08)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pretrained-checkpoint", required=True)
    parser.add_argument("--augmentation-script", required=True)
    parser.add_argument(
        "--allowed-hosts", nargs="+", choices=sorted(SUPPORTED_HOST_ALIASES), default=None,
    )
    args = parser.parse_args()

    seed_everything(args.seed)

    data_root = Path(args.data_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    train_dir = data_root / "train"
    val_dir = data_root / "val"

    if not train_dir.exists():
        raise FileNotFoundError(f"train 폴더가 없습니다: {train_dir}")
    if not val_dir.exists():
        raise FileNotFoundError(f"val 폴더가 없습니다: {val_dir}")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    use_bf16 = (
        device.type == "cuda"
        and torch.cuda.is_bf16_supported()
    )

    print(f"device={device}")
    if device.type == "cuda":
        print(f"gpu={torch.cuda.get_device_name(0)}")
    print(f"bf16={use_bf16}")

    train_transform, eval_transform = build_transforms(args.image_size)

    train_dataset = FilteredImageFolder(
        train_dir,
        transform=train_transform,
        allowed_hosts=args.allowed_hosts,
    )
    val_dataset = FilteredImageFolder(
        val_dir,
        transform=eval_transform,
        allowed_hosts=args.allowed_hosts,
    )

    if train_dataset.classes != val_dataset.classes:
        raise RuntimeError(
            "train과 val 클래스 구성이 다릅니다."
        )

    classes = train_dataset.classes
    num_classes = len(classes)

    print(f"classes={num_classes}")
    print(f"train_images={len(train_dataset)}")
    print(f"val_images={len(val_dataset)}")

    class_weights, class_counts = compute_class_weights(
        train_dataset,
        num_classes,
    )
    class_weights = class_weights.to(device)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.workers > 0,
        prefetch_factor=2 if args.workers > 0 else None,
        drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.workers > 0,
        prefetch_factor=2 if args.workers > 0 else None,
    )

    print("loading local ImageNet pretrained ConvNeXt-Small...")
    pretrained = torch.load(args.pretrained_checkpoint, map_location="cpu", weights_only=False)
    model = models.convnext_small(weights=None)
    model.load_state_dict(pretrained["model_state_dict"])

    in_features = model.classifier[2].in_features
    model.classifier[2] = nn.Linear(in_features, num_classes)

    model = model.to(device)
    model = model.to(memory_format=torch.channels_last)
    augmentation = load_augmentation_module(Path(args.augmentation_script).resolve())

    criterion = nn.CrossEntropyLoss(
        weight=class_weights,
        label_smoothing=args.label_smoothing,
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=args.lr * 0.02,
    )

    scaler = None
    if device.type == "cuda" and not use_bf16:
        scaler = GradScaler("cuda")

    history_path = output_dir / "history.csv"
    with history_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "epoch",
                "lr",
                "train_loss",
                "train_top1",
                "train_top3",
                "val_loss",
                "val_top1",
                "val_top3",
                "val_macro_recall",
                "seconds",
            ]
        )

    best_score = -1.0
    best_epoch = 0
    no_improvement = 0

    for epoch in range(1, args.epochs + 1):
        start = time.time()
        current_lr = optimizer.param_groups[0]["lr"]

        train_metrics = train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
            scaler=scaler,
            use_bf16=use_bf16,
            grad_clip=args.grad_clip,
            augmentation=augmentation,
        )

        val_metrics = evaluate(
            model=model,
            loader=val_loader,
            criterion=criterion,
            device=device,
            use_bf16=use_bf16,
        )

        scheduler.step()
        seconds = time.time() - start

        # 정확도와 희귀 클래스 성능을 함께 반영
        score = (
            0.70 * val_metrics["top1"]
            + 0.30 * val_metrics["macro_recall"]
        )

        print(
            f"[{epoch:02d}/{args.epochs}] "
            f"lr={current_lr:.2e} "
            f"train loss={train_metrics['loss']:.4f} "
            f"top1={train_metrics['top1']:.4f} "
            f"top3={train_metrics['top3']:.4f} | "
            f"val loss={val_metrics['loss']:.4f} "
            f"top1={val_metrics['top1']:.4f} "
            f"top3={val_metrics['top3']:.4f} "
            f"macroR={val_metrics['macro_recall']:.4f} "
            f"score={score:.4f} "
            f"time={seconds:.1f}s"
        )

        with history_path.open(
            "a",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    epoch,
                    current_lr,
                    train_metrics["loss"],
                    train_metrics["top1"],
                    train_metrics["top3"],
                    val_metrics["loss"],
                    val_metrics["top1"],
                    val_metrics["top3"],
                    val_metrics["macro_recall"],
                    seconds,
                ]
            )

        epoch_metrics = {
            "epoch": epoch,
            "learning_rate": current_lr,
            "seconds": seconds,
            "train": train_metrics,
            "validation": val_metrics,
            "score": score,
        }
        epoch_dir = output_dir / "epoch_metrics"
        epoch_dir.mkdir(parents=True, exist_ok=True)
        (epoch_dir / f"epoch_{epoch:03d}.json").write_text(
            json.dumps(epoch_metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "metrics": epoch_metrics,
                "classes": classes,
                "model_name": "convnext_small",
                "image_size": args.image_size,
            },
            output_dir / "last_checkpoint.pt",
        )

        if score > best_score:
            best_score = score
            best_epoch = epoch
            no_improvement = 0

            save_checkpoint(
                output_dir=output_dir,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                epoch=epoch,
                metrics={
                    **val_metrics,
                    "score": score,
                },
                classes=classes,
                args=args,
            )

            print(
                f"  best saved: epoch={epoch}, "
                f"score={score:.4f}"
            )
        else:
            no_improvement += 1
            print(
                f"  no improvement: "
                f"{no_improvement}/{args.patience}"
            )

        if no_improvement >= args.patience:
            print(
                f"early stopping: "
                f"best_epoch={best_epoch}, "
                f"best_score={best_score:.4f}"
            )
            break

    summary = {
        "best_epoch": best_epoch,
        "best_score": best_score,
        "classes": num_classes,
        "train_images": len(train_dataset),
        "val_images": len(val_dataset),
        "output_dir": str(output_dir),
    }

    with (output_dir / "summary.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("=" * 100)
    for key, value in summary.items():
        print(f"{key}={value}")
    print("=" * 100)


if __name__ == "__main__":
    main()
