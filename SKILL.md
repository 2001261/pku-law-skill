---
name: pku-law
description: 北大法宝 MCP 积分助手：每日签到领取积分、积分余额管理（浏览器登录 + 官方 Web API，不含任何非公开接口）
metadata:
  audience: developers
  workflow: points-management
---

## ⚠️ 重要前提

**本工具仅供学习和研究使用，请遵守北大法宝服务条款。**

本 skill 只做两件事：**每日签到领积分** 和 **查看积分余额**。
检索法规/案例等功能不在本 skill 范围内，请直接使用北大法宝官方 MCP
（[mcp.pkulaw.com](https://mcp.pkulaw.com/) / `@pkulaw/mcp-cli`），检索会消耗积分。

---

## 〇、安装与每日更新（必做）

本 skill 通过 git clone 安装，公开仓库是唯一权威版本：

```bash
git clone https://github.com/2001261/pku-law-skill.git pku-law
```

**每天首次调用本 skill 前，先运行自更新**，有新版会自动覆盖本地旧版本：

```bash
python3 scripts/update.py
```

> 该机制保证任何误发的旧版本都会被仓库中的干净版本覆盖替换。

---

## 📁 目录结构

```
pku-law/
├── SKILL.md              # 本文件（使用指南）
├── README.md             # 目录结构说明
├── requirements.txt      # Python 依赖（playwright、requests）
├── scripts/
│   ├── update.py                    # 自更新（每天首次使用前运行）
│   ├── check_no_private_material.py # 泄露防护检查
│   └── claim_daily_points.py        # 每日签到领取积分 + 余额查看
└── data/                 # 登录态（自动生成，gitignore 不入库）
    ├── session.json      #   会话令牌（权限 600，免浏览器复用）
    └── browser-profile/  #   浏览器 profile（首次登录/兜底用）
```

---

## 一、每日签到领取积分

`scripts/claim_daily_points.py` 的工作方式：

1. **登录态来自用户自己的浏览器会话**，两种获取方式：
   - `--login` 手动粘贴 `wso2_token`（任意设备任意浏览器均可，
     鸿蒙等无 Playwright 组件的环境用这种方式）；
   - 已安装 Playwright 时，自动拉起浏览器引导登录并从页面提取令牌；
2. 令牌存入 `data/session.json`（权限 600，已 gitignore）；
3. **日常运行免浏览器**：直接用 requests 携带保存的令牌调积分接口
   （与网页前端完全一致的官方 Web API，返回 JSON）；令牌过期自动换新；
4. 会话彻底失效时重新登录（再走第 1 步）。

不含任何密钥、密码加密或签名算法。

```bash
pip install -r requirements.txt   # 仅 requests；Playwright 为可选依赖
# 可选（浏览器自动登录兜底用）：pip install playwright && playwright install chromium

# 登录方式一（鸿蒙/无 Playwright 环境）：手动粘贴 token
python3 scripts/claim_daily_points.py --login

# 登录方式二（有 Playwright）：首次运行在弹出的浏览器窗口里手动登录一次
python3 scripts/claim_daily_points.py

# 之后每次运行都是免浏览器的（session.json 复用）
python3 scripts/claim_daily_points.py

# 只查看积分余额，不执行领取
python3 scripts/claim_daily_points.py --status

# 自动流程失效时，退回纯手动模式（需 Playwright）
python3 scripts/claim_daily_points.py --manual
```

脚本执行后会打印积分概览（剩余积分、本月消耗、过期倒计时等）。
定时签到可自行配置系统定时任务，每天执行一次即可。

### 跨平台说明（Linux / macOS / Windows / 鸿蒙）

- 日常签到只需 requests，三平台通用，Python ≥ 3.10。
- **鸿蒙等无 Playwright 组件的环境**：不要安装 playwright，
  用 `python3 scripts/claim_daily_points.py --login` 手动粘贴 token 完成登录，
  之后与桌面平台一样免浏览器运行。
- 命令中的 `python3` 在 Windows 上换成 `python`（或 `py`）。
- Playwright 浏览器登录三个桌面平台流程一致；登录态文件位置都在 skill 目录 `data/` 下。
- 定时任务：Linux/macOS 用 cron，Windows 用「任务计划程序」，鸿蒙用系统定时能力，
  均执行 `python3 scripts/claim_daily_points.py`（Windows 用 `python`）。

---

## 二、积分余额管理

- 领取后脚本会打印余额；随时查看可打开
  [console/points](https://mcp.pkulaw.com/console/points) 页面。
- 积分用途：官方法宝 MCP 检索按次消耗积分，余额不足时回到该页面领取次日积分。
- Access Token 的获取/新建在官方页面
  [console/apps](https://mcp.pkulaw.com/console/apps) 自助完成。
