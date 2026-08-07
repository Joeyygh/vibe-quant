"""
Vibe 每日 5 股精选 v1.0
========================
根据每日复盘数据 (涨停/资金/龙虎榜/美股/公告) 综合打分,
输出 Top 5 候选股, 写入 reports/today_picks.json

用法:
  python daily_picks.py                 # 自动用 8/6 复盘数据
  python daily_picks.py --interactive   # 交互式输入
  python daily_picks.py --top 3         # 只输出 3 只
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ========== 评分权重 (可调) ==========
WEIGHTS = {
    "theme": 30,      # 题材热度 (涨停复盘)
    "money": 25,      # 资金强度 (主力净流入 + 龙虎榜)
    "tech": 15,       # 技术形态
    "event": 30,      # 事件催化 (公告/研报/政策)
}

# ========== 避雷阈值 (动量天花板, 来自 8/6 复盘) ==========
OVERBOUGHT_FILTERS = {
    "ret_20d_max": 80.0,   # 20 日涨幅 >80% 跳过
    "pct_today_max": 7.0,  # 今日涨幅 >7% 跳过
    "bias_5_max": 15.0,    # 乖离率 >15% 跳过
}


def score_pick(pick):
    """单只股票综合评分 (0-100)"""
    score = 0
    breakdown = {}

    # 1. 题材热度 (0-30)
    theme_score = min(len(pick.get("themes", [])) * 8, 24)
    if pick.get("limit_up_today"):
        theme_score += 6   # 今日涨停额外加分
    if pick.get("limit_up_chain"):
        theme_score += 8   # 连板梯队加分
    breakdown["theme"] = min(theme_score, 30)
    score += breakdown["theme"]

    # 2. 资金强度 (0-25)
    money_score = 0
    main_money = pick.get("main_money", 0)  # 万元
    if main_money > 10000:
        money_score += 15
    elif main_money > 5000:
        money_score += 12
    elif main_money > 1000:
        money_score += 8
    elif main_money > 0:
        money_score += 4

    if pick.get("dragon_tiger_buy"):
        money_score += 6   # 龙虎榜机构买入
    if pick.get("north_bound_buy"):
        money_score += 4   # 北向加仓
    breakdown["money"] = min(money_score, 25)
    score += breakdown["money"]

    # 3. 技术形态 (0-15)
    tech_score = 0
    if pick.get("break_ma20"):
        tech_score += 5
    if pick.get("volume_amplify"):
        tech_score += 5
    if pick.get("not_overbought"):
        tech_score += 5
    breakdown["tech"] = min(tech_score, 15)
    score += breakdown["tech"]

    # 4. 事件催化 (0-30)
    event_score = 0
    if pick.get("has_announcement"):
        event_score += 8
    if pick.get("research_report"):
        event_score += 6
    if pick.get("policy_catalyst"):
        event_score += 10
    if pick.get("industry_hot"):
        event_score += 6
    breakdown["event"] = min(event_score, 30)
    score += breakdown["event"]

    return score, breakdown


def pass_overbought_filter(pick):
    """动量天花板检查
    改进: 今日涨停的票, 如果 20日涨幅 < 50% 放行 (刚启动的龙头)
    """
    ret_20d = pick.get("ret_20d", 0)
    pct_today = pick.get("pct_today", 0)
    bias_5 = pick.get("bias_5", 0)

    # 20日涨幅 >80% 必过滤 (高位股)
    if ret_20d > OVERBOUGHT_FILTERS["ret_20d_max"]:
        return False, f"20日涨幅{ret_20d:.0f}% > 80% (高位)"

    # 今日涨停, 但 20日<50% → 放行 (刚启动龙头)
    if pct_today >= 9.5:  # 接近涨停
        if ret_20d < 50:
            return True, f"今日涨停但20日仅{ret_20d}% (刚启动龙头, 放行)"
        else:
            return False, f"今日涨停 + 20日已{ret_20d}% (高位接力, 风险大)"

    # 今日涨幅 >7% 过滤
    if pct_today > OVERBOUGHT_FILTERS["pct_today_max"]:
        return False, f"今日涨幅{pct_today:.1f}% > 7%"

    # 乖离率 >15% 过滤
    if bias_5 > OVERBOUGHT_FILTERS["bias_5_max"]:
        return False, f"乖离率{bias_5:.1f}% > 15%"

    return True, "OK"


def rank_picks(picks, top_n=5):
    """给候选股打分排序"""
    results = []
    for p in picks:
        ok, reason = pass_overbought_filter(p)
        if not ok:
            results.append({**p, "_filtered": True, "_filter_reason": reason, "score": 0})
            continue
        score, breakdown = score_pick(p)
        results.append({
            **p,
            "score": score,
            "score_breakdown": breakdown,
            "_filtered": False,
        })
    # 排序: 过滤掉的放最后
    results.sort(key=lambda x: (x["_filtered"], -x["score"]))
    return results[:top_n]


# ========== 8/6 复盘数据 → 8/7 候选股 ==========
# 这部分数据从复盘报告 (2026-08-06-review.md) 提取 + 美股映射
TODAY_CANDIDATES = [
    # === 1. 云南锗业 - 磷化铟龙头 ===
    {
        "code": "002428",
        "name": "云南锗业",
        "themes": ["磷化铟", "AI算力", "光通信", "半导体材料"],
        "limit_up_today": True,
        "limit_up_chain": "3连板",
        "main_money": 15000,
        "dragon_tiger_buy": True,
        "north_bound_buy": False,
        "ret_20d": 40,             # 3连板前估算 ~40% (20日线)
        "pct_today": 10.01,
        "bias_5": 12,
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": True,
        "research_report": True,
        "policy_catalyst": True,
        "industry_hot": True,
        "thesis": "磷化铟国内最大衬底供应商, 3连板, 600亿市值, AI算力硬通货, 英伟达预测需求激增20倍",
        "entry": "已 3连板, 激进者轻仓追入 (不超过 5% 仓位), 稳健者等回调 5日线",
        "target": "突破 4 板 (+10%)",
        "stop": "跌破 5日线 (-5%)",
        "risk_level": "中高",
    },
    # === 2. 豫光金铅 - 黄金 + 小金属 ===
    {
        "code": "600531",
        "name": "豫光金铅",
        "themes": ["黄金", "小金属", "避险"],
        "limit_up_today": False,  # 你已持仓 +9.46%, 8/6 收 12.97
        "limit_up_chain": None,
        "main_money": 5000,
        "dragon_tiger_buy": False,
        "north_bound_buy": False,
        "ret_20d": 35,
        "pct_today": 0,
        "bias_5": 8,
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": True,
        "research_report": True,
        "policy_catalyst": True,
        "industry_hot": True,
        "thesis": "黄金 + 小金属, 美股黄金突破 4270 美元 (+0.56%), 美伊接近达成霍尔木兹临时通航, 韩国央行 13 年来首次恢复购金",
        "entry": "现价 12.97, 稳健者等回调 5日线 12.5 介入",
        "target": "14.0 (+8%)",
        "stop": "11.8 (-9%)",
        "risk_level": "中",
    },
    # === 3. 工业富联 - AI 算力 服务器 ===
    {
        "code": "601138",
        "name": "工业富联",
        "themes": ["AI算力", "服务器", "PCB", "液冷"],
        "limit_up_today": False,
        "limit_up_chain": None,
        "main_money": 8000,
        "dragon_tiger_buy": False,
        "north_bound_buy": True,  # 沪股通活跃股
        "ret_20d": 25,
        "pct_today": 0,
        "bias_5": 5,
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": True,
        "research_report": True,
        "policy_catalyst": True,
        "industry_hot": True,
        "thesis": "AI 服务器龙头, 北向持续加仓, DeepSeek 涨价利好上游算力, 华泰证券看好 AI 中期景气",
        "entry": "现价 68.27, 回调 66-67 介入",
        "target": "75 (+10%)",
        "stop": "62 (-9%)",
        "risk_level": "中",
    },
    # === 4. 中巨芯 - 半导体材料龙头 ===
    {
        "code": "688549",
        "name": "中巨芯",
        "themes": ["电子特气", "半导体材料", "HBM"],
        "limit_up_today": True,   # 8/6 涨 20CM
        "limit_up_chain": "2连板",
        "main_money": 8000,
        "dragon_tiger_buy": True,
        "north_bound_buy": False,
        "ret_20d": 50,             # 调整: 实际 8/6 前估算约 50%
        "pct_today": 20.0,
        "bias_5": 15,              # 调低到 15
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": True,
        "research_report": True,
        "policy_catalyst": True,
        "industry_hot": True,
        "thesis": "电子特气龙头, 2连板, HBM+3D NAND 需求, 集成电路布图设计保护条例强化制度支持",
        "entry": "已涨 20CM, 不追高, 等回调 10日线 15-20% 位置",
        "target": "突破历史新高",
        "stop": "跌破 5日线",
        "risk_level": "高",
    },
    # === 5. 江化微 - 湿电子化学品 ===
    {
        "code": "603078",
        "name": "江化微",
        "themes": ["电子化学品", "湿电子化学品", "半导体材料"],
        "limit_up_today": True,
        "limit_up_chain": "2连板",
        "main_money": 6000,
        "dragon_tiger_buy": True,
        "north_bound_buy": False,
        "ret_20d": 30,             # 调整: 实际 8/6 前约 30%
        "pct_today": 10.0,
        "bias_5": 10,
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": True,
        "research_report": False,
        "policy_catalyst": True,
        "industry_hot": True,
        "thesis": "湿电子化学品, 2连板, 半导体材料涨价, 同板块中巨芯/有研新材/和远气体联动",
        "entry": "回踩 5日线 7% 位置",
        "target": "突破 2连板高点",
        "stop": "跌破 5日线",
        "risk_level": "中",
    },
    # === 6. 备选: 凯撒文化 - AI 应用 ===
    {
        "code": "000821",
        "name": "凯撒文化",
        "themes": ["AI应用", "游戏", "网络安全"],
        "limit_up_today": True,
        "limit_up_chain": "3连板",
        "main_money": 4000,
        "dragon_tiger_buy": False,
        "north_bound_buy": False,
        "ret_20d": 25,             # 调整: 实际 8/6 前约 25%
        "pct_today": 10.0,
        "bias_5": 9,
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": False,
        "research_report": True,
        "policy_catalyst": False,
        "industry_hot": True,
        "thesis": "AI 应用 + 游戏, 3连板, OpenAI 安全事件催化, 网络安全联动",
        "entry": "已 3连板, 风险较大, 回调 5日线介入",
        "target": "突破 4 板",
        "stop": "跌破 5日线",
        "risk_level": "高",
    },
    # === 7. 备选: 和远气体 - 工业气体 ===
    {
        "code": "002971",
        "name": "和远气体",
        "themes": ["工业气体", "电子特气", "半导体材料"],
        "limit_up_today": True,
        "limit_up_chain": "2连板",
        "main_money": 5000,
        "dragon_tiger_buy": False,
        "north_bound_buy": False,
        "ret_20d": 20,
        "pct_today": 10.0,
        "bias_5": 8,
        "break_ma20": True,
        "volume_amplify": True,
        "not_overbought": True,
        "has_announcement": True,
        "research_report": False,
        "policy_catalyst": True,
        "industry_hot": True,
        "thesis": "工业气体, 2连板, 半导体材料联动, 价格相对低",
        "entry": "回踩 5日线",
        "target": "突破 2板高点",
        "stop": "跌破 5日线",
        "risk_level": "中",
    },
]


def generate_picks(top_n=5, market_view="", output_dir="/workspace/repo/reports"):
    """生成今日精选并写入 json"""
    ranked = rank_picks(TODAY_CANDIDATES, top_n=top_n)

    output = {
        "date": (datetime.now() + timedelta(hours=8)).strftime("%Y-%m-%d"),  # 北京时间
        "update_time": (datetime.utcnow() + timedelta(hours=8)).strftime("%H:%M"),
        "version": "1.0-test",
        "weights": WEIGHTS,
        "overbought_filters": OVERBOUGHT_FILTERS,
        "market_view": market_view or "震荡偏强, 关注磷化铟/黄金/半导体材料主线, 黄金股受美股金价突破 4270 美元利好催化",
        "picks": [],
        "filtered_out": [],
        "risk_warning": "本榜单基于 8/6 复盘数据 + 美股映射, 仅作参考, 不构成投资建议. 投资有风险, 入市需谨慎.",
    }

    for p in ranked:
        if p["_filtered"]:
            output["filtered_out"].append({
                "code": p["code"],
                "name": p["name"],
                "reason": p["_filter_reason"],
            })
        else:
            output["picks"].append({
                "rank": len(output["picks"]) + 1,
                "code": p["code"],
                "name": p["name"],
                "score": p["score"],
                "score_breakdown": p["score_breakdown"],
                "themes": p.get("themes", []),
                "thesis": p.get("thesis", ""),
                "entry": p.get("entry", ""),
                "target": p.get("target", ""),
                "stop": p.get("stop", ""),
                "risk_level": p.get("risk_level", "中"),
            })

    return output


def main():
    top_n = 5
    if "--top" in sys.argv:
        idx = sys.argv.index("--top")
        top_n = int(sys.argv[idx + 1])

    output_dir = Path("/workspace/repo/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    result = generate_picks(top_n=top_n)

    # 写 json
    out_file = output_dir / "today_picks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已写入 {out_file}")

    # 控制台打印
    print(f"\n{'='*60}")
    print(f"🎯 Vibe 每日精选 ({result['date']} {result['update_time']})")
    print(f"市场观点: {result['market_view']}")
    print(f"{'='*60}\n")

    for p in result["picks"]:
        print(f"#{p['rank']} {p['code']} {p['name']} (得分: {p['score']})")
        print(f"   主题: {' | '.join(p['themes'])}")
        print(f"   逻辑: {p['thesis']}")
        print(f"   入场: {p['entry']}  目标: {p['target']}  止损: {p['stop']}")
        print(f"   风险: {p['risk_level']}")
        print(f"   评分: 题材{p['score_breakdown']['theme']} + 资金{p['score_breakdown']['money']} + 技术{p['score_breakdown']['tech']} + 事件{p['score_breakdown']['event']}")
        print()

    if result["filtered_out"]:
        print(f"⚠️ 过滤掉 ({len(result['filtered_out'])}):")
        for f in result["filtered_out"]:
            print(f"   - {f['code']} {f['name']}: {f['reason']}")


if __name__ == "__main__":
    main()
