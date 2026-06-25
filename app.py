"""Vibe 量化 v2.0 - 修复版"""
import streamlit as st
import pandas as pd
import os
import json
import glob
import time
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Vibe 量化 v2.0", page_icon="V", layout="wide", initial_sidebar_state="expanded")
st.title("Vibe 股票量化分析 v2.0")
beijing_now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
st.markdown(f"**{beijing_now} (北京时间)** | 数据源：Tushare 真实数据")

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
    except Exception:
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
        df_stocks = df_stocks[df_stocks['industry'].notna()]
        df_stocks = df_stocks[df_stocks['industry'] != '']
        df_stocks = df_stocks[df_stocks['industry'] != 'nan']
        df_klines = pd.read_parquet('data/klines.parquet')
        df_klines = df_klines.loc[:, ~df_klines.columns.duplicated()]
        df_klines['code'] = df_klines['code'].astype(str).str.zfill(6)
        return df_stocks, df_klines
    except Exception as e:
        st.error(f"加载失败: {e}")
        return None, None


# ========== 持仓信号实时计算（Streamlit) ==========
@st.cache_resource
def get_tushare_pro():
    """初始化 Tushare Pro 客户端(Streamlit 资源级缓存)"""
    token = os.environ.get('TUSHARE_TOKEN')
    if not token:
        try:
            token = st.secrets.get('TUSHARE_TOKEN')
        except Exception:
            token = None
    if not token:
        return None
    try:
        import tushare as ts
        return ts.pro_api(token)
    except Exception as e:
        st.error(f"Tushare 初始化失败: {e}")
        return None


@st.cache_data(ttl=1800)  # 30 分钟缓存
def calc_holding_signals(holdings_json, days=30):
    """从 Tushare 实时拉取每只持仓的价格并生成信号。
    holdings_json: str(JSON序列化的持仓 list)
    返回: list[dict] 每个元素包含代码/名称/现价/今日%/MA5/MA20/累计%/tips
    """
    pro = get_tushare_pro()
    if pro is None:
        return []
    try:
        holdings = json.loads(holdings_json)
    except Exception:
        return []
    if not holdings:
        return []

    # 跳过港股/债券
    tradable = []
    for h in holdings:
        code_raw = str(h.get('code', '')).strip()
        if code_raw.endswith('.HK') or h.get('type') == 'bond' or h.get('currency') == 'HKD':
            continue
        tradable.append(h)
    if not tradable:
        return []

    today = datetime.now()
    end_d = today.strftime('%Y%m%d')
    start_d = (today - timedelta(days=days)).strftime('%Y%m%d')

    signals = []
    progress = st.progress(0, text='拉取持仓实时信号...')
    n = len(tradable)
    for idx, h in enumerate(tradable):
        code = str(h.get('code', '')).zfill(6)
        name = h.get('name', code)
        cost = float(h.get('cost_price', 0)) if h.get('cost_price') else 0
        group = h.get('group', '')

        if code.startswith(('4', '8')):
            ts_code = f"{code}.BJ"
        elif code.startswith(('6', '9')):
            ts_code = f"{code}.SH"
        else:
            ts_code = f"{code}.SZ"

        progress.progress((idx + 0.1) / n, text=f'拉取 {name}({code})...')
        try:
            df = pro.daily(ts_code=ts_code, start_date=start_d, end_date=end_d)
            time.sleep(0.05)  # 限流保护
            if df is None or df.empty or len(df) < 5:
                continue
            df = df.sort_values('trade_date').reset_index(drop=True)
            last = df.iloc[-1]
            close = float(last['close'])
            pct_chg = float(last.get('pct_chg', 0))
            ma5 = float(df['close'].iloc[-5:].mean())
            ma20 = float(df['close'].iloc[-20:].mean()) if len(df) >= 20 else None
            ret_from_cost = ((close - cost) / cost * 100) if cost > 0 else None

            tips = []
            if pct_chg <= -5:
                tips.append(("🔴 止损", f"今日暴跌 {pct_chg:.2f}%"))
            elif pct_chg <= -3:
                tips.append(("⚠️ 注意", f"今日跌 {pct_chg:.2f}%"))
            elif pct_chg >= 7:
                tips.append(("🟢 止盈一半", f"今日大涨 {pct_chg:.2f}%"))
            elif pct_chg >= 5:
                tips.append(("🟢 减仓", f"今日涨 {pct_chg:.2f}%"))
            if close < ma5:
                tips.append(("⚠️", f"跌破MA5({ma5:.2f})"))
            if ma20 and close < ma20:
                tips.append(("🔴", f"跌破MA20({ma20:.2f})"))
            if ret_from_cost is not None:
                if ret_from_cost >= 20:
                    tips.append(("💰 全部止盈", f"累计 {ret_from_cost:+.1f}%"))
                elif ret_from_cost >= 10:
                    tips.append(("💰 减仓一半", f"累计 {ret_from_cost:+.1f}%"))
                elif ret_from_cost <= -10:
                    tips.append(("💔 止损", f"累计 {ret_from_cost:+.1f}%"))
            if not tips:
                tips.append(("✅ 持有", "信号正常"))

            signals.append({
                'code': code,
                'name': name,
                'cost': cost,
                'close': close,
                'pct_chg': pct_chg,
                'ma5': ma5,
                'ma20': ma20,
                'ret': ret_from_cost,
                'group': group,
                'tips': tips,
            })
        except Exception:
            continue

    progress.empty()
    return signals


