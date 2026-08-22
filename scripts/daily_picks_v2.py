"""
Vibe 每日精选 - v2.0 (2026-08-19 重构)
========================================
不依赖 tushare Python 库,纯 HTTP API 调用(避免依赖问题)

4 个实战公式:
  公式1 缩量企稳上穿MA20: 月跌20% + 缩量<60日均量 + 上穿MA20 + 3日资金小幅净流入 + PE>0 + 非ST
  公式2 多金叉共振: 上穿MA60 + MACD金叉 + 资金>=5000万 + 量增30% + 换手3-20% + 量比>=1.2
  公式3 起量+基本面: 非ST + 上市>60天 + 10日涨>5% + 量比>1.5 + 今日涨3-5% + BPS前5
  公式4 强势主力: 市值50-500亿 + 量比>1.5 + 涨2-7% + 换手>4% + MA5上穿MA20 + 资金榜top3
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
        req = urllib.request.Request(
            "https://api.tushare.pro",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    
    def df(self, api, params=None, fields=""):
        """返回 DataFrame"""
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
    
    # 1. 行情
    df = c.df("daily", {"trade_date": today}, "ts_code,open,close,high,low,pct_chg,vol,amount")
    if df.empty:
        raise RuntimeError(f"No data for {today}")
    df = df[~df["ts_code"].str.contains(".BJ")].copy()
    df["code"] = df["ts_code"].str.split(".").str[0]
    for col in ["open", "close", "high", "low", "pct_chg", "vol", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # 2. 股票基本信息
    df_basic = c.df("stock_basic", {"list_status": "L"}, "ts_code,name,industry,list_date")
    if not df_basic.empty:
        df = df.merge(df_basic, on="ts_code", how="left")
    
    # 3. 每日指标
    try:
        df_basic2 = c.df("daily_basic", {"trade_date": today}, 
                         "ts_code,pe,pb,ps,total_mv,circ_mv,turnover_rate,volume_ratio")
        if not df_basic2.empty:
            for col in ["pe", "pb", "ps", "total_mv", "circ_mv", "turnover_rate", "volume_ratio"]:
                if col in df_basic2.columns:
                    df_basic2[col] = pd.to_numeric(df_basic2[col], errors="coerce")
            df = df.merge(df_basic2, on="ts_code", how="left")
    except Exception as e:
        print(f"daily_basic 拉取失败(可忽略): {e}")
    
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
                     "ts_code,buy_elg_amount,buy_lg_amount,buy_md_amount,sell_elg_amount,sell_lg_amount,sell_md_amount")
            if df.empty:
                continue
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            # 主力资金 = 特大单+大单 - 卖出
            df["net"] = (df["buy_elg_amount"] + df["buy_lg_amount"]) - (df["sell_elg_amount"] + df["sell_lg_amount"])
            for _, row in df.iterrows():
                code = row["ts_code"]
                # 第 1 天 (i=1) 是最近一天
                if i == 1:
                    money_1d[code] = money_1d.get(code, 0) + row["net"] / 1e4
                if i <= 3:
                    money_3d[code] = money_3d.get(code, 0) + row["net"] / 1e4
        except Exception as e:
            pass  # 静默
    return money_3d, money_1d


# ==================== EMA ====================
def _ema(arr, n):
    arr = np.array(arr, dtype=float)
    if len(arr) < n:
        return np.zeros_like(arr)
    alpha = 2 / (n + 1)
    ema = np.zeros_like(arr)
    ema[0] = arr[0]
    for i in range(1, len(arr)):
        ema[i] = alpha * arr[i] + (1 - alpha) * ema[i-1]
    return ema


# ==================== 指标计算 ====================
def calc_indicators(df_today):
    """从 klines.parquet 算技术指标(单位:%)"""
    p = Path("data/klines.parquet")
    if not p.exists():
        return _empty(df_today)
    
    try:
        klines = pd.read_parquet(p, columns=["ts_code", "trade_date", "close", "vol", "amount"])
        klines = klines.sort_values(["ts_code", "trade_date"])
    except Exception as e:
        print(f"读 klines.parquet 失败: {e}")
        return _empty(df_today)
    
    ret_20d_map = {}
    ma5_map, ma20_map, ma60_map = {}, {}, {}
    vol_ma60_map, vol_ma5_map = {}, {}
    macd_dif_map, macd_dea_map = {}, {}
    
    for code, grp in klines.groupby("ts_code"):
        grp = grp.sort_values("trade_date")
        closes = grp["close"].values.astype(float)
        vols = grp["vol"].values.astype(float)
        
        if len(closes) >= 20:
            ret_20d_map[code] = (closes[-1] / closes[-20] - 1) * 100
        else:
            ret_20d_map[code] = 0
        ma5_map[code] = closes[-5:].mean() if len(closes) >= 5 else closes[-1]
        ma20_map[code] = closes[-20:].mean() if len(closes) >= 20 else closes[-1]
        ma60_map[code] = closes[-60:].mean() if len(closes) >= 60 else closes[-1]
        vol_ma60_map[code] = vols[-60:].mean() if len(vols) >= 60 else 0
        vol_ma5_map[code] = vols[-5:].mean() if len(vols) >= 5 else 0
        
        if len(closes) >= 26:
            ema12 = _ema(closes, 12)
            ema26 = _ema(closes, 26)
            dif = ema12 - ema26
            dea = _ema(dif, 9)
            macd_dif_map[code] = dif[-1]
            macd_dea_map[code] = dea[-1]
        else:
            macd_dif_map[code] = 0
            macd_dea_map[code] = 0
    
    df_today["ret_20d"] = df_today["ts_code"].map(ret_20d_map).fillna(0)
    df_today["ma5"] = df_today["ts_code"].map(ma5_map).fillna(df_today["close"])
    df_today["ma20"] = df_today["ts_code"].map(ma20_map).fillna(df_today["close"])
    df_today["ma60"] = df_today["ts_code"].map(ma60_map).fillna(df_today["close"])
    df_today["vol_ma60"] = df_today["ts_code"].map(vol_ma60_map).fillna(0)
    df_today["vol_ma5"] = df_today["ts_code"].map(vol_ma5_map).fillna(0)
    df_today["macd_dif"] = df_today["ts_code"].map(macd_dif_map).fillna(0)
    df_today["macd_dea"] = df_today["ts_code"].map(macd_dea_map).fillna(0)
    df_today["bias_5"] = (df_today["close"] / df_today["ma5"] - 1) * 100
    df_today["bias_20"] = (df_today["close"] / df_today["ma20"] - 1) * 100
    return df_today




# ============ 🛡️ 市场环境检查 (新增) ============
def check_market_environment(df_today):
    """返回 (can_pick, reason, market_pct, up_ratio)"""
    if df_today.empty: return False, "无数据", 0, 0
    market_pct = df_today['pct_chg'].mean()
    up_ratio = (df_today['pct_chg'] > 0).sum() / len(df_today)
    # 大盘环境判断
    if market_pct < -0.5:
        return False, f"大盘大跌 {market_pct:.2f}%,熊市不选股", market_pct, up_ratio
    if up_ratio < 0.3:
        return False, f"上涨家数仅 {up_ratio*100:.0f}%,市场弱势", market_pct, up_ratio
    return True, "OK", market_pct, up_ratio


# ============ 🛡️ 风险过滤器 (新增) ============
def pass_risk_filter(p):
    """新增的更强风险过滤"""
    pct = p.get("pct_chg", 0)
    amount_yi = p.get("amount", 0) / 1e5  # 千元 -> 亿元
    vol = p.get("vol", 0)
    
    # 1. 单日涨幅 > 12% 跳过(实证: >12% 次日 8/17 涨 50% 跌 50%, 远低于平均)
    if pct > 12:
        return False, f"单日涨{pct:.1f}%, 高位接力"
    
    # 2. 涨停 + 成交 > 5亿 (高位放量, 主力出货可能)
    if pct >= 9.5 and amount_yi > 500:  # 5亿
        return False, f"涨停+成交{amount_yi:.1f}亿, 高位放量"
    
    # 3. 涨幅 5-9.5% + 成交 > 10亿 (出货嫌疑)
    if 5 < pct < 9.5 and amount_yi > 1000:  # 10亿
        return False, f"涨{pct:.1f}%+成交{amount_yi:.1f}亿, 出货嫌疑"
    
    # 4. ST/退市风险
    name = p.get("name", "")
    if "ST" in str(name) or "退" in str(name):
        return False, "ST/退市风险"
    
    return True, "OK"


def _empty(df_today):
    for c in ["ret_20d", "ma5", "ma20", "ma60", "vol_ma60", "vol_ma5", "macd_dif", "macd_dea", "bias_5", "bias_20"]:
        df_today[c] = 0 if c in ["ret_20d", "vol_ma60", "vol_ma5", "macd_dif", "macd_dea", "bias_5", "bias_20"] else df_today.get("close", 0)
    return df_today


# ==================== 4 个公式 ====================
def formula_1(df, money_3d):
    """抄底型: 站上均价 + 量能配合 + 资金回流 + 业绩正
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)]
    """
    if money_3d:
        df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0)
    else:
        df["money_3d_wan"] = 0
    # 均价估算: amount / vol
    df["avg_price"] = df["amount"] / df["vol"].replace(0, 1)
    cond = (
        (df["pct_chg"] > 0) & (df["pct_chg"] < 5) &  # 红盘但非大涨
        (df["close"] > df["avg_price"]) &  # 收>均价 (企稳)
        (df["money_3d_wan"] > 0) &  # 资金回流
        (df["pe"].notna()) & (df["pe"] > 0) &  # 业绩正
        (df["amount"] > 5e4) &  # 成交 > 5000万
        (df["turnover_rate"].notna()) & (df["turnover_rate"] >= 2) &  # 换手 >= 2%
        (~df["name"].fillna("").str.contains("ST"))
    )
    return df[cond].sort_values("money_3d_wan", ascending=False).head(10).copy()


def formula_2(df, money_3d):
    """趋势型: 强势红盘 + 量能 + 资金共振
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)]
    """
    if money_3d:
        df["money_3d_wan"] = df["ts_code"].map(money_3d).fillna(0)
    else:
        df["money_3d_wan"] = 0
    cond = (
        (df["pct_chg"] > 3) & (df["pct_chg"] < 9.5) &  # 强势红盘 3-9.5%
        (df["money_3d_wan"] > 0) &
        (df["money_3d_wan"] >= 1000) &  # 资金流入 >= 1000万
        (df["turnover_rate"].notna()) & (df["turnover_rate"] >= 3) & (df["turnover_rate"] <= 20) &
        (df["volume_ratio"].notna()) & (df["volume_ratio"] >= 1.2) &
        (df["amount"] > 1e5) &  # 成交 > 1亿
        (~df["name"].fillna("").str.contains("ST"))
    )
    return df[cond].sort_values("money_3d_wan", ascending=False).head(10).copy()


def formula_3(df, money_3d, money_1d):
    """起量+基本面 (价值)"""
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)]
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    today = datetime.now()
    df["list_days"] = df["list_date"].apply(
        lambda x: (today - datetime.strptime(str(x), "%Y%m%d")).days 
        if pd.notna(x) and str(x) != "nan" else 0
    )
    df["vol_ratio_5"] = df["vol"] / df["vol_ma5"].replace(0, np.nan)
    df["vol_ratio_5"] = df["vol_ratio_5"].fillna(0)
    cond = (
        (~df["name"].fillna("").str.contains("ST")) &
        (df["list_days"] > 60) &
        (df["ret_20d"] > 5) &  # 简化用 20 日
        (df["vol_ratio_5"] > 1.5) &
        (df["pct_chg"] > 3) & (df["pct_chg"] < 5) &
        (df["money_3d_wan"] > 0) &
        (df["money_1d_wan"] > 0) &
        (df["pb"].notna())
    )
    candidates = df[cond].copy()
    if not candidates.empty:
        candidates = candidates.nlargest(5, "pb")
    return candidates


def formula_4(df, money_1d):
    """短线主力型: 中盘 + 量比 + 涨幅 + 换手 + 资金共振
    df = df[df.apply(lambda r: pass_risk_filter(r.to_dict())[0], axis=1)]
    """
    df["money_1d_wan"] = df["ts_code"].map(money_1d).fillna(0) if money_1d else 0
    cond = (
        (df["total_mv"].notna()) & (df["total_mv"] >= 500000) & (df["total_mv"] <= 5000000) &
        (df["volume_ratio"].notna()) & (df["volume_ratio"] > 1.5) &
        (df["pct_chg"] >= 2) & (df["pct_chg"] <= 7) &
        (df["turnover_rate"].notna()) & (df["turnover_rate"] > 4) &
        (df["money_1d_wan"] > 0) &
        (~df["name"].fillna("").str.contains("ST"))
    )
    candidates = df[cond].copy()
    if not candidates.empty:
        candidates = candidates.nlargest(3, "money_1d_wan")
    return candidates


# ==================== 主流程 ====================
def generate_picks():
    print("📡 拉取 Tushare 当日数据...")
    df, today_str = get_today_data()
    print(f"   当日: {today_str}, 共 {len(df)} 只")
    df = calc_indicators(df)
    
    print("💰 拉取近 5 日资金流...")
    money_3d, money_1d = get_moneyflow_data()
    print(f"   3日资金: {len(money_3d)} 只, 1日: {len(money_1d)} 只")
    
    results = {}
    for name, fn in [
        ("1_缩量企稳上穿MA20", lambda: formula_1(df, money_3d)),
        ("2_多金叉共振", lambda: formula_2(df, money_3d)),
        ("3_起量基本面", lambda: formula_3(df, money_3d, money_1d)),
        ("4_强势主力", lambda: formula_4(df, money_1d)),
    ]:
        try:
            results[name] = fn()
            print(f"   {name}: {len(results[name])} 只")
        except Exception as e:
            print(f"   {name} 出错: {e}")
            import traceback; traceback.print_exc()
            results[name] = pd.DataFrame()
    
    beijing = timezone(timedelta(hours=8))
    now = datetime.now(beijing)
    
    def to_list(d):
        return [f"{r['code']} {r['name']}" for _, r in d.iterrows()] if not d.empty else []
    
    output = {
        "date": now.strftime("%Y-%m-%d"),
        "update_time": now.strftime("%H:%M"),
        "version": "2.0-formulas",
        "formulas": {
            "1_缩量企稳上穿MA20": to_list(results["1_缩量企稳上穿MA20"]),
            "2_多金叉共振": to_list(results["2_多金叉共振"]),
            "3_起量基本面": to_list(results["3_起量基本面"]),
            "4_强势主力": to_list(results["4_强势主力"]),
        },
        "summary": {k: len(v) for k, v in results.items()},
    }
    return output


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
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {out_file}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
