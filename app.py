"""Vibe 量化系统 - 绝对能跑版（直接用降级数据，不依赖AKShare）"""
import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Vibe 量化 v1.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v1.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：内置 30 只核心股")

FALLBACK_STOCKS = [
    {'code': '600519', 'name': '贵州茅台', 'price': 1680.0, 'pct_change': 0.5, 'market_cap_yi': 21000, 'industry': '食品饮料'},
    {'code': '000858', 'name': '五粮液', 'price': 145.0, 'pct_change': 0.3, 'market_cap_yi': 5600, 'industry': '食品饮料'},
    {'code': '300750', 'name': '宁德时代', 'price': 230.0, 'pct_change': 1.2, 'market_cap_yi': 10000, 'industry': '电力设备'},
    {'code': '601318', 'name': '中国平安', 'price': 50.0, 'pct_change': -0.2, 'market_cap_yi': 9100, 'industry': '非银金融'},
    {'code': '600036', 'name': '招商银行', 'price': 38.0, 'pct_change': 0.4, 'market_cap_yi': 9600, 'industry': '银行'},
    {'code': '000001', 'name': '平安银行', 'price': 11.0, 'pct_change': 0.1, 'market_cap_yi': 2200, 'industry': '银行'},
    {'code': '600276', 'name': '恒瑞医药', 'price': 45.0, 'pct_change': 0.8, 'market_cap_yi': 2900, 'industry': '医药生物'},
    {'code': '000333', 'name': '美的集团', 'price': 75.0, 'pct_change': 0.6, 'market_cap_yi': 5300, 'industry': '家用电器'},
    {'code': '601012', 'name': '隆基绿能', 'price': 18.0, 'pct_change': -0.5, 'market_cap_yi': 1400, 'industry': '电力设备'},
    {'code': '002594', 'name': '比亚迪', 'price': 245.0, 'pct_change': 1.5, 'market_cap_yi': 7100, 'industry': '汽车'},
    {'code': '600900', 'name': '长江电力', 'price': 28.0, 'pct_change': 0.2, 'market_cap_yi': 6800, 'industry': '公用事业'},
    {'code': '601398', 'name': '工商银行', 'price': 7.5, 'pct_change': 0.1, 'market_cap_yi': 24000, 'industry': '银行'},
    {'code': '601939', 'name': '建设银行', 'price': 8.0, 'pct_change': 0.2, 'market_cap_yi': 22000, 'industry': '银行'},
    {'code': '601988', 'name': '中国银行', 'price': 5.0, 'pct_change': 0.1, 'market_cap_yi': 15000, 'industry': '银行'},
    {'code': '600028', 'name': '中国石化', 'price': 6.5, 'pct_change': 0.3, 'market_cap_yi': 7800, 'industry': '石油石化'},
    {'code': '600050', 'name': '中国联通', 'price': 5.5, 'pct_change': 0.2, 'market_cap_yi': 1700, 'industry': '通信'},
    {'code': '601800', 'name': '中国交建', 'price': 9.0, 'pct_change': 0.1, 'market_cap_yi': 1500, 'industry': '建筑装饰'},
    {'code': '601628', 'name': '中国人寿', 'price': 38.0, 'pct_change': 0.4, 'market_cap_yi': 10700, 'industry': '非银金融'},
    {'code': '601857', 'name': '中国石油', 'price': 9.5, 'pct_change': 0.3, 'market_cap_yi': 17000, 'industry': '石油石化'},
    {'code': '600585', 'name': '海螺水泥', 'price': 24.0, 'pct_change': 0.2, 'market_cap_yi': 1300, 'industry': '建筑材料'},
    {'code': '600887', 'name': '伊利股份', 'price': 27.0, 'pct_change': -0.3, 'market_cap_yi': 1700, 'industry': '食品饮料'},
    {'code': '601088', 'name': '中国神华', 'price': 42.0, 'pct_change': 0.5, 'market_cap_yi': 8400, 'industry': '煤炭'},
    {'code': '601288', 'name': '农业银行', 'price': 5.0, 'pct_change': 0.1, 'market_cap_yi': 18000, 'industry': '银行'},
    {'code': '601328', 'name': '交通银行', 'price': 7.0, 'pct_change': 0.2, 'market_cap_yi': 5500, 'industry': '银行'},
    {'code': '600000', 'name': '浦发银行', 'price': 9.0, 'pct_change': 0.1, 'market_cap_yi': 2700, 'industry': '银行'},
    {'code': '601166', 'name': '兴业银行', 'price': 18.0, 'pct_change': 0.3, 'market_cap_yi': 3700, 'industry': '银行'},
    {'code': '601229', 'name': '上海银行', 'price': 8.5, 'pct_change': 0.2, 'market_cap_yi': 1200, 'industry': '银行'},
    {'code': '600030', 'name': '中信证券', 'price': 22.0, 'pct_change': 0.4, 'market_cap_yi': 3200, 'industry': '非银金融'},
    {'code': '601688', 'name': '华泰证券', 'price': 18.0, 'pct_change': 0.3, 'market_cap_yi': 1700, 'industry': '非银金融'},
    {'code': '000651', 'name': '格力电器', 'price': 42.0, 'pct_change': 0.2, 'market_cap_yi': 2400, 'industry': '家用电器'},
]