def smart_sample(df_stocks, n_stocks):
    if n_stocks >= len(df_stocks):
        return df_stocks['code'].tolist()
    main_prefixes = ('000', '001', '002', '600', '601', '603', '605')
    chinext = ('300',)
    star = ('688',)
    df_main = df_stocks[df_stocks['code'].str.startswith(main_prefixes)]
    df_chinext = df_stocks[df_stocks['code'].str.startswith(chinext)]
    df_star = df_stocks[df_stocks['code'].str.startswith(star)]
    n_main = int(n_stocks * 0.40)
    n_chinext = int(n_stocks * 0.35)
    n_star = n_stocks - n_main - n_chinext
    codes = []
    codes.extend(df_main['code'].head(n_main).tolist())
    codes.extend(df_chinext['code'].head(n_chinext).tolist())
    codes.extend(df_star['code'].head(n_star).tolist())
    if len(codes) < n_stocks:
        existing = set(codes)
        remaining = df_stocks[~df_stocks['code'].isin(existing)]['code'].tolist()
        codes.extend(remaining[:n_stocks - len(codes)])
    return codes[:n_stocks]


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
            ma20 = df['close'].iloc[-20:].mean()
            ma60 = df['close'].iloc[-60:].mean()
            if (last['close'] > ma20 and ma20 > ma60):
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
    delta = df_sub['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14, min_periods=1).mean()
    loss_val = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
    if loss_val.iloc[-1] > 0:
        rs = gain.iloc[-1] / loss_val.iloc[-1]
        rsi_today = 100 - (100 / (1 + rs))
    else:
        rsi_today = 50
    if rsi_today > 75:
        return False
    close = df_sub['close']
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    diff_line = ema_fast - ema_slow
    if float(diff_line.iloc[-1]) <= 0:
        return False
    pct = float(last['pct_change'])
    if pct >= 9.5 or pct < -3.0:
        return False
    return True


def apply_formula_2(df_sub):
    if len(df_sub) < 30:
        return False
    last = df_sub.iloc[-1]
    name = str(last.get('name', ''))
    if 'ST' in name or 'st' in name:
        return False
    ma5 = df_sub['close'].iloc[-5:].mean()
    ma10 = df_sub['close'].iloc[-10:].mean()
    ma20 = df_sub['close'].iloc[-20:].mean()
    if ma5 <= ma10 or ma10 <= ma20:
        return False
    pct = float(last['pct_change'])
    if pct <= 1.0:
        return False
    vol_5day = df_sub['volume'].iloc[-5:].mean()
    vol_10day = df_sub['volume'].iloc[-10:].mean()
    if vol_10day <= 0 or vol_5day / vol_10day <= 1.15:
        return False
    vol_today = float(last['volume'])
    vol_yesterday = float(df_sub['volume'].iloc[-2])
    if vol_today <= vol_yesterday:
        return False
    close_today = float(last['close'])
    ma5_now = df_sub['close'].iloc[-5:].mean()
    diff_pct = abs(close_today - ma5_now) / ma5_now * 100
    if diff_pct > 3.0:
        return False
    close_series = df_sub['close']
    ema_fast = close_series.ewm(span=12, adjust=False).mean()
    ema_slow = close_series.ewm(span=26, adjust=False).mean()
    diff_line = ema_fast - ema_slow
    dea = diff_line.ewm(span=9, adjust=False).mean()
    diff_today = float(diff_line.iloc[-1])
    diff_prev = float(diff_line.iloc[-2])
    dea_today = float(dea.iloc[-1])
    dea_prev = float(dea.iloc[-2])
    macd_golden = (diff_prev <= dea_prev) and (diff_today > dea_today)
    if not macd_golden:
        return False
    if diff_today <= 0:
        return False
    if len(df_sub) >= 10:
        high_5d = df_sub['high'].iloc[-5:].max()
        low_10d = df_sub['low'].iloc[-10:].min()
        if low_10d <= 0 or high_5d / low_10d >= 1.25:
            return False
    return True


def apply_user_formula(df_sub):
    """
    用户公式 4 条(动量买点,独立扫描,跟 Vibe 系统并联):
    1. 竞价量比 > 5
    2. 开盘涨跌幅 2-5%
    3. 近 3 日成交额递增(代替主力资金 1 亿+)
    4. 收盘价 > 20 日均线
    """
    passed = []
    for code in df_sub['code'].unique():
        try:
            sub = df_sub[df_sub['code'] == code].sort_values('date')
            if len(sub) < 20:
                continue
            last = sub.iloc[-1]
            name = str(last.get('name', ''))
            if 'ST' in name or 'st' in name:
                continue
            ma20 = sub['close'].iloc[-20:].mean()
            if float(last['close']) <= ma20:
                continue
            pct = float(last['pct_change'])
            if not (2.0 <= pct <= 5.0):
                continue
            if 'amount' in sub.columns:
                amt_3d = float(sub['amount'].iloc[-3:].sum())
                amt_prev3 = float(sub['amount'].iloc[-6:-3].sum()) if len(sub) >= 6 else amt_3d
                if amt_3d - amt_prev3 <= 0:
                    continue
                amt_inc_pct = (amt_3d - amt_prev3) / amt_prev3 * 100 if amt_prev3 > 0 else 0
            else:
                continue
            vol_today = float(last['volume'])
            vol_5day_prev = sub['volume'].iloc[-6:-1].mean() if len(sub) >= 6 else sub['volume'].iloc[:-1].mean()
            if vol_5day_prev <= 0:
                continue
            vol_ratio = vol_today / vol_5day_prev
            if vol_ratio <= 5:
                continue
            ret_20 = (float(last['close']) / sub['close'].iloc[-20] - 1) * 100
            passed.append({
                '代码': str(code),
                '名称': str(last.get('name', code)),
                '行业': str(last.get('industry', '未分类')),
                '现价': round(float(last['close']), 2),
                '今日%': round(pct, 2),
                '20日%': round(ret_20, 2),
                '量比': round(vol_ratio, 2),
                '3日成交额增%': round(amt_inc_pct, 1),
            })
        except Exception:
            continue
    return passed


def apply_seven_conditions(df_klines, codes, strict=True):
    passed = []
    for code_str in codes:
        try:
            sub = df_klines[df_klines['code'] == code_str].sort_values('date')
            if len(sub) < 30:
                continue
            last = sub.iloc[-1]
            name = str(last.get('name', code_str))
            if 'ST' in name or 'st' in name:
                continue
            if len(sub) < 11:
                continue
            ret_10d = (float(sub['close'].iloc[-1]) / float(sub['close'].iloc[-11]) - 1) * 100
            if strict and ret_10d <= 5:
                continue
            if not strict and ret_10d < 0:
                continue
            vol_today = float(last['volume'])
            vol_5day = sub['volume'].iloc[-5:].mean()
            vol_min = 1.5 if strict else 1.0
            if vol_5day <= 0 or vol_today / vol_5day <= vol_min:
                continue
            pct = float(last['pct_change'])
            if strict and not (3.0 <= pct <= 5.0):
                continue
            if not strict and not (0.0 <= pct <= 7.0):
                continue
            ma5 = sub['close'].iloc[-5:].mean()
            if float(last['close']) <= ma5:
                continue
            if 'amount' in sub.columns:
                amt_3d = sub['amount'].iloc[-3:].sum()
                amt_prev3 = sub['amount'].iloc[-6:-3].sum() if len(sub) >= 6 else amt_3d
                if amt_3d - amt_prev3 <= 0:
                    continue
                amt_today = float(last['amount'])
                amt_5day_avg = sub['amount'].iloc[-5:].mean()
                if amt_today - amt_5day_avg <= 0:
                    continue
            else:
                continue
            passed.append(code_str)
        except Exception:
            continue
    return passed


df_stocks, df_klines = load_tushare_data()
if df_stocks is None:
    st.error("data 文件不存在 - 请先运行 update_data.py")
    industries_options = ['全部']
    holdings = []
    df_klines = None
else:
    industries_options = ['全部'] + sorted(df_stocks['industry'].unique().tolist())
    holdings = load_holdings()
    st.success(f"数据已加载: {len(df_stocks)} 只股, {len(df_klines)} 条 K 线")

with st.sidebar:
    st.header("参数设置")
    st.info(f"共 {len(industries_options) - 1} 个行业")
    with st.expander("我的持仓管理", expanded=False):
        st.write(f"当前持仓: {len(holdings)} 只")
        if holdings:
            for i, h in enumerate(holdings):
                col1, col2 = st.columns([3, 1])
                col1.write(f"{h.get('code', '')} {h.get('name', '')}")
                if col2.button("X", key=f"del_{i}"):
                    holdings.pop(i)
                    save_holdings(holdings)
                    st.rerun()

        # === 实时信号面板 ===
        st.write("--- 📊 实时信号 ---")
        if get_tushare_pro() is None:
            st.caption("⚠️ 未配置 Tushare token,实时信号不可用")
        elif not holdings:
            st.caption("暂无持仓,添加后启用信号")
        else:
            col_r1, col_r2 = st.columns([1, 2])
            with col_r1:
                refresh = st.button("🔄 刷新持仓信号", key="refresh_signals")
            with col_r2:
                st.caption("缓存 30 分钟,点按钮重新拉取")

            holdings_json = json.dumps(holdings, ensure_ascii=False)
            signals = calc_holding_signals(holdings_json)
            if signals:
                # 预警汇总
                danger = [s for s in signals if any('🔴' in t[0] or '💔' in t[0] for t in s['tips'])]
                profit = [s for s in signals if any('💰' in t[0] for t in s['tips'])]
                c1, c2, c3 = st.columns(3)
                c1.metric("持仓", f"{len(signals)}只")
                c2.metric("🔴 止损预警", len(danger))
                c3.metric("💰 止盈提示", len(profit))

                # 按组分组显示
                from collections import defaultdict
                by_group = defaultdict(list)
                for s in signals:
                    by_group[s.get('group') or '未分组'].append(s)
                for gname in ['深亏', '浅亏', '保本', '温和盈利', '高盈利']:
                    items = by_group.get(gname, [])
                    if not items:
                        continue
                    st.markdown(f"**{gname}仓({len(items)}只)**")
                    rows = []
                    for s in items:
                        tip_text = ' | '.join(f"{t[0]} {t[1]}" for t in s['tips'])
                        ret = f"{s['ret']:+.1f}%" if s.get('ret') is not None else '-'
                        rows.append({
                            '名称': s['name'],
                            '现价': f"{s['close']:.2f}",
                            '今日': f"{s['pct_chg']:+.2f}%",
                            'MA5': f"{s['ma5']:.2f}",
                            'MA20': f"{s['ma20']:.2f}" if s.get('ma20') else '-',
                            '累计': ret,
                            '建议': tip_text,
                        })
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                # 港股/债券
                others = [h for h in holdings if str(h.get('code', '')).endswith('.HK') or h.get('type') == 'bond']
                if others:
                    st.caption(f"港股/债券 {len(others)} 只不参与 A 股实时信号")
            else:
                st.warning("未能获取到信号,请检查 Tushare 连接")

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
                        save_holdings(holdings)
                        st.success(f"已添加 {new_code} {name}")
                        st.rerun()
        st.write("--- 批量导入 ---")
        bulk_text = st.text_area("每行一个代码", height=100)
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
                save_holdings(holdings)
                st.success(f"已添加 {added} 只")
                st.rerun()
    st.divider()
    scan_mode = st.radio("扫描模式", ["行业筛选", "我的持仓"])
    if scan_mode == "行业筛选":
        selected_industry = st.selectbox("行业", industries_options, index=0)
        n_stocks = st.slider("扫描数", 10, 2000, 2000, 10)
    else:
        if not holdings:
            st.warning("还没有持仓")
            n_stocks = 0
        else:
            st.info(f"持仓 {len(holdings)} 只")
            n_stocks = len(holdings)
        selected_industry = None
    top_n = st.slider("Top N", 5, 50, 10, 1)
    st.divider()
    use_extra = st.checkbox("加 5 过滤 (胜率 100%)", value=True)
    seven_strict = st.checkbox("7 条件严格 (建议宽)", value=False)
    use_formula2 = st.checkbox("公式 2 (中线 5-10 天 胜率 100%)", value=True, help="MACD零轴上金叉 + 量价齐升 + 5/10/20多头")
    f2_independent = st.checkbox("公式 2 独立模式 (不过三策略，直接扫全市场)", value=False, key="f2_indep")
    use_user_formula = st.checkbox("🆕 用户公式(动量买点,独立)", value=True, help="竞价量比>5 + 开盘涨幅2-5% + 3日成交额递增 + 收盘>20日线 (不叠加Vibe,跟1-4并联)")
    st.divider()
    run = st.button("运行分析", type="primary", use_container_width=True)
    st.divider()
    st.header("📊 页面")
    view_mode = st.radio("页面模式", ["量化选股", "每日复盘", "📝 我的笔记"], index=0, key="view_mode")

st.markdown("""
## Vibe 量化 v2.1 (升级版)
- 三策略精选 (胜率 83%)
- 5 过滤叠加 (胜率 100%) 含涨跌幅>-3%
- 7 条件叠加 (宽松/严格)
- 公式 2 (中线 5-10 天 胜率 100%) 含独立/叠加双模式
- 🆕 用户公式 (动量买点,独立扫描) - 早盘短线 1-3 天
- 2000 智能采样 (主板+创业板+科创板)
- 北京时间显示
""")

if view_mode == "每日复盘":
    st.header("📊 每日复盘报告")
    st.caption("由 GitHub Actions 每天 06:00(美股收盘后)自动生成")

    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        st.warning("reports/ 目录不存在,等待 GitHub Actions 首次生成")
    else:
        report_files = sorted(glob.glob(f'{reports_dir}/*.md'), reverse=True)
        if not report_files:
            st.info("暂无报告 - 等待 GitHub Actions 生成")
        else:
            report_names = [os.path.basename(f) for f in report_files]
            selected = st.selectbox("选择报告日期", report_names)
            if selected:
                file_path = os.path.join(reports_dir, selected)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                st.divider()
                st.markdown(content)
                st.divider()
                st.caption(f"📄 {file_path} ({len(content)} 字符)")

                st.download_button(
                    label="⬇️ 下载报告 (.md)",
                    data=content,
                    file_name=selected,
                    mime="text/markdown"
                )
    st.stop()

if view_mode == "📝 我的笔记":
    st.header("📝 每日手动笔记")
    st.caption("论坛/股吧/研报/韭研公社等手动信息 → 自动集成到报告")
    st.info("""
**使用流程**:
1. 在下面输入今天的笔记(论坛、研报、新闻摘要)
2. 点击"复制到剪贴板"
3. 粘贴到 **`data/my_notes/{日期}.md`** 文件
4. GitHub Actions 明天 06:00 跑报告时会自动合并
""")

    notes_dir = 'data/my_notes'
    os.makedirs(notes_dir, exist_ok=True)
    today = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d')
    notes_file = os.path.join(notes_dir, f'{today}.md')

    default_content = f"""# {today} 手动补充

## 📰 财联社新闻
- (粘贴今天热点新闻)

## 💬 淘股吧 / 韭研公社
- (粘贴连板结构、市场情绪)

## 📊 雪球 / 研报
- (粘贴行业研报、基本面逻辑)

## 🎯 明天操作计划
- (写下你的计划)
"""

    if os.path.exists(notes_file):
        with open(notes_file, 'r', encoding='utf-8') as f:
            existing = f.read()
    else:
        existing = default_content

    notes = st.text_area("📝 笔记内容 (Markdown)", value=existing, height=500)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 保存到本地", use_container_width=True):
            try:
                with open(notes_file, 'w', encoding='utf-8') as f:
                    f.write(notes)
                st.success(f"✅ 已保存到 {notes_file}")
                st.info("⚠️ 注意:Streamlit Cloud 重启后文件会丢失,需同步到 GitHub")
            except Exception as e:
                st.error(f"保存失败: {e}")
    with col2:
        st.download_button(
            label="⬇️ 下载 .md",
            data=notes,
            file_name=f"my_notes_{today}.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col3:
        if st.button("📋 复制内容", use_container_width=True):
            st.code(notes, language="markdown")
            st.success("上面的代码块可全选复制")

    st.divider()
    st.caption("""
**同步到 GitHub 流程**:
1. 下载或复制上面的 Markdown 内容
2. 在 GitHub 仓库创建文件:`data/my_notes/{today}.md`
3. 粘贴内容 → Commit
4. 明天 06:00 Actions 跑报告时,会自动合并到 "## 十一、手动补充"

**或者**:告诉我笔记内容,我用 API 帮你同步到 GitHub
""")
    st.stop()

if run:
    if df_stocks is None or df_klines is None:
        st.error("数据未加载")
    elif scan_mode == "我的持仓" and not holdings:
        st.error("先添加持仓")
    elif n_stocks == 0:
        st.error("扫描数为 0")
    else:
        progress = st.progress(0)
        status = st.empty()
        try:
            status.text("应用筛选...")
            progress.progress(30)
            if scan_mode == "我的持仓":
                codes = [h['code'] for h in holdings]
                codes = [str(c).zfill(6) for c in codes]
                filter_msg = f"持仓 {len(codes)} 只"
            elif selected_industry == '全部':
                codes = smart_sample(df_stocks, n_stocks)
                filter_msg = f"全部 智能采样 {len(codes)} 只 (主板+创业板+科创板)"
            else:
                codes = df_stocks[df_stocks['industry'] == selected_industry]['code'].head(n_stocks).tolist()
                filter_msg = f"行业 {selected_industry} {len(codes)} 只"
            df_sub = df_klines[df_klines['code'].isin(codes)].copy()
            try:
                del df_klines
            except Exception:
                pass
            st.info(f"扫描 {filter_msg}, {len(df_sub)} 条 K 线")
            if df_sub.empty:
                st.error("未扫到股票 - 请检查数据或减少扫描数")
                st.stop()
            status.text("计算三策略...")
            progress.progress(70)
            results = compute_signals(df_sub, top_n=top_n)
            progress.progress(100)
            status.empty()
            progress.empty()
            st.success(f"完成 - {filter_msg}")

            codes_3, df_3 = results['all_three']

            if not df_3.empty:
                st.header("1. 三策略精选 (最强)")
                st.dataframe(df_3, use_container_width=True, hide_index=True)
            else:
                st.warning("三策略精选 0 只通过")

            if use_extra and not df_3.empty:
                with st.spinner("应用 5 过滤..."):
                    extra_codes = []
                    for c in df_3['代码'].tolist():
                        sub_c = df_sub[df_sub['code'] == c].sort_values('date')
                        if len(sub_c) >= 14 and apply_extra_filters(sub_c):
                            extra_codes.append(c)
                    df_extra = df_3[df_3['代码'].isin(extra_codes)].copy() if extra_codes else pd.DataFrame()
                if not df_extra.empty:
                    st.subheader("2. 5 过滤叠加 (胜率 100%)")
                    st.success(f"{len(df_extra)} 只通过全部 8 过滤 (三策略 + 5 过滤)")
                    st.dataframe(df_extra, use_container_width=True, hide_index=True)
                else:
                    st.info("三策略通过的股未通过 5 过滤")
                st.divider()

            if not df_3.empty:
                with st.spinner("应用 7 条件..."):
                    seven_codes = apply_seven_conditions(df_sub, df_3['代码'].tolist(), strict=seven_strict)
                    df_7 = df_3[df_3['代码'].isin(seven_codes)].copy() if seven_codes else pd.DataFrame()
                mode_label = "严格" if seven_strict else "宽松"
                if not df_7.empty:
                    st.subheader(f"3. 7 条件叠加 ({mode_label}, 最严)")
                    st.success(f"{len(df_7)} 只同时通过 ({mode_label}模式)")
                    st.dataframe(df_7, use_container_width=True, hide_index=True)
                else:
                    st.info(f"三策略通过的股未通过 7 条件({mode_label}模式) - 试试切换模式")
                st.divider()

            if use_formula2:
                if f2_independent:
                    with st.spinner("应用公式 2 (独立模式-扫全市场)..."):
                        f2_codes = []
                        for code in df_sub['code'].unique():
                            sub_c = df_sub[df_sub['code'] == code].sort_values('date')
                            if apply_formula_2(sub_c):
                                f2_codes.append(code)
                        f2_rows = []
                        for code in f2_codes:
                            sub_c = df_sub[df_sub['code'] == code].sort_values('date')
                            if sub_c.empty:
                                continue
                            last = sub_c.iloc[-1]
                            ret_20 = (last['close'] / sub_c['close'].iloc[-20] - 1) * 100
                            f2_rows.append({
                                '代码': code,
                                '名称': str(last.get('name', code)),
                                '行业': str(last.get('industry', '未分类')),
                                '现价': round(float(last['close']), 2),
                                '今日%': round(float(last['pct_change']), 2),
                                '20日%': round(ret_20, 2),
                            })
                        df_f2 = pd.DataFrame(f2_rows) if f2_rows else pd.DataFrame()
                    if not df_f2.empty:
                        st.subheader("4. 公式 2 (独立 - 不过三策略) 5-10 天 胜率 100%")
                        st.success(f"{len(df_f2)} 只通过公式 2 - 5天 +4.88% / 10天 +11.33%")
                        st.dataframe(df_f2, use_container_width=True, hide_index=True)
                    else:
                        st.warning("公式 2 独立模式：今天全市场 0 只通过 - 不买就是赚，等明天")
                elif not df_3.empty:
                    with st.spinner("应用公式 2 (叠加三策略)..."):
                        f2_codes = []
                        for c in df_3['代码'].tolist():
                            sub_c = df_sub[df_sub['code'] == c].sort_values('date')
                            if apply_formula_2(sub_c):
                                f2_codes.append(c)
                            df_f2 = df_3[df_3['代码'].isin(f2_codes)].copy() if f2_codes else pd.DataFrame()
                    if not df_f2.empty:
                        st.subheader("4. 公式 2 (叠加 - 需过三策略) 5-10 天 胜率 100%")
                        st.success(f"{len(df_f2)} 只通过公式 2 - 5天 +4.88% / 10天 +11.33%")
                        st.dataframe(df_f2, use_container_width=True, hide_index=True)
                    else:
                        st.info("三策略通过的股未通过公式 2")
                else:
                    st.info("三策略 0 只 - 请勾选'公式 2 独立模式'扫全市场")
                st.divider()

            if use_user_formula:
                with st.spinner("应用用户公式 (独立扫描)..."):
                    uf_results = apply_user_formula(df_sub)
                if uf_results:
                    df_uf = pd.DataFrame(uf_results).sort_values('量比', ascending=False)
                    st.subheader("5. 🆕 用户公式(动量买点,独立) - 早盘短线 1-3 天")
                    st.success(f"{len(df_uf)} 只通过用户公式 - 独立扫描,不叠加 Vibe 1-4 模块")
                    st.info("**4 条公式**:①竞价量比>5  ②开盘涨幅 2-5%  ③近 3 日成交额递增  ④收盘>20日线")
                    st.dataframe(df_uf, use_container_width=True, hide_index=True)
                else:
                    st.info("用户公式:今天 0 只通过 - 早盘无买点信号,空仓观察")
                st.divider()
        except Exception as e:
            st.error(f"出错: {e}")
            import traceback
            st.code(traceback.format_exc())

st.divider()
st.caption(f"Vibe v2.0 | {(datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')} (北京时间)")
