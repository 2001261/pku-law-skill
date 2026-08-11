#!/usr/bin/env python3
"""北大法宝 MCP 每日积分领取助手（首次浏览器登录，后续免浏览器复用会话）。

工作原理：
  1. 首次运行用 Playwright 拉起真实浏览器，手动登录一次法宝账号；
  2. 从页面 localStorage 读取网页前端自己保存的 wso2_token / wso2_refresh_token，
     存入 skill 目录 data/session.json（权限 600，已 gitignore）；
  3. 后续运行不再启动浏览器：直接用 requests 携带保存的 token 调积分接口
     （与网页前端完全一致的官方 Web API，返回 JSON）；
     access_token 过期时用 refresh_token 自动换新并落盘；
  4. 会话彻底失效（refresh_token 也过期）时才再次拉起浏览器重新登录。

不含任何密钥、密码加密或签名算法。

依赖：
    pip install playwright requests
    playwright install chromium

用法：
    python3 scripts/claim_daily_points.py            # 领取今日积分
    python3 scripts/claim_daily_points.py --status   # 只查看积分余额
    python3 scripts/claim_daily_points.py --headless # 无头模式（需已登录过）
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
CLIENT_ID = "wso2"

SKILL_ROOT = Path(__file__).resolve().parents[1]
# 登录态保存在 skill 目录下管理：浏览器 profile + 会话 token，均 gitignore 不入库
DATA_DIR = SKILL_ROOT / "data"
DEFAULT_PROFILE = DATA_DIR / "browser-profile"
SESSION_FILE = DATA_DIR / "session.json"
_LEGACY_PROFILE = Path.home() / ".pkulaw" / "browser-profile"

# 页面文案为启发式匹配，仅用于判定登录态；官方页面改版后可能需要调整
CLAIM_PATTERN = re.compile(r"领取|签到|claim", re.I)
DONE_PATTERN = re.compile(r"已领取|已签到|明日|明天|claimed", re.I)
LOGIN_BTN_PATTERN = "登录/注册"  # 纯字符串匹配；get_by_role 对含 \s 的正则序列化有兼容问题


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


# ── 会话存取 ────────────────────────────────────────────────────

def load_session() -> dict | None:
    """读取 data/session.json（access_token / refresh_token），没有或损坏返回 None。"""
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        if data.get("access_token"):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def save_session(sess: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps(sess, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    try:
        SESSION_FILE.chmod(0o600)
    except OSError:
        pass


# ── 积分 API（与网页前端一致，Bearer token + JSON）────────────────

class PointsApi:
    def __init__(self, token: str):
        import requests

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })

    def _call(self, method: str, path: str, form: dict | None = None) -> dict:
        r = self.session.request(method, f"{GATEWAY}{path}", data=form, timeout=30)
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


def refresh_session(sess: dict) -> dict | None:
    """用 refresh_token 换新 access_token（网页前端同款刷新接口），成功返回新会话。"""
    if not sess.get("refresh_token"):
        return None
    import requests

    try:
        r = requests.post(
            f"{GATEWAY}/user-register/kc/refresh-token",
            data={"refresh_token": sess["refresh_token"], "client_id": CLIENT_ID},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        data = r.json().get("data") or {}
    except Exception:
        return None
    if not data.get("access_token"):
        return None
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token") or sess["refresh_token"],
    }


def api_from_session(sess: dict) -> PointsApi | None:
    """用保存的会话构造 API 客户端；access_token 过期则自动刷新并落盘。"""
    api = PointsApi(sess["access_token"])
    try:
        api.daily()  # 探测 token 是否有效
        return api
    except ApiError as e:
        if e.status != 401:
            raise
    new_sess = refresh_session(sess)
    if not new_sess:
        return None
    save_session(new_sess)
    print("[i] access_token 已用 refresh_token 自动换新。")
    return PointsApi(new_sess["access_token"])


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
            print("[✓] 登录成功，会话已保存，以后免浏览器复用。")
            return
    raise TimeoutError("等待登录超时（5 分钟）")


def _unwrap_ls_token(raw: str | None) -> str | None:
    """localStorage 中的 token 是 JSON 包装（{"data": "..."}），取 data 字段。"""
    if not raw:
        return None
    try:
        return json.loads(raw).get("data")
    except (json.JSONDecodeError, AttributeError):
        return raw if raw.startswith("eyJ") else None


def extract_session(page, timeout_s: int = 15) -> dict | None:
    """从页面 localStorage 读取 wso2_token / wso2_refresh_token，组成会话。"""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        access = _unwrap_ls_token(page.evaluate("localStorage.getItem('wso2_token')"))
        refresh = _unwrap_ls_token(page.evaluate("localStorage.getItem('wso2_refresh_token')"))
        if access:
            return {"access_token": access, "refresh_token": refresh}
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


def run_claim_flow(api: PointsApi) -> int:
    """查状态 → 按需领取 → 打印余额。"""
    try:
        daily = api.daily()
    except ApiError as e:
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


# ── 入口 ────────────────────────────────────────────────────────

def _migrate_profile(profile: Path) -> None:
    """一次性迁移：旧默认位置（~/.pkulaw/browser-profile）的会话搬到 skill 目录。"""
    if profile.exists() or not _LEGACY_PROFILE.exists():
        return
    import shutil

    profile.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_LEGACY_PROFILE, profile)
    print(f"[i] 已将浏览器登录态从 {_LEGACY_PROFILE} 迁移到 {profile}")


def _browser_login_and_extract(headless: bool) -> dict | None:
    """拉起浏览器（必要时引导手动登录），从页面提取会话 token。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[✗] 缺少依赖，请先执行：pip install playwright && playwright install chromium")
        return None

    _migrate_profile(DEFAULT_PROFILE)
    DEFAULT_PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(DEFAULT_PROFILE),
            headless=headless,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(POINTS_URL, wait_until="domcontentloaded")
            if probe(page) == "logged_out":
                if headless:
                    print("[✗] 无头模式下未登录。请先不带 --headless 运行一次完成登录。")
                    return None
                wait_for_login(page)
            return extract_session(page)
        finally:
            ctx.close()