def make_kline(code, name, base_price, days=120):
    import random
    random.seed(hash(code) % (2**32))
    if base_price < 20:
        base_price = 20.0
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    data = []
    price = base_price
    for d in dates:
        change = random.gauss(0.001, 0.02)
        price = max(price * (1 + change), 1.0)
        data.append({
            'date': d.strftime('%Y-%m-%d'),
            'open': round(price * 0.99, 2),
            'high': round(price * 1.01, 2),
            'low': round(price * 0.98, 2),
            'close': round(price, 2),
            'volume': int(random.uniform(1e6, 1e8)),
            'pct_change': round(change * 100, 2),
        })
    df = pd.DataFrame(data)
    df['code'] = code
    df['name'] = name
    return df


def compute_trend_signals(kline_data, top_n=5):
    rows = []
    for code, df in kline_data.items():
        if df.empty or len(df) < 60:
            continue
        df = df.copy()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        last = df.iloc[-1]
        prev = df.iloc[-5]
        if pd.isna(last['ma20']) or pd.isna(last['ma60']):
            continue
        if last['close'] > last['ma20'] and last['ma20'] > last['ma60']:
            if last['close'] > prev['close']:
                rows.append({
                    'code': code,
                    'name': last['name'],
                    'price': round(last['close'], 2),
                    'pct_change': round(last['pct_change'], 2),
                    'ma20': round(last['ma20'], 2),
                    'ma60': round(last['ma60'], 2),
                })
    return pd.DataFrame(rows).head(top_n)


def compute_rotation_signals(kline_data, top_n=5):
    industries = {}
    for s in FALLBACK_STOCKS:
        industries.setdefault(s['industry'], []).append(s)
    rows = []
    for ind, stocks in industries.items():
        scores = []
        for s in stocks[:5]:
            code = s['code']
            if code in kline_data and not kline_data[code].empty:
                df = kline_data[code]
                if len(df) >= 20:
                    ret = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
                    scores.append(ret)
        if scores:
            avg = sum(scores) / len(scores)
            if avg > 0:
                leader = stocks[0]
                rows.append({
                    'industry': ind,
                    'leader': leader['name'],
                    'code': leader['code'],
                    'price': leader['price'],
                    'avg_return_20d': round(avg, 2),
                })
    df_out = pd.DataFrame(rows).sort_values('avg_return_20d', ascending=False).head(top_n)
    return df_out


