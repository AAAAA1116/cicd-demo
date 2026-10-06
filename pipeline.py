"""本地 CI/CD 流水线模拟器。

把 GitHub Actions 里的 workflow 搬到本机按顺序跑一遍，
让你在没有服务器的情况下也能看到 CI/CD 的完整流程。

用法：
    python pipeline.py              跑完整流水线（CI + CD）
    python pipeline.py --ci-only    只跑 CI，不做构建和部署
    python pipeline.py --inject-bug 自动注入一个 bug，看 CI 如何拦截它
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
DIST_DIR = ROOT / "dist"
DEPLOY_DIR = ROOT / "deploy"
BUG_FILE = SRC_DIR / "pricing.py"

# 用于演示的 bug：把 5% 折扣错写成 50%
GOOD_CODE = "    if subtotal < 500:\n        return 0.05\n"
BAD_CODE = "    if subtotal < 500:\n        return 0.5\n"

LINE = "=" * 66


class StageError(Exception):
    """某个流水线阶段失败。"""


def _banner(text: str) -> None:
    print(f"\n{LINE}\n  {text}\n{LINE}")


def _info(text: str) -> None:
    print(f"      {text}")


# --------------------------------------------------------------------------
# 各阶段（对应 GitHub Actions 里的 steps）
# --------------------------------------------------------------------------


def stage_checkout() -> None:
    """第 1 步：拉取代码。对应 actions/checkout。"""
    required = ["src/pricing.py", "tests/test_pricing.py", "requirements.txt", "pytest.ini"]
    missing = [f for f in required if not (ROOT / f).exists()]
    if missing:
        raise StageError(f"仓库缺少必要文件: {missing}")
    _info(f"仓库就绪，检出 {len(required)} 个关键文件")


def stage_install(force: bool) -> None:
    """第 2 步：安装依赖。真实 CI 里通常有缓存（actions/cache）。"""
    if not force:
        try:
            import pytest  # noqa: F401
        except ImportError:
            pass
        else:
            _info("依赖缓存命中，跳过安装（对应 actions/cache）")
            return
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise StageError("pip install 失败:\n" + r.stdout[-800:])
    _info("依赖安装完成")


def stage_lint() -> None:
    """第 3 步：静态检查。本机用 compileall 代替 ruff/flake8/mypy。"""
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "src", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise StageError("语法检查未通过:\n" + r.stdout[-800:])
    _info("语法/静态检查通过（真实项目这里通常是 ruff + mypy）")


def stage_test() -> None:
    """第 4 步：跑测试。CI 的核心守门员，红灯就到此为止。"""
    r = subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()
    for line in tail[-12:]:
        print(f"      | {line}")
    if r.returncode != 0:
        raise StageError("测试未通过")
    _info("全部测试用例通过")


def stage_build() -> str:
    """第 5 步：构建产物。对应 docker build / npm run build。"""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    DIST_DIR.mkdir(exist_ok=True)
    archive = shutil.make_archive(
        str(DIST_DIR / f"pricing-{version}"), "zip", root_dir=ROOT, base_dir="src"
    )
    size = Path(archive).stat().st_size
    _info(f"构建产物: {Path(archive).name} ({size} bytes)")
    return version


def stage_deploy(version: str) -> None:
    """第 6 步：部署。这里用本地目录 + 部署日志模拟。"""
    target = DEPLOY_DIR / f"pricing-{version}"
    if target.exists():
        shutil.rmtree(target)
    shutil.unpack_archive(str(DIST_DIR / f"pricing-{version}.zip"), str(target))
    (DEPLOY_DIR / "CURRENT").write_text(version, encoding="utf-8")

    log = DEPLOY_DIR / "DEPLOY_LOG.md"
    if not log.exists():
        log.write_text("# 部署记录\n\n| 时间 | 版本 | 结果 |\n| --- | --- | --- |\n", encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"| {stamp} | {version} | 成功 |\n")
    _info(f"已部署到 {target.relative_to(ROOT)}，当前线上版本 = {version}")


# --------------------------------------------------------------------------
# 流水线编排
# --------------------------------------------------------------------------


def run_pipeline(ci_only: bool, force_install: bool, bug_injected: bool) -> int:
    steps = [
        ("1. checkout   拉取代码", lambda: stage_checkout()),
        ("2. install    安装依赖", lambda: stage_install(force_install)),
        ("3. lint       静态检查", lambda: stage_lint()),
        ("4. test       运行测试", lambda: stage_test()),
    ]
    if not ci_only:
        steps.append(("5. build      构建产物", lambda: stage_build()))
        steps.append(("6. deploy     部署上线", lambda: stage_deploy(ctx["version"])))

    _banner(f"CI/CD 流水线启动  {'[含故意注入的 bug]' if bug_injected else ''}")
    print(f"  触发事件: push to main      开始时间: {datetime.now():%H:%M:%S}")

    results: list[tuple[str, str, float]] = []
    ctx = {"version": "unknown"}

    for name, fn in steps:
        print(f"\n  --- STAGE {name} ---")
        t0 = time.perf_counter()
        try:
            out = fn()
            if name.startswith("5."):
                ctx["version"] = out
            elapsed = time.perf_counter() - t0
            results.append((name, "OK  ", elapsed))
            print(f"  [ OK ] {name.split('.')[0]} 完成，耗时 {elapsed:.2f}s")
        except StageError as e:
            elapsed = time.perf_counter() - t0
            results.append((name, "FAIL", elapsed))
            print(f"  [FAIL] {name.split('.')[0]} 失败，耗时 {elapsed:.2f}s")
            print(f"         原因: {e}")
            _summary(results, failed=True)
            print(
                "\n  流水线已中止 —— 后续阶段没有执行。\n"
                "  这就是 CI 的意义：坏代码在这里被拦下，永远到不了 deploy。\n"
            )
            return 1

    _summary(results, failed=False)
    print("\n  流水线全部通过 —— 代码已自动发布。这就是 CD。\n")
    return 0


def _summary(results, failed: bool) -> None:
    _banner("流水线汇总")
    print(f"  {'阶段':<22}{'结果':<8}{'耗时'}")
    for name, status, elapsed in results:
        print(f"  {name:<22}{status:<8}{elapsed:.2f}s")
    for name, status, _ in results:
        if status == "FAIL":
            print(f"\n  失败阶段: {name}")
            break
    print(f"\n  结论: {'失败 (exit 1)' if failed else '成功 (exit 0)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="本地 CI/CD 流水线模拟器")
    ap.add_argument("--ci-only", action="store_true", help="只跑 CI，不做构建和部署")
    ap.add_argument("--force-install", action="store_true", help="强制重新安装依赖")
    ap.add_argument("--inject-bug", action="store_true", help="注入一个 bug 演示 CI 拦截")
    args = ap.parse_args()

    if not args.inject_bug:
        return run_pipeline(args.ci_only, args.force_install, False)

    original = BUG_FILE.read_text(encoding="utf-8")
    if GOOD_CODE not in original:
        print("[!] 找不到可注入的位置，请检查 src/pricing.py")
        return 2
    print("\n  >>> 模拟一次“带 bug 的提交”：把 5% 折扣错写成 50% <<<")
    BUG_FILE.write_text(original.replace(GOOD_CODE, BAD_CODE), encoding="utf-8")
    try:
        return run_pipeline(args.ci_only, args.force_install, True)
    finally:
        BUG_FILE.write_text(original, encoding="utf-8")
        print("  >>> 演示结束，src/pricing.py 已自动还原 <<<")


if __name__ == "__main__":
    sys.exit(main())
