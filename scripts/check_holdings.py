#!/usr/bin/env python3
"""
my_holdings.json 健康检查 (v1, 2026-09-18)
- 文件存在?
- JSON 合法?
- version 字段距今 <3 天?
退出码:
  0 = 正常
  1 = 失败(workflow 会被 fail)
"""
import json
import os
import sys
from datetime import datetime, date

HOLDINGS_PATH = "data/my_holdings.json"
STALE_DAYS = 3


def main():
    # 1. 文件存在?
    if not os.path.exists(HOLDINGS_PATH):
        print(f"❌ {HOLDINGS_PATH} 不存在")
        return 1

    # 2. JSON 合法?
    try:
        with open(HOLDINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ {HOLDINGS_PATH} JSON 解析失败: {e}")
        return 1

    # 3. 必要字段
    version = data.get("version")
    if not version:
        print(f"❌ {HOLDINGS_PATH} 缺少 version 字段")
        return 1

    # 4. version 是 YYYY-MM-DD?
    try:
        v_date = datetime.strptime(version, "%Y-%m-%d").date()
    except ValueError:
        print(f"❌ version 格式错误: {version} (应为 YYYY-MM-DD)")
        return 1

    # 5. 距今
    today = date.today()
    age_days = (today - v_date).days
    if age_days > STALE_DAYS:
        print(f"❌ {HOLDINGS_PATH} 已陈旧 {age_days} 天 (version={version}, today={today})")
        print(f"   阈值 {STALE_DAYS} 天,请更新持仓")
        return 1

    # 6. 顺便校验 groups 结构
    groups = data.get("groups", {})
    total = sum(len(items) for items in groups.values())
    summary_count = data.get("summary", {}).get("total_count")
    if summary_count and summary_count != total:
        print(f"⚠️  summary.total_count={summary_count} ≠ 实际 {total} 只")

    print(f"✅ {HOLDINGS_PATH} 正常 (version={version}, {total} 只, age={age_days}d)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