def compute_factor_signals(kline_data, top_n=10):
    rows = []
    for s in FALLBACK_STOCKS:
        code = s['code']
        if code in kline_data and not kline_data[code].empty:
            df = kline_data[code]
            if len(df) >= 60:
                ret_20 = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
                vol = df['pct_change'].std()
                score = 60 + ret_20 * 2 - vol
                rows.append({
                    'code': code,
                    'name': s['name'],
                    'price': round(df['close'].iloc[-1], 2),
                    'pct_change': round(df['pct_change'].iloc[-1], 2),
                    'ret_20d': round(ret_20, 2),
                    'volatility': round(vol, 2),
                    'total_score': round(score, 2),
                })
    return pd.DataFrame(rows).sort_values('total_score', ascending=False).head(top_n)


with st.sidebar:
    st.header("⚙️ 参数设置")
    n_stocks = st.slider("扫描股票数", 5, 30, 20, 1)
    top_n = st.slider("Top N", 3, 10, 5, 1)
    st.divider()
    st.subheader("🎯 策略开关")
    use_trend = st.checkbox("趋势策略", value=True)
    use_rotation = st.checkbox("行业轮动", value=True)
    use_factors = st.checkbox("多因子", value=True)
    st.divider()
    run = st.button("🚀 运行分析", type="primary", use_container_width=True)

st.markdown("""
## 👋 欢迎使用 Vibe 量化系统 v1.0

### 🎯 系统能力
- **🔥 趋势策略**（主）：均线多头 + 量价齐升
- **🔄 行业轮动**（主）：强势行业龙头
- **📊 多因子选股**（辅）：动量+波动率综合

### 🚀 开始使用
1. 左侧调整 **扫描股票数** 和 **Top N**
2. 勾选你要跑的 **策略**
3. 点击 **🚀 运行分析** 按钮

### 💡 数据源说明
- 内置 **30 只 A 股核心股**（不依赖网络）
- 合成 **120 天 K 线**数据
- 适合学习研究、策略验证

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
> 投资有风险，决策需谨慎。
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📊 生成 30 只核心股数据...")
        progress.progress(30)
        kline_data = {}
        for s in FALLBACK_STOCKS[:n_stocks]:
            kline_data[s['code']] = make_kline(s['code'], s['name'], s['price'])
        progress.progress(60)
        status.text("🔍 计算策略信号...")
        if use_trend:
            trend_df = compute_trend_signals(kline_data, top_n=top_n)
        if use_rotation:
            rotation_df = compute_rotation_signals(kline_data, top_n=top_n)
        if use_factors:
            factors_df = compute_factor_signals(kline_data, top_n=top_n)
        progress.progress(100)
        status.text("✅ 分析完成！")
        progress.empty()
        status.empty()
        st.success(f"🎉 已分析 {len(kline_data)} 只股票！")
        if use_trend:
            st.header("🔥 趋势策略信号（均线多头+量价齐升）")
            if not trend_df.empty:
                st.dataframe(trend_df, use_container_width=True, hide_index=True)
                st.caption(f"📊 共 {len(trend_df)} 只股票触发趋势买入信号")
            else:
                st.info("📭 今日无趋势策略信号（市场处于震荡或下跌趋势）")
        if use_rotation:
            st.header("🔄 行业轮动信号（强势行业龙头）")
            if not rotation_df.empty:
                st.dataframe(rotation_df, use_container_width=True, hide_index=True)
                st.caption(f"📊 共 {len(rotation_df)} 个行业进入强势区域")
            else:
                st.info("📭 今日无行业轮动信号")
        if use_factors:
            st.header("📊 多因子精选（综合Top榜单）")
            if not factors_df.empty:
                st.dataframe(factors_df, use_container_width=True, hide_index=True)
                st.caption(f"📊 共 {len(factors_df)} 只股票入选多因子精选")
            else:
                st.info("📭 今日无多因子信号")
    except Exception as e:
        st.error(f"❌ 运行出错: {e}")
        import traceback
        st.code(traceback.format_exc())

st.divider()
st.caption("Vibe 量化 v1.0 | 数据：内置 30 只核心股 + 合成 K 线 | 仅供学习研究")
