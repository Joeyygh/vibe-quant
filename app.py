"""Vibe 量化系统 - Streamlit 主界面"""
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
    layout="wide"
)

st.title("📊 Vibe 股票量化分析 v1.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：AKShare")

with st.sidebar:
    st.header("⚙️ 参数设置")
    n_stocks = st.slider("扫描股票数", 30, 200, 80, 10)
    top_n = st.slider("Top N", 5, 30, 10)
    use_trend = st.checkbox("趋势策略", value=True)
    use_rotation = st.checkbox("行业轮动", value=True)
    use_factors = st.checkbox("多因子", value=True)
    if st.button("🚀 运行分析", type="primary", use_container_width=True):
        st.session_state.run = True

@st.cache_resource
def get_vibe():
    return create_vibe("config.yaml")

try:
    vibe = get_vibe()
except Exception as e:
    st.error(f"初始化失败: {e}")
    st.stop()

if st.session_state.get('run', False):
    with st.spinner("正在分析..."):
        try:
            kline_data = vibe.load_data(n_stocks=n_stocks)
            industry_map = vibe.get_industry_map()
            results = vibe.run_all(kline_data, industry_map)
        except Exception as e:
            st.error(f"运行失败: {e}")
            st.stop()
    if use_trend and not results.get('trend', pd.DataFrame()).empty:
        st.header("🔥 趋势策略信号")
        st.dataframe(results['trend'], use_container_width=True)
    if use_rotation and not results.get('rotation', pd.DataFrame()).empty:
        st.header("🔄 行业轮动信号")
        st.dataframe(results['rotation'], use_container_width=True)
    if use_factors and not results.get('factors', pd.DataFrame()).empty:
        st.header("📊 多因子精选")
        st.dataframe(results['factors'], use_container_width=True)
else:
    st.markdown("## 👋 欢迎使用\n左侧调整参数，点击 🚀 运行分析。\n\n⚠️ 本系统仅供学习研究，不构成投资建议。")

st.divider()
st.caption("Vibe 量化 v1.0 | 数据：AKShare")
