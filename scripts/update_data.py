#!/usr/bin/env python3
"""每日数据更新脚本 - 由 GitHub Actions 调用（用 AKShare 免费数据）"""
import os
import json
import pandas as pd
from datetime import datetime, timedelta

os.makedirs('data', exist_ok=True)

print("1. 用 AKShare 拉取 A 股列表...")
try:
    import akshare as ak
    df_basic = ak.stock_info_a_code_name()
    df_basic['code'] = df_basic['code'].astype(str).str.zfill(6)
    print(f"   获取 {len(df_basic)} 只股票")
except Exception as e:
    print(f"   AKShare 失败: {e}")
    df_basic = pd.DataFrame()

if df_basic.empty:
    FALLBACK = [
        {'code': '600519', 'name': '贵州茅台', 'industry': '食品饮料'},
        {'code': '601318', 'name': '中国平安', 'industry': '非银金融'},
        {'code': '600036', 'name': '招商银行', 'industry': '银行'},
        {'code': '000858', 'name': '五粮液', 'industry': '食品饮料'},
        {'code': '300750', 'name': '宁德时代', 'industry': '电力设备'},
        {'code': '002594', 'name': '比亚迪', 'industry': '汽车'},
        {'code': '600276', 'name': '恒瑞医药', 'industry': '医药生物'},
        {'code': '000333', 'name': '美的集团', 'industry': '家用电器'},
        {'code': '601012', 'name': '隆基绿能', 'industry': '电力设备'},
        {'code': '600900', 'name': '长江电力', 'industry': '公用事业'},
        {'code': '601398', 'name': '工商银行', 'industry': '银行'},
        {'code': '601939', 'name': '建设银行', 'industry': '银行'},
        {'code': '601988', 'name': '中国银行', 'industry': '银行'},
        {'code': '600028', 'name': '中国石化', 'industry': '石油石化'},
        {'code': '600050', 'name': '中国联通', 'industry': '通信'},
        {'code': '601628', 'name': '中国人寿', 'industry': '非银金融'},
        {'code': '601857', 'name': '中国石油', 'industry': '石油石化'},
        {'code': '600887', 'name': '伊利股份', 'industry': '食品饮料'},
        {'code': '601088', 'name': '中国神华', 'industry': '煤炭'},
        {'code': '601288', 'name': '农业银行', 'industry': '银行'},
        {'code': '601328', 'name': '交通银行', 'industry': '银行'},
        {'code': '600030', 'name': '中信证券', 'industry': '非银金融'},
        {'code': '000651', 'name': '格力电器', 'industry': '家用电器'},
        {'code': '600585', 'name': '海螺水泥', 'industry': '建筑材料'},
        {'code': '601800', 'name': '中国交建', 'industry': '建筑装饰'},
        {'code': '601166', 'name': '兴业银行', 'industry': '银行'},
        {'code': '601229', 'name': '上海银行', 'industry': '银行'},
        {'code': '601688', 'name': '华泰证券', 'industry': '非银金融'},
        {'code': '000001', 'name': '平安银行', 'industry': '银行'},
        {'code': '000002', 'name': '万科A', 'industry': '房地产'},
        {'code': '000063', 'name': '中兴通讯', 'industry': '通信'},
        {'code': '000100', 'name': 'TCL科技', 'industry': '电子'},
        {'code': '000538', 'name': '云南白药', 'industry': '医药生物'},
        {'code': '000568', 'name': '泸州老窖', 'industry': '食品饮料'},
        {'code': '000625', 'name': '长安汽车', 'industry': '汽车'},
        {'code': '000661', 'name': '长春高新', 'industry': '医药生物'},
        {'code': '000725', 'name': '京东方A', 'industry': '电子'},
        {'code': '000776', 'name': '广发证券', 'industry': '非银金融'},
        {'code': '002027', 'name': '分众传媒', 'industry': '传媒'},
        {'code': '002230', 'name': '科大讯飞', 'industry': '计算机'},
        {'code': '002415', 'name': '海康威视', 'industry': '计算机'},
        {'code': '002460', 'name': '赣锋锂业', 'industry': '有色金属'},
        {'code': '002475', 'name': '立讯精密', 'industry': '电子'},
        {'code': '002714', 'name': '牧原股份', 'industry': '农林牧渔'},
        {'code': '300014', 'name': '亿纬锂能', 'industry': '电力设备'},
        {'code': '300033', 'name': '同花顺', 'industry': '计算机'},
        {'code': '300059', 'name': '东方财富', 'industry': '非银金融'},
        {'code': '300124', 'name': '汇川技术', 'industry': '机械设备'},
        {'code': '300274', 'name': '阳光电源', 'industry': '电力设备'},
        {'code': '300760', 'name': '迈瑞医疗', 'industry': '医药生物'},
    ]
    df_basic = pd.DataFrame(FALLBACK)
    df_basic['code'] = df_basic['code'].astype(str)
    print(f"   使用降级数据: {len(df_basic)} 只")

df_basic['industry'] = df_basic['industry'].astype(str)
df_basic.to_csv('data/stock_list.csv', index=False, encoding='utf-8-sig')
print(f"   保存 data/stock_list.csv")

industry_map = dict(zip(df_basic['code'], df_basic['industry']))
with open('data/industry_map.json', 'w', encoding='utf-8') as f:
    json.dump(industry_map, f, ensure_ascii=False)
print(f"   保存 data/industry_map.json")

print("\n2. 拉取最近 K 线（用 AKShare）...")
all_klines = []
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')

try:
    df_today = ak.stock_zh_a_hist(pre_date=start_date, post_date=end_date, adjust='qfq')
    if df_today is not None and not df_today.empty:
        df_today['代码'] = df_today['代码'].astype(str).str.zfill(6)
        all_klines.append(df_today)
        print(f"   一次拉取: {len(df_today)} 条")
except Exception as e:
    print(f"   一次拉取失败: {e}")
    for i, code in enumerate(df_basic['code'].head(50).tolist()):
        try:
            df_one = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=start_date, end_date=end_date, adjust='qfq')
            if df_one is not None and not df_one.empty:
                df_one['代码'] = code
                all_klines.append(df_one)
            if (i+1) % 10 == 0:
                print(f"   进度: {i+1}/50")
        except Exception as e2:
            print(f"   跳过 {code}: {e2}")

if all_klines:
    df_all = pd.concat(all_klines, ignore_index=True)
    for old, new in [('代码', 'code'), ('日期', 'date'), ('开盘', 'open'),
                     ('收盘', 'close'), ('最高', 'high'), ('最低', 'low'),
                     ('成交量', 'volume'), ('涨跌幅', 'pct_change')]:
        if old in df_all.columns:
            df_all = df_all.rename(columns={old: new})
    if 'date' in df_all.columns:
        df_all['date'] = pd.to_datetime(df_all['date']).dt.strftime('%Y-%m-%d')
    if 'code' in df_all.columns:
        df_all['code'] = df_all['code'].astype(str).str.zfill(6)
    name_map = dict(zip(df_basic['code'], df_basic['name']))
    if 'name' not in df_all.columns and 'code' in df_all.columns:
        df_all['name'] = df_all['code'].map(name_map)
    try:
        df_all.to_parquet('data/klines.parquet', index=False)
        print(f"   保存 data/klines.parquet: {len(df_all)} 条")
    except Exception as e:
        print(f"   parquet 失败: {e}")
        df_all.to_csv('data/klines.csv', index=False)
        print(f"   改存 CSV: {len(df_all)} 条")
else:
    print("   K 线拉取全部失败")

print("\n✅ 数据更新完成！")
