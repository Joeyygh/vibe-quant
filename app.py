"""Vibe 量化系统 v2.0 - Tushare 真实数据 + 行业筛选（避免 OOM）"""
import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(
    page_title="Vibe 量化 v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v2.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：Tushare 真实数据（GitHub Actions 自动更新）")


@st.cache_data(ttl=3600, show_spinner="加载 Tushare 真实数据...")
def load_tushare_data():
    if not os.path.exists('data/stock_list.csv'):
        return None, None, "data 文件不存在"
    if not os.path.exists('data/klines.parquet'):
        return None, None, "klines 文件不存在"
    try:
        df_stocks = pd.read_csv('data/stock_list.csv', usecols=['code', 'name', 'industry'])
        df_stocks['code'] = df_stocks['code'].astype(str).str.zfill(6)
        df_stocks['industry'] = df_stocks['industry'].astype(str).fillna('未分类')
        df_klines = pd.read_parquet('data/klines.parquet', columns=['date', 'code', 'name', 'industry', 'open', 'close', 'high', 'low', 'volume', 'pct_change'])
        df_klines['code'] = df_klines['code'].astype(str).str.zfill(6)
        return df_stocks, df_klines, f"已加载 {len(df_stocks)} 只股，{len(df_klines)} 条 K 线"
    except Exception as e:
        return None, None, f"加载失败: {e}"


def compute_all_signals_streaming(df_klines, top_n=20):
    trend_set = set()
    factor_list = []
    industry_groups = {}
    codes = df_klines['code'].unique()
    for code in codes:
        try:
            df = df_klines[df_klines['code'] == code].sort_values('date')
            if len(df) < 60:
                continue
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
            ind = last.get('industry', '未分类')
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
            df_sub = df_klines[df_klines['code'] == code].sort_values('date')
            if df_sub.empty:
                continue
            last = df_sub.iloc[-1]
            ret_20 = (last['close'] / df_sub['close'].iloc[-20] - 1) * 100
            vol = df_sub['pct_change'].std()
            score = 50 + ret_20 * 1.5 - vol * 2
            rows.append({
                '代码': str(code),
                '名称': str(last.get('name', code)),
                '行业': str(last.get('industry', '未分类')),
                '现价': round(float(last['close']), 2),
                '今日%': round(float(last['pct_change']), 2),
                '20日%': round(ret_20, 2),
                '波动率': round(vol, 2),
                '综合分': round(score, 2),
            })
        return pd.DataFrame(rows).sort_values('综合分', ascending=False) if rows else pd.DataFrame()

    return {
        'trend': (trend_set, make_detail(trend_set)),
        'rotation': (rotation_set, make_detail(rotation_set)),
        'factors': (factor_set, make_detail(factor_set)),
        'all_three': (all_three, make_detail(all_three)),
    }


# 关键：先加载数据，再渲染侧边栏
df_stocks, df_klines, load_info = load_tushare_data()

if df_stocks is not None:
    all_industries = sorted(df_stocks['industry'].unique().tolist())
    industries_options = ['全部'] + all_industries
else:
    industries_options = ['全部']

with st.sidebar:
    st.header("⚙️ 参数设置")
    selected_industry = st.selectbox("🏭 行业筛选", industries_options, index=0, help=f"共 {len(industries_options) - 1} 个行业可选")
    if selected_industry == '全部':
        n_stocks = st.slider("扫描股票数", 50, 500, 200, 50, help="建议 ≤ 300")
    else:
        n_stocks = st.slider("扫描股票数", 10, 300, 100, 10)
    top_n = st.slider("Top N", 5, 30, 10, 1)
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
- **真实 Tushare 数据**（每天 17:00 自动更新）
- **GitHub Actions 自动维护**（0 人工干预）

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📊 加载 Tushare 真实数据...")
        progress.progress(20)
        if df_stocks is None or df_klines is None:
            st.error(f"❌ {load_info}")
            st.info("💡 提示：请确保 GitHub Actions 已成功跑过一次（生成 data/ 目录）")
            st.stop()
        st.info(f"📊 {load_info}")
        
        status.text("🎯 应用行业筛选...")
        progress.progress(40)
        if selected_industry == '全部':
            codes = df_stocks['code'].head(n_stocks).tolist()
            filter_msg = f"全部行业，前 {n_stocks} 只"
        else:
            codes = df_stocks[df_stocks['industry'] == selected_industry]['code'].head(n_stocks).tolist()
            filter_msg = f"行业「{selected_industry}」，{len(codes)} 只"
        
        df_sub = df_klines[df_klines['code'].isin(codes)].copy()
        del df_klines
        st.info(f"✅ 扫描 {filter_msg}，{len(df_sub)} 条 K 线")
        
        status.text("🔍 计算三策略信号...")
        progress.progress(70)
        results = compute_all_signals_streaming(df_sub, top_n=top_n)
        del df_sub
        
        progress.progress(100)
        status.text("✅ 分析完成！")
        progress.empty()
        status.empty()
        
        if only_all_three:
            st.header(f"💎 三策略精选（{filter_msg}）")
            codes, df = results['all_three']
            if not df.empty:
                st.success(f"🎯 找到 {len(codes)} 只三策略都通过的股票！")
                st.dataframe(df, use_container_width=True, hide_index=True)
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
            st.success(f"🎉 {filter_msg}，触发 {total_signals} 条信号")
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
st.caption(f"Vibe 量化 v2.0 | Tushare 真实数据 | {datetime.now().strftime('%Y-%m-%d')}")
