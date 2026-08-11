#!/usr/bin/env python3
"""持仓核对 + 自动修复脚本 - 验证 my_holdings.json 中代码 ↔ 名称

用法:
    python scripts/verify_holdings.py                 # 只核对
    python scripts/verify_holdings.py --suggest       # 核对 + 修复建议
    python scripts/verify_holdings.py --fix           # 自动修复(用名字找代码)
    python scripts/verify_holdings.py --fix --backup  # 修复前备份原文件
"""
import os
import sys
import json
import shutil
import argparse
import pandas as pd

HOLDINGS_FILE = 'my_holdings.json'
STOCK_LIST_FILE = 'data/stock_list.csv'
TODAY_QUOTE_FILE = 'data/today_quote.csv'


def load_stock_list():
    """读 stock_list.csv(本地缓存)"""
    if not os.path.exists(STOCK_LIST_FILE):
        return {}, {}
    df = pd.read_csv(STOCK_LIST_FILE, dtype={'code': str})
    df['code'] = df['code'].astype(str).str.zfill(6)

    code_to_name = dict(zip(df['code'], df['name']))
    code_to_industry = dict(zip(df['code'], df['industry']))

    # name → [code] 反向映射
    name_to_codes = {}
    for _, row in df.iterrows():
        name_to_codes.setdefault(row['name'], []).append(row['code'])

    return code_to_name, name_to_codes


def load_today_prices():
    """读 today_quote.csv 获取最近价格"""
    if not os.path.exists(TODAY_QUOTE_FILE):
        return {}
    df = pd.read_csv(TODAY_QUOTE_FILE, dtype={'ts_code': str})
    df['code'] = df['ts_code'].str.split('.').str[0].astype(str).str.zfill(6)
    return dict(zip(df['code'], df['close']))


def find_best_match(user_name, user_cost, current_price, code_to_name, name_to_codes, today_prices):
    """用名字找候选代码,用价格匹配找出最可能的代码"""
    candidates = name_to_codes.get(user_name, [])
    if not candidates:
        return None, []

    if len(candidates) == 1:
        return candidates[0], candidates

    # 多个候选:用价格反查
    matches = []
    for cand_code in candidates:
        price = today_prices.get(cand_code)
        if price and abs(price - current_price) / current_price < 0.05:  # 5% 误差内
            matches.append((cand_code, abs(price - current_price) / current_price))

    if matches:
        # 选误差最小的
        matches.sort(key=lambda x: x[1])
        return matches[0][0], [m[0] for m in matches]

    return None, candidates


def verify_holdings(holdings, code_to_name, name_to_codes, today_prices, today_industry_map):
    """核对每只持仓"""
    results = {'ok': [], 'mismatch': [], 'not_found': [], 'suggestions': []}

    for h in holdings:
        code = h.get('code', '')
        user_name = h.get('name', '')
        cost = h.get('cost_price', 0)
        current = h.get('current_price', 0)

        # 跳过债券
        if not code.isdigit() or len(code) < 6:
            results['ok'].append(h)
            continue

        # 1. 找官方名字
        if code in code_to_name:
            official_name = code_to_name[code]
            if official_name == user_name:
                results['ok'].append(h)
            else:
                # 名字不符 - 给出修复建议
                best, candidates = find_best_match(
                    user_name, cost, current, code_to_name, name_to_codes, today_prices
                )
                results['mismatch'].append({
                    'code': code,
                    'user_name': user_name,
                    'official_name': official_name,
                    'suggested_code': best,
                    'candidates': candidates,
                })
        else:
            # 代码不存在 - 用名字找
            best, candidates = find_best_match(
                user_name, cost, current, code_to_name, name_to_codes, today_prices
            )
            results['not_found'].append({
                'code': code,
                'user_name': user_name,
                'suggested_code': best,
                'candidates': candidates,
            })

    return results


