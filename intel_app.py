"""Vibe 情报 v1.0 - 手动触发版"""
import streamlit as st
import requests
import pandas as pd
import re
import json
import os
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Vibe 情报 v1.0", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")
st.title("🛰️ Vibe 情报系统 v1.0")
beijing_now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
st.markdown(f"**{beijing_now} (北京时间)** | 手动触发 | 数据源：东方财富、财联社")

st.markdown("""
## 4 个情报按钮
- 📰 **东财公告快讯**（东方财富公告 50 条）
- 🎯 **龙虎榜**（最近 5 个交易日）
- 🔥 **题材热度**（近期热门题材 + 龙头股）
- 🤖 **综合情报报告**（持仓关联 + 题材联动）
""")

KEYWORDS_HOT = {
    '涨停': 5, '跌停': -5, '重组': 3, '增持': 3, '减持': -2,
    '回购': 2, '业绩预增': 4, '业绩预减': -3, '中标': 3, '签约': 2,
    '龙虎榜': 3, '北向资金': 2, '机构买入': 4, '机构卖出': -4,
    '破产': -5, '风险提示': -3, 'ST': -4, '退市': -5, '立案调查': -5,
    '实控人变更': 3, '重大合同': 3, '新产品': 2, '获批': 3, '上市': 2,
    '回购股份': 2, '股权激励': 3, '股东减持': -2, '股东增持': 3,
}

def extract_sentiment(text):
    """提取情绪分"""
    score = 0
    for kw, val in KEYWORDS_HOT.items():
        if kw in text:
            score += val
    if score >= 5:
        return '🔥 利好', score
    elif score <= -3:
        return '⚠️ 利空', score
    elif score > 0:
        return '📈 偏多', score
    elif score < 0:
        return '📉 偏空', score
    return '➖ 中性', 0


def fetch_eastmoney_announcements(page_size=50):
    """抓取东方财富公告"""
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        'cb': 'jQuery',
        'sr': -1,
        'page_size': page_size,
        'page_index': 1,
        'ann_type': 'A',
        'client_source': 'web',
        'stock_list': '',
        'f_node': 0,
        's_node': 0,
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://data.eastmoney.com/notices/stock/',
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        text = r.text
        if text.startswith('jQuery'):
            text = text[text.index('(') + 1: text.rindex(')')]
        data = json.loads(text)
        items = data.get('data', {}).get('list', [])
        return items
    except Exception as e:
        st.error(f"抓取失败: {e}")
        return []


def fetch_eastmoney_longhu(date_str=None):
    """抓取龙虎榜"""
    if date_str is None:
        beijing = datetime.now(timezone.utc) + timedelta(hours=8)
        date_str = beijing.strftime('%Y-%m-%d')
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        'reportName': 'RPT_DAILYBILLBOARD_DETAIL',
        'columns': 'SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLANATION,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,BUYER_NAME,SELLER_NAME,CLOSE_PRICE,CHANGE_RATE',
        'filter': f'(TRADE_DATE=\'{date_str}\')',
        'pageNumber': 1,
        'pageSize': 50,
        'sortTypes': -1,
        'sortColumns': 'BILLBOARD_NET_AMT',
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://data.eastmoney.com/stock/lhb.html',
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        data = r.json()
        return data.get('result', {}).get('data', [])
    except Exception as e:
        return []


