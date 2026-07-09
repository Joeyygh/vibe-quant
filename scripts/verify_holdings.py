#!/usr/bin/env python3
"""持仓核对脚本 - 验证 my_holdings.json 中代码 ↔ 名称是否匹配 Tushare

用法: python scripts/verify_holdings.py
"""
import os
import sys
import json
import pandas as pd

HOLDINGS_FILE = 'my_holdings.json'
STOCK_LIST_FILE = 'data/stock_list.csv'


def load_stock_list():
    """读 stock_list.csv(本地缓存)"""
    if not os.path.exists(STOCK_LIST_FILE):
        return {}
    df = pd.read_csv(STOCK_LIST_FILE, dtype={'code': str})
    df['code'] = df['code'].astype(str).str.zfill(6)
    return dict(zip(df['code'], df['name']))


def verify_holdings(holdings, code_name_map):
    """核对每只持仓的代码 ↔ 名称"""
    results = {'ok': [], 'mismatch': [], 'not_found': []}

    for h in holdings:
        code = h.get('code', '')
        user_name = h.get('name', '')

        # 跳过债券
        if not code.isdigit() or len(code) < 6:
            results['ok'].append(h)
            continue

        # 找官方名字
        if code in code_name_map:
            official_name = code_name_map[code]
            if official_name == user_name:
                results['ok'].append(h)
            else:
                results['mismatch'].append({
                    'code': code,
                    'user_name': user_name,
                    'official_name': official_name,
                })
        else:
            results['not_found'].append({
                'code': code,
                'user_name': user_name,
            })

    return results


def main():
    if not os.path.exists(HOLDINGS_FILE):
        print(f"❌ {HOLDINGS_FILE} 不存在")
        sys.exit(1)

    with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
        holdings = json.load(f)

    code_name_map = load_stock_list()
    if not code_name_map:
        print(f"⚠️ {STOCK_LIST_FILE} 不存在或为空,请先跑 update_data.py")
        sys.exit(1)

    results = verify_holdings(holdings, code_name_map)

    print(f"\n{'='*60}")
    print(f"持仓核对报告")
    print(f"{'='*60}")
    print(f"总持仓: {len(holdings)} 只")
    print(f"✅ 正确: {len(results['ok'])} 只")
    print(f"⚠️ 名称不符: {len(results['mismatch'])} 只")
    print(f"❌ 找不到: {len(results['not_found'])} 只")

    if results['mismatch']:
        print(f"\n⚠️ 名称不符清单(需修正):")
        for r in results['mismatch']:
            print(f"  {r['code']} 用户写: {r['user_name']:8}  Tushare: {r['official_name']}")

    if results['not_found']:
        print(f"\n❌ 找不到清单:")
        for r in results['not_found']:
            print(f"  {r['code']} {r['user_name']}")

    # 退出码:有错就返回 1
    if results['mismatch'] or results['not_found']:
        sys.exit(1)
    print(f"\n✅ 全部正确")


if __name__ == '__main__':
    main()