#!/usr/bin/env python3
"""
my_holdings.json 健康检查 (v2, 2026-09-27)

变更原因(v1 的致命设计错误):
  v1 用 STALE_DAYS=3 硬门禁 + workflow continue-on-error=false,
  导致持仓文件超过 3 天没动 -> 整个 daily_report 流水线(fetch_news +
  选股 + 复盘)全部不执行。9/18~9/27 连续失败 9 天,日报完全停摆。

  根因是**耦合错误**: 持仓文件是"用户调仓时才更新"的数据,
  不是每天刷新的数据。拿它当整个系统的启动门禁,等于
  "用户三个月没调仓 -> 选股系统停机"。

v2 设计原则:
  1. **文件级致命错误才 fail**(不存在 / JSON 非法 / 缺 version / 格式错)
     -> 这些情况下报告里的持仓章节确实没法生成,早失败有意义
  2. **陈旧只警告不 fail**(默认阈值 30 天,可用环境变量覆盖)
     -> 持仓旧了照样能算,顶多少了章节
  3. 持仓文件缺失时,整个报告其余部分(日资金流/选股/指数)照常产出

退出码:
  0 = 通过(可能有警告)
  1 = 致命错误(文件级损坏)
"""
import json
import os
import sys
from datetime import datetime, date

HOLDINGS_PATH = "data/my_holdings.json"

# 陈旧阈值:天。默认 30 天(一个月不调仓很正常),不再用 3 天这种
# 只适用于"每天刷新"数据的阈值。可用 HOLDINGS_STALE_DAYS 覆盖。
STALE_DAYS = int(os.environ.get("HOLDINGS_STALE_DAYS", "30"))

# 超过这个天数,陈旧就升级为致命(半年没动过,数据大概率失效)
CRITICAL_STALE_DAYS = int(os.environ.get("HOLDINGS_CRITICAL_STALE_DAYS", "180"))


def main():
    warnings = []

    # ---- 1. 文件存在?(致命) ----
    if not os.path.exists(HOLDINGS_PATH):
        print(f"⚠️  {HOLDINGS_PATH} 不存在 — 报告将跳过持仓章节,其余部分正常产出")
        return 0

    # ---- 2. JSON 合法?(致命) ----
    try:
        with open(HOLDINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ {HOLDINGS_PATH} JSON 解析失败: {e}")
        print(f"    文件损坏,报告无法生成持仓章节,请修复后重跑")
        return 1

    # ---- 3. version 字段存在?(致命) ----
    version = data.get("version")
    if not version:
        print(f"❌ {HOLDINGS_PATH} 缺少 version 字段")
        return 1

    # ---- 4. version 是 YYYY-MM-DD?(致命) ----
    try:
        v_date = datetime.strptime(str(version), "%Y-%m-%d").date()
    except ValueError:
        print(f"❌ version 格式错误: {version} (应为 YYYY-MM-DD)")
        return 1

    # ---- 5. 陈旧检查(只警告,不 fail) ----
    today = date.today()
    age_days = (today - v_date).days
    if age_days < 0:
        warnings.append(f"version={version} 是未来日期,请检查")
        print(f"⚠️  {HOLDINGS_PATH} version={version} 晚于今天({today})")
    elif age_days > CRITICAL_STALE_DAYS:
        # 半年以上没动,数据大概率已失效,这时候 fail 有意义
        print(f"❌ {HOLDINGS_PATH} 已陈旧 {age_days} 天 (version={version}, today={today})")
        print(f"    超过严重阈值 {CRITICAL_STALE_DAYS} 天,请确认持仓是否仍然准确")
        return 1
    elif age_days > STALE_DAYS:
        warnings.append(f"持仓已 {age_days} 天未更新(阈值 {STALE_DAYS})")
        print(f"⚠️  持仓已 {age_days} 天未更新(阈值 {STALE_DAYS} 天)— 报告照常生成,持仓数据可能偏旧")
    elif age_days > 0:
        print(f"ℹ️  持仓 {age_days} 天未更新(正常,调仓才更新)")

    # ---- 6. groups 结构(只警告) ----
    groups = data.get("groups", {})
    if not isinstance(groups, dict):
        print(f"⚠️  groups 不是字典(实际 {type(groups).__name__})")
        return 0

    total = sum(len(items) for items in groups.values() if isinstance(items, list))
    summary_count = (data.get("summary") or {}).get("total_count")
    if summary_count and summary_count != total:
        warnings.append(f"summary.total_count={summary_count} ≠ 实际 {total}")
        print(f"⚠️  summary.total_count={summary_count} ≠ 实际 {total} 只(以实际持仓为准)")

    # ---- 7. cost_price 完整性(只警告,这是 9/18 出过事的字段) ----
    missing_cost = []
    for gname, items in groups.items():
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get("cost_price") in (None, "", 0):
                missing_cost.append(f"{it.get('code', '?')}({gname})")
    if missing_cost:
        preview = ", ".join(missing_cost[:8])
        more = f" 等 {len(missing_cost)} 只" if len(missing_cost) > 8 else ""
        warnings.append(f"{len(missing_cost)} 只缺 cost_price")
        print(f"⚠️  {len(missing_cost)} 只持仓缺 cost_price: {preview}{more}")
        print(f"    这些标的算不出盈亏,报告里会缺失")

    print(f"✅ {HOLDINGS_PATH} 可用 (version={version}, {total} 只, age={age_days}d)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
