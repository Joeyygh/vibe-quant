"""Vibe 量化 v2.0 - Tushare 真实数据版"""
import streamlit as st
import pandas as pd
import random
import os
import json
from datetime import datetime

st.set_page_config(
    page_title="Vibe 量化 v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v2.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：Tushare 真实数据 + 内置降级")


FALLBACK_STOCKS = [
    ('600519', '贵州茅台', '食品饮料', 1680), ('601318', '中国平安', '非银金融', 50),
    ('600036', '招商银行', '银行', 38), ('000858', '五粮液', '食品饮料', 145),
    ('300750', '宁德时代', '电力设备', 230), ('002594', '比亚迪', '汽车', 245),
    ('600276', '恒瑞医药', '医药生物', 45), ('000333', '美的集团', '家用电器', 75),
    ('601012', '隆基绿能', '电力设备', 18), ('600900', '长江电力', '公用事业', 28),
    ('601398', '工商银行', '银行', 7.5), ('601939', '建设银行', '银行', 8),
    ('601988', '中国银行', '银行', 5), ('600028', '中国石化', '石油石化', 6.5),
    ('600050', '中国联通', '通信', 5.5), ('601628', '中国人寿', '非银金融', 38),
    ('601857', '中国石油', '石油石化', 9.5), ('600887', '伊利股份', '食品饮料', 27),
    ('601088', '中国神华', '煤炭', 42), ('601288', '农业银行', '银行', 5),
    ('601328', '交通银行', '银行', 7), ('600030', '中信证券', '非银金融', 22),
    ('000651', '格力电器', '家用电器', 42), ('600585', '海螺水泥', '建筑材料', 24),
    ('601800', '中国交建', '建筑装饰', 9), ('601166', '兴业银行', '银行', 18),
    ('601229', '上海银行', '银行', 8.5), ('601688', '华泰证券', '非银金融', 18),
    ('000001', '平安银行', '银行', 11), ('000002', '万科A', '房地产', 8.5),
    ('000063', '中兴通讯', '通信', 28), ('000100', 'TCL科技', '电子', 4.5),
    ('000538', '云南白药', '医药生物', 52), ('000568', '泸州老窖', '食品饮料', 165),
    ('000625', '长安汽车', '汽车', 14), ('000661', '长春高新', '医药生物', 120),
    ('000725', '京东方A', '电子', 4.2), ('000776', '广发证券', '非银金融', 16),
    ('002027', '分众传媒', '传媒', 7.5), ('002230', '科大讯飞', '计算机', 52),
    ('002415', '海康威视', '计算机', 35), ('002460', '赣锋锂业', '有色金属', 35),
    ('002475', '立讯精密', '电子', 38), ('002714', '牧原股份', '农林牧渔', 45),
    ('300014', '亿纬锂能', '电力设备', 52), ('300033', '同花顺', '计算机', 145),
    ('300059', '东方财富', '非银金融', 18), ('300124', '汇川技术', '机械设备', 65),
    ('300274', '阳光电源', '电力设备', 75), ('300760', '迈瑞医疗', '医药生物', 280),
]


@st.cache_data(ttl=3600, show_spinner="加载 Tushare 真实数据...")
def load_tushare_data():
    try:
        if os.path.exists('data/stock_list.csv'):
            df_stocks = pd.read_csv('data/stock_list.csv', dtype={'code': str})
            df_stocks['code'] = df_stocks['code'].astype(str).str.zfill(6)
            if os.path.exists('data/klines.parquet'):
                df_klines = pd.read_parquet('data/klines.parquet')
                df_klines['code'] = df_klines['code'].astype(str).str.zfill(6)
                return df_stocks, df_klines, "Tushare 真实数据"
    except Exception as e:
        st.warning(f"读 Tushare 数据失败: {e}")
    return None, None, "内置降级数据"


