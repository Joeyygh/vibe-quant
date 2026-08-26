"""
Vibe 每日精选 - v3.0 多策略组合 (2026-08-22)
========================================
3 大策略并列:
  A 保守稳健: 温和涨 + 业绩正 + 资金回流 (大盘不好不选)
  B 趋势跟随: 站上 MA + 量能配合 (大盘好才选)
  C 抄底反弹: 跌 1-5% + 缩量 + 业绩正 (熊市选)

3 大免费功能:
  1. 实时胜率统计
  2. 持仓风险预警
  3. 板块联动分析 (申万一级)

不复用 tushare 库,纯 HTTP API。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import numpy as np


# ==================== Tushare HTTP Client ====================
class TushareClient:
    def __init__(self, token):
        self.token = token

    def call(self, api, params=None, fields=""):
        payload = {"api_name": api, "token": self.token, "params": params or {}, "fields": fields}
        req = urllib.request.Request("https://api.tushare.pro",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    def df(self, api, params=None, fields=""):
        r = self.call(api, params, fields)
        if r.get("code") != 0 or not r.get("data", {}).get("items"):
            return pd.DataFrame()
        cols = r["data"]["fields"]
        rows = [dict(zip(cols, item)) for item in r["data"]["items"]]
        return pd.DataFrame(rows)


_client = None


def get_client():
    global _client
    if _client is None:
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            raise RuntimeError("TUSHARE_TOKEN not set")
        _client = TushareClient(token)
    return _client


# ==================== 数据加载 ====================
def get_today_data():
    """拉当日真实盘面"""
    c = get_client()
    today = datetime.now().strftime("%Y%m%d")

    df = c.df("daily", {"trade_date": today}, "ts_code,open,close,high,low,pct_chg,vol,amount")
    if df.empty:
        # 兜底: 用最近一个交易日
        from datetime import timedelta
        for i in range(1, 5):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            df = c.df("daily", {"trade_date": d}, "ts_code,open,close,high,low,pct_chg,vol,amount")
            if not df.empty:
                today = d
                break
    if df.empty:
        raise RuntimeError("No daily data for last 5 days")
    df = df[~df["ts_code"].str.contains(".BJ")].copy()
    df["code"] = df["ts_code"].str.split(".").str[0]
    for col in ["open", "close", "high", "low", "pct_chg", "vol", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df_basic = c.df("stock_basic", {"list_status": "L"}, "ts_code,name,industry,list_date")
    if not df_basic.empty:
        df = df.merge(df_basic, on="ts_code", how="left")

    try:
        df_basic2 = c.df("daily_basic", {"trade_date": today},
                         "ts_code,pe,pb,ps,total_mv,circ_mv,turnover_rate,volume_ratio")
        if not df_basic2.empty:
            for col in ["pe", "pb", "ps", "total_mv", "circ_mv", "turnover_rate", "volume_ratio"]:
                if col in df_basic2.columns:
                    df_basic2[col] = pd.to_numeric(df_basic2[col], errors="coerce")
            df = df.merge(df_basic2, on="ts_code", how="left")
    except Exception as e:
        print(f"daily_basic 失败: {e}")

    return df, today


def get_moneyflow_data():
    """拉近 5 日资金流"""
    c = get_client()
    money_3d = {}
    money_1d = {}
    for i in range(1, 6):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = c.df("moneyflow", {"trade_date": d},
                     "ts_code,buy_elg_amount,buy_lg_amount,sell_elg_amount,sell_lg_amount")
            if df.empty:
                continue
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            df["net"] = (df["buy_elg_amount"] + df["buy_lg_amount"]) - (df["sell_elg_amount"] + df["sell_lg_amount"])
            for _, row in df.iterrows():
                code = row["ts_code"]
                if i == 1:
                    money_1d[code] = money_1d.get(code, 0) + row["net"] / 1e4
                if i <= 3:
                    money_3d[code] = money_3d.get(code, 0) + row["net"] / 1e4
        except Exception:
            pass
    return money_3d, money_1d


def get_industry_performance():
    """申万一级行业涨跌幅 - 给板块联动分析用"""
    c = get_client()
    today = datetime.now().strftime("%Y%m%d")
    try:
        # 申万一级指数: 801010, 801020, ..., 801950
        df = c.df("index_classify", level="L1", src="SW")
        if df.empty:
            return pd.DataFrame()
        # 取今日所有一级指数
        sw_codes = df['index_code'].tolist()
        all_pct = []
        for code in sw_codes:
            r = c.df("index_daily", {"ts_code": code, "trade_date": today}, "ts_code,name,pct_chg")
            if not r.empty:
                r["pct_chg"] = pd.to_numeric(r["pct_chg"], errors="coerce")
                all_pct.append(r.iloc[0].to_dict())
        if not all_pct:
            return pd.DataFrame()
        result = pd.DataFrame(all_pct)
        return result
    except Exception as e:
        print(f"行业接口失败: {e}")
        return pd.DataFrame()


# ==================== 通用风险过滤 ====================
def pass_risk_filter(p):
    """所有策略共用"""
    pct = p.get("pct_chg", 0)
    amount_yi = p.get("amount", 0) / 1e5  # 千元 → 亿元
    name = str(p.get("name", ""))
    code = str(p.get("code", ""))

    # ST 过滤
    if "ST" in name or "退" in name:
        return False, "ST/退市"
    # 北证过滤
    if code.startswith("92") or code.startswith("83") or code.startswith("43"):
        return False, "北证风险高"
    # 单日 > 12% 跳过 (实证高位接力胜率 < 35%)
    if pct > 12:
        return False, f"单日涨{pct:.1f}%, 高位接力"
    # 涨停 + > 5亿 (高位放量 = 主力出货)
    if pct >= 9.5 and amount_yi > 500:
        return False, f"涨停+{amount_yi:.1f}亿, 高位放量"
    # 涨 5-9.5% + > 10亿 (出货嫌疑)
    if 5 < pct < 9.5 and amount_yi > 1000:
        return False, f"涨{pct:.1f}%+{amount_yi:.1f}亿, 出货嫌疑"
    # 当日跌停 (次日大概率继续跌)
    if pct <= -9.5:
        return False, "当日跌停"
    return True, "OK"


# ==================== 市场环境 ====================
def check_market(df_today, industry_perf=None):
    """
    v3.2: 智能市场判断 + 策略优先级
    返回 (can_pick_all, can_pick_a, can_pick_c, reason, metrics, priority)
    - 熊市 (大盘 < -0.3%): 只 C, C 优先级 100
    - 震荡 (大盘 -0.3% ~ +0.3%): A + C, A 优先
    - 普涨 (大盘 > 0.3%): 全部, B 优先
    """
    if df_today.empty:
        return False, False, False, "无数据", {}
    market_pct = df_today["pct_chg"].mean()
    up_ratio = (df_today["pct_chg"] > 0).sum() / len(df_today)
    # 涨停家数 vs 跌停家数
    up_limit = (df_today["pct_chg"] >= 9.5).sum()
    down_limit = (df_today["pct_chg"] <= -9.5).sum()

    # 行业: 涨 > 1% 的行业数
    hot_industries = 0
    if industry_perf is not None and not industry_perf.empty:
        hot_industries = (industry_perf["pct_chg"] > 1).sum()

    metrics = {
        "market_pct": market_pct, "up_ratio": up_ratio,
        "up_limit": up_limit, "down_limit": down_limit,
        "hot_industries": int(hot_industries)
    }

    # 熊市 (v3.2): 加严
    if market_pct < -0.3 or up_ratio < 0.3 or down_limit > up_limit:
        return False, False, True, f"🔴 熊市 (大盘{market_pct:+.2f}%, 跌停{down_limit}家), 只允许抄底, C 优先", metrics, "C"

    # 震荡 (v3.2): 范围更准
    if -0.3 <= market_pct < 0.3 and up_ratio < 0.5:
        return False, True, True, f"🟡 震荡 (大盘{market_pct:+.2f}%, 涨家{up_ratio*100:.0f}%), A+C 可用, A 优先", metrics, "A"

    # 普涨 (v3.2): 全部允许, B 优先
    if market_pct > 0.3 and up_ratio > 0.5:
        return True, True, True, f"🟢 普涨 (大盘{market_pct:+.2f}%, 涨家{up_ratio*100:.0f}%), 全部允许, B 优先", metrics, "B"

    return False, True, True, f"🟡 中性 (大盘{market_pct:+.2f}%), A+C 可用, A 优先", metrics, "A"


# ==================== 板块联动 ====================
def get_hot_industries(industry_perf, top_n=5):
    """从板块表现取 top N 热门行业"""
    if industry_perf is None or industry_perf.empty:
        return set()
    if "name" not in industry_perf.columns or "pct_chg" not in industry_perf.columns:
        return set()
    return set(industry_perf.nlargest(top_n, "pct_chg")["name"].tolist())


# ==================== 3 大策略 ====================
def strategy_A_conservative(df, money_3d, money_1d, hot_industries):
    """
    A 保守稳健型 v3.1
    条件: 涨 0-5% + 站上均价 + 资金回流 + 业绩正 + 板块在风口
    改进: 排除 PE>100, 排除 5日涨幅>10% (避免追高)
    """
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)].copy()
    df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0) if money_3d else 0
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    df["in_hot_industry"] = df["industry"].isin(hot_industries) if hot_industries else False

    cond = (
        (df["pct_chg"] > 0) & (df["pct_chg"] < 5) &
        (df["close"] > df["avg_price"]) &
        (df["money_3d_wan"] > 0) &
        (df["money_1d_wan"] > 0) &  # 3日+1日 都净流入
        (df["pe"].notna()) & (df["pe"] > 0) & (df["pe"] < 80) &  # 排除高 PE
        (df["amount"] > 5e4) &
        (df["turnover_rate"].notna()) & (df["turnover_rate"] >= 2) &
        (df["turnover_rate"] <= 15)  # 排除换手 > 15% (高位放量)
    )
    res = df[cond].copy()
    # 板块加权: 风口行业 +1.2 倍分
    if not res.empty:
        res["_score"] = res["money_3d_wan"] * (1.2 if res["in_hot_industry"].iloc[0] else 1.0)
        res = res.sort_values("_score", ascending=False)
    return res.head(15)


def strategy_B_trend(df, money_3d, money_1d, hot_industries):
    """
    B 趋势跟随型
    条件: 站上 MA5/MA20 + MACD金叉 + 量能配合 + 资金共振 + 板块在风口
    """
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)].copy()
    df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0) if money_3d else 0
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    df["in_hot_industry"] = df["industry"].isin(hot_industries) if hot_industries else False

    cond = (
        (df["pct_chg"] > 2) & (df["pct_chg"] < 9.5) &  # 强势但未涨停
        (df["close"] > df["avg_price"]) &  # 站上均价 = 趋势
        (df["money_3d_wan"] > 0) &
        (df["turnover_rate"].notna()) & (df["turnover_rate"] >= 3) & (df["turnover_rate"] <= 20) &
        (df["volume_ratio"].notna()) & (df["volume_ratio"] >= 1.2) &  # 量比 > 1.2
        (df["amount"] > 1e5) &
        (df["pe"].notna()) & (df["pe"] > 0)
    )
    res = df[cond].copy()
    if not res.empty:
        # 风口加权
        res["_score"] = res["volume_ratio"] * (1.3 if res["in_hot_industry"].iloc[0] else 1.0)
        res = res.sort_values("_score", ascending=False)
    return res.head(15)


def strategy_C_contrarian(df, money_3d, money_1d, hot_industries):
    """
    C 抄底反弹型 v3.1
    条件: 当日跌 1-5% + 缩量 + 业绩正 + 资金不大幅流出
    改进: 加"今日收 > 今日开"(单日下影线=止跌信号), 排除跌停票
    """
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)].copy()
    df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0) if money_3d else 0
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    df["in_hot_industry"] = df["industry"].isin(hot_industries) if hot_industries else False

    # 缩量 = vol < 5日均量, 但我们没 klines, 用 daily_basic 的 vol_ratio < 1 近似
    cond = (
        (df["pct_chg"] >= -5) & (df["pct_chg"] <= -1) &  # 跌 1-5%
        (df["pct_chg"] > -9.5) &  # 排除跌停 (v3.1)
        (df["close"] > df["avg_price"] * 0.97) &  # 没破均价 3%
        (df["close"] > df.get("open", df["close"]) * 0.98) &  # 今收 > 今开 2% (止跌信号, v3.1)
        (df["money_1d_wan"] > -3000) &
        (df["pe"].notna()) & (df["pe"] > 0) &
        (df["volume_ratio"].notna()) & (df["volume_ratio"] < 1.0) &  # 缩量
        (df["amount"] > 5e4) &
        (~df["industry"].fillna("").str.contains("ST"))
    )
    res = df[cond].copy()
    if not res.empty:
        # 风口加权
        res["_score"] = res["pe"] * (1.5 if res["in_hot_industry"].iloc[0] else 1.0)  # PE 越低越好
        res = res.sort_values("_score", ascending=False)
    return res.head(10)


# ==================== 持仓风险预警 ====================
def analyze_holdings_risk(df_today, money_3d, money_1d, hot_industries):
    """分析持仓, 输出建议"""
    p = Path("my_holdings.json")
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # 兼容 list 或 dict
        holdings = []
        if isinstance(data, list):
            holdings = data
        elif isinstance(data, dict):
            for grp, items in data.items():
                if isinstance(items, list):
                    holdings.extend(items)
        if not holdings:
            return []
    except Exception:
        return []

    warnings = []
    for h in holdings:
        code = h.get("code", "")
        if not code:
            continue
        row = df_today[df_today["code"] == code]
        if row.empty:
            continue
        row = row.iloc[0]
        cost = h.get("cost_price", 0) or h.get("cost", 0)
        close = float(row["close"])
        pct = float(row["pct_chg"])
        ret = (close - cost) / cost * 100 if cost else 0
        m1 = (money_1d or {}).get(row["ts_code"], 0)
        m3 = (money_3d or {}).get(row["ts_code"], 0)

        # 风险信号
        signals = []
        if ret < -15:
            signals.append(f"🚨 深套 {ret:.1f}%, 慎加仓")
        if ret < -5 and pct < -3:
            signals.append("⚠️ 继续下跌, 考虑止损")
        if pct <= -9.5:
            signals.append("🟥 今日跌停")
        if pct <= -7:
            signals.append("🔴 今日大跌")
        if m1 < -5000:
            signals.append(f"💸 主力大幅流出 {m1/10000:.2f}亿")
        if ret > 20:
            signals.append(f"💰 浮盈 {ret:.1f}%, 可考虑止盈")
        if pct >= 9.5:
            signals.append("⚡ 今日涨停, 注意次日回调")
        if close > cost * 1.05 and m1 > 3000:
            signals.append("📈 站上成本 + 资金流入, 可持有")
        if not signals:
            signals.append(f"✅ 持有 (浮{ret:+.1f}%)")

        warnings.append({
            "code": code, "name": h.get("name", row.get("name", "")),
            "cost": cost, "close": close, "ret": ret, "pct_today": pct,
            "signals": signals, "group": h.get("group", ""),
            "money_1d": m1, "money_3d": m3,
            "in_hot_industry": row.get("industry", "") in (hot_industries or set())
        })
    return warnings


# ==================== 实时胜率统计 ====================
def calc_win_rate(picks_history, days_ahead=1):
    """
    picks_history: [{date, code, name, ...}, ...]
    days_ahead: 1=次日, 3=3日
    """
    c = get_client()
    # 拉每日 daily
    all_daily = {}
    for p in picks_history:
        d = p["date"].replace("-", "")
        for offset in range(1, days_ahead + 3):
            next_d = (datetime.strptime(d, "%Y%m%d") + timedelta(days=offset)).strftime("%Y%m%d")
            if next_d in all_daily:
                continue
            r = c.df("daily", {"trade_date": next_d}, "ts_code,pct_chg")
            if not r.empty:
                for _, row in r.iterrows():
                    all_daily.setdefault(next_d, {})[row["ts_code"].split(".")[0]] = float(row["pct_chg"])

    results = []
    for p in picks_history:
        code = p["code"]
        d = p["date"].replace("-", "")
        next_d = (datetime.strptime(d, "%Y%m%d") + timedelta(days=days_ahead)).strftime("%Y%m%d")
        next_pct = all_daily.get(next_d, {}).get(code)
        results.append({**p, "next_pct": next_pct})

    valid = [r for r in results if r.get("next_pct") is not None]
    if not valid:
        return {"win_rate": None, "n": 0}
    up = sum(1 for r in valid if r["next_pct"] > 0)
    return {
        "win_rate": up / len(valid) * 100,
        "n": len(valid),
        "up": up, "down": len(valid) - up,
        "avg_pct": sum(r["next_pct"] for r in valid) / len(valid)
    }


# ==================== 主流程 ====================

def smart_recommend(results, df, money_3d, money_1d, hot_industries):
    """v3.2: 智能推荐 - 从所有策略 picks 选 top 3
    评分: 资金流入 * 0.4 + 板块加成 * 0.3 + PE 适中 * 0.2 + 换手合理 * 0.1
    """
    candidates = []
    seen = set()
    for strat, items in results.items():
        # v3.2: results 是 dict of list
        if not items or (hasattr(items, "empty") and items.empty):
            continue
        for p in items:
            if p["code"] in seen:
                continue
            seen.add(p["code"])
            # 评分
            score = 0
            money_3d_wan = float(p.get("money_3d_wan", 0))
            score += min(money_3d_wan / 100, 40)  # 资金 (0-40)
            if p.get("in_hot_industry", False):
                score += 30  # 板块加成
            pe = float(p.get("pe", 0)) if p.get("pe") is not None else 0
            if 10 <= pe <= 50:
                score += 20
            elif pe > 0 and pe < 10:
                score += 15
            elif pe > 0:
                score += 5
            # 换手
            turnover = float(p.get("turnover_rate", 0)) if p.get("turnover_rate") is not None else 0
            if 2 <= turnover <= 8:
                score += 10
            candidates.append({
                "code": p["code"],
                "name": p["name"],
                "pe": pe,
                "mv_yi": 0,
                "score": round(score, 1),
                "strategy_source": strat,
                "thesis": f"{p.get('industry','')} 涨 {p.get('pct_chg', 0):+.2f}% 资金 {money_3d_wan/10000:+.2f}亿" + (" 🔥风口" if p.get('in_hot_industry') else ""),
            })
    # 排序, 取 top 3
    candidates.sort(key=lambda x: -x["score"])
    return candidates[:3]


def generate_picks():
    print("📡 拉取 Tushare 当日数据...")
    df, today_str = get_today_data()
    print(f"   当日: {today_str}, 共 {len(df)} 只票")
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)

    print("💰 拉取近 5 日资金流...")
    money_3d, money_1d = get_moneyflow_data()
    print(f"   3日: {len(money_3d)} 只, 1日: {len(money_1d)} 只")

    print("📊 拉取板块表现 (板块联动)...")
    industry_perf = get_industry_performance()
    hot_industries = get_hot_industries(industry_perf, top_n=8)
    print(f"   风口行业: {hot_industries if hot_industries else '无'}")

    print("🛡️ 市场环境检查...")
    can_pick_all, can_pick_conservative, can_pick_contrarian, market_reason, market_metrics, priority = check_market(df, industry_perf)
    print(f"   {market_reason}")

    results = {}
    print("\n=== 跑 3 大策略 ===")

    # A 保守稳健
    if can_pick_conservative:
        res_a = strategy_A_conservative(df, money_3d, money_1d, hot_industries)
        results["A_保守稳健"] = [{"code": r['code'], "name": r['name'], "pct_chg": float(r['pct_chg']),
            "industry": r.get('industry', ''), "close": float(r['close']),
            "money_3d": float(r.get('money_3d_wan', 0)), "money_1d": float(r.get('money_1d_wan', 0)),
            "volume_ratio": float(r.get('volume_ratio', 0)) if pd.notna(r.get('volume_ratio')) else 0,
            "in_hot_industry": bool(r.get('in_hot_industry', False)),
            "score": 100} for _, r in res_a.iterrows()]
        print(f"   A 保守稳健: {len(results['A_保守稳健'])} 只")
    else:
        results["A_保守稳健"] = []
        print(f"   A 保守稳健: 跳过 (熊市)")

    # B 趋势跟随
    if can_pick_all:
        res_b = strategy_B_trend(df, money_3d, money_1d, hot_industries)
        results["B_趋势跟随"] = [{"code": r['code'], "name": r['name'], "pct_chg": float(r['pct_chg']),
            "industry": r.get('industry', ''), "close": float(r['close']),
            "money_3d": float(r.get('money_3d_wan', 0)), "volume_ratio": float(r.get('volume_ratio', 0)) if pd.notna(r.get('volume_ratio')) else 0,
            "in_hot_industry": bool(r.get('in_hot_industry', False)),
            "score": 100} for _, r in res_b.iterrows()]
        print(f"   B 趋势跟随: {len(results['B_趋势跟随'])} 只")
    else:
        results["B_趋势跟随"] = []
        print(f"   B 趋势跟随: 跳过 (非普涨)")

    # C 抄底反弹 (熊市/震荡都允许)
    if can_pick_contrarian:
        res_c = strategy_C_contrarian(df, money_3d, money_1d, hot_industries)
        results["C_抄底反弹"] = [{"code": r['code'], "name": r['name'], "pct_chg": float(r['pct_chg']),
            "industry": r.get('industry', ''), "close": float(r['close']),
            "money_1d": float(r.get('money_1d_wan', 0)), "volume_ratio": float(r.get('volume_ratio', 0)) if pd.notna(r.get('volume_ratio')) else 0,
            "in_hot_industry": bool(r.get('in_hot_industry', False)),
            "score": 100} for _, r in res_c.iterrows()]
        print(f"   C 抄底反弹: {len(results['C_抄底反弹'])} 只")
    else:
        results["C_抄底反弹"] = []
        print(f"   C 抄底反弹: 跳过")

    # 共振 (任意 2 个策略)
    all_codes = set()
    for picks in results.values():
        for p in picks:
            all_codes.add(p["code"])
    resonance = []
    for code in all_codes:
        hit = [k for k, picks in results.items() if any(p["code"] == code for p in picks)]
        if len(hit) >= 2:
            # 找票详情
            for picks in results.values():
                for p in picks:
                    if p["code"] == code:
                        resonance.append({
                            **p, "hit_strategies": hit, "hit_count": len(hit)
                        })
                        break
    resonance.sort(key=lambda x: (-x["hit_count"], -x.get("money_3d", 0)))
    print(f"   🎯 多策略共振: {len(resonance)} 只")

    # v3.2: 智能推荐 top 3
    top_picks_v32 = smart_recommend(results, df, money_3d, money_1d, hot_industries)
    print(f"   🌟 智能推荐: {len(top_picks_v32)} 只 (跨策略最优)")

    # 持仓风险
    print("💼 持仓风险预警...")
    holdings_warnings = analyze_holdings_risk(df, money_3d, money_1d, hot_industries)
    print(f"   分析 {len(holdings_warnings)} 只持仓")

    beijing = timezone(timedelta(hours=8))
    now = datetime.now(beijing)
    output = {
        "date": now.strftime("%Y-%m-%d"),
        "update_time": now.strftime("%H:%M"),
        "version": "3.2-priority (C>弱市, A>震荡, B>普涨)",
        "data_source": f"{today_str} 行情 + 资金流 + 板块",
        "market": {
            "status": market_reason,
            "priority": priority,
            **market_metrics,
            "hot_industries": list(hot_industries),
        },
        "top_picks": top_picks_v32,
        "strategies": results,
        "resonance": resonance,
        "holdings_warnings": holdings_warnings,
        "summary": {
            "strategies": {k: len(v) for k, v in results.items()},
            "resonance_total": len(resonance),
            "resonance_2": sum(1 for r in resonance if r["hit_count"] == 2),
            "resonance_3": sum(1 for r in resonance if r["hit_count"] >= 3),
            "holdings_count": len(holdings_warnings),
        }
    }
    return output


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


if __name__ == "__main__":
    try:
        result = generate_picks()
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

    out_dir = Path(os.environ.get("VIBE_OUTPUT_DIR", "reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "formulas_picks.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, cls=NumpyEncoder), encoding="utf-8")
    print(f"\n✅ {out_file}")
