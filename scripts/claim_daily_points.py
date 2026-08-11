#!/usr/bin/env python3
"""北大法宝 MCP 每日积分领取助手（浏览器登录 + 官方 Web API）。

工作原理（混合架构）：
  1. 用 Playwright 拉起真实浏览器完成登录（首次手动，会话存本地 profile 复用）；
  2. 从浏览器页面 localStorage 中读取网页前端自己保存的 wso2_token；
  3. 用 requests 携带该 token 调用积分接口（与网页前端完全一致的
     官方 Web API，返回 JSON）。不含任何密钥、密码加密或签名算法。

依赖：
    pip install playwright requests
    playwright install chromium

用法：
    python3 scripts/claim_daily_points.py            # 领取今日积分（首次登录用）
    python3 scripts/claim_daily_points.py --headless # 无头模式（需已登录过）
    python3 scripts/claim_daily_points.py --status   # 只查看积分余额
    python3 scripts/claim_daily_points.py --manual   # 只打开页面，完全手动操作
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

POINTS_URL = "https://mcp.pkulaw.com/console/points"
GATEWAY = "https://gateway.pkulaw.com"

SKILL_ROOT = Path(__file__).resolve().parents[1]
# 登录态（浏览器 profile）保存在 skill 目录下管理，已 gitignore，不会入库
DEFAULT_PROFILE = SKILL_ROOT / "data" / "browser-profile"
_LEGACY_PROFILE = Path.home() / ".pkulaw" / "browser-profile"

# 页面文案为启发式匹配，仅用于判定登录态；官方页面改版后可能需要调整
CLAIM_PATTERN = re.compile(r"领取|签到|claim", re.I)
DONE_PATTERN = re.compile(r"已领取|已签到|明日|明天|claimed", re.I)
LOGIN_BTN_PATTERN = "登录/注册"  # 纯字符串匹配；get_by_role 对含 \s 的正则序列化有兼容问题


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class PointsApi:
    """与网页前端一致的积分接口（Bearer token 鉴权，JSON 返回）。"""

    def __init__(self, token: str):
        import requests

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })

    def _call(self, method: str, path: str) -> dict:
        r = self.session.request(method, f"{GATEWAY}{path}", timeout=30)
        if r.status_code == 401:
            raise ApiError("token 已过期（401）", status=401)
        try:
            payload = r.json()
        except Exception:
            raise ApiError(f"非 JSON 响应 HTTP {r.status_code}: {r.text[:200]}",
                           status=r.status_code)
        if r.status_code >= 400:
            raise ApiError(f"HTTP {r.status_code}: {str(payload)[:200]}",
                           status=r.status_code)
        return payload

    def daily(self) -> dict:
        """每日领取状态。data.state: CLAIMABLE | CLAIMED | ENDED"""
        return self._call("GET", "/api-portal/rewards/daily").get("data") or {}

    def claim(self) -> dict:
        return self._call("POST", "/api-portal/rewards/daily/claim").get("data") or {}

    def overview(self) -> dict:
        return self._call("GET", "/api-portal/points/overview").get("data") or {}


# ── 浏览器侧：登录态与 token 提取 ─────────────────────────────────

def _visible_buttons(page, pattern):
    """返回页面上文本匹配 pattern 的可见按钮/链接。"""
    found = []
    for loc in (page.get_by_role("button", name=pattern),
                page.get_by_role("link", name=pattern)):
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


def _is_logged_out(page) -> bool:
    """未登录判定：URL 在 CAS 登录域，或页面上存在「登录/注册」按钮。"""
    if "cas.pkulaw.com" in page.url:
        return True
    return bool(_visible_buttons(page, LOGIN_BTN_PATTERN))


def probe(page, timeout_s: int = 30) -> str:
    """轮询判定页面状态，返回 'logged_out' / 'points' / 'unknown'。

    SPA 未渲染完时骨架页只有「正在加载」，两种特征都没有，必须轮询等待。
    """
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if _is_logged_out(page):
            return "logged_out"
        if _visible_buttons(page, CLAIM_PATTERN) or DONE_PATTERN.search(_page_text(page)):
            return "points"
        page.wait_for_timeout(1000)
    return "unknown"


def wait_for_login(page, timeout_s: int = 300) -> None:
    """未登录时引导用户在浏览器里完成登录，轮询等待登录成功。"""
    # 自动点一下「登录/注册」，把登录表单拉出来，减少用户操作
    for btn in _visible_buttons(page, LOGIN_BTN_PATTERN):
        try:
            btn.click()
            break
        except Exception:
            continue
    print("[!] 未登录，请在浏览器窗口中完成法宝账号登录……")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        page.wait_for_timeout(3000)
        if not _is_logged_out(page):
            print("[✓] 登录成功，会话已保存，以后可复用。")
            return
    raise TimeoutError("等待登录超时（5 分钟）")


def extract_token(page, timeout_s: int = 15) -> str | None:
    """从页面 localStorage 读取网页前端保存的 wso2_token（JSON 包装，取 data 字段）。"""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        raw = page.evaluate("localStorage.getItem('wso2_token')")
        if raw:
            try:
                token = json.loads(raw).get("data")
            except (json.JSONDecodeError, AttributeError):
                token = raw if raw.startswith("eyJ") else None
            if token:
                return token
        page.wait_for_timeout(1000)
    return None


# ── 业务流程 ────────────────────────────────────────────────────

# 积分概览中值得每日关注的核心字段（其余字段太啰嗦，不逐日打印）
_OVERVIEW_KEYS = [
    ("remainingPoints", "剩余积分"),
    ("remainingAmountYuan", "折合金额(元)"),
    ("monthConsumePoints", "本月已消耗"),
    ("monthCallTimes", "本月调用次数"),
    ("expiringSoonPoints", "即将过期积分"),
    ("expireInDays", "过期倒计时(天)"),
]


def print_overview(api: PointsApi) -> None:
    try:
        data = api.overview()
    except ApiError as e:
        print(f"[!] 积分概览获取失败：{e}")
        return
    if not data:
        print("[i] 积分概览为空。")
        return
    picked = [(label, data[key]) for key, label in _OVERVIEW_KEYS if key in data]
    if picked:
        print("[i] 积分概览：")
        for label, value in picked:
            print(f"    {label}: {value}")
    else:
        # 字段结构变化时退化为完整输出，便于排查
        print("[i] 积分概览（原始返回）：")
        print(json.dumps(data, ensure_ascii=False, indent=2))


def run_claim_flow(page) -> int:
    """提取 token → 查状态 → 按需领取 → 打印余额。token 过期则刷新页面重取一次。"""
    token = extract_token(page)
    if not token:
        print("[✗] 未能从页面读取 wso2_token，请改用 --manual 手动领取。")
        return 1

    api = PointsApi(token)
    for attempt in (1, 2):
        try:
            daily = api.daily()
            break
        except ApiError as e:
            if e.status == 401 and attempt == 1:
                print("[i] token 过期，刷新页面重新获取……")
                page.reload(wait_until="domcontentloaded")
                token = extract_token(page)
                if not token:
                    print("[✗] 刷新后仍无法读取 token，请不带 --headless 重新登录。")
                    return 1
                api = PointsApi(token)
            else:
                print(f"[✗] 查询每日状态失败：{e}")
                return 1

    state = str(daily.get("state") or "").upper()
    if state == "CLAIMED":
        print("[i] 今日已领取过，无需重复操作。")
    elif state == "ENDED":
        print("[i] 每日领取活动已结束（ENDED）。")
    elif state == "CLAIMABLE":
        try:
            result = api.claim()
        except ApiError as e:
            print(f"[✗] 领取失败：{e}")
            return 1
        if result.get("alreadyClaimed"):
            print("[i] 今日已领取过（接口幂等确认）。")
        else:
            print("[✓] 领取成功。")
            if result:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[!] 未知状态 {state!r}，原始返回：{json.dumps(daily, ensure_ascii=False)[:300]}")

    print_overview(api)
    return 0


def run_status_flow(page) -> int:
    token = extract_token(page)
    if not token:
        print("[✗] 未能从页面读取 wso2_token。")
        return 1
    print_overview(PointsApi(token))
    return 0


def _migrate_profile(profile: Path) -> None:
    """一次性迁移：旧默认位置（~/.pkulaw/browser-profile）的会话搬到 skill 目录。"""
    if profile.exists() or not _LEGACY_PROFILE.exists():
        return
    import shutil

    profile.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_LEGACY_PROFILE, profile)
    print(f"[i] 已将登录态从 {_LEGACY_PROFILE} 迁移到 {profile}")


def main() -> int:
    parser = argparse.ArgumentParser(description="北大法宝 MCP 每日积分领取（浏览器登录 + 官方 Web API）")
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

    if args.profile == DEFAULT_PROFILE:
        _migrate_profile(args.profile)
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

            state = probe(page)  # 轮询等 SPA 渲染后判定登录态

            if state == "logged_out":
                if args.headless:
                    print("[✗] 无头模式下未登录。请先不带 --headless 运行一次完成登录。")
                    return 1
                wait_for_login(page)

            if args.manual:
                print("[i] 已打开积分页，请手动领取。关闭浏览器窗口结束。")
                page.wait_for_event("close", timeout=0)
                return 0

            if args.status:
                return run_status_flow(page)
            return run_claim_flow(page)
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
