#!/usr/bin/env python3
"""Vibe 量化数据更新 - Tushare Pro 真实数据版
v3.6 优化: 按日期批量拉 (1 天 = 1 次 API 调用), 限流重试, 进度可见
- 平时增量 1-3 天 ≈ 3 次 API 调用, 30-60 秒
- 全市场补拉 90 天 ≈ 90 次 API 调用, 5-10 分钟
"""
import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get('TUSHARE_TOKEN', '')
if not TOKEN:
    raise ValueError("TUSHARE_TOKEN 未设置")

import tushare as ts
ts.set_token(TOKEN)
pro = ts.pro_api()

os.makedirs('data', exist_ok=True)

print(f"开始更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ========== 辅助: Tushare 限流重试 ==========
def tushare_call(func, max_retry=3, **kwargs):
    """带限流重试的 Tushare 调用"""
    for attempt in range(max_retry):
        try:
            df = func(**kwargs)
            return df
        except Exception as e:
            err = str(e)
            if '每分钟' in err or '限流' in err or 'rate' in err.lower() or '600' in err:
                wait = 15 * (attempt + 1)
                print(f"  ⚠️ 限流, sleep {wait}s (重试 {attempt+1}/{max_retry})")
                time.sleep(wait)
            elif 'token' in err.lower():
                raise
            else:
                wait = 3 * (attempt + 1)
                print(f"  ⚠️ {err[:80]}, sleep {wait}s (重试 {attempt+1}/{max_retry})")
                time.sleep(wait)
    print(f"  ❌ 重试 {max_retry} 次仍失败, 跳过")
    return None

# ========== Tushare 交易日历 ==========
print("\n[1/5] 交易日历...")
df_cal = tushare_call(pro.trade_cal, exchange='SSE', is_open='1',
                       start_date='20250101',
                       end_date=datetime.now().strftime('%Y%m%d'),
                       fields='cal_date,is_open,pretrade_date')
if df_cal is None or df_cal.empty:
    print("❌ 交易日历拉取失败, 终止")
    exit(1)
trade_dates = sorted(df_cal['cal_date'].tolist())
print(f"  交易日: {trade_dates[0]} ~ {trade_dates[-1]} (共 {len(trade_dates)} 天)")

# ========== 拉 A 股列表 ==========
print("\n[2/5] 拉取 A 股列表...")
df_basic = tushare_call(
    pro.stock_basic,
    list_status='L',
    fields='ts_code,symbol,name,industry,market,list_date'
)
if df_basic is None or df_basic.empty:
    print("❌ 拉股票列表失败, 终止")
    exit(1)
print(f"  获取 {len(df_basic)} 只")

df_basic = df_basic.rename(columns={'symbol': 'code'})
df_basic['code'] = df_basic['code'].astype(str).str.zfill(6)
df_basic['industry'] = df_basic['industry'].astype(str).fillna('未分类')
df_basic['name'] = df_basic['name'].astype(str)
df_basic['price'] = 0.0
df_basic['pct_change'] = 0.0
df_basic['market_cap_yi'] = 0.0

df_basic[['code', 'name', 'industry', 'price', 'pct_change', 'market_cap_yi']].to_csv(
    'data/stock_list.csv', index=False, encoding='utf-8-sig'
)
print(f"  ✅ stock_list.csv")

industry_map = dict(zip(df_basic['code'], df_basic['industry']))
with open('data/industry_map.json', 'w', encoding='utf-8') as f:
    json.dump(industry_map, f, ensure_ascii=False)
print(f"  ✅ industry_map.json ({len(industry_map)} 项)")

name_map = dict(zip(df_basic['code'], df_basic['name']))

# ========== 智能增量 K 线 (按日期批量) ==========
print("\n[3/5] 拉取 K 线 (按日期批量)...")

# 读已有 parquet
last_date = None
df_existing = None
if os.path.exists('data/klines.parquet'):
    try:
        df_existing = pd.read_parquet('data/klines.parquet')
        if 'date' in df_existing.columns and len(df_existing) > 0:
            last_date = df_existing['date'].max()
            print(f"  已有 K 线最后日期: {last_date}")
    except Exception as e:
        print(f"  ⚠️ 读已有 parquet 失败: {e}")

# 决定要拉哪些日期
if last_date:
    last_date_ts = pd.to_datetime(last_date)
    dates_to_fetch = [d for d in trade_dates if pd.to_datetime(d) > last_date_ts]
    if not dates_to_fetch:
        print(f"  数据已最新, 跳过 K 线")
        dates_to_fetch = []
else:
    # 首次: 拉最近 60 个交易日
    dates_to_fetch = trade_dates[-60:]
    print(f"  无已有 K 线, 拉最近 60 个交易日: {dates_to_fetch[0]} ~ {dates_to_fetch[-1]}")

print(f"  待拉交易日: {len(dates_to_fetch)} 天")

df_new_all = []
for i, d in enumerate(dates_to_fetch):
    df_day = tushare_call(pro.daily, max_retry=3, trade_date=d)
    if df_day is not None and not df_day.empty:
        df_new_all.append(df_day)
    if (i + 1) % 10 == 0:
        print(f"  进度: {i+1}/{len(dates_to_fetch)} 天")
    time.sleep(0.1)  # 礼貌延迟

print(f"  拉取完成, {len(dates_to_fetch)} 天共 {sum(len(d) for d in df_new_all)} 条")

# 合并
if df_new_all:
    df_new = pd.concat(df_new_all, ignore_index=True)
    df_new = df_new.loc[:, ~df_new.columns.duplicated()]
    df_new = df_new.rename(columns={
        'trade_date': 'date', 'vol': 'volume', 'pct_chg': 'pct_change'
    })
    df_new['date'] = pd.to_datetime(df_new['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    df_new['code'] = df_new['ts_code'].str.split('.').str[0].str.zfill(6)
    df_new['name'] = df_new['code'].map(name_map)
    df_new['industry'] = df_new['code'].map(industry_map).fillna('未分类')
    
    if df_existing is not None and len(df_existing) > 0:
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
        df_all = df_all.drop_duplicates(subset=['ts_code', 'date'], keep='last')
    else:
        df_all = df_new
else:
    df_all = df_existing if df_existing is not None else pd.DataFrame()

# 字段顺序
cols = ['date', 'code', 'name', 'industry', 'open', 'high', 'low', 'close',
        'pre_close', 'change', 'pct_change', 'volume', 'amount', 'ts_code']
cols = [c for c in cols if c in df_all.columns]
df_all = df_all[cols]

try:
    df_all.to_parquet('data/klines.parquet', index=False)
    print(f"  ✅ klines.parquet: {len(df_all)} 条")
except Exception as e:
    df_all.to_csv('data/klines.csv', index=False)
    print(f"  ✅ klines.csv: {len(df_all)} 条")

# ========== 今日行情 ==========
print("\n[4/5] 拉取今日行情...")
end_date = datetime.now().strftime('%Y%m%d')
df_today = tushare_call(pro.daily, max_retry=3, trade_date=end_date)
if df_today is not None and not df_today.empty:
    df_today = df_today.loc[:, ~df_today.columns.duplicated()]
    df_today['code'] = df_today['ts_code'].str.split('.').str[0].str.zfill(6)
    df_today['name'] = df_today['code'].map(name_map)
    df_today['industry'] = df_today['code'].map(industry_map).fillna('未分类')
    df_today = df_today.rename(columns={'pct_chg': 'pct_change', 'vol': 'volume'})
    df_today.to_csv('data/today_quote.csv', index=False, encoding='utf-8-sig')
    print(f"  ✅ today_quote.csv: {len(df_today)} 条")
    
    # 填充 stock_list
    price_map = dict(zip(df_today['code'], df_today['close']))
    pct_map = dict(zip(df_today['code'], df_today['pct_change']))
    df_basic['price'] = df_basic['code'].map(price_map).fillna(0.0)
    df_basic['pct_change'] = df_basic['code'].map(pct_map).fillna(0.0)
    df_basic[['code', 'name', 'industry', 'price', 'pct_change', 'market_cap_yi']].to_csv(
        'data/stock_list.csv', index=False, encoding='utf-8-sig'
    )
    print(f"  ✅ stock_list.csv 已用 {len(price_map)} 只今日价格填充")
else:
    print(f"  ⚠️ 今日行情拉取失败 (可能非交易日或限流)")

with open('data/last_update.txt', 'w') as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d')}T17:30:00")
print(f"  ✅ last_update.txt")

# ========== 触发选股 ==========
print("\n[5/5] 生成今日精选 daily_picks_dynamic.py (动态版)...")
import subprocess
try:
    os.makedirs('reports', exist_ok=True)
    result = subprocess.run(
        ['python', 'scripts/daily_picks_dynamic.py'],
        capture_output=True, text=True, timeout=300,
        env={**__import__('os').environ, 'VIBE_OUTPUT_DIR': 'data'}
    )
    if result.returncode == 0:
        print(f"  ✅ daily_picks_dynamic 完成")
    else:
        print(f"  ⚠️ daily_picks_dynamic 失败 (returncode={result.returncode})")
        print(f"  stderr: {result.stderr[:200]}")
except Exception as e:
    print(f"  ⚠️ daily_picks_dynamic 异常: {e}")

print(f"\n🎉 数据更新完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
