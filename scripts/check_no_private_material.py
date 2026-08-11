#!/usr/bin/env python3
"""泄露防护检查：扫描本仓库，发现私有密钥/逆向实现特征串即报错退出。

本地与 CI 共用：
    python3 scripts/check_no_private_material.py

任何提交前必须通过本检查；GitHub Actions 也会在每次 push 时运行。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 私有密钥 / 逆向实现特征串（历史上曾误入公开渠道，永不入库）
FORBIDDEN = [
    "kDGFD+T2Ch3icUXS0o2XDA",      # Sign AES-192 key
    "DYgjCEIMVrj2W9xN",            # Sign AES IV
    "PKULAW-MBIOLE-APPLICATION",   # Sign HMAC key
    "5485693214587452",            # 登录页 AES IV
    "compute_sign",
    "_aes_encrypt_password",
    "check-username-login",
    "PkulawClient",
    "get_article(",
]

TEXT_SUFFIXES = {".md", ".py", ".json", ".txt", ".toml", ".cfg", ".yaml", ".yml"}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
# 本检查脚本自身包含特征串清单，豁免
SKIP_FILES = {Path(__file__).resolve()}


def main() -> int:
    offenders: list[str] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or path.resolve() in SKIP_FILES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in FORBIDDEN:
            if needle in text:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}: 含禁止串 {needle!r}"
                )
    if offenders:
        print("[✗] 发现私有/逆向痕迹，禁止发布：")
        print("\n".join(offenders))
        return 1
    print("[✓] 未发现私有密钥或逆向实现痕迹。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