def print_report(results, show_suggestions=False):
    """打印核对报告"""
    print(f"\n{'='*70}")
    print(f"持仓核对报告")
    print(f"{'='*70}")
    print(f"总持仓: {sum(len(v) for v in results.values() if isinstance(v, list)) - (len(results.get('suggestions', [])) if 'suggestions' in results else 0)} 只")
    print(f"✅ 正确: {len(results['ok'])} 只")
    print(f"⚠️ 名称不符: {len(results['mismatch'])} 只")
    print(f"❌ 找不到: {len(results['not_found'])} 只")

    if results['mismatch']:
        print(f"\n⚠️ 名称不符清单(需修正):")
        for r in results['mismatch']:
            print(f"  {r['code']} 用户写: {r['user_name']:8}  Tushare: {r['official_name']}", end='')
            if show_suggestions:
                if r['suggested_code']:
                    print(f"  → 建议改为 {r['suggested_code']} (价格匹配)")
                else:
                    print(f"  → 候选: {r['candidates']}")
            else:
                print()

    if results['not_found']:
        print(f"\n❌ 找不到清单:")
        for r in results['not_found']:
            print(f"  {r['code']} {r['user_name']}", end='')
            if show_suggestions:
                if r['suggested_code']:
                    print(f"  → 建议改为 {r['suggested_code']} (价格匹配)")
                else:
                    print(f"  → 候选: {r['candidates']}")
            else:
                print()

    if not results['mismatch'] and not results['not_found']:
        print(f"\n🎉 全部正确!")


def auto_fix(holdings, results):
    """根据建议自动修复"""
    fixed = 0
    new_holdings = []

    for h in holdings:
        code = h.get('code', '')
        if not code.isdigit() or len(code) < 6:
            new_holdings.append(h)
            continue

        # 看是否在 mismatch 或 not_found 中
        suggestion = None
        for r in results['mismatch'] + results['not_found']:
            if r['code'] == code:
                suggestion = r.get('suggested_code')
                break

        if suggestion:
            h_new = h.copy()
            h_new['code'] = suggestion
            new_holdings.append(h_new)
            print(f"  🔧 修复: {code} {h.get('name')} → {suggestion}")
            fixed += 1
        else:
            new_holdings.append(h)

    return new_holdings, fixed


def main():
    parser = argparse.ArgumentParser(description='持仓核对 + 自动修复工具')
    parser.add_argument('--suggest', action='store_true', help='显示修复建议')
    parser.add_argument('--fix', action='store_true', help='自动修复')
    parser.add_argument('--backup', action='store_true', help='修复前备份原文件')
    args = parser.parse_args()

    if not os.path.exists(HOLDINGS_FILE):
        print(f"❌ {HOLDINGS_FILE} 不存在")
        sys.exit(1)

    with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
        _raw = json.load(f)
    # 兼容新版 dict 结构: {holdings:[...], closed_holdings:[...]}
    if isinstance(_raw, dict):
        holdings = _raw.get('holdings', [])
    else:
        holdings = _raw

    code_to_name, name_to_codes = load_stock_list()
    if not code_to_name:
        print(f"⚠️ {STOCK_LIST_FILE} 不存在或为空,请先跑 update_data.py")
        sys.exit(1)

    today_prices = load_today_prices()
    today_industry_map = {}  # 简化

    results = verify_holdings(holdings, code_to_name, name_to_codes, today_prices, today_industry_map)

    print_report(results, show_suggestions=args.suggest or args.fix)

    if args.fix and (results['mismatch'] or results['not_found']):
        print(f"\n🔧 开始自动修复...")
        if args.backup:
            backup = f"{HOLDINGS_FILE}.bak.{int(os.path.getmtime(HOLDINGS_FILE))}"
            shutil.copy2(HOLDINGS_FILE, backup)
            print(f"  💾 备份: {backup}")

        new_holdings, fixed_count = auto_fix(holdings, results)
        with open(HOLDINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_holdings, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 修复完成: 共修复 {fixed_count} 只")
        print(f"  备份: {'是' if args.backup else '否'}")
        print(f"  建议再次跑 `python scripts/verify_holdings.py` 验证")

    if results['mismatch'] or results['not_found']:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()