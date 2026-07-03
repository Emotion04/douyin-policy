# 抖音小灵通 · GitHub Actions 版 计划书

> 创建于 2026/07/03 · 基于 Douyin-Policy-Pro 的纯 API 分支

## 架构

```
GitHub Actions Cron (周一/四 9:00)
  ├── 8路 API curl 并行抓取 → data/*.json
  ├── Python analyze.py 解析/过滤/去重/分级
  ├── 推送飞书 + 企微（低优先→高优先）
  ├── 更新 seen.json → git commit 回仓库
  └── ❌ 无 WebBridge 降级
```

## 与 Windows 版关系

| | Windows Pro | GitHub |
|--|:--:|:--:|
| 运行环境 | Win 本机 | Ubuntu runner |
| WebBridge降级 | ✅ | ❌ |
| @触发 | ❌ | ❌ |
| 定时 | 待实现 | ✅ cron |
| 推送飞书 | ✅ | ✅ |
| 推送企微 | 待实现 | ✅ |
| seen.json | 本地 | 仓库内持久化 |

## 进度

- [x] 项目框架搭建
- [x] GitHub Action workflow (policy-cron.yml)
- [x] analyze.py 核心脚本
- [x] config.example.json
- [x] .gitignore
- [ ] init git repo + push to GitHub
- [ ] 配置 GitHub Secrets
- [ ] 首次手动触发测试
- [ ] 确认飞书/企微推送正常
- [ ] 补 WebSearch 步骤到 workflow

## 安全注意事项

- 仓库必须 **Private**
- webhook URL 只能放 Secrets
- config.example.json 仅做格式参考
