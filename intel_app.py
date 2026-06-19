"""Vibe 情报 v1.0 - 手动触发版"""
import streamlit as st
import requests
import pandas as pd
import re
import json
import os
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Vibe 情报 v1.0", page_icon="V", layout="wide", initial_sidebar_state="expanded")
st.title("Vibe 情报系统 v1.0")
beijing_now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
st.markdown(f"**{beijing_now} (北京时间)** | 手动触发 | 数据源：东方财富")

st.markdown("""
## 4 个情报按钮
- 东财公告快讯（东方财富公告 50 条）
- 龙虎榜（最近 5 个交易日）
- 题材热度（近期热门题材 + 龙头股）
- 综合情报报告（持仓关联 + 题材联动）
""")

KEYWORDS_HOT = {
'涨停': 5, '跌停': -5, '重组': 3, '增持': 3, '减持': -2,
'回购': 2, '业绩预增': 4, '业绩预减': -3, '中标': 3, '签约': 2,
'龙虎榜': 3, '北向资金': 2, '机构买入': 4, '机构卖出': -4,
'破产': -5, '风险提示': -3, 'ST': -4, '退市': -5, '立案调查': -5,
'实控人变更': 3, '重大合同': 3, '新产品': 2, '获批': 3, '上市': 2,
}

def get_score(text):
    s = 0
    for k, v in KEYWORDS_HOT.items():
        if k in text:
            s += v
    if s >= 5:
        return '利好', s
    elif s <= -3:
        return '利空', s
    elif s > 0:
        return '偏多', s
    elif s < 0:
        return '偏空', s
    return '中性', 0


def fetch_ann():
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {'cb': 'jQuery', 'sr': -1, 'page_size': 50, 'page_index': 1,
              'ann_type': 'A', 'client_source': 'web', 'stock_list': '', 'f_node': 0, 's_node': 0}
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/notices/stock/'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        text = r.text
        if text.startswith('jQuery'):
            text = text[text.index('(') + 1: text.rindex(')')]
        data = json.loads(text)
        return data.get('data', {}).get('list', [])
    except Exception:
        return []


def fetch_longhu(date_str):
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        'reportName': 'RPT_DAILYBILLBOARD_DETAIL',
        'columns': 'SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLANATION,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,CLOSE_PRICE,CHANGE_RATE',
        'filter': f'(TRADE_DATE=\'{date_str}\')',
        'pageNumber': 1, 'pageSize': 50, 'sortTypes': -1, 'sortColumns': 'BILLBOARD_NET_AMT',
    }
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/stock/lhb.html'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        return r.json().get('result', {}).get('data', [])
    except Exception:
        return []


def fetch_hot():
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {'pn': 1, 'pz': 30, 'po': 1, 'np': 1, 'fltt': 2, 'invt': 2,
              'fid': 'f3', 'fs': 'm:90+t:2', 'fields': 'f1,f2,f3,f4,f5,f6,f12,f14'}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        return r.json().get('data', {}).get('diff', [])
    except Exception:
        return []


