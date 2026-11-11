"""资产库假数据。

关键点：资产库不是"写一份 assets.json 就行"。页面打开时会用 ``libraryPath``
重新扫描磁盘，凡是不在该目录下的资产一律被删除。所以 fixture 必须把媒体文件
真正放进库目录，并让扫描器自己建立索引。

为了顺带验证元数据解析链路，图片会写入 ComfyUI 同名的 ``workflow`` PNG 文本块。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from . import context
from .context import FIXTURE_TAG, Manifest
from .images import make_card

TITLE = "资产库"

VARIANTS = {
    "basic": "11 张图 + 2 段视频，3 个分类",
    "edge": "basic + 无元数据图 / 超大分辨率 / 深层目录 / 损坏文件 / 空文件 / 不支持格式",
    "stress": "basic + 50 张小图，验证列表滚动与缩略图加载",
    "empty": "空库，验证空状态",
}

# 目录名即分类名（扫描器按文件夹建分类）
# (子目录, 文件名, 调色板, 标题, 尺寸, 正向提示词, 模型)
_STILLS: List[tuple] = [
    ("风景", "晨光山谷", "dawn", "晨光山谷", (1024, 1024),
     "vast mountain valley at sunrise, volumetric fog, 35mm, ultra detailed",
     "fixture-sdxl-base.safetensors"),
    ("风景", "林间小径", "forest", "林间小径", (1024, 768),
     "dense forest path, dappled sunlight, shallow depth of field",
     "fixture-sdxl-base.safetensors"),
    ("风景", "海面长曝", "ocean", "海面长曝", (1344, 768),
     "long exposure seascape, silk smooth water, minimal horizon, ND1000",
     "fixture-sdxl-base.safetensors"),
    ("风景", "霓虹街角", "violet", "霓虹街角", (1024, 1024),
     "neon street corner at night, rain reflections, cyberpunk palette",
     "fixture-sd15.safetensors"),
    ("风景", "沙丘曲线", "sand", "沙丘曲线", (1344, 768),
     "desert dunes, clean curves, high key minimalism, soft shadow",
     "fixture-sdxl-base.safetensors"),
    ("人像", "人像柔光", "dawn", "人像柔光", (832, 1216),
     "portrait with soft butterfly lighting, 85mm, natural skin texture",
     "fixture-sdxl-base.safetensors"),
    ("人像", "侧逆光人像", "violet", "侧逆光人像", (832, 1216),
     "rim lit portrait, cool backlight, editorial mood, shallow dof",
     "fixture-sdxl-base.safetensors"),
    ("人像", "海边人像", "ocean", "海边人像", (832, 1216),
     "portrait at seaside, overcast diffuse light, 85mm",
     "fixture-sd15.safetensors"),
    ("测试集", "金属材质球", "steel", "金属材质球", (1024, 1024),
     "metal material sphere, studio HDRI lighting, product render",
     "fixture-sdxl-base.safetensors"),
    ("测试集", "薄荷渐变", "mint", "薄荷渐变", (768, 768),
     "flat mint gradient, design reference sheet",
     "fixture-sd15.safetensors"),
    ("测试集", "炉火静物", "ember", "炉火静物", (768, 1024),
     "still life with fireplace glow, warm tungsten key light",
     "fixture-sdxl-base.safetensors"),
]

# 由静图转出的短视频：(子目录, 源静图名, 视频名, 尺寸)
_VIDEOS: List[tuple] = [
    ("风景", "海面长曝", "海面长曝-推进", (1344, 768)),
    ("风景", "晨光山谷", "晨光山谷-环绕", (1024, 1024)),
]

_NEGATIVE = "blurry, low quality, watermark, deformed"


def library_dir() -> Path:
    return context.fixtures_dir() / "library"


def _workflow_payload(title: str, prompt: str, model: str, width: int, height: int) -> Dict:
    """构造与 ComfyUI 导出一致的 UI 格式工作流，供 PNG 文本块内嵌。"""
    nodes = [
        {"id": 1, "type": "CheckpointLoaderSimple", "pos": [80, 120], "size": [315, 98],
         "widgets_values": [model]},
        {"id": 2, "type": "CLIPTextEncode", "pos": [440, 60], "size": [420, 160],
         "widgets_values": [prompt]},
        {"id": 3, "type": "CLIPTextEncode", "pos": [440, 260], "size": [420, 120],
         "widgets_values": [_NEGATIVE]},
        {"id": 4, "type": "EmptyLatentImage", "pos": [440, 420], "size": [315, 106],
         "widgets_values": [width, height, 1]},
        {"id": 5, "type": "KSampler", "pos": [900, 100], "size": [315, 262],
         "widgets_values": [156680208700286, "randomize", 28, 7.5, "euler", "normal", 1]},
        {"id": 6, "type": "VAEDecode", "pos": [1250, 120], "size": [210, 46],
         "widgets_values": []},
        {"id": 7, "type": "SaveImage", "pos": [1500, 120], "size": [315, 270],
         "widgets_values": [title]},
    ]
    links = [
        [1, 1, 0, 2, 0, "CLIP"],
        [2, 1, 0, 3, 0, "CLIP"],
        [3, 1, 0, 5, 0, "MODEL"],
        [4, 2, 0, 5, 1, "CONDITIONING"],
        [5, 3, 0, 5, 2, "CONDITIONING"],
        [6, 4, 0, 5, 3, "LATENT"],
        [7, 5, 0, 6, 1, "LATENT"],
        [8, 1, 2, 6, 0, "VAE"],
        [9, 6, 0, 7, 0, "IMAGE"],
    ]
    return {
        "last_node_id": 7,
        "last_link_id": 9,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {"ds": {"scale": 0.85, "offset": [40, 60]}},
        "version": 0.4,
    }


def _render_still(item: tuple, manifest: Manifest) -> Path:
    folder, filename, palette, title, size, prompt, model = item
    target = library_dir() / folder / f"{filename}.png"
    payload = _workflow_payload(title, prompt, model, size[0], size[1])
    make_card(
        target, size, palette, title, f"{FIXTURE_TAG} 假资产",
        text_chunks={"workflow": json.dumps(payload, ensure_ascii=False)},
    )
    manifest.record(target)
    return target


def _render_plain(folder: str, filename: str, palette: str, title: str,
                  size: tuple, manifest: Manifest) -> Path:
    """不写 workflow 文本块：扫描器拿不到提示词，只能靠文件名建条目。"""
    target = library_dir() / folder / f"{filename}.png"
    make_card(target, size, palette, title, f"{FIXTURE_TAG} 无元数据")
    manifest.record(target)
    return target


def _render_broken(folder: str, filename: str, manifest: Manifest,
                   payload: bytes) -> Path:
    """故意写坏的文件，验证扫描器的单文件容错。"""
    target = library_dir() / folder / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    manifest.record(target)
    return target


def _render_video(item: tuple, manifest: Manifest) -> Optional[Path]:
    folder, source_name, video_name, size = item
    source = library_dir() / folder / f"{source_name}.png"
    if not source.exists():
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    target = library_dir() / folder / f"{video_name}.mp4"
    command = [
        ffmpeg, "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(source),
        "-t", "2", "-r", "12",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        str(target),
    ]
    try:
        subprocess.run(command, check=True, timeout=90, capture_output=True)
    except (subprocess.SubprocessError, OSError):
        return None
    if not target.exists():
        return None
    manifest.record(target)
    return target


def _write_library_settings(manifest: Manifest) -> None:
    """只设置 libraryPath，资产与分类交给扫描器按磁盘内容重建。"""
    payload = {
        "version": "1.0",
        "settings": {
            "libraryPath": str(library_dir()),
            "lastScanTime": None,
            "nsfwAutoClassify": False,
            "nsfwThreshold": 0.6,
            "nsfwAutoBlur": True,
        },
        "categories": [
            {"id": "all", "name": "全部", "isSystem": True, "parentId": None, "sortOrder": 0},
            {"id": "favorites", "name": "收藏", "isSystem": True, "parentId": None, "sortOrder": 1},
        ],
        "assets": [],
    }
    context.write_json(context.gallery_dir() / "assets.json", payload, manifest)


def _run_initial_scan(manifest: Manifest) -> Optional[Dict]:
    """立刻跑一次扫描，让首页/统计类页面一启动就有数据。

    页面本身也会在打开时扫描，但首页的"资产库"计数在扫描前是 0，
    提前索引可以避免这种时序差。
    """
    try:
        from backend.src.gallery.scanner import gallery_scanner

        result = gallery_scanner.scan_library(str(library_dir()))
    except Exception as exc:  # 扫描失败不影响其余 fixture
        print(f"[warn] 资产库首次扫描失败，页面打开时会重试: {exc}")
        return None
    manifest.record(context.gallery_dir() / "assets.json")
    return result


def _seed_basic(manifest: Manifest, include_video: bool) -> tuple:
    """返回 (静图数, 视频数)。"""
    for item in _STILLS:
        _render_still(item, manifest)

    if not include_video:
        return len(_STILLS), 0

    videos = 0
    for item in _VIDEOS:
        if _render_video(item, manifest):
            videos += 1
    return len(_STILLS), videos


def _seed_edge_extras(manifest: Manifest) -> int:
    """边界样本：每一种都对应扫描器的一条容错分支。"""
    created = 0

    # 1. 无 workflow 文本块 —— 拿不到提示词，只能靠文件名
    _render_plain("无元数据", "纯图无工作流", "steel", "纯图无工作流",
                  (1024, 1024), manifest)
    created += 1

    # 2. 超大分辨率 —— 缩略图生成耗时与内存
    _render_plain("无元数据", "超大分辨率", "mint", "超大分辨率 2048",
                  (2048, 2048), manifest)
    created += 1

    # 3. 深层目录 —— 分类树的层级深度
    _render_plain("测试集/材质/金属", "金属球", "steel", "深层目录",
                  (768, 768), manifest)
    created += 1

    # 4. 损坏的 PNG —— PIL 打不开，单文件失败不能影响整次扫描
    _render_broken("测试集", "损坏图片.png",
                   manifest, b"\x89PNG\r\n\x1a\n" + b"broken" * 20)
    created += 1

    # 5. 0 字节文件 —— 边界值
    _render_broken("测试集", "空文件.png", manifest, b"")
    created += 1

    # 6. 不支持的扩展名 —— 应被扫描器直接忽略
    _render_broken("测试集", "说明.txt", manifest, "这不是资产文件".encode("utf-8"))
    created += 1

    # 7. 超长文件名 —— 卡片标题与路径截断
    long_name = ("这是一个用于验证文件名截断与卡片标题溢出的超长资产名称"
                 "-0123456789-abcdefghij")
    _render_plain("测试集", long_name, "violet", "超长文件名",
                  (1024, 768), manifest)
    created += 1

    return created


def _seed_stress(manifest: Manifest, count: int = 50) -> int:
    palettes = list(("dawn", "forest", "ocean", "ember", "violet", "sand", "steel", "mint"))
    for index in range(1, count + 1):
        folder = f"压测/组{(index - 1) // 13 + 1}"
        _render_plain(folder, f"压测-{index:03d}",
                      palettes[index % len(palettes)], f"压测 {index:03d}",
                      (512, 512), manifest)
    return count


def seed(manifest: Manifest, variant: str = "basic",
         include_video: bool = True) -> Dict:
    """建立库目录与媒体文件，并指向它。"""
    if variant not in VARIANTS:
        raise ValueError(f"未知资产库变体: {variant}")

    # 切换变体时先回收上一批，避免两套数据混在一起
    context.reset_domain(manifest, "gallery", prune_root=library_dir())

    if variant == "empty":
        images = videos = 0
    else:
        images, videos = _seed_basic(manifest, include_video)
        if variant == "edge":
            images += _seed_edge_extras(manifest)
        elif variant == "stress":
            images += _seed_stress(manifest)

    _write_library_settings(manifest)
    scan = _run_initial_scan(manifest)

    assets_file = context.gallery_dir() / "assets.json"
    created = [path for path in library_dir().rglob("*") if path.is_file()]
    created.append(assets_file)
    manifest.set_domain_files("gallery", created)

    return {
        "variant": variant,
        "library": str(library_dir()),
        "images": images,
        "videos": videos,
        "categories": len({item[0] for item in _STILLS}) if images else 0,
        "indexed": (scan or {}).get("added", 0),
    }
