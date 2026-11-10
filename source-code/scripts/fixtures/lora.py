"""LoRA 索引假数据：模型文件 + models.json。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from . import context
from .context import FIXTURE_TAG, Manifest
from .images import make_card

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


def _timestamp(index: int) -> str:
    base = datetime(2026, 9, 20, 10, 0, 0)
    return (base + timedelta(days=index)).isoformat(timespec="seconds")


def _ensure_model_file(relative: str, size_kb: int, manifest: Manifest) -> Path:
    """在假 ComfyUI 的 models/loras 下创建占位模型文件。"""
    target = context.fake_comfyui_dir() / "models" / "loras" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        header = b"\x00" * 8 + b'{"__metadata__":{"format":"pt"}}'
        target.write_bytes(header + b"\x00" * max(0, size_kb * 1024 - len(header)))
    manifest.record(target)
    return target


def _preview_for(index: int, name: str, manifest: Manifest) -> Path:
    palette = ("violet", "mint", "dawn", "ocean", "forest")[index % 5]
    target = context.lora_dir() / "preview" / f"fixture-lora-{index:02d}.png"
    make_card(target, (512, 512), palette, name, FIXTURE_TAG)
    manifest.record(target)
    return target


def _build_model(index: int, item: tuple, manifest: Manifest) -> Dict:
    relative, size_kb, category, folder, trigger_words, tags = item
    model_file = _ensure_model_file(relative, size_kb, manifest)
    stem = Path(relative).stem
    preview = _preview_for(index, stem, manifest)
    return {
        "id": str(uuid.uuid4()),
        "name": stem,
        "size_kb": float(size_kb),
        "path": str(model_file),
        "folder": folder,
        "file_extension": ".safetensors",
        "created_at": _timestamp(index),
        "modified_at": _timestamp(index),
        "category": category,
        "preview_url": str(preview),
        "trigger_words": trigger_words,
        "tags": list(tags) + [FIXTURE_TAG.strip("[]")],
        "default_weight": "0.8",
        "recommended_sampler": "euler",
        "civitai_url": "",
        "notes": f"{FIXTURE_TAG} 假数据，可安全删除。",
        "file_hash": f"fixture{index:02d}" + "0" * 58,
        "is_local": True,
        "preview_blurred": False,
        "pull_status": 0,
        "imported_preview_paths": [str(preview)],
    }


def seed(manifest: Manifest) -> Dict:
    """写入 lora_data/models.json。"""
    models = [
        _build_model(index, item, manifest)
        for index, item in enumerate(_LORA_FILES, start=1)
    ]
    payload = {
        "version": "1.0.0",
        "updated_at": context.now_iso(),
        "count": len(models),
        "models": models,
    }
    context.write_json(context.lora_dir() / "models.json", payload, manifest)
    return {"models": len(models)}
