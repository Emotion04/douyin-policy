# 抖音小灵通 · GitHub Actions 版

抖音电商规则变更情报采集与分析系统——纯 API 版，跑在 GitHub Actions 上。面向服饰/牛仔商家。

## 核心需求

1. **定时采集**：每周一、周四 9:00 自动抓取抖音电商规则变更
2. **多渠道推送**：飞书 + 企微（同事微信接收）
3. **去重过滤**：seen.json 持久化，不重复推送
4. **隐私安全**：webhook 存 GitHub Secrets，仓库 Private

## 文件结构

```
D:\WCode\Douyin-Policy-Github\
├── .github/workflows/policy-cron.yml   ← GA cron: 周一/四 9:00 + workflow_dispatch
├── scripts/analyze.py                  ← 解析JSON → 过滤 → 去重分级 → 推送飞书/企微
├── .claude/skills/douyin-policy-github.md ← skill 文件
├── seen.json                           ← 去重状态（每次运行 commit 回仓库）
├── config.example.json                 ← Secrets 格式参考（勿放真实值）
├── .gitignore                          ← 排除 data/ 临时文件
└── plan.md                             ← 计划书
```

## 运行方式

| 方式 | 操作 |
|------|------|
| **定时** | 自动，周一/四 UTC 1:00 |
| **手动触发** | GitHub → Actions → policy-cron → Run workflow |
| **本地测试** | `python3 scripts/analyze.py`（需先手动跑 curl 抓 data/） |
| **本地测试周回顾** | `python3 scripts/analyze.py --recap` |

### 运行模式

| 模式 | 触发 | 去重 | 标记 |
|------|------|:--:|------|
| **常规** | 周一/四 9:00 | ✅ | 🆕新增 📌已追踪 |
| **周回顾** | 周日 10:00 | ❌ | 📋 本周回顾 |
| **心跳** | 无新增时自动 | — | 📭 暂无变更 |
| **手动** | workflow_dispatch 可选 recap | 默认✅ | — |

## 与 Windows 版（Douyin-Policy-Pro）的关系

| | Windows 版 | GitHub 版（本仓库） |
|------|:--:|:--:|
| 运行环境 | Windows 本机 | Ubuntu runner |
| 触发 | `/douyin-policy-pro` 手动 | Cron 定时 |
| WebBridge 降级 | ✅ | ❌ |
| seen.json | 本地磁盘 | 仓库内 git 持久化 |
| 推送 | 飞书 | 飞书 + 企微 |

## 工作流程

```
GitHub Actions Cron 触发
  → 8路 curl 并行抓取 API JSON → data/*.json
  → python3 analyze.py
      ├─ 解析 8 个 JSON
      ├─ 过滤（跳过无关行业）
      ├─ 去重（交叉 seen.json）
      ├─ 分级（P1/P2/P3）
      ├─ 推送飞书 低→高（P3→P2→P1）
      ├─ 推送企微 同上
      └─ 更新 seen.json
  → git commit seen.json → push
```

## 核心 API（school.jinritemai.com，无需认证）

| 子分类 | node_id | API Path | 条数 | 优先级 |
|--------|---------|----------|------|:--:|
| 更新公示 | 13174 | `/api/eschool/v2/library/article/list?node_id=13174&page_size=10` | 88 | P1 |
| 意见征集 | 13173 | `/api/eschool/v2/library/article/list?node_id=13173&page_size=10` | 45 | P2 |
| 规则速递 | 11689 | `/api/eschool/v2/library/article/list?node_id=11689&page_size=10` | 247 | P3 |
| 治理公告 | 11687 | `/api/eschool/v2/library/article/list?node_id=11687&page_size=10` | 240 | P1 |
| 违规公示 | 11693 | `/api/eschool/v2/library/article/list?node_id=11693&page_size=10` | 10 | P2 |
| 临时公告 | 11686 | `/api/eschool/v2/library/article/list?node_id=11686&page_size=10` | 53 | P2 |
| 首页 | — | `/api/eschool/v1/rule/center/main?new_rule_num=6&violation_num=6` | — | P2 |
| 带摘要 | — | `/api/eschool/v1/rule/list?rule_type=4&page=1&page_size=10` | 10 | P3 |

返回字段：`articles[].id, title, create_at, update_at, extra_tags(["新增"|"更新"])`

## 优先级体系

| 级别 | 来源 | 含义 |
|:---:|------|------|
| P1 | 更新公示 + 治理公告 | 确认变更，一定生效 |
| P2 | 意见征集 + 违规/临时公告 + 首页公告 | 提案或通知类 |
| P3 | 规则速递 + 最新规则 | 规则原文，看不到变化细节 |

## 推送策略

- **顺序**：低优先→高优先（P3→P2→P1，最重要的出现在聊天底部）
- **飞书**：交互卡片（lark_md + 📎按钮），每条间隔 3 秒
- **企微**：markdown 文本，10 条/消息封顶
- 0 条则跳过该级别

## 过滤规则

**直接跳过**：全球购、珠宝文玩、农资园艺、水产、宠物、保健品、药品、医疗器械、食品、图书、游戏、车厘子、海鲜、二奢、二手数码、即时零售

**保留**：商家/创作者/消费者/发货/退款/保证金/体验分/虚假宣传/违规/治理/平台 + 服饰/服装/牛仔

## Secrets 配置

GitHub 仓库 → Settings → Secrets and variables → Actions：

| Secret | 说明 |
|--------|------|
| `FEISHU_WEBHOOK` | 飞书机器人 webhook URL |
| `WECOM_WEBHOOK` | 企微机器人 webhook URL |

## 隐私与限制

- 仓库必须为 **Private**（否则 webhook 可通过 Actions 日志泄露）
- Free plan 私有仓库：**2000 分钟/月** Actions，本项目 ~3 分钟/次 × 8 次/月 ≈ 24 分钟，完全够用
- API 一路失败不影响其他路，失败的在推送中标注 ⚠️
