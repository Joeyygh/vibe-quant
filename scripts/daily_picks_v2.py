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


# ==================== 大盘风格判断 (v3.3 新增) ====================
def get_market_style(df_today):
    """
    v3.3: 判断大盘 vs 小盘 强弱
    - 大盘涨 > 小盘涨: 大盘风格 (价值/红利占优) → 量化(小盘)谨慎
    - 小盘涨 > 大盘涨: 小盘风格 (成长占优) → 量化(小盘)可积极
    返回: (style, large_pct, small_pct, bias_small_cap)
        bias_small_cap: True = 应该偏向小盘量化
    """
    if df_today.empty or "circ_mv" not in df_today.columns:
        return "unknown", 0, 0, False
    # 大盘: 流通市值 > 500亿
    large = df_today[df_today["circ_mv"] > 500]
    # 小盘: 流通市值 < 100亿 (v3.3 用更严的 100 亿, 避免被中盘票干扰)
    small = df_today[(df_today["circ_mv"] < 100) & (df_today["circ_mv"] > 0)]
    if large.empty or small.empty:
        return "unknown", 0, 0, False
    large_pct = large["pct_chg"].mean()
    small_pct = small["pct_chg"].mean()
    # 小盘强势 → 量化可积极
    bias_small = small_pct > large_pct
    if small_pct > large_pct + 0.3:
        style = "small_cap"  # 小盘占优
    elif large_pct > small_pct + 0.3:
        style = "large_cap"  # 大盘占优
    else:
        style = "balanced"
    return style, large_pct, small_pct, bias_small


# ==================== 量能检测 (v3.3 新增) ====================
def check_volume_regime(df_today):
    """
    v3.3: 判断量能状态
    - 放量: 当日总成交 > 5日均 (假设 vol_ratio > 1.2 的票占多数)
    - 缩量: 多数 vol_ratio < 1
    返回: ("expansion" | "contraction" | "normal", ratio, vol_ratio_avg)
    """
    if df_today.empty or "volume_ratio" not in df_today.columns:
        return "unknown", 0.5, 1.0
    vr = df_today["volume_ratio"].dropna()
    if vr.empty:
        return "unknown", 0.5, 1.0
    avg = float(vr.mean())
    up_ratio = (vr > 1.2).sum() / len(vr)  # 放量的票占比
    if up_ratio > 0.4 and avg > 1.1:
        return "expansion", up_ratio, avg
    if up_ratio < 0.25 and avg < 0.95:
        return "contraction", up_ratio, avg
    return "normal", up_ratio, avg


# ==================== 市场环境 ====================
def check_market(df_today, industry_perf=None):
    """
    v3.3: 升级市场环境判断
    - 加入: 大盘/小盘风格 + 量能状态
    - 弱市 (大盘 < -0.3% 或 大盘风格占优): 自动加重 C, 限制 B
    - 震荡 + 缩量: 加重 C, 限制 A 范围
    - 普涨 + 放量: 全部允许
    """
    if df_today.empty:
        return False, False, False, "无数据", {}
    market_pct = df_today["pct_chg"].mean()
    up_ratio = (df_today["pct_chg"] > 0).sum() / len(df_today)
    up_limit = (df_today["pct_chg"] >= 9.5).sum()
    down_limit = (df_today["pct_chg"] <= -9.5).sum()

    # v3.3: 新增大盘风格 + 量能
    style, large_pct, small_pct, bias_small = get_market_style(df_today)
    vol_status, vol_up_ratio, vol_avg = check_volume_regime(df_today)

    hot_industries = 0
    if industry_perf is not None and not industry_perf.empty:
        hot_industries = (industry_perf["pct_chg"] > 1).sum()

    metrics = {
        "market_pct": market_pct, "up_ratio": up_ratio,
        "up_limit": up_limit, "down_limit": down_limit,
        "hot_industries": int(hot_industries),
        # v3.3 新增
        "market_style": style,
        "large_cap_pct": float(large_pct),
        "small_cap_pct": float(small_pct),
        "volume_status": vol_status,
        "volume_ratio_avg": float(vol_avg),
        "bias_small_cap": bias_small,
    }

    # 熊市 (v3.3): 加严 - 大盘平均 < -0.3% 或 涨家比 < 30% 或 跌停 > 涨停
    is_bear = (market_pct < -0.3) or (up_ratio < 0.3) or (down_limit > up_limit)
    if is_bear:
        # v3.3: 熊市只允许 C + 强调"抄底优先"
        reason = f"🔴 熊市 (大盘{market_pct:+.2f}%, 跌停{down_limit}家, 风格{style}), 只允许抄底"
        return False, False, True, reason, metrics

    # 普涨: 大盘 > 0.3% 且 涨家 > 50%
    if market_pct > 0.3 and up_ratio > 0.5:
        reason = f"🟢 普涨 (大盘{market_pct:+.2f}%, 涨家{up_ratio*100:.0f}%, 风格{style}, 量能{vol_status}), 全部允许"
        return True, True, True, reason, metrics

    # 震荡/中性: -0.3% ~ +0.3% 或 涨家 30-50%
    # v3.3: 震荡时若大盘风格占优 + 缩量 → 只 A + C (不开 B)
    if style == "large_cap" and vol_status == "contraction":
        # 弱市: 大盘股涨, 小盘股不跟, 量化没机会 → 关闭 B, 加重 C
        reason = f"🟡 弱市 (大盘+{large_pct:.2f}%, 小盘{small_pct:+.2f}%, 缩量), 关闭趋势, 加重抄底"
        return False, True, True, reason, metrics

    if -0.5 <= market_pct < 0.3 and up_ratio < 0.5:
        reason = f"🟡 震荡 (大盘{market_pct:+.2f}%, 涨家{up_ratio*100:.0f}%, 风格{style}), 保守+抄底"
        return False, True, True, reason, metrics

    return False, True, True, f"🟡 中性 (大盘{market_pct:+.2f}%, 风格{style}), 保守+抄底", metrics


