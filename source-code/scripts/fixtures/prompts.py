"""提示词库假数据：分类树、配方、预览图、元数据统计。

边界样本对应界面上的真实状态：

* 空正向提示词 —— 卡片摘要为空，列表不能塌
* 超长提示词 —— 卡片截断与详情面板滚动
* 无预览图 —— 占位图分支
* 深层分类 —— 分类树三层缩进
* 只有负向提示词 —— 正向摘要为空但配方可用
* 视频无时长 —— 时长字段缺失时的展示
* 孤儿分类 —— 分类 id 指向不存在的节点，树不应报错
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List

from . import context
from .context import FIXTURE_TAG, Manifest
from .images import make_card

TITLE = "提示词库"

VARIANTS = {
    "basic": "8 条配方 + 4 个分类（含一层嵌套）",
    "edge": "basic + 7 条边界配方（空/超长/无预览/深层分类/孤儿分类）",
    "stress": "basic + 80 条配方，验证列表滚动与搜索",
    "empty": "空库，验证空状态",
}

# 分类：(id, 名称, 图标, 父级 id, 排序)
FIXTURE_CATEGORIES: List[tuple] = [
    ("fixture-landscape", f"{FIXTURE_TAG} 风景", "image", None, 10),
    ("fixture-landscape-night", f"{FIXTURE_TAG} 夜景", "file-text", "fixture-landscape", 11),
    ("fixture-portrait", f"{FIXTURE_TAG} 人像", "user", None, 12),
    ("fixture-product", f"{FIXTURE_TAG} 产品", "sparkles", None, 13),
]

# 第三层分类，只在 edge / stress 变体里出现
_DEEP_CATEGORY = (
    "fixture-landscape-night-cyber", f"{FIXTURE_TAG} 赛博夜景",
    "sparkles", "fixture-landscape-night", 14,
)

_DEFAULT_NEGATIVE = "blurry, low quality, watermark, deformed"

# 配方：(名称, 分类, 调色板, 正向, 标签, 收藏, 使用次数, 资产类型)
_RECIPES: List[tuple] = [
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

# 边界配方：缺省字段由 _spec 补齐
_EDGE_SPECS: List[Dict] = [
    {
        "name": "空正向提示词",
        "category": "fixture-product",
        "palette": "steel",
        "positive": "",
        "tags": ["边界", "空值"],
        "usage": 0,
    },
    {
        "name": "超长提示词",
        "category": "fixture-landscape",
        "palette": "forest",
        "positive": "extremely detailed landscape, " * 60,
        "tags": ["边界", "超长"],
        "usage": 3,
    },
    {
        "name": "无预览图",
        "category": "fixture-product",
        "palette": "mint",
        "positive": "minimal product render, seamless backdrop, 3 point light",
        "tags": ["边界", "无预览"],
        "usage": 6,
        "preview": False,
    },
    {
        "name": "深层分类配方",
        "category": "fixture-landscape-night-cyber",
        "palette": "violet",
        "positive": "cyberpunk alley, holographic signage, wet asphalt reflections",
        "tags": ["边界", "深层分类"],
        "usage": 9,
    },
    {
        "name": "只有负向提示词",
        "category": "fixture-portrait",
        "palette": "ember",
        "positive": "",
        "negative": "blurry, extra fingers, bad anatomy, lowres, watermark",
        "tags": ["边界", "仅负向"],
        "usage": 2,
    },
    {
        "name": "视频无时长",
        "category": "fixture-landscape",
        "palette": "ocean",
        "positive": "slow dolly across a frozen lake, winter light",
        "tags": ["边界", "视频"],
        "usage": 4,
        "asset_type": "video",
        "duration": None,
    },
    {
        "name": "孤儿分类配方",
        "category": "fixture-missing-category",
        "palette": "sand",
        "positive": "orphan category sample, should not break the tree",
        "tags": ["边界", "孤儿分类"],
        "usage": 1,
    },
]


def _spec(name: str, category: str, palette: str, positive: str,
          tags=(), favorite: bool = False, usage: int = 0,
          asset_type: str = "image", **extra) -> Dict:
    """把配方元组展开成带缺省值的字典。"""
    spec = {
        "name": name,
        "category": category,
        "palette": palette,
        "positive": positive,
        "negative": _DEFAULT_NEGATIVE,
        "tags": tags,
        "favorite": favorite,
        "usage": usage,
        "asset_type": asset_type,
        "duration": 2.0 if asset_type == "video" else None,
        "preview": True,
        "workflow": "portrait-basic",
    }
    spec.update(extra)
    return spec


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


def _build_prompt(index: int, spec: Dict, manifest: Manifest) -> Dict:
    preview_name = f"fixture-prompt-{index:03d}.png"
    preview_url = ""
    if spec["preview"]:
        preview_file = context.prompt_images_dir() / preview_name
        make_card(preview_file, (768, 768), spec["palette"], spec["name"],
                  f"{FIXTURE_TAG} 提示词")
        manifest.record(preview_file)
        preview_url = f"local://images/{preview_name}"

    is_video = spec["asset_type"] == "video"
    return {
        "id": str(uuid.uuid4()),
        "name": spec["name"],
        "positive_prompt": spec["positive"],
        "negative_prompt": spec["negative"],
        "preview_image": preview_url,
        "remark": f"{FIXTURE_TAG} 由假数据生成，可安全删除。",
        "category_id": spec["category"],
        "tags": spec["tags"],
        "is_favorite": spec["favorite"],
        "usage_count": spec["usage"],
        "created_at": _timestamp(index),
        "updated_at": _timestamp(index),
        "model": "fixture-sdxl-base.safetensors",
        "sampler": "euler",
        "scheduler": "normal",
        "steps": 24 + index % 12,
        "cfg": 7.5,
        "seed": 156680208700286 + index,
        "width": 1024,
        "height": 768 if is_video else 1024,
        "duration": spec["duration"],
        "asset_type": spec["asset_type"],
        "source_asset_id": f"fixture-asset-{index:03d}",
        "workflow_name": spec["workflow"],
        "workflow_path": "",
    }


def _base_specs() -> List[Dict]:
    return [
        _spec(*recipe[:8])
        for recipe in _RECIPES
    ]


def _stress_specs(count: int = 80) -> List[Dict]:
    palettes = ["dawn", "forest", "ocean", "ember", "violet", "sand", "steel", "mint"]
    categories = [item[0] for item in FIXTURE_CATEGORIES]
    return [
        _spec(
            f"批量配方 {index:03d}",
            categories[index % len(categories)],
            palettes[index % len(palettes)],
            f"batch prompt {index:03d}, consistent style, varied subject",
            ["批量", f"组{index % 5}"],
            index % 7 == 0,
            index % 40,
            "image",
        )
        for index in range(1, count + 1)
    ]


def seed(manifest: Manifest, variant: str = "basic") -> Dict:
    """写入提示词库三份 JSON 与预览图。"""
    if variant not in VARIANTS:
        raise ValueError(f"未知提示词库变体: {variant}")

    context.reset_domain(manifest, "prompt", prune_root=context.prompt_images_dir())

    system_categories = [
        {"id": "all", "name": "全部", "icon": "layers", "parent_id": None,
         "sort_order": 0, "is_system": True},
        {"id": "favorites", "name": "收藏", "icon": "star", "parent_id": None,
         "sort_order": 1, "is_system": True},
    ]
    custom = [_build_category(*item) for item in FIXTURE_CATEGORIES]

    if variant == "empty":
        specs: List[Dict] = []
    else:
        specs = _base_specs()
        if variant == "edge":
            custom.append(_build_category(*_DEEP_CATEGORY))
            specs += [_spec(**{**item, "favorite": False}) for item in _EDGE_SPECS]
        elif variant == "stress":
            specs += _stress_specs()

    categories = system_categories + custom
    prompts = [
        _build_prompt(index, spec, manifest)
        for index, spec in enumerate(specs, start=1)
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

    created = [path for path in context.prompt_images_dir().glob("*.png")]
    created += [
        context.prompt_dir() / "categories.json",
        context.prompt_dir() / "prompts.json",
        context.prompt_dir() / "metadata.json",
    ]
    manifest.set_domain_files("prompt", created)

    return {
        "variant": variant,
        "prompts": len(prompts),
        "categories": len(categories),
    }
