"""dev / test 环境的假数据生成器。

设计约束（不可违反）：

1. **只写 dev 与 test**。``prod`` 一律拒绝，不做任何写入。
2. **可识别**。所有 fixture 记录带 ``[FIXTURE]`` 标记，所有文件位于
   ``<数据根>/fixtures/`` 或由清单登记。
3. **可回滚**。覆盖任何既有文件前先备份到 ``<数据根>/fixtures/backup/``，
   ``clean`` 时原样还原。
4. **不碰真实 ComfyUI**。假环境指向自建的 ``fixtures/comfyui`` 骨架。
"""

from .context import FixtureError

__all__ = ["FixtureError"]