def fetch_eastmoney_hot_concepts():
    """抓取热门题材（东方财富概念板块）"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        'pn': 1,
        'pz': 30,
        'po': 1,
        'np': 1,
        'fltt': 2,
        'invt': 2,
        'fid': 'f3',
        'fs': 'm:90+t:2',
        'fields': 'f1,f2,f3,f4,f5,f6,f12,f14',
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://quote.eastmoney.com/center/',
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        data = r.json()
        items = data.get('data', {}).get('diff', [])
        return items
    except Exception as e:
        return []


def load_holdings():
    if os.path.exists('my_holdings.json'):
        try:
            with open('my_holdings.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def load_stock_list():
    if os.path.exists('data/stock_list.csv'):
        try:
            return pd.read_csv('data/stock_list.csv', dtype={'code': str})
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


df_stocks = load_stock_list()
holdings = load_holdings()
holdings_codes = set(h.get('code', '') for h in holdings)

with st.sidebar:
    st.header("🎯 情报中心")
    st.info(f"持仓 {len(holdings)} 只 | 股票池 {len(df_stocks)} 只")
    st.divider()

    st.subheader("📰 1. 公告快讯")
    if st.button("🔍 抓取最新公告 (50 条)", use_container_width=True, type="primary"):
        st.session_state.run_ann = True
    st.divider()

    st.subheader("🎯 2. 龙虎榜")
    longhu_date = st.text_input("日期", value=beijing_now[:10], placeholder="2026-06-19")
    if st.button("🔍 抓取龙虎榜", use_container_width=True):
        st.session_state.run_longhu = True
    st.divider()

    st.subheader("🔥 3. 题材热度")
    if st.button("🔍 抓取热门题材 (Top 30)", use_container_width=True):
        st.session_state.run_hot = True
    st.divider()

    st.subheader("🤖 4. 综合情报报告")
    if st.button("🚀 一键综合分析", use_container_width=True, type="primary"):
        st.session_state.run_full = True

if st.session_state.get('run_ann'):
    st.header("📰 东方财富公告快讯 (最新 50 条)")
    with st.spinner("抓取中..."):
        items = fetch_eastmoney_announcements(50)
    if items:
        rows = []
        for it in items[:50]:
            codes = it.get('codes', [])
            code = codes[0].get('stock_code', '') if codes else ''
            name = codes[0].get('short_name', '') if codes else ''
            title = it.get('title', '')
            time = it.get('display_time', '')[:16]
            cols = [c.get('column_name', '') for c in it.get('columns', [])]
            tag = '/'.join(cols[:2])
            sentiment, score = extract_sentiment(title)
            in_holdings = '⭐' if code in holdings_codes else ''
            rows.append({
                '持仓': in_holdings,
                '代码': code,
                '名称': name,
                '情绪': sentiment,
                '分': score,
                '时间': time,
                '类型': tag,
                '标题': title[:80],
            })
        df = pd.DataFrame(rows)
        st.success(f"抓取到 {len(df)} 条公告")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("公告数", len(df))
        col2.metric("利好", len(df[df['分'] > 0]))
        col3.metric("利空", len(df[df['分'] < 0]))
        col4.metric("持仓相关", len(df[df['持仓'] == '⭐']))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.session_state.last_ann = df

if st.session_state.get('run_longhu'):
    st.header("🎯 龙虎榜")
    with st.spinner("抓取中..."):
        items = fetch_eastmoney_longhu(longhu_date)
    if items:
        rows = []
        for it in items[:30]:
            code = it.get('SECURITY_CODE', '')
            name = it.get('SECURITY_NAME_ABBR', '')
            net = it.get('BILLBOARD_NET_AMT', 0)
            buy = it.get('BILLBOARD_BUY_AMT', 0)
            sell = it.get('BILLBOARD_SELL_AMT', 0)
            close = it.get('CLOSE_PRICE', 0)
            change = it.get('CHANGE_RATE', 0)
            explain = it.get('EXPLANATION', '')
            in_holdings = '⭐' if code in holdings_codes else ''
            rows.append({
                '持仓': in_holdings,
                '代码': code,
                '名称': name,
                '收盘': close,
                '涨幅%': change,
                '净买(万)': round(net / 10000, 2),
                '买(万)': round(buy / 10000, 2),
                '卖(万)': round(sell / 10000, 2),
                '解读': explain[:30],
            })
        df = pd.DataFrame(rows)
        st.success(f"抓取到 {len(df)} 条龙虎榜")
        col1, col2, col3 = st.columns(3)
        col1.metric("上榜数", len(df))
        col2.metric("净流入(万)", round(df['净买(万)'].sum(), 2))
        col3.metric("持仓相关", len(df[df['持仓'] == '⭐']))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.session_state.last_longhu = df
    else:
        st.warning(f"{longhu_date} 当天无龙虎榜或抓取失败（试试最近交易日）")

if st.session_state.get('run_hot'):
    st.header("🔥 热门题材 (东方财富板块 Top 30)")
    with st.spinner("抓取中..."):
        items = fetch_eastmoney_hot_concepts()
    if items:
        rows = []
        for it in items[:30]:
            rows.append({
                '题材': it.get('f14', ''),
                '代码': it.get('f12', ''),
                '涨幅%': round(float(it.get('f3', 0)), 2),
                '主力净流入(亿)': round(float(it.get('f6', 0)) / 1e8, 2) if it.get('f6') else 0,
            })
        df = pd.DataFrame(rows)
        st.success(f"抓取到 {len(df)} 个题材")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.session_state.last_hot = df

if st.session_state.get('run_full'):
    st.header("🤖 综合情报报告")
    st.write("正在汇总 4 类情报...")
    with st.spinner("抓取所有情报..."):
        ann = fetch_eastmoney_announcements(50)
        longhu_items = fetch_eastmoney_longhu(beijing_now[:10])
        hot_items = fetch_eastmoney_hot_concepts()
        st.success("情报抓取完成")
    st.subheader("📌 持仓相关公告")
    if ann:
        holding_news = [it for it in ann if it.get('codes') and it['codes'][0].get('stock_code') in holdings_codes]
        if holding_news:
            for it in holding_news[:10]:
                code = it['codes'][0].get('stock_code', '')
                name = it['codes'][0].get('short_name', '')
                title = it.get('title', '')
                sentiment, score = extract_sentiment(title)
                st.write(f"{sentiment} **{code} {name}** ({score}分) - {title[:60]}")
        else:
            st.info("今日持仓无重大公告")
    st.divider()
    st.subheader("🎯 持仓股龙虎榜")
    if longhu_items:
        holding_lh = [it for it in longhu_items if it.get('SECURITY_CODE') in holdings_codes]
        if holding_lh:
            for it in holding_lh[:10]:
                code = it.get('SECURITY_CODE', '')
                name = it.get('SECURITY_NAME_ABBR', '')
                net = round(it.get('BILLBOARD_NET_AMT', 0) / 10000, 2)
                st.write(f"**{code} {name}** 净买: {net} 万 - {it.get('EXPLANATION', '')[:40]}")
        else:
            st.info("今日持仓未上榜")
    else:
        st.info("今日无龙虎榜数据")
    st.divider()
    st.subheader("🔥 当前热门题材 Top 10")
    if hot_items:
        for it in hot_items[:10]:
            name = it.get('f14', '')
            change = round(float(it.get('f3', 0)), 2)
            emoji = '🚀' if change > 5 else ('📈' if change > 0 else '📉')
            st.write(f"{emoji} **{name}** 板块涨幅: {change}%")
    st.divider()
    st.subheader("💡 决策建议")
    st.info("""
**当前建议**：
1. 查看持仓相关公告，判断利好利空
2. 查看持仓股是否上榜龙虎榜（机构动向）
3. 关注热门题材，对比持仓是否在风口
4. 结合 Vibe 量化 App 的选股结果
""")

st.divider()
st.caption(f"Vibe 情报 v1.0 | {beijing_now} (北京时间) | 手动触发")
