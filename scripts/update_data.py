#!/usr/bin/env python3
"""Vibe 量化数据更新 - Tushare Pro 真实数据版
v3.5 优化: 智能增量 (只拉 parquet 之后), 限流重试, 进度可见
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
print(f"Tushare 限流策略: 失败 sleep 2s, 限流 sleep 10s 重试")

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

print("\n[1/4] 拉取 A 股列表...")
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

# ========== 智能增量: 读已有 parquet 最后日期 ==========
print("\n[2/4] 拉取 K 线 (智能增量)...")
end_date = datetime.now().strftime('%Y%m%d')

# 检查已有 parquet
last_date = None
df_existing = None
if os.path.exists('data/klines.parquet'):
    try:
        df_existing = pd.read_parquet('data/klines.parquet')
        if 'date' in df_existing.columns and len(df_existing) > 0:
            last_date = df_existing['date'].max()
            # last_date 是 '2026-09-04' 这种格式,转成 YYYYMMDD
            last_date_str = pd.to_datetime(last_date).strftime('%Y%m%d')
            print(f"  已有 K 线最后日期: {last_date} ({last_date_str})")
            # 只拉这个日期之后 1 天起 (覆盖)
            start_date_dt = pd.to_datetime(last_date) + timedelta(days=1)
            start_date = start_date_dt.strftime('%Y%m%d')
            if start_date > end_date:
                print(f"  数据已最新 (klines 已有 {last_date}), 跳过 K 线拉取")
                start_date = end_date  # 让循环不执行
        else:
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
    except Exception as e:
        print(f"  ⚠️ 读已有 parquet 失败: {e}")
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
else:
    print("  没有已有 parquet, 拉 90 天历史")
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

print(f"  K 线拉取范围: {start_date} ~ {end_date}")

all_klines = []
codes = df_basic['code'].tolist()
total = len(codes)

if start_date <= end_date:
    for i, code in enumerate(codes):
        ts_code = df_basic[df_basic['code'] == code]['ts_code'].iloc[0]
        df = tushare_call(
            pro.daily,
            max_retry=2,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        if df is not None and not df.empty:
            df['code'] = code
            all_klines.append(df)
        
        if (i + 1) % 500 == 0:
            print(f"  进度: {i+1}/{total} (已拉 {len(all_klines)} 只)")
        
        # 每 100 只小睡一下, 主动避免限流
        if (i + 1) % 100 == 0:
            time.sleep(0.3)
    
    print(f"  拉取完成, 共 {len(all_klines)} 只有新数据")
    
    if all_klines:
        df_new = pd.concat(all_klines, ignore_index=True)
        df_new = df_new.loc[:, ~df_new.columns.duplicated()]
        df_new = df_new.rename(columns={
            'trade_date': 'date', 'vol': 'volume', 'pct_chg': 'pct_change'
        })
        df_new['date'] = pd.to_datetime(df_new['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        name_map = dict(zip(df_basic['code'], df_basic['name']))
        df_new['name'] = df_new['code'].map(name_map)
        df_new['industry'] = df_new['code'].map(industry_map).fillna('未分类')
        df_new['code'] = df_new['code'].astype(str).str.zfill(6)
        
        # 合并到已有
        if df_existing is not None and len(df_existing) > 0:
            df_all = pd.concat([df_existing, df_new], ignore_index=True)
            df_all = df_all.drop_duplicates(subset=['ts_code', 'date'], keep='last')
        else:
            df_all = df_new
        
        try:
            df_all.to_parquet('data/klines.parquet', index=False)
            print(f"  ✅ klines.parquet: {len(df_all)} 条 (新增 {len(df_new)})")
        except Exception as e:
            df_all.to_csv('data/klines.csv', index=False)
            print(f"  ✅ klines.csv: {len(df_all)} 条")
    else:
        df_all = df_existing if df_existing is not None else pd.DataFrame()
        print(f"  无新数据")
else:
    df_all = df_existing if df_existing is not None else pd.DataFrame()
    print(f"  跳过 K 线 (已有 {last_date})")

# ========== 今日行情 ==========
print("\n[3/4] 拉取今日行情...")
df_today = tushare_call(pro.daily, max_retry=3, trade_date=end_date)
if df_today is not None and not df_today.empty:
    df_today = df_today.loc[:, ~df_today.columns.duplicated()]
    df_today['code'] = df_today['ts_code'].str.split('.').str[0]
    df_today['code'] = df_today['code'].astype(str).str.zfill(6)
    name_map = dict(zip(df_basic['code'], df_basic['name']))
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

# ========== 触发选股脚本 ==========
print("\n[4/4] 生成今日精选 daily_picks_dynamic.py (动态版)...")
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
