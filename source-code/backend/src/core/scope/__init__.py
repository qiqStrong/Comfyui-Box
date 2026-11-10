"""
数据范围（Package / DataSpace / scopeMap）解析层。

设计约定（详见 docs/architecture/data-layout.md）：
- 一个包（Package）内有一个全局数据空间（global_space_id）和若干根（ComfyUI 环境）；
- 每根默认拥有一个私有数据空间（data_space_id）；
- 每类业务数据（资产库/提示词/AI 对话/工作流/LoRA）有一个 scope 绑定，取值
  ``global`` / ``private`` / ``custom``；
- 绑定只保存配置与引用，不复制、不迁移真实数据。
"""

from .resolver import (
    CATEGORY_SPECS,
    SWITCHABLE_CATEGORIES,
    bind_environment,
    bump_scope_epoch,
    get_scope_epoch,
    get_scope_matrix,
    normalize_registry,
    preview_scope_change,
    resolve_scope,
    set_scope,
)

__all__ = [
    "CATEGORY_SPECS",
    "SWITCHABLE_CATEGORIES",
    "bind_environment",
    "bump_scope_epoch",
    "get_scope_epoch",
    "get_scope_matrix",
    "normalize_registry",
    "preview_scope_change",
    "resolve_scope",
    "set_scope",
]
