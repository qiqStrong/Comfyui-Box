"""生成占位图，用于资产库与提示词库的预览。

不依赖网络与外部素材，纯色渐变 + 文本，保证每张图肉眼可区分。
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

# 中文字体候选，找不到就退回 PIL 默认位图字体
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
)

# 每张图的配色：上、下、文字
PALETTES = {
    "dawn": ((255, 176, 120), (120, 60, 140), (255, 255, 255)),
    "forest": ((60, 140, 110), (16, 48, 60), (235, 255, 245)),
    "ocean": ((70, 150, 220), (12, 40, 90), (240, 250, 255)),
    "ember": ((220, 90, 60), (70, 20, 30), (255, 240, 230)),
    "violet": ((150, 110, 220), (40, 20, 70), (250, 245, 255)),
    "sand": ((235, 205, 160), (140, 100, 60), (60, 40, 25)),
    "steel": ((150, 165, 180), (45, 55, 70), (240, 245, 250)),
    "mint": ((150, 230, 200), (30, 90, 80), (20, 60, 55)),
}


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _gradient(size: Tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    """垂直线性渐变。"""
    width, height = size
    canvas = Image.new("RGB", (1, height))
    pixels = canvas.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        pixels[0, y] = tuple(
            int(top[channel] + (bottom[channel] - top[channel]) * ratio)
            for channel in range(3)
        )
    return canvas.resize((width, height), Image.BILINEAR)


def _draw_centered(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], text: str,
                   font: ImageFont.FreeTypeFont, fill: tuple) -> None:
    left, top, right, bottom = box
    text_box = draw.textbbox((0, 0), text, font=font)
    x = left + (right - left - (text_box[2] - text_box[0])) // 2
    y = top + (bottom - top - (text_box[3] - text_box[1])) // 2
    draw.text((x, y), text, font=font, fill=fill)


def make_card(path: Path, size: Tuple[int, int], palette: str, title: str,
              subtitle: str = "", text_chunks: dict | None = None) -> Path:
    """画一张带标题的渐变卡片。

    Args:
        text_chunks: 写入 PNG 文本块的内容（键名与 ComfyUI 一致，如 ``workflow``）。
    """
    top, bottom, text_color = PALETTES.get(palette, PALETTES["steel"])
    image = _gradient(size, top, bottom)
    draw = ImageDraw.Draw(image)

    width, height = size
    title_font = _load_font(max(18, width // 14))
    sub_font = _load_font(max(13, width // 26))

    margin = int(height * 0.08)
    _draw_centered(draw, (margin, 0, width - margin, height - margin), title, title_font, text_color)
    if subtitle:
        _draw_centered(draw, (margin, height - margin * 3, width - margin, height - margin),
                       subtitle, sub_font, text_color)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if text_chunks:
        from PIL.PngImagePlugin import PngInfo

        info = PngInfo()
        for key, value in text_chunks.items():
            info.add_text(key, value)
        image.save(path, format="PNG", optimize=True, pnginfo=info)
    else:
        image.save(path, format="PNG", optimize=True)
    return path


def make_thumbnail(source: Path, target: Path, longest_edge: int = 320) -> Path:
    """按最长边等比缩放生成缩略图。"""
    source = Path(source)
    target = Path(target)
    with Image.open(source) as image:
        ratio = longest_edge / max(image.size)
        resized = image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
            Image.LANCZOS,
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    resized.save(target, format="PNG", optimize=True)
    return target


def make_portrait(path: Path, size: Tuple[int, int], palette: str, label: str) -> Path:
    """竖版卡片，用于视频封面等比例不同的场景。"""
    return make_card(path, size, palette, label)
