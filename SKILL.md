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
└── data/
    └── browser-profile/  # 登录态（浏览器 profile，自动生成，gitignore 不入库）
```

---

## 一、每日签到领取积分

`scripts/claim_daily_points.py` 采用混合架构：

1. **浏览器只负责登录**——用 Playwright 拉起真实浏览器，首次手动登录一次法宝账号，
   会话保存在 skill 目录下的 `data/browser-profile/`（已 gitignore，不入库）后复用；
2. **操作走官方 Web API**——从页面 localStorage 读取网页前端自己保存的访问令牌，
   用 requests 调用积分接口（与网页前端完全一致），返回结构化 JSON。

不模拟点击、不怕页面文案改版，不含任何密钥、密码加密或签名算法。

```bash
pip install -r requirements.txt
playwright install chromium

# 首次运行：在弹出的浏览器窗口里手动登录一次法宝账号
python3 scripts/claim_daily_points.py

# 登录态保存后，可无头运行，适合定时任务
python3 scripts/claim_daily_points.py --headless

# 只查看积分余额，不执行领取
python3 scripts/claim_daily_points.py --status

# 自动流程失效时，退回纯手动模式
python3 scripts/claim_daily_points.py --manual
```

脚本执行后会打印积分概览（剩余积分、本月消耗、过期倒计时等）。
定时签到可自行配置系统定时任务（cron / 任务计划程序），每天执行一次即可。

---

## 二、积分余额管理

- 领取后脚本会打印余额；随时查看可打开
  [console/points](https://mcp.pkulaw.com/console/points) 页面。
- 积分用途：官方法宝 MCP 检索按次消耗积分，余额不足时回到该页面领取次日积分。
- Access Token 的获取/新建在官方页面
  [console/apps](https://mcp.pkulaw.com/console/apps) 自助完成。