def generate_fallback_klines(n_stocks=50):
    random.seed(42)
    kline_dict = {}
    INDUSTRY_PRICE = {
        '食品饮料': 80, '银行': 12, '非银金融': 18, '电力设备': 50,
        '汽车': 35, '医药生物': 45, '家用电器': 35, '公用事业': 18,
        '石油石化': 12, '通信': 22, '建筑装饰': 8, '建筑材料': 22,
        '煤炭': 18, '房地产': 8, '电子': 35, '机械设备': 22,
        '基础化工': 18, '计算机': 35, '传媒': 15, '农林牧渔': 14,
        '国防军工': 28, '有色金属': 25, '钢铁': 6, '纺织服饰': 18,
        '交通运输': 12, '社会服务': 18,
    }
    for code, name, industry, base_p in FALLBACK_STOCKS[:n_stocks]:
        try:
            base_price = INDUSTRY_PRICE.get(industry, 15) * random.uniform(0.5, 2.5)
            base_price = max(min(base_price, 1500), 3)
            if industry in ['电子', '计算机', '电力设备', '国防军工', '机械设备', '传媒', '汽车']:
                trend = random.uniform(0.002, 0.012)
            elif industry in ['银行', '公用事业', '石油石化', '煤炭', '建筑装饰']:
                trend = random.uniform(-0.003, 0.005)
            else:
                trend = random.uniform(-0.005, 0.008)
            days = 120
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            data = []
            price = base_price
            for d in dates:
                change = random.gauss(trend, 0.025)
                price = max(price * (1 + change), 0.5)
                data.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'code': code, 'name': name, 'industry': industry,
                    'open': round(price * 0.995, 2),
                    'high': round(price * 1.015, 2),
                    'low': round(price * 0.985, 2),
                    'close': round(price, 2),
                    'volume': int(random.uniform(1e6, 1e8)),
                    'pct_change': round(change * 100, 2),
                })
            kline_dict[code] = (pd.DataFrame(data), industry)
        except Exception:
            continue
    return kline_dict


def compute_all_signals(kline_dict, top_n=20):
    trend_set = set()
    factor_list = []
    industry_groups = {}

    for code, (df, ind) in kline_dict.items():
        if df is None or len(df) < 60:
            continue
        try:
            last = df.iloc[-1]
            prev = df.iloc[-5]
            ma20 = df['close'].iloc[-20:].mean()
            ma60 = df['close'].iloc[-60:].mean()
            if (last['close'] > ma20 and ma20 > ma60 and last['close'] > prev['close']):
                trend_set.add(code)
            ret_20 = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
            vol = df['pct_change'].std()
            score = 50 + ret_20 * 1.5 - vol * 2
            factor_list.append((code, score))
            industry_groups.setdefault(ind, []).append((code, ret_20))
        except Exception:
            continue

    factor_list.sort(key=lambda x: -x[1])
    factor_set = set(c for c, _ in factor_list[:top_n])
    rotation_set = set()
    for ind, lst in industry_groups.items():
        if lst:
            best = max(lst, key=lambda x: x[1])
            if best[1] > 0:
                rotation_set.add(best[0])
    all_three = trend_set & rotation_set & factor_set

    def make_detail(code_set):
        rows = []
        for code in code_set:
            df, ind = kline_dict[code]
            if df is None or len(df) == 0:
                continue
            last = df.iloc[-1]
            ret_20 = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
            vol = df['pct_change'].std()
            score = 50 + ret_20 * 1.5 - vol * 2
            rows.append({
                '代码': str(code), '名称': str(last['name']),
                '行业': ind, '现价': round(float(last['close']), 2),
                '今日%': round(float(last['pct_change']), 2),
                '20日%': round(ret_20, 2), '波动率': round(vol, 2),
                '综合分': round(score, 2),
            })
        return pd.DataFrame(rows).sort_values('综合分', ascending=False) if rows else pd.DataFrame()

    return {
        'trend': (trend_set, make_detail(trend_set)),
        'rotation': (rotation_set, make_detail(rotation_set)),
        'factors': (factor_set, make_detail(factor_set)),
        'all_three': (all_three, make_detail(all_three)),
    }


with st.sidebar:
    st.header("⚙️ 参数设置")
    n_stocks = st.slider("扫描股票数", 30, 5500, 200, 10, help="Tushare 数据建议 500 以内")
    top_n = st.slider("Top N", 5, 50, 20, 5)
    st.divider()
    st.subheader("🎯 策略开关")
    use_trend = st.checkbox("趋势策略", value=True)
    use_rotation = st.checkbox("行业轮动", value=True)
    use_factors = st.checkbox("多因子", value=True)
    st.divider()
    st.subheader("💎 精选模式")
    only_all_three = st.checkbox("🎯 只看三策略都通过", value=False)
    st.divider()
    run = st.button("🚀 运行分析", type="primary", use_container_width=True)

