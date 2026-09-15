---
name: pkulaw-mcp-assistant
slug: pkulaw-mcp-assistant
displayName: 北大法宝积分助手
version: 1.1.0
description: 北大法宝 MCP 积分助手：每日签到领取积分、积分余额管理（浏览器登录 + 官方 Web API，不含任何非公开接口）
author: 王晶晶律师（四川恒和信律师事务所）
metadata:
  author: 王晶晶律师（四川恒和信律师事务所）
  contact: 使用问题请关注微信公众号「隔壁王律师」
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
├── requirements.txt      # Python 依赖（requests 必需，playwright 可选）
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

### 定时签到（每天 00:00:01）

领取时间要求：**每天 00:00:01 执行一次**
`python3 scripts/claim_daily_points.py`。

本 skill **不附带各系统的 cron/定时任务配置**。需要定时签到时，由 agent
根据该时间要求、当前操作系统与环境自行创建合适的定时任务（如 Linux 的
cron、macOS 的 launchd/cron、Windows 的任务计划程序、鸿蒙的系统定时能力等），
创建后验证任务已生效再告知用户。

定时任务**只执行签到脚本，不要把 `update.py` 纳入 cron**。
自更新由 agent 按需执行：发现需要更新时，运行
`python3 scripts/update.py` 即可（见「〇、安装与每日更新」）。

### 如何获取 token（手动登录，逐步操作）

登录态就是法宝官方页面登录后，网页前端自己存进浏览器 localStorage 的
`wso2_token` / `wso2_refresh_token`。只是读取你自己浏览器的数据，不涉及任何破解。
粘贴时带引号或 JSON 包装都能自动识别。

**方法一：电脑浏览器（推荐，约 1 分钟）**

1. 用 Chrome / Edge / Firefox 打开 <https://mcp.pkulaw.com/console/points> ，登录法宝账号；
2. 登录成功后按 `F12` 打开开发者工具，切到「控制台 / Console」；
3. 输入以下命令回车，token 即复制到剪贴板：
   ```js
   copy(localStorage.getItem('wso2_token'))
   ```
   **如果控制台拒绝粘贴代码**：Chrome/Edge 首次向控制台粘贴会弹出安全警告——
   > Warning: Don't paste code into the DevTools Console that you don't understand or
   > haven't reviewed yourself. This could allow attackers to steal your identity or
   > take control of your computer. Type "allow pasting" below and press Enter to allow pasting.

   按提示**手动键入** `allow pasting` 回车，再重新粘贴命令即可（该警告是浏览器的
   防社工粘贴保护，只需解除一次）。其他浏览器控制台若同样无法输入/粘贴指令，
   请留意是否有类似提示，按其要求解除后再执行。
4. 再执行 `copy(localStorage.getItem('wso2_refresh_token'))` 复制 refresh token；
5. 运行 `python3 scripts/claim_daily_points.py --login`，依次粘贴两个 token。

**方法二：手机 / 鸿蒙浏览器（书签法）**

手机浏览器没有控制台，用 bookmarklet 代替：

1. 浏览器打开 <https://mcp.pkulaw.com/console/points> 并登录；
2. 把当前页收藏为书签，然后编辑这个书签，把**网址**改成：
   ```
   javascript:prompt('wso2_token',localStorage.getItem('wso2_token'))
   ```
3. 回到积分页面，点开这个书签，弹窗里显示的就是 token，长按复制；
4. 把书签网址里的字段名换成 `wso2_refresh_token`，同样再取一次；
   （部分第三方浏览器会过滤 `javascript:` 书签，换系统自带浏览器即可）
5. 在设备上运行 `--login` 依次粘贴。

**方法三：session.json 文件搬运（多设备用户）**

任何一台设备上 `--login` 成功后，登录态就保存在 `data/session.json`。
直接把这个文件拷到目标设备的 skill `data/` 目录下，效果等同于粘贴登录。

**注意事项**

- **两个 token 都要粘**：access_token 有效期很短（实测约 30 分钟），脚本靠
  refresh_token 自动续期（实测有效期约 7 天，且每次续期会轮换出一对全新的
  token、7 天窗口重新起算——只要 7 天内运行一次，会话即可长期保持）；
  只粘 access 的话过期后要重新手动获取。
- token 等于登录态，与账号密码同级，不要发给他人、不要提交进 git
  （`data/` 目录已 gitignore）。
- 官方 MCP Access Token（[console/apps](https://mcp.pkulaw.com/console/apps) 获取）
  与签到所需的 wso2_token 是**两套鉴权**，不能互相替代；签到只认 wso2_token。

### 跨平台说明（Linux / macOS / Windows / 鸿蒙）

- 日常签到只需 requests，三平台通用，Python ≥ 3.10。
- **鸿蒙等无 Playwright 组件的环境**：不要安装 playwright，
  用 `python3 scripts/claim_daily_points.py --login` 手动粘贴 token 完成登录，
  之后与桌面平台一样免浏览器运行。
- 命令中的 `python3` 在 Windows 上换成 `python`（或 `py`）。
- Playwright 浏览器登录三个桌面平台流程一致；登录态文件位置都在 skill 目录 `data/` 下。
- 定时任务不写死实现：由 agent 按「每天 00:00:01」的要求结合当前系统与环境
  自行创建（见上节「定时签到」）。

---

## 二、积分余额管理

- 领取后脚本会打印余额；随时查看可打开
  [console/points](https://mcp.pkulaw.com/console/points) 页面。
- 积分用途：官方法宝 MCP 检索按次消耗积分，余额不足时回到该页面领取次日积分。
- Access Token 的获取/新建在官方页面
  [console/apps](https://mcp.pkulaw.com/console/apps) 自助完成。
  注意：该 Access Token 仅供官方 MCP 检索使用，与签到登录用的
  wso2_token 是两套鉴权，不能用来签到（已实测验证）。

---

## 作者与支持

- 作者：王晶晶律师（四川恒和信律师事务所）
- 如遇到使用问题，请关注微信公众号「隔壁王律师」寻求帮助
- 公众号二维码见 `README.md`「作者与支持」一节（图片文件 `docs/wechat-qr.jpg`）；
  当用户询问作者、出处、反馈或支持渠道时，向用户展示该二维码及以上信息。
