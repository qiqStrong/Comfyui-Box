"""提示词库假数据：分类树、配方、预览图、元数据统计。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from . import context
from .context import FIXTURE_TAG, Manifest
from .images import make_card

# 分类：(id, 名称, 图标, 父级 id, 排序)
FIXTURE_CATEGORIES: List[tuple] = [
    ("fixture-landscape", f"{FIXTURE_TAG} 风景", "image", None, 10),
    ("fixture-landscape-night", f"{FIXTURE_TAG} 夜景", "file-text", "fixture-landscape", 11),
    ("fixture-portrait", f"{FIXTURE_TAG} 人像", "user", None, 12),
    ("fixture-product", f"{FIXTURE_TAG} 产品", "sparkles", None, 13),
]

# 配方：(名称, 分类, 调色板, 正向提示词, 标签, 是否收藏, 使用次数, 资产类型)
_RECIPES = [
    ("晨光山谷配方", "fixture-landscape", "dawn",
     "vast mountain valley at sunrise, volumetric fog, 35mm, ultra detailed",
     ["风景", "日出"], True, 12, "image"),
    ("长曝海面配方", "fixture-landscape", "ocean",
     "long exposure seascape, silk smooth water, minimal horizon, ND1000",
     ["风景", "长曝"], False, 4, "image"),
    ("沙丘极简配方", "fixture-landscape", "sand",
     "desert dunes, clean curves, high key minimalism, soft shadow",
     ["风景", "极简"], False, 2, "image"),
    ("霓虹街角配方", "fixture-landscape-night", "violet",
     "neon street corner at night, rain reflections, cyberpunk palette, cinematic",
     ["夜景", "霓虹"], True, 21, "image"),
    ("柔光人像配方", "fixture-portrait", "dawn",
     "portrait with soft butterfly lighting, 85mm, natural skin texture",
     ["人像", "柔光"], True, 33, "image"),
    ("侧逆光人像配方", "fixture-portrait", "violet",
     "rim lit portrait, cool backlight, editorial mood, shallow dof",
     ["人像", "侧逆光"], False, 7, "image"),
    ("金属材质球配方", "fixture-product", "steel",
     "metal material sphere, studio HDRI lighting, product render, 4k",
     ["产品", "材质"], False, 1, "image"),
    ("短视频推进配方", "fixture-landscape", "ocean",
     "coastal cliff aerial, slow camera push in, golden hour, cinematic motion",
     ["视频", "航拍"], False, 5, "video"),
]


def _category_id(index: int) -> str:
    return f"fixture-category-{index:02d}"


def _preview_name(index: int) -> str:
    return f"fixture-prompt-{index:02d}.png"


def _timestamp(index: int) -> str:
    base = datetime(2026, 10, 5, 14, 0, 0)
    return (base + timedelta(hours=5 * index)).isoformat(timespec="seconds")


def _build_category(cid: str, name: str, icon: str, parent_id, order: int) -> Dict:
    return {
        "id": cid,
        "name": name,
        "icon": icon,
        "parent_id": parent_id,
        "sort_order": order,
        "is_system": False,
    }


def _build_prompt(index: int, recipe: tuple, manifest: Manifest) -> Dict:
    name, category, palette, positive, tags, favorite, usage, asset_type = recipe
    preview_file = context.prompt_images_dir() / _preview_name(index)
    make_card(preview_file, (768, 768), palette, name, f"{FIXTURE_TAG} 提示词")
    manifest.record(preview_file)

    is_video = asset_type == "video"
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "positive_prompt": positive,
        "negative_prompt": "blurry, low quality, watermark, deformed",
        "preview_image": f"local://images/{preview_file.name}",
        "remark": f"{FIXTURE_TAG} 由假数据生成，可安全删除。",
        "category_id": category,
        "tags": tags,
        "is_favorite": favorite,
        "usage_count": usage,
        "created_at": _timestamp(index),
        "updated_at": _timestamp(index),
        "model": "fixture-sdxl-base.safetensors",
        "sampler": "euler",
        "scheduler": "normal",
        "steps": 24 + index,
        "cfg": 7.5,
        "seed": 156680208700286 + index,
        "width": 1024,
        "height": 768 if is_video else 1024,
        "duration": 2.0 if is_video else None,
        "asset_type": asset_type,
        "source_asset_id": f"fixture-asset-{index:02d}",
        "workflow_name": "portrait-basic" if index % 2 else "landscape-wide",
        "workflow_path": "",
    }


def seed(manifest: Manifest) -> Dict:
    """写入提示词库三份 JSON 与预览图。"""
    system_categories = [
        {"id": "all", "name": "全部", "icon": "layers", "parent_id": None,
         "sort_order": 0, "is_system": True},
        {"id": "favorites", "name": "收藏", "icon": "star", "parent_id": None,
         "sort_order": 1, "is_system": True},
    ]
    custom = [_build_category(*item) for item in FIXTURE_CATEGORIES]
    categories = system_categories + custom

    prompts = [
        _build_prompt(index, recipe, manifest)
        for index, recipe in enumerate(_RECIPES, start=1)
    ]

    context.write_json(
        context.prompt_dir() / "categories.json",
        {"version": "1.0", "categories": categories},
        manifest,
    )
    context.write_json(
        context.prompt_dir() / "prompts.json",
        {"version": "1.0", "prompts": prompts},
        manifest,
    )

    timestamp = context.now_iso()
    metadata = {
        "version": "1.0.0",
        "created_at": timestamp,
        "updated_at": timestamp,
        "stats": {
            "total_prompts": len(prompts),
            "total_categories": len(categories),
            "total_usage": sum(item["usage_count"] for item in prompts),
        },
        "settings": {
            "default_category_id": "all",
            "auto_backup": True,
            "backup_interval_days": 7,
        },
    }
    context.write_json(context.prompt_dir() / "metadata.json", metadata, manifest)

    return {"prompts": len(prompts), "categories": len(categories)}
