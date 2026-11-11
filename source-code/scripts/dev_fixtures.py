"""dev / test 环境场景化假数据生成器（CLI）。

用法::

    python scripts/dev_fixtures.py list
    python scripts/dev_fixtures.py seed  --env dev
    python scripts/dev_fixtures.py seed  --env dev --scenario edge
    python scripts/dev_fixtures.py seed  --env dev --only workflow
    python scripts/dev_fixtures.py seed  --env dev --variant workflow=stress
    python scripts/dev_fixtures.py clean --env dev
    python scripts/dev_fixtures.py status --env dev

约定：

* 只允许 ``dev`` / ``test``；``prod`` 直接拒绝，不写入任何字节。
* 所有产物落在 ``<数据根>/fixtures/``，并在 ``.fixture_manifest.json`` 登记。
* 覆盖既有文件前先备份，``clean`` 会还原备份。
* 切换变体时先回收该域上一批产物，不留下两套数据混杂。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import FixtureError, registry  # noqa: E402
from fixtures import context  # noqa: E402


def _parse_pairs(values) -> dict:
    """把 ``domain=variant`` 列表解析成字典。"""
    pairs = {}
    for item in values or []:
        if "=" not in item:
            raise FixtureError(f"参数格式应为 域=变体，收到 {item!r}")
        domain, variant = item.split("=", 1)
        pairs[domain.strip()] = variant.strip()
    return pairs


def _parse_only(values) -> list:
    if not values:
        return []
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


def _seed_kwargs(domain: str, skip_video: bool) -> dict:
    if domain == "gallery":
        return {"include_video": not skip_video}
    return {}


def _cmd_seed(args) -> int:
    context.activate_env(args.env)
    manifest = context.Manifest().load()
    manifest.set_env(args.env)

    plan = registry.resolve(
        scenario=args.scenario,
        overrides=_parse_pairs(args.variant),
        only=_parse_only(args.only),
    )

    print(f"[seed] 环境 = {args.env}")
    print(f"[seed] 数据根 = {context.user_root()}")
    print(f"[seed] 产物目录 = {context.fixtures_dir()}")
    print(f"[seed] 场景 = {plan.scenario}"
          f"（{registry.SCENARIO_HINTS.get(plan.scenario, '')}）")

    for domain, variant in plan:
        info = registry.DOMAINS[domain]
        print(f"[seed] -- {info.title} / {variant}: {info.variants[variant]}")
        result = info.seeder(
            manifest, variant=variant, **_seed_kwargs(domain, args.skip_video)
        )
        print(f"[seed]    {_summarize(domain, result)}")

    manifest.save()
    print(f"[seed] 清单已写入 {manifest.path}")
    print(f"[seed] 完成。清理: python scripts/dev_fixtures.py clean --env {args.env}")
    return 0


def _summarize(domain: str, result: dict) -> str:
    """把各域的返回值压成一行可读摘要。"""
    if domain == "state":
        return (f"首启标记{'已建' if result.get('marker_created') else '已存在'} / "
                f"settings{'已建' if result.get('settings_created') else '已存在'}")
    if domain == "comfyui":
        return (f"根目录 {result.get('comfyui_root')} "
                f"(插件 {result.get('plugins')} / 模型 {result.get('model_files')})")
    if domain == "workflow":
        return f"{result.get('workflows')} 个工作流 -> {result.get('root')}"
    if domain == "gallery":
        return (f"图片 {result.get('images')} / 视频 {result.get('videos')} / "
                f"已索引 {result.get('indexed')}")
    if domain == "prompt":
        return f"{result.get('prompts')} 条配方 / {result.get('categories')} 个分类"
    if domain == "lora":
        return f"{result.get('models')} 个模型"
    if domain == "assistant":
        return f"{result.get('topics')} 个话题 / {result.get('messages')} 条消息"
    return str(result)


def _cmd_clean(args) -> int:
    context.activate_env(args.env)
    manifest = context.Manifest().load()
    if not manifest.exists():
        print(f"[clean] 未发现清单，环境 {args.env} 无需清理")
        return 0
    if manifest.env and manifest.env != args.env:
        raise FixtureError(
            f"清单属于环境 {manifest.env}，拒绝用 {args.env} 清理。"
            f"请用 --env {manifest.env}"
        )

    result = manifest.cleanup()
    print(f"[clean] 删除 {result['removed']} 项，还原 {result['restored']} 项，"
          f"缺失 {result['missing']} 项")
    print("[clean] 完成")
    return 0


def _cmd_status(args) -> int:
    context.activate_env(args.env)
    manifest = context.Manifest().load()
    print(f"[status] 环境 = {args.env}")
    print(f"[status] 数据根 = {context.user_root()}")
    if not manifest.exists():
        print("[status] 无 fixture 记录")
        return 0

    print(f"[status] 清单环境 = {manifest.env}")
    print(f"[status] 登记路径 {len(manifest._data.get('paths', []))} 项")
    print(f"[status] 备份 {len(manifest._data.get('backups', {}))} 项")
    domains = manifest._data.get("domains", {})
    if domains:
        print("[status] 各域产物：")
        for domain, paths in domains.items():
            print(f"  {domain:<10} {len(paths)} 个文件")
    return 0


def _cmd_list(args) -> int:
    for line in registry.catalog_lines():
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comfyui-Box dev/test 场景化假数据生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=("list", "seed", "clean", "status"))
    parser.add_argument("--env", default="dev", help="目标环境，只支持 dev / test")
    parser.add_argument("--scenario", default="typical",
                        help="场景预设，默认 typical；用 list 查看全部")
    parser.add_argument("--variant", action="append", metavar="域=变体",
                        help="覆盖单个域的变体，可重复")
    parser.add_argument("--only", action="append", metavar="域[,域]",
                        help="只播种这些域（前置域始终保留）")
    parser.add_argument("--skip-video", action="store_true",
                        help="资产库不生成视频（seed 有效）")
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            return _cmd_list(args)
        if args.command == "seed":
            return _cmd_seed(args)
        if args.command == "clean":
            return _cmd_clean(args)
        return _cmd_status(args)
    except FixtureError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