st.markdown("""
## 👋 欢迎使用 Vibe 量化系统 v2.0

### 🎯 系统能力
- **🔥 趋势策略**：均线多头 + 量价齐升
- **🔄 行业轮动**：强势行业龙头
- **📊 多因子选股**：动量+波动率综合
- **💎 三策略精选**：取三策略交集，**最强信号**！

### 💡 数据源
- **优先**：Tushare 真实数据（每天 17:00 自动更新）
- **降级**：内置 50 只核心股（万一 Tushare 失败）

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
""")


@st.cache_data(ttl=3600)
def load_all_data(n_stocks):
    df_stocks, df_klines, source = load_tushare_data()
    if df_stocks is not None and df_klines is not None and len(df_klines) > 0:
        kline_dict = {}
        codes = df_stocks['code'].astype(str).str.zfill(6).head(n_stocks).tolist()
        for code in codes:
            df_sub = df_klines[df_klines['code'].astype(str).str.zfill(6) == code]
            if not df_sub.empty:
                df_sub = df_sub.sort_values('date').reset_index(drop=True)
                row = df_stocks[df_stocks['code'].astype(str).str.zfill(6) == code]
                ind = row['industry'].iloc[0] if not row.empty and 'industry' in row.columns else '未分类'
                name = row['name'].iloc[0] if not row.empty and 'name' in row.columns else code
                df_sub['name'] = name
                kline_dict[code] = (df_sub, ind)
        return kline_dict, source, len(df_stocks)
    else:
        return generate_fallback_klines(n_stocks), source, 50


if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📊 加载数据...")
        progress.progress(20)
        kline_dict, data_source, total_stocks = load_all_data(n_stocks)
        if not kline_dict:
            st.error("❌ 加载数据失败")
            st.stop()
        st.info(f"📊 数据源：**{data_source}** | 股票池：{total_stocks} 只 | 实际加载：{len(kline_dict)} 只")
        status.text("🔍 计算三策略信号...")
        progress.progress(60)
        results = compute_all_signals(kline_dict, top_n=top_n)
        progress.progress(100)
        status.text("✅ 分析完成！")
        progress.empty()
        status.empty()

        if only_all_three:
            st.header("💎 三策略精选（最强信号）")
            codes, df = results['all_three']
            if not df.empty:
                st.success(f"🎯 找到 {len(codes)} 只三策略都通过的股票！")
                st.dataframe(df, use_container_width=True, hide_index=True)
                with st.expander("📊 详细评分"):
                    for _, row in df.iterrows():
                        st.markdown(f"**{row['代码']} {row['名称']}** ({row['行业']})")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("现价", f"{row['现价']}")
                        c2.metric("今日%", f"{row['今日%']}%")
                        c3.metric("20日%", f"{row['20日%']}%")
                        c4.metric("综合分", f"{row['综合分']}")
            else:
                st.warning("📭 三策略无交集")
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("🔥 趋势", len(results['trend'][0]))
            c2.metric("🔄 行业轮动", len(results['rotation'][0]))
            c3.metric("📊 多因子", len(results['factors'][0]))
        else:
            total_signals = 0
            if use_trend: total_signals += len(results['trend'][0])
            if use_rotation: total_signals += len(results['rotation'][0])
            if use_factors: total_signals += len(results['factors'][0])
            st.success(f"🎉 已扫描 {len(kline_dict)} 只，触发 {total_signals} 条信号")
            codes, df = results['all_three']
            if not df.empty:
                st.header("💎 三策略精选（最强信号）")
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"💎 三策略交集（共 {len(codes)} 只）")
                st.divider()
            if use_trend:
                st.header("🔥 趋势策略信号")
                _, df = results['trend']
                if not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("📭 无信号")
            if use_rotation:
                st.header("🔄 行业轮动信号")
                _, df = results['rotation']
                if not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("📭 无信号")
            if use_factors:
                st.header("📊 多因子精选")
                _, df = results['factors']
                if not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("📭 无信号")
    except Exception as e:
        st.error(f"❌ 运行出错: {e}")
        import traceback
        st.code(traceback.format_exc())

st.divider()
st.caption(f"Vibe 量化 v2.0 | 数据：Tushare 真实 + 内置降级 | {datetime.now().strftime('%Y-%m-%d')}")
