---
name: pku-law
description: 北大法宝 MCP 积分助手：每日签到领取积分、积分余额管理（浏览器自动化，不含任何非公开接口）
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
├── requirements.txt      # Python 依赖（playwright）
└── scripts/
    ├── update.py                    # 自更新（每天首次使用前运行）
    ├── check_no_private_material.py # 泄露防护检查
    └── claim_daily_points.py        # 每日签到领取积分 + 余额查看（浏览器自动化）
```

---

## 一、每日签到领取积分

`scripts/claim_daily_points.py` 用 Playwright 拉起真实浏览器打开官方积分页
[console/points](https://mcp.pkulaw.com/console/points)，模拟你本人点击「领取」——
不调用任何非公开接口，登录态就是你浏览器里的登录态。

```bash
pip install -r requirements.txt
playwright install chromium

# 首次运行：在弹出的浏览器窗口里手动登录一次法宝账号
python3 scripts/claim_daily_points.py

# 登录态保存后（~/.pkulaw/browser-profile），可无头运行，适合定时任务
python3 scripts/claim_daily_points.py --headless

# 只查看积分余额，不执行领取
python3 scripts/claim_daily_points.py --status

# 自动点击失效时（官方页面改版），退回纯手动模式
python3 scripts/claim_daily_points.py --manual
```

脚本执行后会顺带打印页面上的积分余额信息。
定时签到可自行配置系统定时任务（cron / 任务计划程序），每天执行一次即可。

---

## 二、积分余额管理

- 领取后脚本会打印余额；随时查看可打开
  [console/points](https://mcp.pkulaw.com/console/points) 页面。
- 积分用途：官方法宝 MCP 检索按次消耗积分，余额不足时回到该页面领取次日积分。
- Access Token 的获取/新建在官方页面
  [console/apps](https://mcp.pkulaw.com/console/apps) 自助完成。
