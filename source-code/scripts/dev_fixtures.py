"""dev / test 环境假数据生成器（CLI）。

用法::

    python scripts/dev_fixtures.py seed  --env dev
    python scripts/dev_fixtures.py clean --env dev
    python scripts/dev_fixtures.py status --env dev

约定：

* 只允许 ``dev`` / ``test``；``prod`` 直接拒绝，不写入任何字节。
* 所有产物落在 ``<数据根>/fixtures/``，并在 ``.fixture_manifest.json`` 登记。
* 覆盖既有文件前先备份，``clean`` 会还原备份。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import FixtureError  # noqa: E402
from fixtures import assistant, comfyui, context, gallery, lora, prompts  # noqa: E402


def _cmd_seed(env: str, skip_video: bool) -> int:
    context.activate_env(env)
    manifest = context.Manifest().load()
    manifest.set_env(env)

    print(f"[seed] 环境 = {env}")
    print(f"[seed] 数据根 = {context.user_root()}")
    print(f"[seed] 产物目录 = {context.fixtures_dir()}")

    comfyui_info = comfyui.seed(manifest)
    print(f"[seed] 假 ComfyUI: {comfyui_info['comfyui_root']} "
          f"(插件 {comfyui_info['plugins']} / 模型 {comfyui_info['model_files']})")

    gallery_info = gallery.seed(manifest, include_video=not skip_video)
    print(f"[seed] 资产库: {gallery_info['library']} "
          f"（图片 {gallery_info['images']} / 视频 {gallery_info['videos']} / "
          f"分类目录 {gallery_info['categories']} / 已索引 {gallery_info['indexed']}）")

    prompt_info = prompts.seed(manifest)
    print(f"[seed] 提示词库: {prompt_info['prompts']} 条配方 / {prompt_info['categories']} 个分类")

    lora_info = lora.seed(manifest)
    print(f"[seed] LoRA 索引: {lora_info['models']} 个模型")

    assistant_info = assistant.seed(manifest)
    print(f"[seed] AI 对话: {assistant_info['topics']} 个话题 / {assistant_info['messages']} 条消息")

    manifest.save()
    print(f"[seed] 清单已写入 {manifest.path}")
    print("[seed] 完成。清理请执行: python scripts/dev_fixtures.py clean "
          f"--env {env}")
    return 0


def _cmd_clean(env: str) -> int:
    context.activate_env(env)
    manifest = context.Manifest().load()
    if not manifest.exists():
        print(f"[clean] 未发现清单，环境 {env} 无需清理")
        return 0
    if manifest.env and manifest.env != env:
        raise FixtureError(
            f"清单属于环境 {manifest.env}，拒绝用 {env} 清理。请用 --env {manifest.env}"
        )

    result = manifest.cleanup()
    print(f"[clean] 删除 {result['removed']} 项，还原 {result['restored']} 项，"
          f"缺失 {result['missing']} 项")
    print("[clean] 完成")
    return 0


def _cmd_status(env: str) -> int:
    context.activate_env(env)
    manifest = context.Manifest().load()
    print(f"[status] 环境 = {env}")
    print(f"[status] 数据根 = {context.user_root()}")
    if not manifest.exists():
        print("[status] 无 fixture 记录")
        return 0
    print(f"[status] 清单环境 = {manifest.env}")
    print(f"[status] 登记路径 {len(manifest._data.get('paths', []))} 项")
    print(f"[status] 备份 {len(manifest._data.get('backups', {}))} 项")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comfyui-Box dev/test 假数据生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=("seed", "clean", "status"))
    parser.add_argument("--env", default="dev", help="目标环境，只支持 dev / test")
    parser.add_argument("--skip-video", action="store_true", help="不生成视频资产（seed 有效）")
    args = parser.parse_args(argv)

    try:
        if args.command == "seed":
            return _cmd_seed(args.env, args.skip_video)
        if args.command == "clean":
            return _cmd_clean(args.env)
        return _cmd_status(args.env)
    except FixtureError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
