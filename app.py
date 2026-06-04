"""Vibe 量化系统 - Streamlit 主界面（带清缓存按钮）"""
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import create_vibe

st.set_page_config(
    page_title="Vibe 量化 v1.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v1.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：AKShare + 降级数据")

with st.sidebar:
    st.header("⚙️ 参数设置")
    n_stocks = st.slider("扫描股票数", 10, 50, 20, 5, help="首次使用建议10-20")
    top_n = st.slider("Top N", 3, 20, 5, 1)
    st.divider()
    st.subheader("🎯 策略开关")
    use_trend = st.checkbox("趋势策略", value=True)
    use_rotation = st.checkbox("行业轮动", value=True)
    use_factors = st.checkbox("多因子", value=True)
    st.divider()
    if st.button("🚀 运行分析", type="primary", use_container_width=True):
        st.session_state.run = True
    st.divider()
    if st.button("🔄 清除缓存并重启", use_container_width=True, help="如果数据出错点这个"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()

@st.cache_resource(show_spinner=False)
def get_vibe():
    try:
        return create_vibe("config.yaml")
    except Exception as e:
        st.error(f"初始化失败: {e}")
        return None

vibe = get_vibe()
if vibe is None:
    st.stop()

if st.session_state.get('run', False):
    progress_bar = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📊 加载数据中...")
        progress_bar.progress(20)
        kline_data = vibe.load_data(n_stocks=n_stocks, min_market_cap=0)
        progress_bar.progress(50)
        if not kline_data or len(kline_data) == 0:
            st.error("❌ 未能获取到任何股票数据，请点击左侧 🔄 清除缓存并重启")
            st.stop()
        status.text("🏭 加载行业分类中...")
        industry_map = vibe.get_industry_map()
        progress_bar.progress(70)
        results = {}
        if use_trend:
            status.text("🔥 扫描趋势信号...")
            results['trend'] = vibe.run_trend_scan(kline_data, top_n=top_n)
        if use_rotation:
            status.text("🔄 扫描行业轮动...")
            results['rotation'] = vibe.run_rotation_scan(kline_data, industry_map)
        if use_factors:
            status.text("📊 计算多因子...")
            results['factors'] = vibe.run_factor_scan(kline_data)
        progress_bar.progress(100)
        status.text("✅ 分析完成！")
        if use_trend and not results.get('trend', pd.DataFrame()).empty:
            st.header("🔥 趋势策略信号（突破+量能+趋势）")
            st.dataframe(results['trend'], use_container_width=True, hide_index=True)
            st.caption(f"📊 共 {len(results['trend'])} 只股票触发趋势买入信号")
        elif use_trend:
            st.info("📭 今日无趋势策略信号（市场处于震荡或下跌趋势）")
        if use_rotation and not results.get('rotation', pd.DataFrame()).empty:
            st.header("🔄 行业轮动信号（强势行业龙头）")
            st.dataframe(results['rotation'], use_container_width=True, hide_index=True)
        elif use_rotation:
            st.info("📭 今日无行业轮动信号")
        if use_factors and not results.get('factors', pd.DataFrame()).empty:
            st.header("📊 多因子精选（综合Top榜单）")
            st.dataframe(results['factors'], use_container_width=True, hide_index=True)
        elif use_factors:
            st.info("📭 今日无多因子信号")
        st.success("🎉 分析完成！请结合盘面信息做出投资决策。")
    except Exception as e:
        st.error(f"❌ 运行出错: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        progress_bar.empty()
        status.empty()
else:
    st.markdown("""
    ## 👋 欢迎使用 Vibe 量化系统 v1.0
    
    ### 🎯 系统能力
    - **🔥 趋势策略**（主）：海龟交易法则改良版
    - **🔄 行业轮动**（主）：申万一级行业动量排序  
    - **📊 多因子选股**（辅）：价值+质量+成长+动量+低波
    - **⚖️ 智能风控**：单股≤20%、单行业≤30%
    
    ### 🚀 开始使用
    1. 左侧调整 **扫描股票数**（首次建议10-20只）
    2. 勾选你要跑的 **策略**
    3. 点击 **🚀 运行分析** 按钮
    
    ### 💡 数据源说明
    - 主数据源：**AKShare**（免费A股数据）
    - 降级数据：**模拟K线**（网络异常时启用）
    
    ### ⚠️ 风险提示
    > 本系统仅供学习研究，不构成投资建议。
    > 投资有风险，决策需谨慎。
    """)

st.divider()
st.caption("Vibe 量化 v1.0 | 数据：AKShare + 模拟 | 仅供学习研究")
