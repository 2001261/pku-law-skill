#!/usr/bin/env python3
"""skill 自更新：检查公开仓库是否有新版本，有则覆盖本地版本。

每天首次使用本 skill 前先运行：
    python3 scripts/update.py

要求本 skill 通过 git clone 安装：
    git clone https://github.com/2001261/pku-law-skill.git pku-law

更新策略：以公开仓库为唯一权威版本，本地改动一律被覆盖（git reset --hard），
保证任何历史遗留内容（包括误发的旧版本）都会被干净版本替换。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/2001261/pku-law-skill.git"


def _git(*args: str) -> str:
    r = subprocess.run(
        ["git", *args], cwd=SKILL_ROOT, capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {r.stderr.strip()}")
    return r.stdout.strip()


def main() -> int:
    if not (SKILL_ROOT / ".git").exists():
        print("[!] 当前 skill 不是 git clone 安装，无法自更新。")
        print(f"    请改用 clone 安装：git clone {REPO_URL} pku-law")
        return 0

    try:
        _git("fetch", "origin")
    except RuntimeError as e:
        print(f"[!] 无法连接远端仓库，跳过更新（{e}）。")
        return 0  # 网络问题不阻断当日使用

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "main"
    local = _git("rev-parse", "HEAD")
    remote = _git("rev-parse", f"origin/{branch}")

    if local == remote:
        print(f"[✓] 已是最新版本 ({local[:8]})。")
        return 0

    print(f"[i] 发现新版本 {local[:8]} → {remote[:8]}，覆盖本地版本……")
    _git("reset", "--hard", f"origin/{branch}")
    print("[✓] 更新完成，本地旧版本已被覆盖。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