# ==================== 板块联动 ====================
def get_hot_industries(industry_perf, top_n=5):
    """从板块表现取 top N 热门行业"""
    if industry_perf is None or industry_perf.empty:
        return set()
    if "name" not in industry_perf.columns or "pct_chg" not in industry_perf.columns:
        return set()
    return set(industry_perf.nlargest(top_n, "pct_chg")["name"].tolist())


# ==================== 3 大策略 ====================
def strategy_A_conservative(df, money_3d, money_1d, hot_industries, market_ctx=None):
    """
    A 保守稳健型 v3.3
    v3.3 改进:
      - 加逆动量因子: 今日微跌 0-1% 反而加分 (超跌反弹机会)
      - 弱市放宽: PE < 200, 涨跌幅 0-7%
      - 大盘风格过滤: 大盘占优时只选流通市值 > 50 亿
    """
    market_ctx = market_ctx or {}
    bias_small = market_ctx.get("bias_small_cap", True)
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)].copy()
    df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0) if money_3d else 0
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    df["in_hot_industry"] = df["industry"].isin(hot_industries) if hot_industries else False

    # v3.3 弱市放宽 PE: 80 → 200
    pe_max = 200 if not bias_small else 80

    # v3.3 大盘风格过滤: 大盘占优时不要小盘票
    if not bias_small and "circ_mv" in df.columns:
        df = df[df["circ_mv"].fillna(0) > 50].copy()

    cond = (
        (df["pct_chg"] > 0) & (df["pct_chg"] < 7) &  # v3.3 放宽到 7%
        (df["close"] > df["avg_price"]) &
        (df["money_3d_wan"] > 0) &
        (df["money_1d_wan"] > 0) &
        (df["pe"].notna()) & (df["pe"] > 0) & (df["pe"] < pe_max) &
        (df["amount"] > 5e4) &
        (df["turnover_rate"].notna()) & (df["turnover_rate"] >= 2) &
        (df["turnover_rate"] <= 15)
    )
    res = df[cond].copy()
    if not res.empty:
        # v3.3 修复按行加权
        # 加分项: 资金 60% + 风口 30% + 逆动量 10% (今日微跌 0-1% 反而奖励)
        res["_score"] = (
            res["money_3d_wan"] * 0.6 +
            res["money_1d_wan"] * 0.2 +
            res["in_hot_industry"].map(lambda x: 100 if x else 0) * 0.3 +
            # 逆动量: 今日 0-1% 涨幅 (温和但不强) 加分
            res["pct_chg"].map(lambda p: 50 if 0 <= p <= 1 else 0) * 0.1
        )
        res = res.sort_values("_score", ascending=False)
    return res.head(15)


def strategy_B_trend(df, money_3d, money_1d, hot_industries, market_ctx=None):
    """
    B 趋势跟随型 v3.3
    v3.3 改进:
      - 加大盘风格过滤: 大盘占优时关闭 B (动量策略失效)
      - 加量能过滤: 缩量时不选 B
    """
    market_ctx = market_ctx or {}
    bias_small = market_ctx.get("bias_small_cap", True)
    vol_status = market_ctx.get("volume_status", "normal")

    # v3.3: 弱市或缩量 → 直接关闭 B
    if not bias_small or vol_status == "contraction":
        return df.iloc[0:0]  # 空 df

    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)].copy()
    df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0) if money_3d else 0
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    df["in_hot_industry"] = df["industry"].isin(hot_industries) if hot_industries else False

    cond = (
        (df["pct_chg"] > 2) & (df["pct_chg"] < 9.5) &
        (df["close"] > df["avg_price"]) &
        (df["money_3d_wan"] > 0) &
        (df["turnover_rate"].notna()) & (df["turnover_rate"] >= 3) & (df["turnover_rate"] <= 20) &
        (df["volume_ratio"].notna()) & (df["volume_ratio"] >= 1.2) &
        (df["amount"] > 1e5) &
        (df["pe"].notna()) & (df["pe"] > 0)
    )
    res = df[cond].copy()
    if not res.empty:
        # v3.3 修复按行加权
        res["_score"] = (
            res["volume_ratio"] * 0.5 +
            res["in_hot_industry"].map(lambda x: 100 if x else 0) * 0.3 +
            res["money_3d_wan"] * 0.2
        )
        res = res.sort_values("_score", ascending=False)
    return res.head(15)


