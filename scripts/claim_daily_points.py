#!/usr/bin/env python3
"""北大法宝 MCP 每日积分领取助手（浏览器自动化）。

原理：用 Playwright 拉起真实浏览器，打开官方积分页
https://mcp.pkulaw.com/console/points ，模拟用户本人点击「领取」。
全程不调用任何非公开接口、不含任何密钥或签名算法——
登录态就是用户自己在浏览器里的登录态。

首次使用：在弹出的浏览器窗口中手动登录一次法宝账号，
会话会保存在本地浏览器 profile（默认 ~/.pkulaw/browser-profile），
之后即可复用，可配合 --headless 无人值守运行。

依赖：
    pip install playwright
    playwright install chromium

用法：
    python3 scripts/claim_daily_points.py            # 自动领取（首次登录用）
    python3 scripts/claim_daily_points.py --headless # 无头模式（需已登录过）
    python3 scripts/claim_daily_points.py --status   # 只查看积分余额
    python3 scripts/claim_daily_points.py --manual   # 只打开页面，完全手动操作
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

POINTS_URL = "https://mcp.pkulaw.com/console/points"
DEFAULT_PROFILE = Path.home() / ".pkulaw" / "browser-profile"

# 页面文案为启发式匹配，官方页面改版后可能需要调整
CLAIM_PATTERN = re.compile(r"领取|签到|claim", re.I)
DONE_PATTERN = re.compile(r"已领取|已签到|明日|明天|claimed", re.I)
SUCCESS_PATTERN = re.compile(r"成功|已领取|success", re.I)


def _visible_buttons(page, pattern):
    """返回页面上文本匹配 pattern 的可见按钮（含 button/链接/可点击元素）。"""
    locators = [
        page.get_by_role("button", name=pattern),
        page.get_by_role("link", name=pattern),
    ]
    found = []
    for loc in locators:
        for i in range(loc.count()):
            el = loc.nth(i)
            try:
                if el.is_visible() and el.is_enabled():
                    found.append(el)
            except Exception:
                continue
    return found


def _page_text(page) -> str:
    try:
        return page.inner_text("body", timeout=5000)
    except Exception:
        return ""


BALANCE_PATTERN = re.compile(r"(余额|当前积分|积分|points?|balance)\s*[:：]?\s*(\d[\d,]*)", re.I)


def print_balance(page) -> None:
    """从积分页文本中启发式提取并打印积分余额信息。"""
    text = _page_text(page)
    seen = set()
    found = False
    for m in BALANCE_PATTERN.finditer(text):
        label, num = m.group(1), m.group(2)
        if (label, num) in seen:
            continue
        seen.add((label, num))
        print(f"[i] {label}: {num}")
        found = True
    if not found:
        print("[i] 未能从页面解析余额数字，可打开 console/points 页面查看。")


def wait_for_login(page, timeout_ms: int = 300_000) -> None:
    """等待用户在浏览器里完成登录并进入 console 页面。"""
    if "cas.pkulaw.com" in page.url or "/auth/" in page.url:
        print("[!] 检测到未登录，请在浏览器窗口中登录法宝账号……")
        page.wait_for_url(re.compile(r"mcp\.pkulaw\.com"), timeout=timeout_ms)
        print("[✓] 登录成功，会话已保存，以后可复用。")
    if "/console/points" not in page.url:
        page.goto(POINTS_URL, wait_until="domcontentloaded")


def claim(page) -> str:
    """执行领取，返回 claimed / already / manual-needed。"""
    page.goto(POINTS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)  # 等待 SPA 渲染

    text = _page_text(page)
    if DONE_PATTERN.search(text) and not _visible_buttons(page, CLAIM_PATTERN):
        return "already"

    buttons = _visible_buttons(page, CLAIM_PATTERN)
    if not buttons:
        return "manual-needed"

    buttons[0].click()
    page.wait_for_timeout(3000)

    text = _page_text(page)
    if SUCCESS_PATTERN.search(text) or DONE_PATTERN.search(text):
        return "claimed"
    return "manual-needed"


def main() -> int:
    parser = argparse.ArgumentParser(description="北大法宝 MCP 每日积分领取（浏览器自动化）")
    parser.add_argument("--headless", action="store_true", help="无头模式（需已登录过）")
    parser.add_argument("--manual", action="store_true", help="只打开积分页，完全手动操作")
    parser.add_argument("--status", action="store_true", help="只查看积分余额，不执行领取")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE,
                        help=f"浏览器 profile 目录（默认 {DEFAULT_PROFILE}）")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[✗] 缺少依赖，请先执行：pip install playwright && playwright install chromium")
        return 1

    args.profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(args.profile),
            headless=args.headless,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(POINTS_URL, wait_until="domcontentloaded")

            if args.headless and ("cas.pkulaw.com" in page.url or "/auth/" in page.url):
                print("[✗] 无头模式下未登录。请先不带 --headless 运行一次完成登录。")
                return 1

            if not args.headless:
                wait_for_login(page)

            if args.manual:
                print("[i] 已打开积分页，请手动领取。关闭浏览器窗口结束。")
                page.wait_for_event("close", timeout=0)
                return 0

            if args.status:
                page.wait_for_timeout(3000)
                print_balance(page)
                return 0

            result = claim(page)
            print_balance(page)
            if result == "claimed":
                print("[✓] 领取成功（或页面已确认领取）。")
                return 0
            if result == "already":
                print("[i] 今日已领取过，无需重复操作。")
                return 0
            print("[!] 未能自动定位领取按钮（官方页面可能已改版）。")
            print("    请改用 --manual 打开页面手动领取，或更新脚本中的文案匹配。")
            return 1
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
