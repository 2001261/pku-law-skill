# pku-law Skill

北大法宝 MCP 积分助手：每日签到领取积分 + 积分余额管理
（浏览器负责登录态，操作走与网页前端一致的官方 Web API）。

## 目录结构

```
pku-law/
├── SKILL.md              # 使用指南（主文档）
├── README.md             # 本文件
├── requirements.txt      # Python 依赖（playwright、requests）
├── scripts/
│   ├── update.py                    # 自更新（每天首次使用前运行）
│   ├── check_no_private_material.py # 泄露防护检查
│   └── claim_daily_points.py        # 每日签到领取积分 + 余额查看
└── data/
    └── browser-profile/  # 登录态（浏览器 profile，自动生成，gitignore 不入库）
```

## 使用方式

```bash
pip install -r requirements.txt && playwright install chromium
python3 scripts/claim_daily_points.py   # 首次在弹出窗口中手动登录一次
```

详见 `SKILL.md`。法规/案例检索不在本 skill 范围内，请使用北大法宝官方 MCP。

## 说明

- 本工具仅供学习和研究使用，请遵守北大法宝服务条款。
- 全部内容均可公开，不含账号、密钥等敏感信息；也不要将个人账号配置放入本目录。