def strategy_C_contrarian(df, money_3d, money_1d, hot_industries, market_ctx=None):
    """
    C 抄底反弹型 v3.3
    v3.3 改进:
      - 跌幅放宽到 -7% (原 -5%)
      - 加 RSI 超卖近似: 跌幅越大分越高 (逆动量核心)
      - 加 PE < 100 (估值安全垫)
      - 大盘风格过滤: 大盘占优时反而要选小盘抄底 (均值回归)
    """
    market_ctx = market_ctx or {}
    bias_small = market_ctx.get("bias_small_cap", True)

    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)].copy()
    df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0) if money_3d else 0
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    df["in_hot_industry"] = df["industry"].isin(hot_industries) if hot_industries else False

    cond = (
        (df["pct_chg"] >= -7) & (df["pct_chg"] <= -1) &  # v3.3 放宽到 -7%
        (df["pct_chg"] > -9.5) &  # 排除跌停
        (df["close"] > df["avg_price"] * 0.97) &
        (df["close"] > df.get("open", df["close"]) * 0.98) &  # 下影线止跌
        (df["money_1d_wan"] > -3000) &
        (df["pe"].notna()) & (df["pe"] > 0) & (df["pe"] < 100) &  # v3.3 加估值过滤
        (df["volume_ratio"].notna()) & (df["volume_ratio"] < 1.0) &  # 缩量
        (df["amount"] > 5e4) &
        (~df["industry"].fillna("").str.contains("ST"))
    )
    res = df[cond].copy()
    if not res.empty:
        # v3.3 修复 + 逆动量: 跌幅越大分越高 (PE 越低越好)
        # PE 越低 (valuation) + 跌幅越深 (oversold) = 越高分
        res["_oversold_score"] = -res["pct_chg"]  # 跌 5% → 5 分
        res["_score"] = (
            res["_oversold_score"] * 3 +  # 跌幅权重最高
            (100 - res["pe"]).clip(lower=0) * 0.5 +  # PE 越低越好
            res["in_hot_industry"].map(lambda x: 100 if x else 0) * 0.3 +
            res["money_1d_wan"].clip(lower=-1000, upper=1000) * 0.001  # 资金不大幅流出
        )
        res = res.sort_values("_score", ascending=False)
    return res.head(10)


# ==================== 持仓风险预警 ====================
def analyze_holdings_risk(df_today, money_3d, money_1d, hot_industries, holdings_path="my_holdings.json"):
    """分析持仓, 输出建议"""
    p = Path(holdings_path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # 兼容 list 或 dict
        holdings = []
        if isinstance(data, list):
            holdings = data
        elif isinstance(data, dict):
            # v3.3 修复: 嵌套结构兼容 {groups: {deep_loss: [...], ...}}
            for grp, items in data.items():
                if isinstance(items, list):
                    holdings.extend(items)
                elif isinstance(items, dict):
                    # 二层 dict (新版格式: {groups: {deep_loss: [{...}]}})
                    for sub_grp, sub_items in items.items():
                        if isinstance(sub_items, list):
                            holdings.extend(sub_items)
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
    can_pick_all, can_pick_conservative, can_pick_contrarian, market_reason, market_metrics = check_market(df, industry_perf)
    print(f"   {market_reason}")

    results = {}
    print("\n=== 跑 3 大策略 ===")

    # v3.3: 构造市场上下文, 传给所有策略
    market_ctx = {
        "bias_small_cap": market_metrics.get("bias_small_cap", True),
        "market_style": market_metrics.get("market_style", "balanced"),
        "volume_status": market_metrics.get("volume_status", "normal"),
    }
    print(f"   风格: {market_ctx['market_style']} | 量能: {market_ctx['volume_status']} | 偏小盘: {market_ctx['bias_small_cap']}")

    # A 保守稳健
    if can_pick_conservative:
        res_a = strategy_A_conservative(df, money_3d, money_1d, hot_industries, market_ctx)
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
        res_b = strategy_B_trend(df, money_3d, money_1d, hot_industries, market_ctx)
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
        res_c = strategy_C_contrarian(df, money_3d, money_1d, hot_industries, market_ctx)
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

    # 持仓风险
    print("💼 持仓风险预警...")
    holdings_warnings = analyze_holdings_risk(df, money_3d, money_1d, hot_industries)
    print(f"   分析 {len(holdings_warnings)} 只持仓")

    beijing = timezone(timedelta(hours=8))
    now = datetime.now(beijing)
    # v3.3: 强制盘后时间戳 (17:30), 避免早上跑也显示早上
    output = {
        "date": now.strftime("%Y-%m-%d"),
        "update_time": "17:30 (盘后)",
        "actual_run_time": now.strftime("%H:%M"),  # 真实跑批时间, 调试用
        "version": "v3.3 (大小盘风格+量能+逆动量+修复iloc[0]bug)",
        "data_source": f"{today_str} 行情 + 资金流 + 板块",
        "market": {
            "status": market_reason,
            **market_metrics,
            "hot_industries": list(hot_industries),
        },
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
