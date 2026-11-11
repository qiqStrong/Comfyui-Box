"""数据集注册表：域 → 变体 → 场景。

三个概念
--------

**域（domain）**
    一类数据，对应一个 fixture 模块（工作流、资产库、提示词库…）。

**变体（variant）**
    该域的一种完整数据集。约定命名：

    * ``basic``  —— 正常数据，页面能正常展示
    * ``edge``   —— basic + 边界/脏数据，考验容错与降级
    * ``stress`` —— basic + 大批量，考验性能与布局
    * ``empty``  —— 空集，考验空状态

**场景（scenario）**
    各域变体的组合，一次把环境调成某种验证状态。

为什么要区分
------------

优化工作流时需要的是"能暴露工作流问题的数据"，不是"13 张资产图"。
有了这套注册表，可以只播种工作流域并指定 ``edge`` 变体，
其余域保持不动，验证面小、信号强。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from . import assistant, comfyui, gallery, lora, prompts, state, workflows
from .context import FixtureError

# 域模块按播种顺序排列：先建环境骨架，再写依赖它的数据
_DOMAIN_MODULES = (
    ("state", state),
    ("comfyui", comfyui),
    ("workflow", workflows),
    ("gallery", gallery),
    ("prompt", prompts),
    ("lora", lora),
    ("assistant", assistant),
)

# 这些域是其余域的前置条件，--only 也不能省略
PREREQUISITE_DOMAINS = ("state", "comfyui")


@dataclass(frozen=True)
class Domain:
    """一个数据域。"""

    key: str
    title: str
    variants: Mapping[str, str]
    seeder: Callable[..., dict]

    def describe_variants(self) -> str:
        return " / ".join(self.variants)


DOMAINS: Dict[str, Domain] = {
    key: Domain(
        key=key,
        title=module.TITLE,
        variants=dict(module.VARIANTS),
        seeder=module.seed,
    )
    for key, module in _DOMAIN_MODULES
}

# 场景预设。键为域名，值为变体名。
SCENARIOS: Dict[str, Dict[str, str]] = {
    "typical": {
        "state": "base",
        "comfyui": "base",
        "workflow": "basic",
        "gallery": "basic",
        "prompt": "basic",
        "lora": "basic",
        "assistant": "basic",
    },
    "empty": {
        "state": "base",
        "comfyui": "base",
        "workflow": "empty",
        "gallery": "empty",
        "prompt": "empty",
        "lora": "empty",
        "assistant": "empty",
    },
    "edge": {
        "state": "base",
        "comfyui": "base",
        "workflow": "edge",
        "gallery": "edge",
        "prompt": "edge",
        "lora": "edge",
        "assistant": "edge",
    },
    "stress": {
        "state": "base",
        "comfyui": "base",
        "workflow": "stress",
        "gallery": "stress",
        "prompt": "stress",
        "lora": "stress",
        "assistant": "basic",
    },
    "degraded": {
        "state": "base",
        "comfyui": "degraded",
        "workflow": "basic",
        "gallery": "basic",
        "prompt": "basic",
        "lora": "basic",
        "assistant": "basic",
    },
}

SCENARIO_HINTS = {
    "typical": "日常开发与全页面走查的默认数据集",
    "empty": "全部空集，验证空状态与引导文案",
    "edge": "各域边界/脏数据，验证容错与降级",
    "stress": "大批量数据，验证列表性能与布局",
    "degraded": "环境残缺（无 Python、无插件目录），验证异常提示",
}


def _check_domain(domain: str) -> Domain:
    if domain not in DOMAINS:
        raise FixtureError(
            f"未知域 {domain!r}，可用: {', '.join(DOMAINS)}"
        )
    return DOMAINS[domain]


def _check_variant(domain: str, variant: str) -> str:
    info = _check_domain(domain)
    if variant not in info.variants:
        raise FixtureError(
            f"域 {domain} 没有变体 {variant!r}，可用: {', '.join(info.variants)}"
        )
    return variant


@dataclass
class Plan:
    """一次播种计划：域 → 变体。"""

    scenario: str
    variants: Dict[str, str]

    def __iter__(self):
        return iter(self.variants.items())

    def __len__(self) -> int:
        return len(self.variants)


def resolve(
    scenario: str = "typical",
    overrides: Optional[Mapping[str, str]] = None,
    only: Optional[Sequence[str]] = None,
) -> Plan:
    """把场景名、单域覆盖、域过滤合并成一份可执行的计划。

    Args:
        scenario: 场景名，见 :data:`SCENARIOS`。
        overrides: ``{域名: 变体名}``，覆盖场景里的取值。
        only: 只播种这些域；前置域（state/comfyui）始终保留。

    Returns:
        校验通过的 :class:`Plan`。

    Raises:
        FixtureError: 场景、域或变体不存在。
    """
    if scenario not in SCENARIOS:
        raise FixtureError(
            f"未知场景 {scenario!r}，可用: {', '.join(SCENARIOS)}"
        )

    selected: Dict[str, str] = dict(SCENARIOS[scenario])

    for domain, variant in (overrides or {}).items():
        _check_domain(domain)
        selected[domain] = _check_variant(domain, variant)

    if only:
        wanted = [item.strip() for item in only if item.strip()]
        for domain in wanted:
            _check_domain(domain)
        keep = set(wanted) | set(PREREQUISITE_DOMAINS)
        selected = {k: v for k, v in selected.items() if k in keep}

    # 按固定顺序输出，保证日志与产物稳定
    ordered = {key: selected[key] for key, _ in _DOMAIN_MODULES if key in selected}
    return Plan(scenario=scenario, variants=ordered)


def catalog_lines() -> List[str]:
    """给 ``list`` 命令用的可读目录。"""
    lines: List[str] = ["场景："]

    for name, preset in SCENARIOS.items():
        lines.append(f"  {name:<9} {SCENARIO_HINTS.get(name, '')}")
        pairs = ", ".join(f"{key}={value}" for key, value in preset.items())
        lines.append(f"            {pairs}")

    lines.append("")
    lines.append("域与变体：")
    for key, info in DOMAINS.items():
        lines.append(f"  {key:<10} {info.title}")
        for variant, description in info.variants.items():
            lines.append(f"    - {variant:<7} {description}")

    return lines
