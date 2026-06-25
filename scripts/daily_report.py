"""
A 股每日复盘报告生成器 v2.0 (增强版)
====================================
数据源: Tushare Pro (A 股) + Yahoo Finance (美股/商品)
覆盖:
  ✓ A 股盘面 (沪/深/创/沪深300/科创50 + 涨跌停统计)
  ✓ 北向资金 + 两融数据
  ✓ 龙虎榜 (机构动向)
  ✓ 大宗交易
  ✓ 申万一级行业板块涨跌
  ✓ 个股资金流 (前 20 大资金流入)
  ✓ 涨停股 + 连板结构
  ✓ 美股隔夜 (三大指数 + 20 只科技中概股)
  ✓ 大宗商品 (原油/黄金/白银/铜/美元/离岸人民币)
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import numpy as np
import yfinance as yf

beijing_tz = timezone(timedelta(hours=8))
now = datetime.now(beijing_tz)
REPORTS_DIR = 'reports'
os.makedirs(REPORTS_DIR, exist_ok=True)

TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')
pro = None
if TUSHARE_TOKEN:
    try:
        import tushare as ts
        pro = ts.pro_api(TUSHARE_TOKEN)
    except Exception as e:
        print(f"Tushare 初始化失败: {e}")

US_TICKERS = {
    '^GSPC': '标普 500', '^DJI': '道琼斯', '^IXIC': '纳斯达克', '^VIX': 'VIX 恐慌',
    'AAPL': '苹果', 'MSFT': '微软', 'NVDA': '英伟达', 'TSLA': '特斯拉',
    'GOOGL': '谷歌', 'AMZN': '亚马逊', 'META': 'Meta',
    'BABA': '阿里巴巴', 'PDD': '拼多多', 'JD': '京东',
    'BIDU': '百度', 'NIO': '蔚来', 'XPEV': '小鹏', 'LI': '理想',
    'TME': '腾讯音乐', 'BILI': '哔哩哔哩',
}

COMMODITY_TICKERS = {
    'CL=F': 'WTI 原油', 'BZ=F': '布伦特原油',
    'GC=F': '黄金', 'SI=F': '白银', 'HG=F': '铜',
    'DX-Y.NYB': '美元指数', 'CNH=X': '离岸人民币',
}

_name_cache = {}


def get_target_date():
    today = now.date()
    target = today if now.hour >= 17 else (today - timedelta(days=1))
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target.strftime('%Y-%m-%d')


def fmt_pct(v):
    if v is None or pd.isna(v):
        return '-'
    return f"{'+' if v > 0 else ''}{v:.2f}%"


def _get_name_map():
    global _name_cache
    if not _name_cache and pro:
        try:
            df = pro.stock_basic(list_status='L', fields='ts_code,name,industry')
            if df is not None and not df.empty:
                _name_cache = dict(zip(df['ts_code'], df[['name', 'industry']].values.tolist()))
        except Exception as e:
            print(f"  ⚠️ 股票基础信息: {e}")
    return _name_cache


def _is_limit(code, pct):
    if pct is None or pd.isna(pct):
        return False
    if code.startswith(('300', '301', '688')):
        return pct >= 19.5
    return pct >= 9.5


def get_yf_data(tickers_dict, label='美股', retries=3):
    """yfinance 抓数据,带限流重试"""
    result = {}
    tickers_list = list(tickers_dict.keys())
    print(f"  → 抓取 {label} ({len(tickers_list)} 个)...")
    for attempt in range(retries):
        try:
            data = yf.download(tickers_list, period='5d', progress=False,
                               group_by='ticker', threads=True)
            for ticker, name in tickers_dict.items():
                try:
                    df = data if len(tickers_list) == 1 else (
                        data[ticker] if ticker in data.columns.get_level_values(0) else pd.DataFrame())
                    if df.empty or len(df) < 2:
                        result[name] = {'error': '数据不足'}
                        continue
                    last_close = float(df.iloc[-1]['Close'])
                    prev_close = float(df.iloc[-2]['Close'])
                    if pd.isna(last_close) or pd.isna(prev_close) or prev_close == 0:
                        result[name] = {'error': 'NaN'}
                        continue
                    result[name] = {
                        'close': round(last_close, 2),
                        'change_pct': round((last_close - prev_close) / prev_close * 100, 2),
                    }
                except Exception as e:
                    result[name] = {'error': str(e)[:30]}
            return result
        except Exception as e:
            print(f"    重试 {attempt+1}/{retries}: {str(e)[:60]}")
            time.sleep(15)
    for n in tickers_dict.values():
        result[n] = {'error': '全部失败'}
    return result


# ============== A 股数据 ==============

def get_a_indices(date_str):
    if not pro:
        return []
    targets = [
        ('000001.SH', '上证指数'), ('399001.SZ', '深证成指'),
        ('399006.SZ', '创业板指'), ('000300.SH', '沪深 300'),
        ('000688.SH', '科创 50'), ('000016.SH', '上证 50'),
        ('000905.SH', '中证 500'),
    ]
    rows = []
    for code, name in targets:
        try:
            df = pro.index_daily(ts_code=code, start_date=date_str, end_date=date_str)
            if df is not None and not df.empty:
                r = df.iloc[0]
                rows.append({'name': name, 'close': float(r['close']),
                             'pct_chg': float(r.get('pct_chg', 0))})
        except Exception:
            continue
    return rows


def get_limit_count_from_daily(date_str):
    """从 daily 数据自己算涨停跌停数"""
    if not pro:
        return None, None
    try:
        df = pro.daily(trade_date=date_str)
        if df is None or df.empty:
            return None, None
        df['is_limit_up'] = df.apply(lambda r: _is_limit(r['ts_code'], r.get('pct_chg', 0)), axis=1)
        df['is_limit_down'] = df.apply(
            lambda r: (r['ts_code'].startswith(('300', '301', '688')) and r.get('pct_chg', 0) <= -19.5)
                      or (not r['ts_code'].startswith(('300', '301', '688')) and r.get('pct_chg', 0) <= -9.5),
            axis=1)
        return int(df['is_limit_up'].sum()), int(df['is_limit_down'].sum())
    except Exception as e:
        print(f"  ⚠️ 涨跌停: {e}")
        return None, None


def get_north_flow(date_str):
    if not pro:
        return None, None
    try:
        df = pro.moneyflow_hsgt(trade_date=date_str)
        if df is not None and not df.empty:
            row = df.iloc[0]
            north_wan = float(row.get('north_money', 0))
            south_wan = float(row.get('south_money', 0))
            return north_wan / 1e4, south_wan / 1e4
    except Exception as e:
        print(f"  ⚠️ 北向资金: {e}")
    return None, None


def get_margin(date_str):
    if not pro:
        return []
    try:
        df = pro.margin(trade_date=date_str)
        if df is not None and not df.empty:
            return df.to_dict('records')
    except Exception as e:
        print(f"  ⚠️ 两融: {e}")
    return []


def get_sector_perf(date_str, top_n=10):
    """申万行业板块涨跌(用 daily + stock_basic 自己算)"""
    if not pro:
        return [], []
    try:
        daily_df = pro.daily(trade_date=date_str)
        if daily_df is None or daily_df.empty:
            return [], []
        basic_df = pro.stock_basic(list_status='L', fields='ts_code,industry')
        if basic_df is None or basic_df.empty:
            return [], []
        df = daily_df.merge(basic_df[['ts_code', 'industry']], on='ts_code', how='left')
        df = df[df['industry'].notna() & (df['industry'] != '') & (df['industry'] != 'nan') & (df['industry'] != '未分类')]
        if df.empty:
            return [], []
        sector = df.groupby('industry').agg(
            avg_pct=('pct_chg', 'mean'),
            total_amount=('amount', 'sum'),
            stock_count=('ts_code', 'count'),
        ).reset_index().sort_values('avg_pct', ascending=False)
        up = sector.head(top_n).to_dict('records')
        down = sector.tail(top_n)[::-1].to_dict('records')
        return up, down
    except Exception as e:
        print(f"  ⚠️ 板块涨跌: {e}")
        return [], []


def get_top_list(date_str, top_n=15):
    if not pro:
        return []
    try:
        df = pro.top_list(trade_date=date_str)
        if df is not None and not df.empty:
            return df.head(top_n).to_dict('records')
    except Exception as e:
        print(f"  ⚠️ 龙虎榜: {e}")
    return []


def get_block_trade(date_str, top_n=15):
    if not pro:
        return []
    try:
        df = pro.block_trade(trade_date=date_str)
        if df is not None and not df.empty:
            return df.head(top_n).to_dict('records')
    except Exception as e:
        print(f"  ⚠️ 大宗交易: {e}")
    return []


def get_top_moneyflow(date_str, top_n=20):
    """个股资金流(超大单+大单净流入前 N)"""
    if not pro:
        return []
    try:
        df = pro.moneyflow(trade_date=date_str)
        if df is not None and not df.empty:
            for col in ['buy_lg_amount', 'buy_elg_amount', 'sell_lg_amount', 'sell_elg_amount']:
                if col not in df.columns:
                    df[col] = 0
            df['net_main'] = (
                df['buy_lg_amount'].fillna(0) + df['buy_elg_amount'].fillna(0)
                - df['sell_lg_amount'].fillna(0) - df['sell_elg_amount'].fillna(0)
            )
            name_map = _get_name_map()
            df_top = df.nlargest(top_n, 'net_main')[['ts_code', 'net_main']].copy()
            df_top['name'] = df_top['ts_code'].map(
                lambda c: name_map.get(c, ['-', '-'])[0] if c in name_map else '-')
            df_top['pct_change'] = 0
            try:
                daily_df = pro.daily(trade_date=date_str, fields='ts_code,pct_chg')
                if daily_df is not None and not daily_df.empty:
                    pct_map = dict(zip(daily_df['ts_code'], daily_df['pct_chg']))
                    df_top['pct_change'] = df_top['ts_code'].map(pct_map).fillna(0)
            except Exception:
                pass
            return df_top.to_dict('records')
    except Exception as e:
        print(f"  ⚠️ 个股资金流: {e}")
    return []


def get_limit_up_stocks(date_str, top_n=20):
    """涨停股(用 daily 自己算)"""
    if not pro:
        return []
    try:
        df = pro.daily(trade_date=date_str)
        if df is None or df.empty:
            return []
        df['is_limit'] = df.apply(lambda r: _is_limit(r['ts_code'], r.get('pct_chg', 0)), axis=1)
        df = df[df['is_limit']].copy()
        name_map = _get_name_map()
        df['name'] = df['ts_code'].map(lambda c: name_map.get(c, ['-', '-'])[0] if c in name_map else '-')
        df['industry'] = df['ts_code'].map(lambda c: name_map.get(c, ['-', '-'])[1] if c in name_map else '-')
        df['limit_amount_wan'] = 0
        df = df.sort_values('amount', ascending=False).head(top_n)
        return df[['ts_code', 'name', 'industry', 'close', 'pct_chg', 'amount', 'limit_amount_wan']].to_dict('records')
    except Exception as e:
        print(f"  ⚠️ 涨停股: {e}")
    return []


def calc_consecutive_limit(date_str):
    """连板结构"""
    if not pro:
        return []
    try:
        df_today = pro.daily(trade_date=date_str)
        if df_today is None or df_today.empty:
            return []
        target_codes = df_today[df_today.apply(
            lambda r: _is_limit(r['ts_code'], r.get('pct_chg', 0)), axis=1)]['ts_code'].tolist()
        name_map = _get_name_map()
        results = []
        for code in target_codes[:25]:
            try:
                start_d = (datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=15)).strftime('%Y%m%d')
                hist = pro.daily(ts_code=code, start_date=start_d, end_date=date_str)
                if hist is not None and not hist.empty:
                    hist = hist.sort_values('trade_date')
                    cnt = 0
                    max_consec = 0
                    for _, r in hist.iterrows():
                        if _is_limit(code, float(r.get('pct_chg', 0))):
                            cnt += 1
                            max_consec = max(max_consec, cnt)
                        else:
                            cnt = 0
                    if max_consec >= 2:
                        results.append({
                            'code': code,
                            'name': name_map.get(code, ['-', '-'])[0] if code in name_map else '-',
                            'consecutive': max_consec,
                        })
            except Exception:
                pass
        return sorted(results, key=lambda x: -x['consecutive'])[:10]
    except Exception as e:
        print(f"  ⚠️ 连板: {e}")
        return []


# ============== 报告生成 ==============

def generate_report():
    target_date = get_target_date()
    date_str = target_date.replace('-', '')
    print(f"\n{'='*50}\n开始生成复盘报告 - {target_date}\n{'='*50}\n")

    sections = []
    sections.append(f"# 📊 A 股每日复盘报告 - {target_date}")
    sections.append("")
    sections.append(f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M')} 北京时间")
    sections.append("**数据源**: Tushare Pro (A 股) + Yahoo Finance (美股/商品)")
    sections.append("")
    sections.append("---")
    sections.append("")

    # 一、盘面速览
    sections.append("## 一、A 股盘面速览")
    sections.append("")
    indices = get_a_indices(date_str)
    if indices:
        sections.append("| 指数 | 收盘 | 涨跌幅 |")
        sections.append("|------|------|--------|")
        for idx in indices:
            sections.append(f"| **{idx['name']}** | {idx['close']:.2f} | {fmt_pct(idx['pct_chg'])} |")
    else:
        sections.append("- ⚠️ 大盘指数获取失败")
    sections.append("")
    up, down = get_limit_count_from_daily(date_str)
    if up is not None:
        sections.append(f"- **涨停**: {up} 家  |  **跌停**: {down} 家")
    sections.append("")

    # 二、北向 + 两融
    sections.append("## 二、资金面:北向 + 两融")
    sections.append("")
    north, south = get_north_flow(date_str)
    if north is not None:
        sections.append(f"- **北向资金**: 净{'流入' if north > 0 else '流出'} **{abs(north):.2f} 亿元**")
        sections.append(f"- **南向资金**: 净{'流入' if south > 0 else '流出'} {abs(south):.2f} 亿元")
    sections.append("")
    margins = get_margin(date_str)
    if margins:
        sections.append("### 两融余额")
        sections.append("")
        sections.append("| 市场 | 融资余额(亿) | 融券余额(亿) | 融资买入(亿) |")
        sections.append("|------|------------|------------|------------|")
        for m in margins:
            ex = m.get('exchange_id', '?')
            ex_name = {'SSE': '沪市', 'SZSE': '深市', 'BSE': '北交所'}.get(ex, ex)
            rzye = float(m.get('rzye', 0)) / 1e8
            rqye = float(m.get('rqye', 0)) / 1e8
            rzmre = float(m.get('rzmre', 0)) / 1e8
            sections.append(f"| {ex_name} | {rzye:,.2f} | {rqye:,.2f} | {rzmre:,.2f} |")
        sections.append("")

    # 三、申万行业板块
    sections.append("## 三、申万一级行业板块")
    sections.append("")
    top_up, top_down = get_sector_perf(date_str, top_n=10)
    if top_up:
        sections.append("### 🟢 涨幅前 10")
        sections.append("")
        sections.append("| 行业 | 涨幅 | 成交额(亿) | 样本数 |")
        sections.append("|------|------|----------|--------|")
        for s in top_up:
            amount_yi = float(s.get('total_amount', 0)) / 1e8
            sections.append(f"| {s['industry']} | {fmt_pct(s['avg_pct'])} | {amount_yi:,.0f} | {s.get('stock_count', 0)} |")
        sections.append("")
    if top_down:
        sections.append("### 🔴 跌幅前 10")
        sections.append("")
        sections.append("| 行业 | 涨幅 | 成交额(亿) | 样本数 |")
        sections.append("|------|------|----------|--------|")
        for s in top_down:
            amount_yi = float(s.get('total_amount', 0)) / 1e8
            sections.append(f"| {s['industry']} | {fmt_pct(s['avg_pct'])} | {amount_yi:,.0f} | {s.get('stock_count', 0)} |")
        sections.append("")

    # 四、个股资金流
    sections.append("## 四、大资金流入榜(前 20)")
    sections.append("")
    flows = get_top_moneyflow(date_str, top_n=20)
    if flows:
        sections.append("超大单 + 大单净流入排名(单位:元)")
        sections.append("")
        sections.append("| 代码 | 名称 | 涨幅 | 主力净流入 |")
        sections.append("|------|------|------|------------|")
        for f in flows:
            net_wan = f['net_main'] / 10000
            sections.append(f"| {f['ts_code']} | {f.get('name', '-')} | {fmt_pct(f.get('pct_change', 0))} | {net_wan:,.0f} 万 |")
        sections.append("")

    # 五、龙虎榜
    sections.append("## 五、龙虎榜(前 15)")
    sections.append("")
    tops = get_top_list(date_str, top_n=15)
    if tops:
        sections.append("| 代码 | 名称 | 收盘 | 涨幅 | 成交额(万) |")
        sections.append("|------|------|------|------|------------|")
        for t in tops:
            sections.append(f"| {t.get('ts_code', '-')} | {t.get('name', '-')} | "
                          f"{float(t.get('close', 0)):.2f} | {fmt_pct(t.get('pct_change', 0))} | "
                          f"{float(t.get('amount', 0))/10000:,.0f} |")
    else:
        sections.append("- 今日无龙虎榜")
    sections.append("")

    # 六、大宗交易
    sections.append("## 六、大宗交易(前 15)")
    sections.append("")
    blocks = get_block_trade(date_str, top_n=15)
    if blocks:
        sections.append("| 代码 | 价格 | 成交量(万股) | 成交额(万) | 买方 | 卖方 |")
        sections.append("|------|------|------------|------------|------|------|")
        for b in blocks:
            sections.append(f"| {b.get('ts_code', '-')} | {float(b.get('price', 0)):.2f} | "
                          f"{float(b.get('vol', 0))/10000:.2f} | "
                          f"{float(b.get('amount', 0))/10000:,.0f} | "
                          f"{str(b.get('buyer', '-'))[:8]} | {str(b.get('seller', '-'))[:8]} |")
    else:
        sections.append("- 今日无大宗交易")
    sections.append("")

    # 七、涨停 + 连板
    sections.append("## 七、涨停股 + 连板结构")
    sections.append("")
    limit_ups = get_limit_up_stocks(date_str, top_n=20)
    if limit_ups:
        sections.append("### 涨停股(按成交额前 20)")
        sections.append("")
        sections.append("| 代码 | 名称 | 行业 | 现价 | 涨幅 | 成交额(亿) |")
        sections.append("|------|------|------|------|------|------------|")
        for r in limit_ups:
            sections.append(f"| {r.get('ts_code', '-')} | {r.get('name', '-')} | "
                          f"{r.get('industry', '-')} | "
                          f"{float(r.get('close', 0)):.2f} | "
                          f"{fmt_pct(r.get('pct_chg', 0))} | "
                          f"{float(r.get('amount', 0))/1e8:.2f} |")
        sections.append("")
    consecutive = calc_consecutive_limit(date_str)
    if consecutive:
        sections.append("### 连板结构")
        sections.append("")
        sections.append("| 代码 | 名称 | 连板数 |")
        sections.append("|------|------|--------|")
        for r in consecutive:
            sections.append(f"| {r['code']} | {r['name']} | **{r['consecutive']} 连板** |")
        sections.append("")

    # 八、美股隔夜
    sections.append("## 八、美股隔夜收盘")
    sections.append("")
    sections.append("*美股夏令时北京时间凌晨 4:00 收盘*")
    sections.append("")
    us_data = get_yf_data(US_TICKERS, '美股')
    sections.append("### 主要指数")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    for n in ['标普 500', '道琼斯', '纳斯达克', 'VIX 恐慌']:
        if n in us_data and 'close' in us_data[n]:
            sections.append(f"| **{n}** | {us_data[n]['close']} | {fmt_pct(us_data[n]['change_pct'])} |")
    sections.append("")
    sections.append("### 科技股 / 中概股")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    others = [n for n in us_data.keys() if n not in ['标普 500', '道琼斯', '纳斯达克', 'VIX 恐慌']]
    for n in others[:16]:
        if 'close' in us_data[n]:
            sections.append(f"| {n} | {us_data[n]['close']} | {fmt_pct(us_data[n]['change_pct'])} |")
    sections.append("")

    # 九、商品外汇
    sections.append("## 九、大宗商品 & 外汇")
    sections.append("")
    comm = get_yf_data(COMMODITY_TICKERS, '商品')
    sections.append("| 品种 | 价格 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    for n in COMMODITY_TICKERS.values():
        if n in comm and 'close' in comm[n]:
            sections.append(f"| **{n}** | {comm[n]['close']} | {fmt_pct(comm[n]['change_pct'])} |")
    sections.append("")

    # 十、明日关注
    sections.append("## 十、明日关注(规则化提示)")
    sections.append("")
    sections.append("> **未自动覆盖**(需手动浏览,后续接爬虫+LLM):")
    sections.append("> - 📰 财联社 / 同花顺 / 东方财富新闻: 热点题材、突发公告")
    sections.append("> - 💬 淘股吧 / 韭研公社 / 雪球: 短线情绪 + 题材拆解")
    sections.append("> - 📊 萝卜投研 / Wind 研报: 中长线基本面")
    sections.append("")
    sections.append("**基于今日数据的自动提示**:")
    sections.append("")
    if us_data.get('纳斯达克', {}).get('change_pct', 0) > 1:
        sections.append("- 🟢 纳指涨 > 1% → 明日 A 股科技股/创业板/科创板可能高开")
    if comm.get('WTI 原油', {}).get('change_pct', 0) > 2:
        sections.append("- 🛢️ 原油涨 > 2% → 关注油气股")
    if comm.get('黄金', {}).get('change_pct', 0) > 1.5:
        sections.append("- 🥇 黄金涨 > 1.5% → 关注黄金股(山东黄金/紫金矿业等)")
    if north is not None and north < 0:
        sections.append(f"- 📉 北向资金净流出 {abs(north):.0f} 亿 → 注意外资重仓白马股压力")
    if north is not None and north > 0:
        sections.append(f"- 📈 北向资金净流入 {north:.0f} 亿 → 关注外资重仓蓝筹")
    sections.append("")

    sections.append("---")
    sections.append("")
    sections.append("**报告生成**: GitHub Actions 北京时间 06:00 自动")
    sections.append("**自动覆盖**: Tushare 官方数据 + 美股 + 商品")
    sections.append("**手动补充**: 论坛/股吧/研报/韭研公社/淘股吧")
    sections.append("")

    output_path = os.path.join(REPORTS_DIR, f'{target_date}.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sections))
    print(f"\n✅ 报告已生成: {output_path}")
    return output_path, target_date


if __name__ == '__main__':
    try:
        path, date = generate_report()
    except Exception as e:
        import traceback
        print(f"\n❌ 失败: {e}")
        traceback.print_exc()
        sys.exit(1)