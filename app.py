"""Vibe 量化 v2.0 - 持仓管理 + 行业筛选 + 7条件 + 5过滤"""
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


HOLDINGS_FILE = 'my_holdings.json'

def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_holdings(holdings):
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


def apply_extra_filters(df_sub):
    """5 个额外过滤条件"""
    if len(df_sub) < 14:
        return False
    last = df_sub.iloc[-1]
    ret_10d = (float(df_sub['close'].iloc[-1]) / float(df_sub['close'].iloc[-11]) - 1) * 100
    if ret_10d > 20:
        return False
    vol_today = float(last['volume'])
    vol_5day = df_sub['volume'].iloc[-5:].mean()
    if vol_5day <= 0 or vol_today / vol_5day < 0.8:
        return False
    diff_close = df_sub['close'].diff()
    gain = diff_close.where(diff_close > 0, 0).rolling(14).mean()
    loss = (-diff_close.where(diff_close < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_today = float(rsi.iloc[-1]) if not rsi.empty else 50
    if rsi_today > 75:
        return False
    close = df_sub['close']
    ema_fast = close.ewm(span=12, adjust=