def _open_manual_page() -> int:
    """--manual：只打开积分页，完全手动操作。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[✗] 缺少依赖，请先执行：pip install playwright && playwright install chromium")
        return 1

    _migrate_profile(DEFAULT_PROFILE)
    DEFAULT_PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(DEFAULT_PROFILE), headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(POINTS_URL, wait_until="domcontentloaded")
            if probe(page) == "logged_out":
                wait_for_login(page)
            print("[i] 已打开积分页，请手动领取。关闭浏览器窗口结束。")
            page.wait_for_event("close", timeout=0)
            return 0
        finally:
            ctx.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="北大法宝 MCP 每日积分领取（首次浏览器登录，后续免浏览器复用会话）"
    )
    parser.add_argument("--headless", action="store_true",
                        help="无头模式（仅浏览器兜底路径生效；有保存会话时无需浏览器）")
    parser.add_argument("--manual", action="store_true", help="只打开积分页，完全手动操作")
    parser.add_argument("--status", action="store_true", help="只查看积分余额，不执行领取")
    args = parser.parse_args()

    if args.manual:
        return _open_manual_page()

    # 路径一：已保存会话，免浏览器
    sess = load_session()
    if sess:
        try:
            api = api_from_session(sess)
        except ApiError as e:
            print(f"[!] 保存的会话异常（{e}），改用浏览器重新登录。")
            api = None
        if api:
            print("[i] 使用已保存的会话（免浏览器）。")
            if args.status:
                print_overview(api)
                return 0
            return run_claim_flow(api)
        print("[i] 保存的会话已失效，改用浏览器重新登录。")

    # 路径二：浏览器登录并保存会话
    sess = _browser_login_and_extract(headless=args.headless)
    if not sess:
        print("[✗] 未能获取登录会话。")
        return 1
    save_session(sess)
    api = PointsApi(sess["access_token"])
    if args.status:
        print_overview(api)
        return 0
    return run_claim_flow(api)


if __name__ == "__main__":
    sys.exit(main())
