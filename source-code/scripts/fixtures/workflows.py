"""工作流场景数据集。

每个样本都对应工作流页的一条真实代码分支，不是随便凑数量：

===================  =========================================================
样本                 覆盖的代码路径
===================  =========================================================
basic-*              ``WorkflowParser`` 正常解析 + 依赖面板只有 comfy-core
edge-01 多插件依赖    节点 → 插件反查（``rext_map``），依赖面板出现多个插件
edge-02 未知节点      ``_resolve_github_url`` 全部落空 → 归入未知来源
edge-03 虚拟节点      ``is_virtual_node`` 跳过 Reroute / Note，节点数不计
edge-04 空图          ``nodes: []``，卡片节点数 0
edge-05 无提示词      无 CLIPTextEncode → 转入提示词库返回 ``no_prompt_detected``
edge-06 大图          120 节点，图预览与节点计数的性能
edge-07 损坏          ``json.loads`` 抛错 → 整条跳过，不得刷屏
edge-08 非对象        顶层是数组 → ``isinstance(data, dict)`` 分支跳过
edge-09 API 格式      没有 ``nodes`` 字段（API 格式），节点数 0
edge-10 子图          ``extra.groupNodes`` 里的节点也要计入插件统计
edge-11 嵌套目录      ``_sync_folders_from_filesystem`` 的文件夹树
edge-12 超长名称      卡片标题截断与布局溢出
===================  =========================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import context
from .comfyui import FIXTURE_ENV_ID
from .context import FIXTURE_TAG, Manifest

TITLE = "工作流库"

VARIANTS = {
    "basic": "3 个标准 SDXL 工作流（纯内置节点）",
    "edge": "basic + 12 个边界样本（多插件/未知节点/空图/大图/损坏/API 格式/子图/嵌套目录）",
    "stress": "basic + 60 个批量工作流，分 4 个文件夹",
    "empty": "不生成任何工作流，验证空状态",
}

# 已知插件节点：类型名取自真实映射表，依赖面板能反查出插件仓库
_PLUGIN_NODES = {
    "ipadapter": "IPAdapterAdvanced",      # cubiq/ComfyUI_IPAdapter_plus
    "detailer": "FaceDetailer",            # ltdrdata/ComfyUI-Impact-Pack
    "animatediff": "ADE_ADBlockCombo",     # Kosinkadink/ComfyUI-AnimateDiff-Evolved
    "controlnet": "AIO_Preprocessor",      # Fannovel16/comfyui_controlnet_aux
}

_NEGATIVE = "blurry, low quality, watermark, deformed"


# ---------------------------------------------------------------- 图元构造


def _node(
    node_id: int,
    node_type: str,
    pos: Sequence[int],
    size: Sequence[int],
    widgets: Optional[list] = None,
    properties: Optional[dict] = None,
) -> Dict:
    return {
        "id": node_id,
        "type": node_type,
        "pos": list(pos),
        "size": list(size),
        "flags": {},
        "order": node_id - 1,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "properties": properties or {"Node name for S&R": node_type},
        "widgets_values": widgets or [],
    }


def _graph(nodes: List[Dict], links: List[list], extra: Optional[Dict] = None) -> Dict:
    return {
        "last_node_id": max((node["id"] for node in nodes), default=0),
        "last_link_id": max((link[0] for link in links), default=0),
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": extra or {"ds": {"scale": 0.85, "offset": [40, 60]}},
        "version": 0.4,
    }


def _txt2img_graph(
    checkpoint: str,
    prompt: str,
    steps: int,
    width: int = 1024,
    height: int = 1024,
) -> Dict:
    """标准文生图：Checkpoint → 双 CLIP → 空 Latent → KSampler → VAE → 保存。"""
    nodes = [
        _node(1, "CheckpointLoaderSimple", (80, 120), (315, 98), [checkpoint]),
        _node(2, "CLIPTextEncode", (440, 60), (420, 160), [prompt]),
        _node(3, "CLIPTextEncode", (440, 260), (420, 120), [_NEGATIVE]),
        _node(4, "EmptyLatentImage", (440, 420), (315, 106), [width, height, 1]),
        _node(5, "KSampler", (900, 100), (315, 262),
              [156680208700286, "randomize", steps, 7.5, "euler", "normal", 1]),
        _node(6, "VAEDecode", (1250, 120), (210, 46)),
        _node(7, "SaveImage", (1500, 120), (315, 270), ["ComfyUI"]),
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
    return _graph(nodes, links)


# ---------------------------------------------------------------- 基础样本

_BASIC = [
    ("portrait-basic", "fixture-sdxl-base.safetensors",
     "a cinematic portrait of an astronaut, soft rim light, 50mm", 28, 832, 1216),
    ("landscape-wide", "fixture-sdxl-base.safetensors",
     "vast mountain valley at sunrise, volumetric fog, ultra wide", 32, 1344, 768),
    ("product-shot", "fixture-sd15.safetensors",
     "a ceramic mug on a marble table, studio softbox, minimal", 20, 1024, 1024),
]


def _basic_payloads() -> Dict[str, Dict]:
    return {
        name: _txt2img_graph(checkpoint, prompt, steps, width, height)
        for name, checkpoint, prompt, steps, width, height in _BASIC
    }


# ---------------------------------------------------------------- 边界样本


def _multi_plugin() -> Dict:
    """6 个节点、3 个第三方插件：依赖面板应出现多条待安装项。"""
    nodes = [
        _node(1, "CheckpointLoaderSimple", (80, 120), (315, 98),
              ["fixture-sdxl-base.safetensors"]),
        _node(2, "CLIPTextEncode", (440, 60), (420, 160),
              ["portrait of a knight, ornate armor, dramatic light"]),
        _node(3, "CLIPTextEncode", (440, 260), (420, 120), [_NEGATIVE]),
        _node(4, "EmptyLatentImage", (440, 420), (315, 106), [832, 1216, 1]),
        _node(5, _PLUGIN_NODES["ipadapter"], (900, 380), (315, 130),
              ["ipadapter.safetensors", 0.85, "linear", 0.6],
              {"cnr_id": "comfyui_ipadapter_plus", "ver": "2024.11.07"}),
        _node(6, "KSampler", (900, 60), (315, 262),
              [156680208700286, "randomize", 30, 7.0, "euler", "normal", 1]),
        _node(7, "VAEDecode", (1250, 120), (210, 46)),
        _node(8, _PLUGIN_NODES["detailer"], (1500, 120), (315, 300),
              ["bbox", "sam", 0.5, 0.3, 10, True]),
        _node(9, _PLUGIN_NODES["animatediff"], (1250, 380), (315, 160),
              [16, 1, "uniform", False]),
        _node(10, "SaveImage", (1850, 120), (315, 270), ["ComfyUI"]),
    ]
    links = [
        [1, 1, 0, 2, 0, "CLIP"],
        [2, 1, 0, 3, 0, "CLIP"],
        [3, 1, 0, 6, 0, "MODEL"],
        [4, 2, 0, 6, 1, "CONDITIONING"],
        [5, 3, 0, 6, 2, "CONDITIONING"],
        [6, 4, 0, 6, 3, "LATENT"],
        [7, 1, 0, 5, 0, "MODEL"],
        [8, 5, 0, 6, 0, "MODEL"],
        [9, 6, 0, 7, 1, "LATENT"],
        [10, 1, 2, 7, 0, "VAE"],
        [11, 7, 0, 8, 0, "IMAGE"],
        [12, 6, 0, 9, 0, "MODEL"],
        [13, 8, 0, 10, 0, "IMAGE"],
    ]
    return _graph(nodes, links)


def _unknown_nodes() -> Dict:
    """两个映射表里都不存在的节点类型，依赖面板应归到未知来源。"""
    nodes = [
        _node(1, "CheckpointLoaderSimple", (80, 120), (315, 98),
              ["fixture-sdxl-base.safetensors"]),
        _node(2, "CLIPTextEncode", (440, 60), (420, 160),
              ["concept art, floating islands, painterly"]),
        _node(3, "MyCustomNodeXYZ", (440, 300), (315, 120), [1, 2, 3]),
        _node(4, "TotallyUnknownNode", (800, 300), (315, 120), ["unknown"]),
        _node(5, "KSampler", (900, 60), (315, 262),
              [42, "fixed", 24, 7.5, "euler", "normal", 1]),
        _node(6, "VAEDecode", (1250, 120), (210, 46)),
        _node(7, "SaveImage", (1500, 120), (315, 270), ["ComfyUI"]),
    ]
    links = [
        [1, 1, 0, 2, 0, "CLIP"],
        [2, 1, 0, 5, 0, "MODEL"],
        [3, 2, 0, 5, 1, "CONDITIONING"],
        [4, 3, 0, 5, 3, "LATENT"],
        [5, 4, 0, 5, 2, "CONDITIONING"],
        [6, 5, 0, 6, 1, "LATENT"],
        [7, 1, 2, 6, 0, "VAE"],
        [8, 6, 0, 7, 0, "IMAGE"],
    ]
    return _graph(nodes, links)


def _virtual_nodes() -> Dict:
    """混入 Reroute / Note：7 个节点里只有 5 个应计入节点数。"""
    nodes = [
        _node(1, "CheckpointLoaderSimple", (80, 120), (315, 98),
              ["fixture-sdxl-base.safetensors"]),
        _node(2, "Reroute", (440, 120), (75, 26)),
        _node(3, "Note", (440, 220), (300, 120),
              ["这里是一条备注节点，不应计入节点数"]),
        _node(4, "CLIPTextEncode", (560, 60), (420, 160),
              ["isometric city block, warm evening light"]),
        _node(5, "KSampler", (1020, 60), (315, 262),
              [7, "randomize", 26, 7.0, "dpmpp_2m", "karras", 1]),
        _node(6, "VAEDecode", (1370, 120), (210, 46)),
        _node(7, "SaveImage", (1620, 120), (315, 270), ["ComfyUI"]),
    ]
    links = [
        [1, 1, 0, 2, 0, "CLIP"],
        [2, 2, 0, 4, 0, "CLIP"],
        [3, 1, 0, 5, 0, "MODEL"],
        [4, 4, 0, 5, 1, "CONDITIONING"],
        [5, 5, 0, 6, 1, "LATENT"],
        [6, 1, 2, 6, 0, "VAE"],
        [7, 6, 0, 7, 0, "IMAGE"],
    ]
    return _graph(nodes, links)


def _empty_graph() -> Dict:
    return _graph([], [])


def _no_prompt() -> Dict:
    """没有 CLIPTextEncode：转入提示词库时应返回 no_prompt_detected。"""
    nodes = [
        _node(1, "CheckpointLoaderSimple", (80, 120), (315, 98),
              ["fixture-sd15.safetensors"]),
        _node(2, "EmptyLatentImage", (440, 120), (315, 106), [768, 768, 1]),
        _node(3, "KSampler", (800, 120), (315, 262),
              [1, "fixed", 20, 7.5, "euler", "normal", 1]),
        _node(4, "VAEDecode", (1150, 120), (210, 46)),
        _node(5, "SaveImage", (1400, 120), (315, 270), ["ComfyUI"]),
    ]
    links = [
        [1, 1, 0, 3, 0, "MODEL"],
        [2, 2, 0, 3, 3, "LATENT"],
        [3, 3, 0, 4, 1, "LATENT"],
        [4, 1, 2, 4, 0, "VAE"],
        [5, 4, 0, 5, 0, "IMAGE"],
    ]
    return _graph(nodes, links)


def _large_graph(count: int = 120) -> Dict:
    """1 个加载器 + 1 个提示词 + 若干缩放节点链 + 采样保存。"""
    nodes = [
        _node(1, "CheckpointLoaderSimple", (0, 0), (315, 98),
              ["fixture-sdxl-base.safetensors"]),
        _node(2, "CLIPTextEncode", (0, 140), (420, 160),
              ["highly detailed matte painting, dramatic sky"]),
    ]
    links: List[list] = [[1, 1, 0, 2, 0, "CLIP"]]

    previous = 1
    link_id = 2
    for index in range(3, 3 + count):
        column = (index % 12) * 220
        row = (index // 12) * 140
        nodes.append(_node(index, "ImageScale", (column, row), (210, 130),
                           ["lanczos", 1.5, "disabled"]))
        links.append([link_id, previous, 0, index, 0, "IMAGE"])
        previous = index
        link_id += 1

    tail = 3 + count
    nodes.append(_node(tail, "SaveImage", (0, 600), (315, 270), ["ComfyUI"]))
    links.append([link_id, previous, 0, tail, 0, "IMAGE"])
    return _graph(nodes, links)


def _subgraph() -> Dict:
    """extra.groupNodes 里的节点也要计入插件依赖统计。"""
    graph = _txt2img_graph(
        "fixture-sdxl-base.safetensors",
        "character sheet, three views, clean background", 24, 1024, 1024,
    )
    graph["extra"]["groupNodes"] = {
        "人物精修组": {
            "nodes": [
                {"id": 101, "type": _PLUGIN_NODES["detailer"],
                 "properties": {"Node name for S&R": _PLUGIN_NODES["detailer"]}},
                {"id": 102, "type": _PLUGIN_NODES["controlnet"],
                 "properties": {"Node name for S&R": _PLUGIN_NODES["controlnet"]}},
            ]
        }
    }
    return graph


# ---------------------------------------------------------------- 落盘


def _root() -> Path:
    return context.comfyui_workflows_dir()


def _write(relative: str, text: str, manifest: Manifest, created: List[Path]) -> None:
    target = _root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    manifest.record(target)
    created.append(target)


def _write_json(relative: str, payload: Dict, manifest: Manifest,
                created: List[Path]) -> None:
    _write(relative, json.dumps(payload, ensure_ascii=False, indent=2), manifest, created)


def _reset(manifest: Manifest) -> None:
    context.reset_domain(manifest, "workflow", prune_root=_root())


def _write_metadata(manifest: Manifest, entries: Dict[str, Dict]) -> None:
    """补充收藏/标签/描述，让卡片不是清一色默认态。"""
    if not entries:
        return
    path = context.workflows_dir() / f"{FIXTURE_ENV_ID}_metadata.json"
    store = context.read_json(path, {"version": 1, "workflows": {}, "folders": []})
    workflows = store.setdefault("workflows", {})
    for filename, payload in entries.items():
        workflows[filename] = {
            "name": payload.get("name", ""),
            "description": payload.get("description", ""),
            "tags": payload.get("tags", []),
            "is_favorite": payload.get("favorite", False),
            "folder_id": None,
            "previews": [],
            "has_auto_preview": False,
        }
    store.setdefault("folders", [])
    context.write_json(path, store, manifest)


def _seed_basic(manifest: Manifest, created: List[Path]) -> int:
    for name, payload in _basic_payloads().items():
        _write_json(f"{name}.json", payload, manifest, created)
    _write_metadata(manifest, {
        "portrait-basic.json": {
            "name": "人像基础",
            "description": f"{FIXTURE_TAG} 收藏样本，用于验证卡片收藏态与标签展示",
            "tags": ["人像", "SDXL"],
            "favorite": True,
        },
        "landscape-wide.json": {
            "name": "宽幅风景",
            "description": f"{FIXTURE_TAG} 横版构图样本",
            "tags": ["风景", "宽幅"],
            "favorite": False,
        },
    })
    return len(_BASIC)


def _seed_edge(manifest: Manifest, created: List[Path]) -> int:
    total = _seed_basic(manifest, created)

    samples = [
        ("edge-01-多插件依赖.json", _multi_plugin()),
        ("edge-02-未知节点.json", _unknown_nodes()),
        ("edge-03-虚拟节点.json", _virtual_nodes()),
        ("edge-04-空图.json", _empty_graph()),
        ("edge-05-无提示词.json", _no_prompt()),
        ("edge-06-大图.json", _large_graph()),
        ("edge-09-API格式.json",
         {"3": {"class_type": "KSampler", "inputs": {"seed": 1}},
          "4": {"class_type": "VAEDecode", "inputs": {}}}),
        ("edge-10-子图.json", _subgraph()),
    ]
    for relative, payload in samples:
        _write_json(relative, payload, manifest, created)
        total += 1

    # 损坏 JSON：截断到一半，json.loads 必然抛错
    _write("edge-07-损坏.json",
           '{"last_node_id": 5, "nodes": [{"id": 1, "type": "KSampler"',
           manifest, created)
    # 顶层非对象：走 isinstance(data, dict) 分支
    _write("edge-08-非对象.json", "[1, 2, 3]", manifest, created)
    total += 2

    _write_json("edge-11-嵌套目录/人物/人像精修.json",
                _txt2img_graph("fixture-sdxl-base.safetensors",
                               "portrait retouch, clean skin, studio light", 30, 832, 1216),
                manifest, created)
    _write_json("edge-11-嵌套目录/人物/半身像.json",
                _txt2img_graph("fixture-sdxl-base.safetensors",
                               "half body portrait, neutral background", 26, 832, 1216),
                manifest, created)
    _write_json("edge-11-嵌套目录/风景/远景.json",
                _txt2img_graph("fixture-sdxl-base.safetensors",
                               "distant mountains, atmospheric haze", 28, 1344, 768),
                manifest, created)
    total += 3

    long_name = ("这是一个用于验证标题截断与卡片布局溢出的超长工作流名称"
                 "-0123456789-abcdefghij")
    _write_json(f"edge-12-{long_name}.json",
                _txt2img_graph("fixture-sd15.safetensors",
                               "layout stress test, long filename", 18, 512, 512),
                manifest, created)
    total += 1

    return total


def _seed_stress(manifest: Manifest, created: List[Path]) -> int:
    total = _seed_basic(manifest, created)
    groups = ["组A", "组B", "组C", "组D"]
    for index in range(1, 61):
        group = groups[(index - 1) // 15]
        checkpoint = ("fixture-sdxl-base.safetensors" if index % 2
                      else "fixture-sd15.safetensors")
        payload = _txt2img_graph(
            checkpoint,
            f"batch sample {index:03d}, varied subject, consistent style",
            20 + index % 12,
            1024 if index % 3 else 768,
            1024 if index % 3 else 768,
        )
        _write_json(f"批量/{group}/stress-{index:03d}.json", payload, manifest, created)
        total += 1
    return total


def seed(manifest: Manifest, variant: str = "basic") -> Dict:
    """按变体写入工作流文件。"""
    _reset(manifest)
    created: List[Path] = []

    if variant == "empty":
        total = 0
    elif variant == "stress":
        total = _seed_stress(manifest, created)
    elif variant == "edge":
        total = _seed_edge(manifest, created)
    elif variant == "basic":
        total = _seed_basic(manifest, created)
    else:
        raise ValueError(f"未知工作流变体: {variant}")

    manifest.set_domain_files("workflow", created)
    return {"variant": variant, "workflows": total, "root": str(_root())}
