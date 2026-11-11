"""LoRA 索引假数据：模型文件 + models.json。

边界样本对应真实状态：

* 索引有记录但磁盘文件缺失 —— 卡片显示但无法加载，不能整页报错
* 同名不同目录 —— 列表靠 id 区分，不能靠名字去重
* 无预览图 —— 占位图分支
* 无触发词 —— 标签区为空
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from . import context
from .context import FIXTURE_TAG, Manifest
from .images import make_card

TITLE = "LoRA 索引"

VARIANTS = {
    "basic": "5 个模型，分 3 个文件夹",
    "edge": "basic + 4 个边界条目（文件缺失/同名/无预览/无触发词）",
    "stress": "basic + 40 个模型，验证列表滚动与筛选",
    "empty": "空索引，验证空状态",
}

# (相对 models/loras 的路径, 大小 KB, 分类, 文件夹, 触发词, 标签)
_LORA_FILES: List[tuple] = [
    ("fixture-detail-tweaker.safetensors", 144, "detail", "",
     ["detail", "sharp"], ["细节", "通用"]),
    ("fixture-film-grain.safetensors", 96, "style", "",
     ["film grain", "analog"], ["风格", "胶片"]),
    ("风格/fixture-anime-lineart.safetensors", 208, "style", "风格",
     ["anime lineart", "cel shade"], ["风格", "二次元"]),
    ("风格/fixture-watercolor.safetensors", 176, "style", "风格",
     ["watercolor", "wet wash"], ["风格", "水彩"]),
    ("人物/fixture-portrait-light.safetensors", 256, "character", "人物",
     ["soft portrait light"], ["人物", "光效"]),
]

# 边界条目：file_exists=False 的只写索引、不写文件
_EDGE_ENTRIES: List[Dict] = [
    {
        "relative": "缺失/fixture-missing-file.safetensors",
        "size_kb": 512,
        "category": "style",
        "folder": "缺失",
        "trigger_words": ["missing"],
        "tags": ["边界", "文件缺失"],
        "file_exists": False,
        "preview": True,
    },
    {
        "relative": "风格/fixture-detail-tweaker.safetensors",
        "size_kb": 144,
        "category": "detail",
        "folder": "风格",
        "trigger_words": ["detail"],
        "tags": ["边界", "同名"],
        "file_exists": True,
        "preview": True,
    },
    {
        "relative": "风格/fixture-no-preview.safetensors",
        "size_kb": 64,
        "category": "style",
        "folder": "风格",
        "trigger_words": ["no preview"],
        "tags": ["边界", "无预览"],
        "file_exists": True,
        "preview": False,
    },
    {
        "relative": "人物/fixture-no-trigger.safetensors",
        "size_kb": 88,
        "category": "character",
        "folder": "人物",
        "trigger_words": [],
        "tags": ["边界", "无触发词"],
        "file_exists": True,
        "preview": True,
    },
]


def _timestamp(index: int) -> str:
    base = datetime(2026, 9, 20, 10, 0, 0)
    return (base + timedelta(days=index)).isoformat(timespec="seconds")


def _write_placeholder(target: Path, size_kb: int) -> None:
    header = b"\x00" * 8 + b'{"__metadata__":{"format":"pt"}}'
    target.write_bytes(header + b"\x00" * max(0, size_kb * 1024 - len(header)))


def _ensure_model_file(relative: str, size_kb: int, manifest: Manifest) -> Path:
    """在假 ComfyUI 的 models/loras 下创建占位模型文件。"""
    target = context.comfyui_models_dir() / "loras" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        _write_placeholder(target, size_kb)
    manifest.record(target)
    return target


def _preview_for(index: int, name: str, manifest: Manifest) -> Path:
    palette = ("violet", "mint", "dawn", "ocean", "forest")[index % 5]
    target = context.lora_dir() / "preview" / f"fixture-lora-{index:03d}.png"
    make_card(target, (512, 512), palette, name, FIXTURE_TAG)
    manifest.record(target)
    return target


def _model_entry(index: int, relative: str, size_kb: int, category: str,
                 folder: str, trigger_words: List[str], tags: List[str],
                 manifest: Manifest, *, file_exists: bool = True,
                 preview: bool = True) -> Dict:
    stem = Path(relative).stem
    if file_exists:
        model_file = _ensure_model_file(relative, size_kb, manifest)
        path = str(model_file)
    else:
        path = str(context.comfyui_models_dir() / "loras" / relative)

    preview_path = ""
    if preview:
        preview_path = str(_preview_for(index, stem, manifest))

    return {
        "id": str(uuid.uuid4()),
        "name": stem,
        "size_kb": float(size_kb),
        "path": path,
        "folder": folder,
        "file_extension": ".safetensors",
        "created_at": _timestamp(index),
        "modified_at": _timestamp(index),
        "category": category,
        "preview_url": preview_path,
        "trigger_words": list(trigger_words),
        "tags": list(tags) + [FIXTURE_TAG.strip("[]")],
        "default_weight": "0.8",
        "recommended_sampler": "euler",
        "civitai_url": "",
        "notes": f"{FIXTURE_TAG} 假数据，可安全删除。",
        "file_hash": f"fixture{index:03d}" + "0" * 57,
        "is_local": True,
        "preview_blurred": False,
        "pull_status": 0,
        "imported_preview_paths": [preview_path] if preview_path else [],
    }


def _basic_models(manifest: Manifest) -> List[Dict]:
    return [
        _model_entry(index, *item, manifest)
        for index, item in enumerate(_LORA_FILES, start=1)
    ]


def _edge_models(manifest: Manifest, offset: int) -> List[Dict]:
    models = []
    for order, item in enumerate(_EDGE_ENTRIES, start=1):
        index = offset + order
        models.append(_model_entry(
            index,
            item["relative"],
            item["size_kb"],
            item["category"],
            item["folder"],
            item["trigger_words"],
            item["tags"],
            manifest,
            file_exists=item["file_exists"],
            preview=item["preview"],
        ))
    return models


def _stress_models(manifest: Manifest, offset: int, count: int = 40) -> List[Dict]:
    categories = ["style", "character", "detail", "concept"]
    models = []
    for order in range(1, count + 1):
        index = offset + order
        relative = f"批量/组{(order - 1) // 10 + 1}/fixture-batch-{order:03d}.safetensors"
        models.append(_model_entry(
            index, relative, 64 + order, categories[order % len(categories)],
            f"批量/组{(order - 1) // 10 + 1}",
            [f"batch {order:03d}"], ["批量"],
            manifest,
        ))
    return models


def seed(manifest: Manifest, variant: str = "basic") -> Dict:
    """写入 lora_data/models.json。"""
    if variant not in VARIANTS:
        raise ValueError(f"未知 LoRA 变体: {variant}")

    context.reset_domain(manifest, "lora", prune_root=context.lora_dir() / "preview")

    models: List[Dict] = []
    if variant != "empty":
        models = _basic_models(manifest)
        if variant == "edge":
            models += _edge_models(manifest, len(models))
        elif variant == "stress":
            models += _stress_models(manifest, len(models))

    payload = {
        "version": "1.0.0",
        "updated_at": context.now_iso(),
        "count": len(models),
        "models": models,
    }
    models_file = context.lora_dir() / "models.json"
    context.write_json(models_file, payload, manifest)

    created = [path for path in (context.lora_dir() / "preview").glob("*.png")]
    created.append(models_file)
    manifest.set_domain_files("lora", created)

    return {"variant": variant, "models": len(models)}