def load_holdings():
    if os.path.exists('my_holdings.json'):
        try:
            with open('my_holdings.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_holdings(holdings):
    try:
        with open('my_holdings.json', 'w', encoding='utf-8') as f:
            json.dump(holdings, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_stock_list():
    if os.path.exists('data/stock_list.csv'):
        try:
            return pd.read_csv('data/stock_list.csv', dtype={'code': str})
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


df_stocks = load_stock_list()
if 'holdings' not in st.session_state:
    st.session_state.holdings = load_holdings()
holdings = st.session_state.holdings
holdings_codes = set(h.get('code', '') for h in holdings)

with st.sidebar:
    st.header("情报中心")
    st.info(f"持仓 {len(holdings)} 只 | 股票池 {len(df_stocks)} 只")
    st.divider()

    with st.expander("我的持仓管理", expanded=False):
        st.write(f"当前持仓: {len(holdings)} 只")
        if holdings:
            for i, h in enumerate(holdings):
                col1, col2 = st.columns([3, 1])
                col1.write(f"{h.get('code', '')} {h.get('name', '')}")
                if col2.button("X", key=f"del_{i}"):
                    holdings.pop(i)
                    st.session_state.holdings = holdings
                    save_holdings(holdings)
                    st.rerun()
        st.write("--- 添加 ---")
        new_code = st.text_input("代码 (6位)", key="new_code", placeholder="如 600519")
        if st.button("添加", key="add_btn"):
            new_code = new_code.strip()
            if len(new_code) == 6 and new_code.isdigit() and df_stocks is not None:
                match = df_stocks[df_stocks['code'] == new_code]
                if not match.empty:
                    name = match.iloc[0]['name']
                    if not any(h.get('code') == new_code for h in holdings):
                        holdings.append({'code': new_code, 'name': name})
                        st.session_state.holdings = holdings
                        save_holdings(holdings)
                        st.success(f"已添加 {new_code} {name}")
                        st.rerun()
        st.write("--- 批量导入 ---")
        bulk_text = st.text_area("每行一个代码", height=100, key="bulk")
        if st.button("批量导入", key="bulk_btn"):
            new_codes = [c.strip() for c in bulk_text.split('\n') if c.strip()]
            added = 0
            for nc in new_codes:
                if len(nc) == 6 and nc.isdigit() and not any(h.get('code') == nc for h in holdings) and df_stocks is not None:
                    match = df_stocks[df_stocks['code'] == nc]
                    if not match.empty:
                        holdings.append({'code': nc, 'name': match.iloc[0]['name']})
                        added += 1
            if added:
                st.session_state.holdings = holdings
                save_holdings(holdings)
                st.success(f"已添加 {added} 只")
                st.rerun()
    st.divider()

    st.subheader("1. 公告快讯")
    if st.button("抓取最新公告 (50 条)", use_container_width=True, type="primary"):
        st.session_state.run_ann = True
    st.divider()

    st.subheader("2. 龙虎榜")
    longhu_date = st.text_input("日期", value=beijing_now[:10])
    if st.button("抓取龙虎榜", use_container_width=True):
        st.session_state.run_longhu = True
    st.divider()

    st.subheader("3. 题材热度")
    if st.button("抓取热门题材 (Top 30)", use_container_width=True):
        st.session_state.run_hot = True
    st.divider()

    st.subheader("4. 综合情报报告")
    if st.button("一键综合分析", use_container_width=True, type="primary"):
        st.session_state.run_full = True

if st.session_state.get('run_ann'):
    st.header("东方财富公告快讯 (最新 50 条)")
    with st.spinner("抓取中..."):
        items = fetch_ann()
    if items:
        rows = []
        for it in items[:50]:
            codes = it.get('codes', [])
            code = codes[0].get('stock_code', '') if codes else ''
            name = codes[0].get('short_name', '') if codes else ''
            title = it.get('title', '')
            sentiment, score = get_score(title)
            in_holdings = '*' if code in holdings_codes else ''
            rows.append({
                '持仓': in_holdings,
                '代码': code,
                '名称': name,
                '情绪': sentiment,
                '分': score,
                '标题': title[:80],
            })
        df = pd.DataFrame(rows)
        st.success(f"抓取到 {len(df)} 条公告")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("公告数", len(df))
        col2.metric("利好", len(df[df['分'] > 0]))
        col3.metric("利空", len(df[df['分'] < 0]))
        col4.metric("持仓相关", len(df[df['持仓'] == '*']))
        st.dataframe(df, use_container_width=True, hide_index=True)

if st.session_state.get('run_longhu'):
    st.header("龙虎榜")
    with st.spinner("抓取中..."):
        items = fetch_longhu(longhu_date)
    if items:
        rows = []
        for it in items[:30]:
            code = it.get('SECURITY_CODE', '')
            name = it.get('SECURITY_NAME_ABBR', '')
            net = it.get('BILLBOARD_NET_AMT', 0)
            close = it.get('CLOSE_PRICE', 0)
            change = it.get('CHANGE_RATE', 0)
            in_holdings = '*' if code in holdings_codes else ''
            rows.append({
                '持仓': in_holdings,
                '代码': code,
                '名称': name,
                '收盘': close,
                '涨幅%': change,
                '净买(万)': round(net / 10000, 2),
            })
        df = pd.DataFrame(rows)
        st.success(f"抓取到 {len(df)} 条龙虎榜")
        col1, col2, col3 = st.columns(3)
        col1.metric("上榜数", len(df))
        col2.metric("净流入(万)", round(df['净买(万)'].sum(), 2))
        col3.metric("持仓相关", len(df[df['持仓'] == '*']))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"{longhu_date} 当天无龙虎榜或抓取失败")

if st.session_state.get('run_hot'):
    st.header("热门题材 Top 30")
    with st.spinner("抓取中..."):
        items = fetch_hot()
    if items:
        rows = []
        for it in items[:30]:
            rows.append({
                '题材': it.get('f14', ''),
                '代码': it.get('f12', ''),
                '涨幅%': round(float(it.get('f3', 0)), 2),
            })
        df = pd.DataFrame(rows)
        st.success(f"抓取到 {len(df)} 个题材")
        st.dataframe(df, use_container_width=True, hide_index=True)

if st.session_state.get('run_full'):
    st.header("综合情报报告")
    with st.spinner("汇总中..."):
        ann = fetch_ann()
        longhu_items = fetch_longhu(beijing_now[:10])
        hot_items = fetch_hot()
    st.success("情报汇总完成")
    st.subheader("持仓相关公告")
    if ann:
        holding_news = [it for it in ann if it.get('codes') and it['codes'][0].get('stock_code') in holdings_codes]
        if holding_news:
            for it in holding_news[:10]:
                code = it['codes'][0].get('stock_code', '')
                name = it['codes'][0].get('short_name', '')
                title = it.get('title', '')
                sentiment, score = get_score(title)
                st.write(f"{sentiment} **{code} {name}** ({score}分) - {title[:60]}")
        else:
            st.info("今日持仓无重大公告")
    st.divider()
    st.subheader("持仓股龙虎榜")
    if longhu_items:
        holding_lh = [it for it in longhu_items if it.get('SECURITY_CODE') in holdings_codes]
        if holding_lh:
            for it in holding_lh[:10]:
                code = it.get('SECURITY_CODE', '')
                name = it.get('SECURITY_NAME_ABBR', '')
                net = round(it.get('BILLBOARD_NET_AMT', 0) / 10000, 2)
                st.write(f"**{code} {name}** 净买: {net} 万")
        else:
            st.info("今日持仓未上榜")
    st.divider()
    st.subheader("当前热门题材 Top 10")
    if hot_items:
        for it in hot_items[:10]:
            name = it.get('f14', '')
            change = round(float(it.get('f3', 0)), 2)
            st.write(f"**{name}** 板块涨幅: {change}%")
    st.divider()
    st.subheader("决策建议")
    st.info("""
1. 查看持仓相关公告，判断利好利空
2. 查看持仓股是否上榜龙虎榜
3. 关注热门题材，对比持仓
4. 结合 Vibe 量化 App 的选股结果
""")

st.divider()
st.caption(f"Vibe 情报 v1.0 | {beijing_now} (北京时间)")
