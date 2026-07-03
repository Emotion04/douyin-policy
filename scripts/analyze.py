#!/usr/bin/env python3
"""抖音小灵通 GitHub Actions 版 — 数据处理 + 推送"""

import json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEEN_FILE = ROOT / "seen.json"

# ============================================================
# 配置
# ============================================================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
WECOM_WEBHOOK = os.environ.get("WECOM_WEBHOOK", "")

SKIP_KEYWORDS = [
    "全球购", "珠宝文玩", "农资园艺", "水产", "宠物", "保健品",
    "药品", "医疗器械", "食品", "图书", "游戏", "车厘子", "海鲜",
    "二奢", "二手数码", "即时零售", "滋补", "文玩"
]

KEEP_KEYWORDS = [
    "商家", "创作者", "消费者", "发货", "退款", "保证金", "体验分",
    "虚假宣传", "违规", "治理", "平台", "服饰", "服装", "牛仔",
    "运费", "材质", "成分", "面料", "三包"
]

SOURCE_LABELS = {
    "13174": "规则动态-更新公示",
    "13173": "规则动态-意见征集",
    "11689": "规则动态-规则速递",
    "11687": "公告专区-治理公告",
    "11693": "公告专区-违规公示",
    "11686": "公告专区-临时公告",
}

PRIORITY = {
    "13174": "P1",   # 更新公示
    "11687": "P1",   # 治理公告
    "13173": "P2",   # 意见征集
    "11693": "P2",   # 违规公示
    "11686": "P2",   # 临时公告
    "11689": "P3",   # 规则速递
    "main": "P2",    # 首页公告
}

# ============================================================
# 工具函数
# ============================================================

def load_seen():
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": "", "articles": {}}

