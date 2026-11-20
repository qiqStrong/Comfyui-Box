"""构建脚本与 CLI 帮助文本的回归测试。

覆盖两处低危修复：
- 构建.ps1 用无 BOM UTF-8 写配置、按原始字节恢复，且无遗留死变量；
- main.py 的 --env 帮助文本反映其最高优先级，不再声称打包产物忽略该参数。
"""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_SOURCE_ROOT / "backend"), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_build_script_uses_bom_free_write_and_byte_restore():
    script = (_SOURCE_ROOT / "build_scripts" / "构建.ps1").read_text(encoding="utf-8-sig")
    assert "UTF8Encoding($false)" in script
    assert "[IO.File]::WriteAllBytes" in script
    assert "Set-Content $DeployConfigPath -Encoding UTF8" not in script
    assert "$OriginalDeployConfig = $null" not in script


def test_cli_help_describes_env_override():
    main_py = (_SOURCE_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "--env <dev|test|prod>" in main_py
    assert "优先级最高" in main_py
    assert "此参数被忽略" not in main_py
