#!/usr/bin/env python3
"""泄露防护检查：扫描本仓库，发现私有密钥/逆向实现特征串即报错退出。

本地与 CI 共用：
    python3 scripts/check_no_private_material.py

任何提交前必须通过本检查；GitHub Actions 也会在每次 push 时运行。

设计说明：真实密钥一律不以明文入库（历史上曾有脚本把密钥明文写进
检测清单导致二次泄露），清单中只保存密钥的 (长度, SHA-256) 指纹，
扫描时对文件内容做等长滑窗哈希比对，检测能力等价但不可逆推原文。
函数名等逆向特征串不是密钥，仍以明文子串匹配。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 私有密钥指纹：(密钥长度, 密钥明文的 SHA-256)。明文永不入库。
FORBIDDEN_KEY_HASHES = [
    (22, "9d3e54c9b3fe8ef74a10e15e94f853a362adb63a2c4ee3acb8b1855d913fedc1"),  # Sign AES key
    (16, "039d13bea7404f0c1323d564e1fcd801d45773ea5b16cb26fd3baa569d2e43d7"),  # Sign AES IV
    (25, "2c409f493bc14c3ea755f7f014c7a24b505b78a2ed52a5d47272c6aa9e59be5c"),  # Sign HMAC key
    (16, "74a135f1d4fad5dbb5992b5166eb54521f9f0fb597460511f869a677079d33bc"),  # 登录页 AES IV
]

# 逆向实现特征串（函数名/接口名，非密钥，明文匹配即可）
FORBIDDEN_STRINGS = [
    "compute_sign",
    "_aes_encrypt_password",
    "check-username-login",
    "PkulawClient",
    "get_article(",
]

TEXT_SUFFIXES = {".md", ".py", ".json", ".txt", ".toml", ".cfg", ".yaml", ".yml"}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
# 本检查脚本自身包含特征串清单，豁免（密钥只存哈希，不在豁免风险内）
SKIP_FILES = {Path(__file__).resolve()}


def _contains_forbidden_key(text: str) -> bool:
    """对文本做等长滑窗 SHA-256 比对，命中任一密钥指纹即返回 True。"""
    for length, digest in FORBIDDEN_KEY_HASHES:
        if len(text) < length:
            continue
        for i in range(len(text) - length + 1):
            if hashlib.sha256(text[i:i + length].encode("utf-8")).hexdigest() == digest:
                return True
    return False


def main() -> int:
    # Windows 控制台默认 GBK，输出 ✓/✗ 会 UnicodeEncodeError，强制 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

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
        rel = path.relative_to(REPO_ROOT)
        for needle in FORBIDDEN_STRINGS:
            if needle in text:
                offenders.append(f"{rel}: 含禁止特征串 {needle!r}")
        if _contains_forbidden_key(text):
            offenders.append(f"{rel}: 含私有密钥（指纹命中）")
    if offenders:
        print("[✗] 发现私有/逆向痕迹，禁止发布：")
        print("\n".join(offenders))
        return 1
    print("[✓] 未发现私有密钥或逆向实现痕迹。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