def save_seen(data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def should_skip(title):
    for kw in SKIP_KEYWORDS:
        if kw in title:
            return True
    return False

def should_keep(title):
    for kw in KEEP_KEYWORDS:
        if kw in title:
            return True
    return False

def parse_api_file(filepath):
    """解析 API JSON 文件，提取条目列表"""
    if not filepath.exists():
        return [], False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return [], False

    articles = []
    # /api/eschool/v2/library/article/list 格式
    if "data" in data and "articles" in data.get("data", {}):
        for a in data["data"]["articles"]:
            articles.append({
                "id": str(a.get("id", "")),
                "title": a.get("title", ""),
                "date": (a.get("update_at") or a.get("create_at", ""))[:10],
                "tags": a.get("extra_tags", []),
                "view_count": a.get("view_count", 0),
            })
    # rule_type=4 格式
    elif "data" in data and "rule_infos" in data.get("data", {}):
        for r in data["data"]["rule_infos"]:
            articles.append({
                "id": str(r.get("knowledge_id", "")),
                "title": r.get("title", ""),
                "date": (r.get("update_time") or r.get("effect_start", ""))[:10],
                "summary": r.get("summary", ""),
                "status_code": r.get("status_code", ""),
            })
    # 首页格式
    elif "data" in data:
        d = data["data"]
        # new_rules
        if "new_rules" in d:
            for r in d["new_rules"]:
                articles.append({
                    "id": str(r.get("id", r.get("knowledge_id", ""))),
                    "title": r.get("title", ""),
                    "date": (r.get("update_at") or r.get("create_at", ""))[:10],
                    "source_extra": "首页-最新规则",
                })
        # violations
        if "violations" in d:
            for v in d["violations"]:
                articles.append({
                    "id": str(v.get("id", "")),
                    "title": v.get("title", ""),
                    "date": v.get("date", "")[:10],
                    "source_extra": "首页-违规公示",
                })
        # latest_rule
        if "latest_rule" in d and isinstance(d["latest_rule"], dict):
            r = d["latest_rule"]
            articles.append({
                "id": str(r.get("id", r.get("knowledge_id", ""))),
                "title": r.get("title", ""),
                "date": (r.get("update_at") or r.get("create_at", ""))[:10],
                "source_extra": "首页-最新公告",
            })

    return articles, True

# ============================================================
# 主流程
# ============================================================

def collect():
    """并行解析所有 API 数据源"""
    sources = {
        "13174": DATA / "13174.json",
        "13173": DATA / "13173.json",
        "11689": DATA / "11689.json",
        "11687": DATA / "11687.json",
        "11693": DATA / "11693.json",
        "11686": DATA / "11686.json",
        "main": DATA / "main.json",
        "rule_type_4": DATA / "rule_type_4.json",
    }

    all_entries = []
    status = {}
    for node_id, filepath in sources.items():
        articles, ok = parse_api_file(filepath)
        status[node_id] = {"ok": ok, "count": len(articles)}
        label = SOURCE_LABELS.get(node_id, node_id)
        for a in articles:
            a["node_id"] = node_id
            a["source_label"] = label
            a["priority"] = PRIORITY.get(node_id, "P3")
            a["url"] = f"https://school.jinritemai.com/doudian/web/articlev0/{a['id']}"
        all_entries.extend(articles)

    return all_entries, status

def filter_and_classify(entries, seen_data):
    """过滤 + 去重 + 分级"""
    today = datetime.now()
    cutoff = today - timedelta(days=7)
    seen_articles = seen_data.get("articles", {})

    result = {"P1": [], "P2": [], "P3": [], "OTHER": [], "SKIPPED": []}
    new_count = 0
    tracked_count = 0

    for e in entries:
        title = e.get("title", "")
        if not title:
            continue

        # 过滤
        if should_skip(title) and not ("服饰" in title or "服装" in title or "牛仔" in title):
            result["SKIPPED"].append(e)
            continue

        # 去重：用 title 匹配
        is_new = True
        for _, v in seen_articles.items():
            if v.get("title", "") == title:
                is_new = False
                break

        if is_new:
            new_count += 1
            e["status"] = "new"
        else:
            tracked_count += 1
            e["status"] = "tracked"

        # 时间分组
        try:
            d = datetime.strptime(e.get("date", "2000-01-01"), "%Y-%m-%d")
            e["is_recent"] = d >= cutoff
        except ValueError:
            e["is_recent"] = False

        # 分级
        p = e.get("priority", "P3")
        result[p].append(e)

    return result, new_count, tracked_count

def build_feishu_card(entries, header_title, template_color):
    """构建飞书消息卡片"""
    if not entries:
        return None

    elements = []
    for i, e in enumerate(entries[:10]):
        status_emoji = "🆕" if e.get("status") == "new" else "📌"
        title = e.get("title", "无标题")
        source = e.get("source_label", "")
        date = e.get("date", "")
        summary = e.get("summary", "") or ""

        md = f"{status_emoji} **{title}**\n{source} · {date}"
        if summary:
            md += f"\n{summary[:200]}"

        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": md}})
        elements.append({
            "tag": "action",
            "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "📎 查看原文"}, "url": e.get("url", ""), "type": "default"}],
            "layout": "flow"
        })
        if i < len(entries[:10]) - 1:
            elements.append({"tag": "hr"})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": header_title}, "template": template_color},
            "elements": elements
        }
    }

def build_wecom_markdown(entries, header):
    """构建企微 markdown 消息"""
    if not entries:
        return None
    lines = [f"## {header}", ""]
    for e in entries[:10]:
        status = "🆕" if e.get("status") == "new" else "📌"
        title = e.get("title", "")
        source = e.get("source_label", "")
        date = e.get("date", "")
        url = e.get("url", "")
        lines.append(f"{status} **{title}**")
        lines.append(f"> {source} · {date}")
        lines.append(f"> [查看原文]({url})")
        lines.append("")
    return {"msgtype": "markdown", "markdown": {"content": "\n".join(lines)}}

def push_feishu(card):
    """推送飞书消息"""
    if not FEISHU_WEBHOOK or not card:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=json.dumps(card).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"  ⚠️ 飞书推送失败: {e}")
        return False

def push_wecom(msg):
    """推送企微消息"""
    if not WECOM_WEBHOOK or not msg:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            WECOM_WEBHOOK,
            data=json.dumps(msg).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"  ⚠️ 企微推送失败: {e}")
        return False

def update_seen(classified, seen_data):
    """更新 seen.json"""
    today = datetime.now().strftime("%Y-%m-%dT00:00:00Z")
    seen_data["last_updated"] = today
    articles = seen_data.get("articles", {})

    for p in ["P1", "P2", "P3"]:
        for e in classified.get(p, []):
            if e.get("status") != "new":
                continue
            key = e.get("id", "") or e.get("title", "").replace(" ", "_")[:40]
            if key not in articles:
                articles[key] = {
                    "url": e.get("url", ""),
                    "title": e.get("title", ""),
                    "source": e.get("source_label", ""),
                    "first_seen": today,
                    "trust_level": "official",
                    "status": "active",
                    "tags": e.get("tags", [])
                }

    seen_data["articles"] = articles
    save_seen(seen_data)
    return seen_data

