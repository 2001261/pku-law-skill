# pku-law Skill

北大法宝 MCP 积分助手：每日签到领取积分 + 积分余额管理
（浏览器负责登录态，操作走与网页前端一致的官方 Web API）。

## 目录结构

```
pku-law/
├── SKILL.md              # 使用指南（主文档）
├── README.md             # 本文件
├── requirements.txt      # Python 依赖（requests 必需，playwright 可选）
├── scripts/
│   ├── update.py                    # 自更新（每天首次使用前运行）
│   └── claim_daily_points.py        # 每日签到领取积分 + 余额查看
└── data/                 # 登录态（自动生成，gitignore 不入库）
    ├── session.json      #   会话令牌（权限 600，免浏览器复用）
    └── browser-profile/  #   浏览器 profile（首次登录/兜底用）
```

## 使用方式

```bash
pip install -r requirements.txt   # 仅 requests；Playwright 为可选依赖
# 已装 Playwright 时直接运行（首选），首次在弹出窗口中手动登录一次：
python3 scripts/claim_daily_points.py
# 无 Playwright 环境（如鸿蒙）则手动粘贴 token 登录：
python3 scripts/claim_daily_points.py --login
```

支持 Linux / macOS / Windows / 鸿蒙（Windows 上命令用 `python` 替代 `python3`；
鸿蒙环境请勿安装 playwright，用 `--login` 登录）。
详见 `SKILL.md`。法规/案例检索不在本 skill 范围内，请使用北大法宝官方 MCP。

## 说明

- 本工具仅供学习和研究使用，请遵守北大法宝服务条款。
- 全部内容均可公开，不含账号、密钥等敏感信息；也不要将个人账号配置放入本目录。

## 作者与支持

**王晶晶律师 · 四川恒和信律师事务所**

如遇到使用问题，请关注微信公众号「**隔壁王律师**」寻求帮助：

![微信公众号「隔壁王律师」二维码](docs/wechat-qr.jpg)
