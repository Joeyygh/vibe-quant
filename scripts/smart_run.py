#!/usr/bin/env python3
"""
Vibe 智能运行 wrapper
====================
不再要求"必须是当天数据",而是"用最新可得的数据"。
支持任何时间调用:盘前 / 盘中 / 盘后。

用法:
  python scripts/smart_run.py                         # 自动判断时段
  python scripts/smart_run.py --mode pre              # 强制盘前模式
  python scripts/smart_run.py --mode intraday         # 强制盘中模式
  python scripts/smart_run.py --mode post             # 强制盘后模式
  python scripts/smart_run.py --as-of 2026-09-13      # 指定报告日期
  python scripts/smart_run.py --dry-run               # 只打印配置不跑

环境变量透传给 daily_report.py:
  VIBE_AS_OF_DATE  — 报告日期 (YYYY-MM-DD)
  VIBE_SESSION     — 报告时段 (pre_market / intraday_* / post_close)
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path


def get_market_session() -> str:
    """根据北京时间判断当前交易时段"""
    now = datetime.now().time()
    if time(0, 0) <= now < time(9, 0):
        return "pre_market"
    if time(9, 0) <= now < time(9, 30):
        return "pre_open"
    if time(9, 30) <= now < time(11, 30):
        return "intraday_morning"
    if time(11, 30) <= now < time(13, 0):
        return "lunch"
    if time(13, 0) <= now < time(15, 0):
        return "intraday_afternoon"
    if time(15, 0) <= now < time(17, 0):
        return "post_close"
    return "after_hours"


def get_last_update_date(repo_root: Path) -> str | None:
    """读 data/last_update.txt,返回数据日期字符串 (YYYY-MM-DD)"""
    p = repo_root / "data" / "last_update.txt"
    if not p.exists():
        return None
    try:
        raw = p.read_text(encoding="utf-8").strip()
        # 格式: "2026-09-11T17:30:00" 或 "2026-09-11"
        return raw.split("T")[0].split()[0]
    except Exception:
        return None


def freshness_warning(last_update_date: str | None) -> str | None:
    """检查数据陈旧度,只警告不阻止"""
    if not last_update_date:
        return "⚠️ data/last_update.txt 不存在,数据状态未知"
    try:
        last = datetime.strptime(last_update_date, "%Y-%m-%d").date()
    except ValueError:
        return f"⚠️ last_update.txt 格式异常: {last_update_date}"
    today = datetime.now().date()
    age_days = (today - last).days
    if age_days == 0:
        return "✅ 数据为今天"
    if age_days == 1:
        return f"ℹ️ 数据为昨日 ({last_update_date}),今天数据将在 22:00 北京前自动更新"
    return f"⚠️ 数据已陈旧 {age_days} 天 ({last_update_date}),请检查 daily.yml"


def build_report_config(session: str, as_of: str | None) -> dict:
    """根据时段构建报告配置"""
    if as_of is None:
        as_of = datetime.now().strftime("%Y-%m-%d")
    config = {
        "as_of_date": as_of,
        "session": session,
        "report_title_suffix": {
            "pre_open": "盘前预判",
            "pre_market": "盘前预判",
            "intraday_morning": "盘中快报(上午)",
            "lunch": "午间快报",
            "intraday_afternoon": "盘中快报(下午)",
            "post_close": "盘后复盘",
            "after_hours": "盘后分析",
        }.get(session, "分析报告"),
        "skip_data_refresh": True,  # 永远不触发数据拉取(盘中/盘后数据反正也更新不了)
    }
    return config


def run_daily_report(config: dict) -> int:
    """调用 daily_report.py,透传环境变量"""
    env = os.environ.copy()
    env["VIBE_AS_OF_DATE"] = config["as_of_date"]
    env["VIBE_SESSION"] = config["session"]
    env["VIBE_SKIP_REFRESH"] = "1"

    result = subprocess.run(
        [sys.executable, "scripts/daily_report.py"],
        env=env,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Vibe 智能运行 wrapper")
    parser.add_argument(
        "--mode",
        choices=["pre", "intraday", "post", "auto"],
        default="auto",
        help="报告模式 (默认 auto 根据当前时间判断)",
    )
    parser.add_argument(
        "--as-of", type=str, default=None,
        help="指定报告日期 YYYY-MM-DD,默认 = today",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印配置不执行 daily_report.py",
    )
    args = parser.parse_args()

    # 1. 判断时段
    if args.mode == "auto":
        session = get_market_session()
    elif args.mode == "pre":
        session = "pre_market"
    elif args.mode == "intraday":
        session = "intraday_afternoon"
    else:
        session = "post_close"

    # 2. 找 repo root
    repo_root = Path(__file__).resolve().parent.parent

    # 3. 数据陈旧度警告(不阻止)
    last_date = get_last_update_date(repo_root)
    warn = freshness_warning(last_date)
    if warn:
        print(warn)

    # 4. 构建报告配置
    config = build_report_config(session, args.as_of)

    print(f"\n📊 Vibe 智能运行")
    print(f"  时段: {session}")
    print(f"  报告日期: {config['as_of_date']}")
    print(f"  报告类型: {config['report_title_suffix']}")
    print(f"  数据日期: {last_date or '未知'}")
    print(f"  跳过数据刷新: {config['skip_data_refresh']}")

    if args.dry_run:
        print("\n[dry-run] 不执行 daily_report.py")
        return 0

    # 5. 调用报告
    print("\n" + "=" * 50)
    return run_daily_report(config)


if __name__ == "__main__":
    sys.exit(main())
