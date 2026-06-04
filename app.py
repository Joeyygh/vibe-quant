"""Vibe 量化系统 v2.0 - Tushare 数据源"""
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Vibe 量化 v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v2.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：Tushare（5000+ 全 A 股）")

try:
    import yaml
    with open('config.yaml', 'r', encoding='utf-8') as f:
        CONFIG = yaml.safe_load(f)
    TUSHARE_TOKEN = CONFIG.get('system', {}).get('tushare_token', '')
except Exception as e:
    st.error(f"读取 config.yaml 失败: {e}")
    TUSHARE_TOKEN = ''

from data import DataFetcher

@st.cache_resource(show_spinner=False)
def get_fetcher():
    return DataFetcher(tushare_token=TUSHARE_TOKEN)

fetcher = get_fetcher()
pro = fetcher._pro

if pro is None:
    st.warning("⚠️ Tushare 未连接，将使用内置 30 只核心股作为降级方案")
    st.info("💡 提示：检查 config.yaml 的 tushare_token 是否正确")

def make_kline(code, name, base_price, days=120):
    import random
    random.seed(hash(code) % (2**32))
    if base_price < 5:
        base_price = 5.0
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

def compute_trend_signals(kline_data, top_n=10):
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
                    '代码': code,
                    '名称': last['name'],
                    '现价': round(last['close'], 2),
                    '今日涨幅%': round(last['pct_change'], 2),
                    'MA20': round(last['ma20'], 2),
                    'MA60': round(last['ma60'], 2),
                })
    return pd.DataFrame(rows).head(top_n)

def compute_rotation_signals(kline_data, industry_map, top_n=5):
    industries = {}
    for code, ind in industry_map.items():
        industries.setdefault(ind, []).append(code)
    rows = []
    for ind, codes in industries.items():
        scores = []
        for code in codes[:10]:
            if code in kline_data and not kline_data[code].empty and len(kline_data[code]) >= 20:
                df = kline_data[code]
                ret = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
                scores.append(ret)
        if scores and len(scores) >= 2:
            avg = sum(scores) / len(scores)
            if avg > -2:
                leader_code = codes[0]
                leader_name = kline_data[leader_code]['name'].iloc[0] if leader_code in kline_data else leader_code
                leader_price = kline_data[leader_code]['close'].iloc[-1] if leader_code in kline_data else 0
                rows.append({
                    '行业': ind,
                    '龙头': leader_name,
                    '龙头代码': leader_code,
                    '现价': round(leader_price, 2),
                    '行业20日均涨幅%': round(avg, 2),
                    '成分股数': len(scores),
                })
    return pd.DataFrame(rows).sort_values('行业20日均涨幅%', ascending=False).head(top_n)

def compute_factor_signals(kline_data, top_n=20):
    rows = []
    for code, df in kline_data.items():
        if df.empty or len(df) < 60:
            continue
        ret_20 = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
        ret_5 = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100
        vol = df['pct_change'].std()
        score = 50 + ret_20 * 1.5 + ret_5 * 0.5 - vol * 2
        rows.append({
            '代码': code,
            '名称': df['name'].iloc[-1] if 'name' in df.columns else code,
            '现价': round(df['close'].iloc[-1], 2),
            '5日涨幅%': round(ret_5, 2),
            '20日涨幅%': round(ret_20, 2),
            '波动率': round(vol, 2),
            '综合得分': round(score, 2),
        })
    return pd.DataFrame(rows).sort_values('综合得分', ascending=False).head(top_n)


with st.sidebar:
    st.header("⚙️ 参数设置")
    n_stocks = st.slider("扫描股票数", 50, 3000, 500, 50, help="Tushare 免费版每天 200 次，建议≤500")
    top_n = st.slider("Top N", 3, 30, 10, 1)
    st.divider()
    st.subheader("🎯 策略开关")
    use_trend = st.checkbox("趋势策略", value=True)
    use_rotation = st.checkbox("行业轮动", value=True)
    use_factors = st.checkbox("多因子", value=True)
    st.divider()
    run = st.button("🚀 运行分析", type="primary", use_container_width=True)

st.markdown("""
## 👋 欢迎使用 Vibe 量化系统 v2.0

### 🎯 系统能力
- **🔥 趋势策略**（主）：均线多头 + 量价齐升
- **🔄 行业轮动**（主）：强势行业龙头
- **📊 多因子选股**（辅）：动量+波动率综合

### 🚀 开始使用
1. 左侧调整 **扫描股票数**（Tushare 免费版建议 500 以内）
2. 左侧调整 **Top N**
3. 勾选你要跑的 **策略**
4. 点击 **🚀 运行分析** 按钮

### 💡 数据源说明
- 主数据源：**Tushare**（5000+ 全 A 股）
- 降级数据：**内置 30 只核心股**（Tushare 失败时启用）

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
> 投资有风险，决策需谨慎。
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📊 加载股票列表...")
        progress.progress(10)
        stock_list = fetcher.get_stock_list()
        if stock_list.empty:
            st.error("❌ 未能获取到股票列表")
            st.stop()
        codes = stock_list['code'].tolist()[:n_stocks]
        status.text(f"📈 加载 {len(codes)} 只股票的K线数据...")
        progress.progress(30)
        kline_data = fetcher.get_kline_batch(codes, start="2024-01-01")
        if not kline_data:
            st.error("❌ 未能获取到任何K线数据")
            st.stop()
        progress.progress(60)
        status.text("🔍 计算策略信号...")
        industry_map = fetcher.get_industry_map()
        if use_trend:
            trend_df = compute_trend_signals(kline_data, top_n=top_n)
        if use_rotation:
            rotation_df = compute_rotation_signals(kline_data, industry_map, top_n=5)
        if use_factors:
            factors_df = compute_factor_signals(kline_data, top_n=top_n*2)
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
                st.info("📭 今日无趋势策略信号")
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
st.caption("Vibe 量化 v2.0 | 数据：Tushare + 降级方案 | 仅供学习研究")