# ============================================================
# main
# ============================================================

def main():
    print(f"=== 抖音小灵通 GitHub Actions ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. 解析数据
    print("📡 解析 API 数据...")
    entries, status = collect()
    api_ok = sum(1 for v in status.values() if v["ok"])
    api_fail = sum(1 for v in status.values() if not v["ok"])
    print(f"   ✅ {api_ok} 路成功  ❌ {api_fail} 路失败  共 {len(entries)} 条原始条目")
    for node_id, s in status.items():
        symbol = "✅" if s["ok"] else "❌"
        label = SOURCE_LABELS.get(node_id, node_id)
        print(f"   {symbol} {label}: {s['count']} 条")

    # 2. 过滤+去重+分级
    seen_data = load_seen()
    classified, new_count, tracked_count = filter_and_classify(entries, seen_data)

    p1_count = len(classified["P1"])
    p2_count = len(classified["P2"])
    p3_count = len(classified["P3"])
    total = p1_count + p2_count + p3_count

    print(f"\n📊 过滤后: {total} 条有效 (🆕{new_count} 📌{tracked_count})")
    print(f"   P1🔴 {p1_count}  P2🟡 {p2_count}  P3⚪ {p3_count}  跳过 {len(classified['SKIPPED'])} 条")

    # 3. 推送 — 低优先级先发
    date_str = datetime.now().strftime("%Y/%m/%d")

    print("\n📤 推送中...")

    # P3
    p3_card = build_feishu_card(classified["P3"], f"⚪ 近期更新的规则 {date_str}", "wathet")
    p3_wc = build_wecom_markdown(classified["P3"], f"⚪ 近期更新的规则 {date_str}")
    if p3_card:
        push_feishu(p3_card)
        push_wecom(p3_wc)
        print("   ✅ P3 已推送")
        time.sleep(3)

    # P2
    p2_card = build_feishu_card(classified["P2"], f"🟡 提案与通知 {date_str}", "yellow")
    p2_wc = build_wecom_markdown(classified["P2"], f"🟡 提案与通知 {date_str}")
    if p2_card:
        push_feishu(p2_card)
        push_wecom(p2_wc)
        print("   ✅ P2 已推送")
        time.sleep(3)

    # P1（最后发，最重要）
    p1_entries = classified["P1"]
    if p1_entries:
        # 按时效分组
        recent = [e for e in p1_entries if e.get("is_recent")]
        older = [e for e in p1_entries if not e.get("is_recent")]
        combined = recent + older

        for chunk_idx in range(0, len(combined), 10):
            chunk = combined[chunk_idx:chunk_idx+10]
            part = f"({chunk_idx//10 + 1}/{(len(combined)-1)//10 + 1})" if len(combined) > 10 else ""
            card = build_feishu_card(chunk, f"🔴 确认规则变更 {part} {date_str}", "red")
            wc = build_wecom_markdown(chunk, f"🔴 确认规则变更 {part} {date_str}")
            if card:
                push_feishu(card)
                push_wecom(wc)
                print(f"   ✅ P1 {part} 已推送")
                time.sleep(3)

    # 4. 更新 seen.json
    print("\n💾 更新 seen.json...")
    seen_data = update_seen(classified, seen_data)
    print(f"   总条目: {len(seen_data.get('articles', {}))}")

    # 5. 输出报告摘要
    print(f"\n{'='*50}")
    print(f"# 抖音政策情报报告 — {date_str}")
    print(f"共 {total} 条 · 🆕新增 {new_count} · 📌已追踪 {tracked_count}")
    if api_fail > 0:
        print(f"⚠️ {api_fail} 个数据源获取失败（可能需手动补采）")

    # 打印 P1 条目
    print(f"\n━━━ P1 🔴 确认变更 ━━━")
    for e in classified["P1"]:
        s = "🆕" if e["status"] == "new" else "📌"
        print(f"  {s} {e['title']} | {e['source_label']} · {e['date']}")

    print(f"\nDone. ✅")

if __name__ == "__main__":
    main()
