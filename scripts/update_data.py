#!/usr/bin/env python3
"""每日数据更新脚本 - 由 GitHub Actions 调用"""
import os
import json
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta

TOKEN = os.environ.get('TUSHARE_TOKEN', '')
if not TOKEN:
    raise ValueError("TUSHARE_TOKEN 未设置")

ts.set_token(TOKEN)
pro = ts.pro_api()

os.makedirs('data', exist_ok=True)

print("1. 拉取股票列表（含行业）...")
df_basic = pro.stock_basic(
    list_status='L',
    fields='ts_code,symbol,name,industry,market,list_date'
)
print(f"   获取 {len(df_basic)} 只股票")

df_basic = df_basic.rename(columns={'symbol': 'code'})
df_basic['code'] = df_basic['code'].astype(str).str.zfill(6)
df_basic['industry'] = df_basic['industry'].astype(str).fillna('未分类')
df_basic['name'] = df_basic['name'].astype(str)

df_basic.to_csv('data/stock_list.csv', index=False, encoding='utf-8-sig')
print(f"   保存到 data/stock_list.csv")

industry_map = dict(zip(df_basic['code'], df_basic['industry']))
with open('data/industry_map.json', 'w', encoding='utf-8') as f:
    json.dump(industry_map, f, ensure_ascii=False)
print(f"   保存行业映射: {len(industry_map)} 个")

print("\n2. 拉取最近 60 个交易日K线...")
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')

all_klines = []
codes = df_basic['code'].tolist()
total = len(codes)
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
        print(f"   跳过 {code}: {e}")

    if (i + 1) % 500 == 0:
        print(f"   进度: {i+1}/{total}")

if all_klines:
    df_all = pd.concat(all_klines, ignore_index=True)
    df_all = df_all.rename(columns={
        'trade_date': 'date', 'vol': 'volume',
        'amount': 'amount', 'pct_chg': 'pct_change'
    })
    df_all['date'] = pd.to_datetime(df_all['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    name_map = dict(zip(df_basic['code'], df_basic['name']))
    df_all['name'] = df_all['code'].map(name_map)
    
    df_all.to_parquet('data/klines.parquet', index=False)
    print(f"   保存 {len(df_all)} 条K线到 data/klines.parquet")

print("\n3. 拉取最新行情...")
df_today = pro.daily(trade_date=end_date)
if df_today is not None and not df_today.empty:
    df_today = df_today.rename(columns={
        'trade_date': 'date', 'vol': 'volume',
        'pct_chg': 'pct_change', 'ts_code': 'ts_code'
    })
    df_today['code'] = df_today['ts_code'].str.split('.').str[0]
    df_today['name'] = df_today['code'].map(name_map)
    df_today['industry'] = df_today['code'].map(industry_map)
    df_today.to_csv('data/today_quote.csv', index=False, encoding='utf-8-sig')
    print(f"   保存 {len(df_today)} 条今日行情")

print("\n✅ 数据更新完成！")
