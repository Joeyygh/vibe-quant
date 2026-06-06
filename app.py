"""Vibe 量化 v2.0 - 持仓管理 + 行业筛选"""
import streamlit as st
import pandas as pd
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
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：Tushare 真实数据")


# ========== 持仓管理 ==========
HOLDINGS_FILE = 'my_holdings.json'

def load_holdings():
    """从 GitHub 加载持仓"""
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_holdings(holdings):
    """保存到 GitHub"""
    try:
        with open(HOLDINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(holdings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False

def load_tushare_data():
    if not os.path.exists('data/stock_list.csv'):
        return None, None
    if not os.path.exists('data/klines.parquet'):
        return None, None
    try:
        df_stocks = pd.read_csv('data/stock_list.csv', dtype={'code': str})
        df_stocks['code'] = df_stocks['code'].astype(str).str.zfill(6)
        df_stocks['industry'] = df_stocks['industry'].astype(str).fillna('未分类')
        df_stocks = df_stocks[df_stocks['industry'].notna() & (df_stocks['industry'] != '') & (df_stocks['industry'] != 'nan')]
        
        df_klines = pd.read_parquet('data/klines.parquet')
        df_klines = df_klines.loc[:, ~df_klines.columns.duplicated()]
        df_klines['code'] = df_klines['code'].astype(str).str.zfill(6)
        if 'industry' in df_klines.columns:
            df_klines['industry'] = df_klines['industry'].astype(str).fillna('未分类')
        return df_stocks, df_klines
    except Exception as e:
        st.error(f"数据加载失败: {e}")
        return None, None


def compute_signals(df_klines, top_n=20):
    trend_set = set()
    factor_list = []
    industry_groups = {}
    for code in df_klines['code'].unique():
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
            ind = str(last.get('industry', '未分类'))
            industry_groups.setdefault(ind, []).append((code, ret_20))
        except Exception:
            continue
    factor_list.sort(key=lambda x: -x[1])
    factor_set = set(c for c, _ in factor_list[:top_n])
    rotation_set = set()
    for ind, lst in industry_groups.items():
        if lst and ind != 'nan' and ind != '':
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


# ========== 主流程 ==========
df_stocks, df_klines = load_tushare_data()

if df_stocks is None:
    st.error("❌ data 文件不存在！请确保 GitHub Actions 跑成功过")
    st.stop()

industries_options = ['全部'] + sorted(df_stocks['industry'].unique().tolist())
holdings = load_holdings()

with st.sidebar:
    st.header("⚙️ 参数设置")
    st.info(f"📊 共 {len(industries_options) - 1} 个行业，{len(df_stocks)} 只股")
    
    # ========== 持仓管理 UI ==========
    with st.expander("🎯 我的持仓管理", expanded=False):
        st.write(f"当前持仓: **{len(holdings)} 只**")
        
        if holdings:
            st.write("--- 当前持仓 ---")
            for i, h in enumerate(holdings):
                col1, col2 = st.columns([3, 1])
                col1.write(f"{h.get('code', '')} {h.get('name', '')}")
                if col2.button("🗑", key=f"del_{i}"):
                    holdings.pop(i)
                    save_holdings(holdings)
                    st.rerun()
        
        st.write("--- 添加持仓 ---")
        new_code = st.text_input("股票代码（6 位）", key="new_code", placeholder="如 600519")
        if st.button("➕ 添加", key="add_btn"):
            new_code = new_code.strip()
            if len(new_code) == 6 and new_code.isdigit():
                match = df_stocks[df_stocks['code'] == new_code]
                if not match.empty:
                    name = match.iloc[0]['name']
                    industry = match.iloc[0]['industry']
                    if not any(h.get('code') == new_code for h in holdings):
                        holdings.append({'code': new_code, 'name': name, 'industry': industry})
                        save_holdings(holdings)
                        st.success(f"已添加 {new_code} {name}")
                        st.rerun()
                    else:
                        st.warning("已在持仓中")
                else:
                    st.error("代码不存在")
            else:
                st.error("请输入 6 位代码")
        
        st.write("--- 批量导入（粘贴代码） ---")
        bulk_text = st.text_area("每行一个代码", height=100, placeholder="600519\n000001\n300750")
        if st.button("📥 批量导入", key="bulk_btn"):
            new_codes = [c.strip() for c in bulk_text.split('\n') if c.strip()]
            added = 0
            for nc in new_codes:
                if len(nc) == 6 and nc.isdigit() and not any(h.get('code') == nc for h in holdings):
                    match = df_stocks[df_stocks['code'] == nc]
                    if not match.empty:
                        holdings.append({
                            'code': nc,
                            'name': match.iloc[0]['name'],
                            'industry': match.iloc[0]['industry']
                        })
                        added += 1
            if added:
                save_holdings(holdings)
                st.success(f"已添加 {added} 只")
                st.rerun()
    
    st.divider()
    
    scan_mode = st.radio(
        "📊 扫描模式",
        ["行业筛选", "我的持仓"],
        help="选'行业筛选'看全市场/特定行业；选'我的持仓'看自己的股"
    )
    
    if scan_mode == "行业筛选":
        selected_industry = st.selectbox("🏭 行业筛选", industries_options, index=0)
        n_stocks = st.slider("扫描股票数", 10, 500, 200, 10)
    else:
        if not holdings:
            st.warning("⚠️ 还没有持仓，请先在 '🎯 我的持仓管理' 里添加")
            n_stocks = 0
        else:
            st.info(f"📊 持仓 {len(holdings)} 只，全部扫描")
            n_stocks = len(holdings)
        selected_industry = None
    
    top_n = st.slider("Top N", 5, 50, 10, 1, help="多因子策略显示前 N 名")
    st.divider()
    st.subheader("🎯 策略开关")
    use_trend = st.checkbox("趋势策略", value=True)
    use_rotation = st.checkbox("行业轮动", value=True)
    use_factors = st.checkbox("多因子", value=True)
    st.divider()
    only_all_three = st.checkbox("🎯 只看三策略都通过", value=False)
    st.divider()
    run = st.button("🚀 运行分析", type="primary", use_container_width=True)

st.markdown("""
## 👋 欢迎使用 Vibe 量化系统 v2.0

### 🎯 三策略
- **🔥 趋势策略**：均线多头 + 量价齐升
- **🔄 行业轮动**：强势行业龙头
- **📊 多因子选股**：动量+波动率综合
- **💎 三策略精选**：取三策略交集，**最强信号**！

### 🎯 我的持仓
- **侧边栏 "🎯 我的持仓管理"** 添加/删除持仓
- **扫描模式选"我的持仓"** 专门分析你的股

### 💡 数据源
- **真实 Tushare 数据**（每天 17:00 自动更新）
- **GitHub Actions 自动维护**
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        if scan_mode == "我的持仓" and not holdings:
            st.error("请先在侧边栏添加持仓股")
            st.stop()
        
        status.text("🎯 应用筛选...")
        progress.progress(30)
        
        if scan_mode == "我的持仓":
            codes = [h['code'] for h in holdings]
            codes = [str(c).zfill(6) for c in codes]
            filter_msg = f"我的持仓，{len(codes)} 只"
        elif selected_industry == '全部':
            codes = df_stocks['code'].head(n_stocks).tolist()
            filter_msg = f"全部行业，前 {n_stocks} 只"
        else:
            codes = df_stocks[df_stocks['industry'] == selected_industry]['code'].head(n_stocks).tolist()
            filter_msg = f"行业「{selected_industry}」，{len(codes)} 只"
        
        df_sub = df_klines[df_klines['code'].isin(codes)].copy()
        del df_klines
        st.info(f"✅ 扫描 {filter_msg}，{len(df_sub)} 条 K 线")
        
        status.text("🔍 计算三策略...")
        progress.progress(70)
        results = compute_signals(df_sub, top_n=top_n)
        del df_sub
        
        progress.progress(100)
        status.text("✅ 完成！")
        progress.empty()
        status.empty()
        
        st.success(f"🎉 {filter_msg}，三策略信号已出")
        
        codes, df = results['all_three']
        if not df.empty:
            st.header("💎 三策略精选（最强信号）")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.divider()
        
        if use_trend:
            st.header("🔥 趋势策略")
            _, df = results['trend']
            if not df.empty: st.dataframe(df, use_container_width=True, hide_index=True)
            else: st.info("📭 无信号")
        if use_rotation:
            st.header("🔄 行业轮动")
            _, df = results['rotation']
            if not df.empty: st.dataframe(df, use_container_width=True, hide_index=True)
            else: st.info("📭 无信号")
        if use_factors:
            st.header("📊 多因子")
            _, df = results['factors']
            if not df.empty: st.dataframe(df, use_container_width=True, hide_index=True)
            else: st.info("📭 无信号")
    except Exception as e:
        st.error(f"❌ 出错: {e}")
        import traceback
        st.code(traceback.format_exc())

st.divider()
st.caption(f"Vibe 量化 v2.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
