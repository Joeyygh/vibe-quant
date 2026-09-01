#!/usr/bin/env python3
"""Vibe 量化数据更新 - Tushare Pro 真实数据版"""
import os
import json
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

print("\n[1/3] 拉取 A 股列表...")
df_basic = pro.stock_basic(
    list_status='L',
    fields='ts_code,symbol,name,industry,market,list_date'
)
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

print("\n[2/3] 拉取 K 线...")
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

all_klines = []
codes = df_basic['code'].tolist()
total = len(codes)
print(f"  待拉取: {total} 只")

for i, code in enumerate(codes):
    ts_code = df_basic[df_basic['code'] == code]['ts_code'].iloc[0]
    try:
        df = pro.daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        if df is not None and not df.empty:
            df['code'] = code
            all_klines.append(df)
    except Exception as e:
        pass
    
    if (i + 1) % 1000 == 0:
        print(f"  进度: {i+1}/{total}")

if all_klines:
    df_all = pd.concat(all_klines, ignore_index=True)
    df_all = df_all.loc[:, ~df_all.columns.duplicated()]
    df_all = df_all.rename(columns={
        'trade_date': 'date', 'vol': 'volume', 'pct_chg': 'pct_change'
    })
    df_all = df_all.loc[:, ~df_all.columns.duplicated()]
    df_all['date'] = pd.to_datetime(df_all['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    name_map = dict(zip(df_basic['code'], df_basic['name']))
    df_all['name'] = df_all['code'].map(name_map)
    df_all['industry'] = df_all['code'].map(industry_map).fillna('未分类')
    df_all['code'] = df_all['code'].astype(str).str.zfill(6)
    df_all = df_all.loc[:, ~df_all.columns.duplicated()]
    
    try:
        df_all.to_parquet('data/klines.parquet', index=False)
        print(f"  ✅ klines.parquet: {len(df_all)} 条")
    except Exception as e:
        df_all.to_csv('data/klines.csv', index=False)
        print(f"  ✅ klines.csv: {len(df_all)} 条")

print("\n[3/3] 拉取今日行情...")
df_today = pro.daily(trade_date=end_date)
if df_today is not None and not df_today.empty:
    df_today = df_today.loc[:, ~df_today.columns.duplicated()]
    df_today['code'] = df_today['ts_code'].str.split('.').str[0]
    df_today['code'] = df_today['code'].astype(str).str.zfill(6)
    df_today['name'] = df_today['code'].map(name_map)
    df_today['industry'] = df_today['code'].map(industry_map).fillna('未分类')
    df_today = df_today.rename(columns={'pct_chg': 'pct_change', 'vol': 'volume'})
    df_today.to_csv('data/today_quote.csv', index=False, encoding='utf-8-sig')
    print(f"  ✅ today_quote.csv: {len(df_today)} 条")
    
    # 填充 stock_list.csv 的 price/pct_change (用今日收盘价)
    price_map = dict(zip(df_today['code'], df_today['close']))
    pct_map = dict(zip(df_today['code'], df_today['pct_change']))
    df_basic['price'] = df_basic['code'].map(price_map).fillna(0.0)
    df_basic['pct_change'] = df_basic['code'].map(pct_map).fillna(0.0)
    df_basic[['code', 'name', 'industry', 'price', 'pct_change', 'market_cap_yi']].to_csv(
        'data/stock_list.csv', index=False, encoding='utf-8-sig'
    )
    print(f"  ✅ stock_list.csv 已用 {len(price_map)} 只今日价格填充")

with open('data/last_update.txt', 'w') as f:
    # v3.4 修复: 强制写"盘后 17:30" 字符串, App 统一显示
    f.write(f"{datetime.now().strftime('%Y-%m-%d')}T17:30:00")


# ========== 顺便生成今日精选 (动态版 v1.4) ==========
import subprocess
try:
    print('\n[4/4] 生成今日精选 daily_picks_dynamic.py (动态版)...')
    # 把 picks 写到 data/ 下, 让 git add data/ 能一起 commit
    # 同时也在 reports/ 下保留一份给 App 看
    os.makedirs('reports', exist_ok=True)
    result = subprocess.run(
        ['python', 'scripts/daily_picks_dynamic.py'],
        capture_output=True, text=True, timeout=300,
        env={**__import__('os').environ, 'VIBE_OUTPUT_DIR': 'data'}
    )
    if result.returncode == 0:
        print('  ✅ daily_picks_dynamic 成功')
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    else:
        print(f'  ⚠️ daily_picks_dynamic 失败 (returncode={result.returncode})')
        print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
except Exception as e:
    print(f'  ⚠️ daily_picks_dynamic 调用异常: {e}')


try:
    print('\n[4.5/4] 生成 4 个实战公式 picks (v2.0)...')
    os.makedirs('reports', exist_ok=True)
    result2 = subprocess.run(
        ['python', 'scripts/daily_picks_v2.py'],
        capture_output=True, text=True, timeout=300,
        env={**__import__('os').environ, 'VIBE_OUTPUT_DIR': 'data'}
    )
    if result2.returncode == 0:
        print('  ✅ daily_picks_v2 成功 (4 个实战公式)')
        # 同步到 data/ 让 git commit
        formulas_data = 'data/formulas_picks.json'
        formulas_reports = 'reports/formulas_picks.json'
        if os.path.exists(formulas_data):
            shutil.copy2(formulas_data, formulas_reports)
            print(f'  📋 formulas 同步: {formulas_data} -> {formulas_reports}')
    else:
        print(f'  ⚠️ daily_picks_v2 失败 (returncode={result2.returncode})')
        print(result2.stderr[-500:] if len(result2.stderr) > 500 else result2.stderr)
except Exception as e:
    print(f'  ⚠️ daily_picks_v2 调用异常: {e}')

print('\n✅ 完成！真实数据！')

# 把 picks 同步到 reports/ 给 App 读 (workflow 走 data/, App 读 reports/)
import shutil
src = 'data/today_picks.json'
dst = 'reports/today_picks.json'
if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f'  📋 picks 同步: {src} -> {dst}')
