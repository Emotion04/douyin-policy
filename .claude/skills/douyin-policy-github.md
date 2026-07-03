---
name: douyin-policy-github
description: 抖音小灵通 GitHub Actions 版 — 纯 API curl + WebSearch，无 WebBridge。定时推飞书+企微。
---

# 抖音小灵通 · GitHub Actions 版

> ✅ **纯 API 版**：所有 school.jinritemai.com 数据通过 curl HTTP JSON 获取。
> ⛔ **无 WebBridge**：GitHub runner 没有浏览器，不支持 WebBridge 降级。
> 🔍 **WebSearch 补充**：火山引擎、第三方媒体。
> 🔒 **Secrets 管理**：飞书/企微 webhook 存储在 GitHub Secrets。

## 运行方式

- **定时**：每周一、周四 北京时间 9:00（GitHub Actions cron）
- **手动**：GitHub Actions → `policy-cron` → `Run workflow`
- **本地测试**：`python3 scripts/analyze.py`

## 前置条件

1. GitHub 仓库设为 **Private**
2. Settings → Secrets → Actions 添加：
   - `FEISHU_WEBHOOK`
   - `WECOM_WEBHOOK`（可选）

## 数据源

### 官方 API（8路并行 curl）
| 来源 | node_id | 条数 |
|------|---------|------|
| 规则动态-更新公示 | 13174 | 88 |
| 规则动态-意见征集 | 13173 | 45 |
| 规则动态-规则速递 | 11689 | 247 |
| 公告专区-治理公告 | 11687 | 240 |
| 公告专区-违规公示 | 11693 | 10 |
| 公告专区-临时公告 | 11686 | 53 |
| 首页 | /rule/center/main | - |
| 带摘要规则 | rule_type=4 | 10 |

### 第三方（WebSearch）
| 来源 | 获取 |
|------|------|
| 电商报 ec100.cn | WebSearch |
| 亿邦动力 ebrun.com | WebSearch |
| DoNews donews.com | WebSearch |
| 新榜 newrank.cn | WebSearch |
| 36氪 36kr.com | WebSearch |
| 火山引擎 volcengine.com | WebSearch |

## 文件结构

```
Douyin-Policy-Github/
├── .github/workflows/policy-cron.yml   ← GitHub Action
├── scripts/analyze.py                  ← 核心处理脚本
├── data/                               ← API JSON 临时存储(gitignore)
├── seen.json                           ← 去重状态(每次commit)
├── config.example.json                 ← Secrets 模板
├── CLAUDE.md                           ← 本文件
└── plan.md                             ← 计划书
```

## 过滤规则

**跳过**：全球购、珠宝文玩、农资园艺、水产、宠物、保健品、药品、医疗器械、食品、图书、游戏、车厘子、海鲜、二奢、二手数码、即时零售

**保留**：通用规则 + 服饰/服装/牛仔

## 推送格式

- **飞书**：交互卡片（lark_md + 📎按钮），低优先→高优先
- **企微**：markdown 消息，同上顺序
