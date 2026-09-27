#!/usr/bin/env python3
"""
check_freshness.py — 判断 A 股日线数据是否已更新到目标交易日 (2026-09-27)

给 safety_net.yml 调用,替代原先那段"在 YAML 块标量里内嵌 python -c +
跨行单引号"的写法 —— 后者正是 safety_net.yml 长期解析失败、从而
整个兜底机制静默失效的根因。

输出: 往 stdout 打印 FRESH 或 STALE,并把状态写进 $GITHUB_OUTPUT(如果有)。
退出码永远是 0,让调用方自己判断,不因为网络抖动把 workflow 搞挂。
"""
import os
import sys
from datetime import datetime, timedelta


def target_trade_date():
    """最近一个"应该有数据"的交易日(不考虑节假日,保守起见取昨天)。"""
    d = datetime.now() - timedelta(days=1)
    while d.weekday() >= 5:  # 周末往前推
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')


def main():
    target = target_trade_date()
    token = os.environ.get('TUSHARE_TOKEN')
    state = 'STALE'
    detail = ''

    if not token:
        detail = 'TUSHARE_TOKEN 未设置'
    else:
        try:
            import tushare as ts
            pro = ts.pro_api(token)
            df = pro.daily(trade_date=target, fields='ts_code,trade_date')
            n = 0 if df is None else len(df)
            if n > 100:
                state = 'FRESH'
                detail = f'{target} 有 {n} 条'
            else:
                detail = f'{target} 仅 {n} 条'
        except Exception as e:
            detail = f'查询失败: {e}'

    print(f'freshness={state}')
    print(f'  目标交易日 {target} | {state} | {detail}')

    # 写回 Actions output(如果在被 Actions 调用)
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'freshness={state}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
