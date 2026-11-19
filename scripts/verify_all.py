"""逐个运行案例的 client.py，确认 22 个案例都能从零跑通。

用法：
    uv run python scripts/verify_all.py            # 全部
    uv run python scripts/verify_all.py --only 01  # 只跑 01 篇
    uv run python scripts/verify_all.py --list     # 只列案例
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_cases(prefix: str | None = None) -> list[Path]:
    cases = sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit())
    cases = [p for p in cases if (p / "client.py").is_file()]
    if prefix:
        cases = [p for p in cases if p.name.startswith(prefix)]
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="只跑指定前缀，例如 01 / 0201")
    parser.add_argument("--list", action="store_true", help="只列出案例，不执行")
    parser.add_argument("--timeout", type=int, default=90, help="单个案例超时秒数")
    args = parser.parse_args()

    cases = find_cases(args.only)
    if not cases:
        print("没有找到带 client.py 的案例目录")
        return 1

    if args.list:
        for case in cases:
            print(case.name)
        return 0

    failures: list[tuple[str, str]] = []
    started = time.monotonic()

    for index, case in enumerate(cases, 1):
        print(f"[{index:02d}/{len(cases)}] {case.name} ... ", end="", flush=True)
        begin = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-u", "client.py"],
                cwd=case,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=args.timeout,
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            print("超时")
            failures.append((case.name, f"超过 {args.timeout}s 未结束"))
            continue

        elapsed = time.monotonic() - begin
        if proc.returncode == 0:
            print(f"OK ({elapsed:.1f}s)")
        else:
            print(f"FAIL ({elapsed:.1f}s)")
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-8:]
            failures.append((case.name, "\n".join(tail)))

    total = time.monotonic() - started
    print(f"\n通过 {len(cases) - len(failures)}/{len(cases)}，总耗时 {total:.1f}s")

    if failures:
        print("\n失败明细：")
        for name, detail in failures:
            print(f"\n--- {name} ---\n{detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
