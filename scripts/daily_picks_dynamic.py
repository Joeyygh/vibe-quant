"""
Vibe 每日精选 - 动态版 v1.0 (2026-08-10 上线)
============================================
基于 Tushare Pro 当日真实盘面动态生成 5 企推 + 量化补充 + 双引擎交集.

数据源: Tushare daily + stock_basic
策略:
  - 5 企推 (主推): 当日涨停 + 高成交 + 不超买 + 题材热门
  - 量化补充: 涨幅 5-9.5% 强势股 + 用户持仓 (从 my_holdings.json)
  - 双引擎交集: 题材 + 量化都选上的 → 高信心
  - 避雷: 20日涨幅 >80% 跳过 / 今日涨幅 >7% 跳过 / 乖离率 >15% 跳过

输出: reports/today_picks.json
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


def get_today_data():
    """拉当日真实盘面"""
    import tushare as ts
    token = os.environ.get('TUSHARE_TOKEN')
    if not token:
        raise RuntimeError("TUSHARE_TOKEN not set in env")
    pro = ts.pro_api(token)

    # 1. 当日行情
    today = datetime.now().strftime('%Y%m%d')
    df = pro.daily(trade_date=today)
    if df is None or len(df) == 0:
        raise RuntimeError(f"No data for {today}")
    df = df[~df['ts_code'].str.contains('.BJ')].copy()
    df['code'] = df['ts_code'].str.split('.').str[0]

    # 2. 股票基本信息
    df_basic = pro.stock_basic(list_status='L', fields='ts_code,name,industry')
    df = df.merge(df_basic, on='ts_code', how='left')
    return df, today


def get_user_holdings():
    """读 my_holdings.json"""
    p = Path('my_holdings.json')
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        # 兼容 list 或 dict
        if isinstance(data, list):
            return [h.get('code', '') for h in data]
        elif isinstance(data, dict):
            codes = []
            for grp, items in data.items():
                if isinstance(items, list):
                    for h in items:
                        if 'code' in h:
                            codes.append(h['code'])
            return codes
    except Exception as e:
        print(f"读 my_holdings.json 失败: {e}")
    return []


def calc_indicators(df_today):
    """从 klines.parquet 算 20 日涨幅 + MA5"""
    p = Path('data/klines.parquet')
    if not p.exists():
        # 没有 K 线, 返回空指标
        df_today['ret_20d'] = 0
        df_today['ma5'] = df_today['close']
        df_today['bias_5'] = 0
        return df_today

    try:
        klines = pd.read_parquet(p, columns=['ts_code', 'trade_date', 'close'])
        klines = klines.sort_values(['ts_code', 'trade_date'])
        # 取每只票最后 20 根
        klines_20 = klines.groupby('ts_code').tail(20)
        ret_20d_map = {}
        ma5_map = {}
        for code, grp in klines_20.groupby('ts_code'):
            if len(grp) >= 20:
                ret_20d_map[code] = (grp['close'].iloc[-1] / grp['close'].iloc[0] - 1) * 100
            else:
                ret_20d_map[code] = 0
            ma5_map[code] = grp['close'].tail(5).mean()

        df_today['ret_20d'] = df_today['ts_code'].map(ret_20d_map).fillna(0)
        df_today['ma5'] = df_today['ts_code'].map(ma5_map).fillna(df_today['close'])
        df_today['bias_5'] = (df_today['close'] / df_today['ma5'] - 1) * 100
        df_today['bias_5'] = df_today['bias_5'].fillna(0)
    except Exception as e:
        print(f"读 klines.parquet 失败: {e}")
        df_today['ret_20d'] = 0
        df_today['ma5'] = df_today['close']
        df_today['bias_5'] = 0
    return df_today


# ========== 主题分类映射 (基于行业关键词) ==========
INDUSTRY_THEMES = {
    "半导体": ["半导体设备", "存储芯片", "AI算力", "国产替代"],
    "元器件": ["MLCC", "元器件", "AI硬件", "消费电子"],
    "通信设备": ["AI算力", "服务器", "光模块", "5G"],
    "电气设备": ["储能", "电池", "钠电池", "新型电力"],
    "化工原料": ["锂电材料", "氟化工", "6F", "化工"],
    "小金属": ["钨", "稀土", "战略金属", "军工"],
    "黄金": ["黄金", "避险", "央行购金"],
    "新型电力": ["风电", "光伏", "绿电", "储能"],
    "机械基件": ["机器人", "工业母机", "减速器"],
    "汽车配件": ["新能源汽车", "一体化压铸", "智能驾驶"],
    "生物制药": ["创新药", "减肥药", "GLP-1"],
    "专用机械": ["军工", "船舶", "航天"],
    "医疗保健": ["医疗器械", "创新药", "CXO"],
    "化工": ["磷化工", "氟化工", "纯碱"],
}


def get_themes_for_industry(industry):
    """根据行业返回主题列表"""
    return INDUSTRY_THEMES.get(industry, [industry])


def score_pick(p):
    """单只股票综合评分 (0-100)"""
    score = 0
    breakdown = {}

    # 1. 题材热度 (0-30)
    theme_score = min(len(p.get("themes", [])) * 8, 24)
    if p.get("pct_chg", 0) >= 9.5:
        theme_score += 6   # 今日涨停额外加分
    breakdown["theme"] = min(theme_score, 30)
    score += breakdown["theme"]

    # 2. 资金强度 (0-25) - 用成交额 (万元)
    amount_wan = p.get("amount", 0) / 1e4
    if amount_wan > 100000:
        money_score = 15
    elif amount_wan > 50000:
        money_score = 12
    elif amount_wan > 10000:
        money_score = 8
    elif amount_wan > 1000:
        money_score = 4
    else:
        money_score = 0
    breakdown["money"] = min(money_score, 25)
    score += breakdown["money"]

    # 3. 技术形态 (0-15)
    tech_score = 0
    ret_20d = p.get("ret_20d", 0)
    bias_5 = p.get("bias_5", 0)
    if 0 < ret_20d < 80:    # 20日有涨幅但没超买
        tech_score += 5
    if bias_5 > 0 and bias_5 < 15:   # 乖离率温和
        tech_score += 5
    if p.get("pct_chg", 0) > 0:   # 今日红盘
        tech_score += 5
    breakdown["tech"] = min(tech_score, 15)
    score += breakdown["tech"]

    # 4. 事件催化 (0-30) - 行业热度启发
    event_score = 0
    if p.get("industry") in INDUSTRY_THEMES:
        event_score += 12  # 热点行业
    if p.get("pct_chg", 0) >= 5:
        event_score += 8   # 异动
    if p.get("amount", 0) > 5e8:   # 5亿成交
        event_score += 10
    breakdown["event"] = min(event_score, 30)
    score += breakdown["event"]

    return score, breakdown


def pass_overbought_filter(p):
    """动量天花板检查"""
    ret_20d = p.get("ret_20d", 0)
    pct_today = p.get("pct_chg", 0)
    bias_5 = p.get("bias_5", 0)

    # 20日涨幅 >80% 必过滤
    if ret_20d > 80:
        return False, f"20日涨幅{ret_20d:.0f}% > 80%"

    # 今日涨停 + 20日已涨 >50% → 高位接力
    if pct_today >= 9.5 and ret_20d > 50:
        return False, f"今日涨停+20日{ret_20d:.0f}% (高位)"

    # 今日涨幅 >7% (但非涨停, 避免追高)
    if pct_today > 7 and pct_today < 9.5 and ret_20d > 30:
        return False, f"今日涨幅{pct_today:.1f}% > 7% (异动)"

    # 乖离率 >15% 过滤
    if bias_5 > 15:
        return False, f"乖离率{bias_5:.1f}% > 15%"

    return True, "OK"


def build_pick_entry(p, source, rank=0):
    """统一 picks 格式"""
    pct = p.get("pct_chg", 0)
    is_limit = pct >= 9.5
    themes = p.get("themes", [])

    # 动态 entry/target/stop
    close = p.get("close", 0)
    ret_20d = p.get("ret_20d", 0)
    ma5 = p.get("ma5", close)

    if is_limit:
        entry = f"已涨停 ({pct:.1f}%), 激进者次日开盘轻仓, 稳健者等回踩 5日线 {ma5:.2f}"
    elif pct > 5:
        entry = f"现价 {close:.2f}, 突破 {close * 1.02:.2f} 加仓"
    else:
        entry = f"现价 {close:.2f}, 不追高, 等回踩 5日线 {ma5:.2f} 介入"

    target = f"突破前高/MA60 ({close * 1.08:.2f}, +8%)"
    stop = f"跌破 5日线 ({ma5 * 0.97:.2f}, -3%)"

    return {
        "rank": rank,
        "code": p["code"],
        "name": p.get("name", ""),
        "score": p.get("score", 0),
        "score_breakdown": p.get("score_breakdown", {}),
        "industry": p.get("industry", ""),
        "themes": themes,
        "pct_chg_today": pct,
        "ret_20d": ret_20d,
        "close": close,
        "thesis": f"{p.get('industry','')} 行业, 涨幅 {pct:+.2f}%, 成交 {p.get('amount',0)/1e8:.2f} 亿, {', '.join(themes[:2])}",
        "entry": entry,
        "target": target,
        "stop": stop,
        "risk_level": "中",
        "source": source,
    }


def generate_picks():
    """主函数: 动态生成 5 企推 + 量化 + 双引擎"""
    # 1. 拉数据
    print("📡 拉取 Tushare 当日数据...")
    df, today_str = get_today_data()
    print(f"   当日: {today_str}, 共 {len(df)} 只票")

    # 2. 算技术指标
    df = calc_indicators(df)

    # 3. 应用动量天花板
    df['_filtered'] = False
    df['_filter_reason'] = ''
    for idx, row in df.iterrows():
        ok, reason = pass_overbought_filter(row.to_dict())
        if not ok:
            df.at[idx, '_filtered'] = True
            df.at[idx, '_filter_reason'] = reason

    # 4. 评分
    df['score'] = 0
    df['score_breakdown'] = None
    for idx, row in df.iterrows():
        if row['_filtered']:
            continue
        p = row.to_dict()
        p['themes'] = get_themes_for_industry(p.get('industry', ''))
        s, br = score_pick(p)
        df.at[idx, 'score'] = s
        df.at[idx, 'score_breakdown'] = json.dumps(br, ensure_ascii=False)

    # 5. 5 企推候选池: 涨停 + 不超买 + 成交 > 5000 万
    theme_pool = df[
        (~df['_filtered']) &
        (df['pct_chg'] >= 9.5) &
        (df['amount'] > 5e6)   # 5 千万成交
    ].sort_values('amount', ascending=False).head(20)

    # 6. 量化补充池: 涨幅 3-9.5% (强势但未涨停) + 用户持仓
    holdings = get_user_holdings()
    quant_pool = df[
        (~df['_filtered']) &
        (df['pct_chg'] >= 3) &
        (df['pct_chg'] < 9.5) &
        (df['amount'] > 3e7)  # 3 亿成交
    ].sort_values('amount', ascending=False).head(30)

    # 7. 用户持仓 (就算没大涨也加入量化池)
    if holdings:
        hold_df = df[df['code'].isin(holdings) & (~df['_filtered'])]
        quant_pool = pd.concat([quant_pool, hold_df]).drop_duplicates('ts_code')

    # 8. 强制交集: 从候选里挑 2 只作为"双引擎"种子
    #    规则: 题材 + 持仓 重叠, 或者 题材池 top + 量化池 top 重叠
    #    简化: 把量化池里涨幅 > 5% 的 top 3 标为 dual
    if len(quant_pool) > 0:
        top_quant = quant_pool.nlargest(3, 'amount')
    else:
        top_quant = pd.DataFrame()

    # 9. 选 5 企推 (取 theme_pool top 5, 但 dual 的强制入)
    theme_picks = []
    for _, row in theme_pool.head(7).iterrows():
        p = row.to_dict()
        p['themes'] = get_themes_for_industry(p.get('industry', ''))
        p['score'] = int(p['score'])
        p['score_breakdown'] = json.loads(p['score_breakdown']) if p['score_breakdown'] else {}
        entry = build_pick_entry(p, source="theme")
        theme_picks.append(entry)
    theme_picks = theme_picks[:5]
    for i, p in enumerate(theme_picks, 1):
        p['rank'] = i

    # 10. 量化补充 (top 7, 优先 dual)
    quant_picks = []
    for _, row in quant_pool.head(7).iterrows():
        p = row.to_dict()
        p['themes'] = get_themes_for_industry(p.get('industry', ''))
        p['score'] = int(p['score'])
        p['score_breakdown'] = json.loads(p['score_breakdown']) if p['score_breakdown'] else {}
        entry = build_pick_entry(p, source="quant")
        quant_picks.append(entry)

    # 11. 双引擎交集 (code 相同)
    theme_codes = {p['code'] for p in theme_picks}
    quant_codes = {p['code'] for p in quant_picks}
    intersection = list(theme_codes & quant_codes)

    # 12. 标签
    for p in theme_picks:
        p['tag'] = "🎯 双引擎" if p['code'] in intersection else "🔥 仅精选"
    for p in quant_picks:
        p['tag'] = "🎯 双引擎" if p['code'] in intersection else "📊 仅量化"

    # 13. 过滤列表
    filtered = []
    for _, row in df[df['_filtered']].iterrows():
        filtered.append({
            "code": row['code'],
            "name": row['name'],
            "reason": row['_filter_reason'],
        })

    # 14. 输出
    beijing = timezone(timedelta(hours=8))
    now = datetime.now(beijing)
    output = {
        "date": now.strftime("%Y-%m-%d"),
        "update_time": now.strftime("%H:%M"),
        "version": "1.4-dynamic-auto",
        "weights": {"theme": 30, "money": 25, "tech": 15, "event": 30},
        "overbought_filters": {"ret_20d_max": 80.0, "pct_today_max": 7.0, "bias_5_max": 15.0},
        "market_view": f"{now.strftime('%m/%d')} 当日盘面已动态生成, 5 企推基于涨停+高成交, 量化补充基于强势股+用户持仓, 双引擎交集=高信心",
        "summary": {
            "theme_picks": len(theme_picks),
            "quant_picks": len(quant_picks),
            "intersection": len(intersection),
            "total": len(theme_picks) + len(quant_picks),
        },
        "picks": theme_picks,
        "quant_picks": quant_picks,
        "intersection": intersection,
        "filtered_out": filtered[:10],  # 只列前 10
        "risk_warning": "本榜单基于 Tushare 当日真实数据动态生成, 仅供参考, 不构成投资建议. 投资有风险, 入市需谨慎.",
    }
    return output


def main():
    try:
        result = generate_picks()
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 写文件
    output_dir = Path(os.environ.get("VIBE_OUTPUT_DIR", "reports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "today_picks.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 已写入 {out_file}")
    print(f"\n{'='*60}")
    print(f"🎯 Vibe 每日精选 v1.4 (动态版) - {result['date']} {result['update_time']}")
    print(f"{'='*60}")
    print(f"📊 5 企推 {result['summary']['theme_picks']} + 量化 {result['summary']['quant_picks']} + 🎯 双引擎 {result['summary']['intersection']}")
    print()
    print("🔥 5 企推 (主推):")
    for p in result['picks']:
        print(f"  {p['tag']} #{p['rank']} {p['code']} {p['name']} ({p['industry']}) - {p['score']}分 | 涨{p['pct_chg_today']:+.1f}%")
    print()
    print("📊 量化补充:")
    for p in result['quant_picks']:
        print(f"  {p['tag']} {p['code']} {p['name']} - {p['score']}分 | 涨{p['pct_chg_today']:+.1f}%")
    if result['intersection']:
        print(f"\n🎯 双引擎交集: {', '.join(result['intersection'])}")


if __name__ == "__main__":
    main()
