"""Vibe 量化 v2.0 - 修复版"""
import streamlit as st
import pandas as pd
import os
import json
import glob
import time
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Vibe 量化 v2.0", page_icon="V", layout="wide", initial_sidebar_state="expanded")


# ============ 🔐 密码登录 (Vibe v2.1) ============
def check_password():
    """如果用户没输对密码,显示登录框并停在这里。"""
    if st.session_state.get("password_correct", False):
        return True
    with st.form("login_form"):
        st.markdown("### 🔐 Vibe 量化系统 v2.1")
        st.markdown("**请输入密码访问**")
        password = st.text_input("密码", type="password", placeholder="联系作者获取")
        submitted = st.form_submit_button("🚀 登录", use_container_width=True)
        if submitted:
            try:
                valid_str = st.secrets.get("APP_PASSWORDS", "ygh960805")
                valid = [p.strip() for p in valid_str.split(";") if p.strip()]
            except Exception:
                valid = ["ygh960805"]
            if password in valid:
                st.session_state["password_correct"] = True
                st.session_state["login_time"] = str(datetime.now())
                st.rerun()
            else:
                st.error("❌ 密码错误,请重试")
                st.info("💡 忘记密码请联系作者")
    return False


# 验证密码,不通过就停
if not check_password():
    st.stop()


st.title("Vibe 股票量化分析 v2.0")
beijing_now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
# 动态读 last_update.txt
_update_str = "未知"
for _path in ['data/last_update.txt', '../data/last_update.txt', './last_update.txt']:
    if os.path.exists(_path):
        try:
            with open(_path, 'r') as _f:
                _raw = _f.read().strip()
            # 转 UTC 为北京时间
            _dt = datetime.fromisoformat(_raw)
            _bj = _dt.astimezone(timezone(timedelta(hours=8)))
            _update_str = _bj.strftime('%Y-%m-%d %H:%M')
        except Exception:
            _update_str = _raw[:16].replace('T', ' ')
        break
st.markdown(f"**{beijing_now} (北京时间)** | 数据源：Tushare 真实数据 | 数据更新：**{_update_str}**")

HOLDINGS_FILE = 'my_holdings.json'


def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # 兼容两种结构: 1) list of dict (老格式)  2) {"holdings": [...], "closed_holdings": [...]} (新格式)
            if isinstance(raw, dict):
                holdings = raw.get('holdings', [])
            else:
                holdings = raw
            # 字段归一化: 兼容 cost / cost_price 两种命名
            normalized = []
            for h in holdings:
                if not isinstance(h, dict):
                    continue
                nh = dict(h)
                # cost -> cost_price
                if 'cost_price' not in nh and 'cost' in nh:
                    nh['cost_price'] = nh.pop('cost')
                # current 字段保留
                normalized.append(nh)
            return normalized
        except Exception as e:
            print(f"load_holdings 失败: {e}")
            return []
    return []


def save_holdings(holdings):
    try:
        with open(HOLDINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(holdings, f, ensure_ascii=False, indent=2)
        # 自动推 GitHub(可选,失败不影响本地)
        try:
            with open(HOLDINGS_FILE, 'rb') as fh:
                push_to_github(fh.read(), 'update my_holdings.json from app')
        except Exception:
            pass
        return True
    except Exception:
        return False


def push_to_github(content_bytes, message='update my_holdings.json', filename='my_holdings.json'):
    """推文件到 GitHub(需要 GITHUB_TOKEN secret)"""
    try:
        import base64, urllib.request
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            try:
                token = st.secrets.get('GITHUB_TOKEN')
            except Exception:
                token = None
        if not token:
            return False, '未配置 GITHUB_TOKEN'
        # 拿 SHA
        url = f"https://api.github.com/repos/Joeyygh/vibe-quant/contents/{filename}?ref=main"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "User-Agent": "vibe-quant-app"})
        sha = None
        try:
            with urllib.request.urlopen(req) as r:
                sha = json.loads(r.read())["sha"]
        except Exception:
            pass
        # PUT
        b64 = base64.b64encode(content_bytes).decode()
        url = f"https://api.github.com/repos/Joeyygh/vibe-quant/contents/{filename}"
        data = {"message": message, "branch": "main", "content": b64}
        if sha:
            data["sha"] = sha
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={"Authorization": f"token {token}", "Content-Type": "application/json", "User-Agent": "vibe-quant-app"}, method="PUT")
        with urllib.request.urlopen(req) as r:
            return True, "已推送到 GitHub"
    except Exception as e:
        return False, str(e)[:60]


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
    """按板块分层采样:主板35% / 创业板35% / 科创板30%(提高科创板+创业板比例)"""
    if n_stocks >= len(df_stocks):
        return df_stocks['code'].tolist()
    main_prefixes = ('000', '001', '002', '600', '601', '603', '605')
    chinext = ('300',)
    star = ('688',)
    df_main = df_stocks[df_stocks['code'].str.startswith(main_prefixes)]
    df_chinext = df_stocks[df_stocks['code'].str.startswith(chinext)]
    df_star = df_stocks[df_stocks['code'].str.startswith(star)]
    # 调高创业板/科创板比例(原 40/35/25 → 35/35/30)
    n_main = int(n_stocks * 0.35)
    n_chinext = int(n_stocks * 0.35)
    n_star = n_stocks - n_main - n_chinext
    codes = []
    codes.extend(df_main['code'].head(n_main).tolist())
    codes.extend(df_chinext['code'].head(n_chinext).tolist())
    codes.extend(df_star['code'].head(n_star).tolist())
    # 如果某些板块不够,从其他板块补足(但不重复)
    if len(codes) < n_stocks:
        existing = set(codes)
        remaining = df_stocks[~df_stocks['code'].isin(existing)]['code'].tolist()
        codes.extend(remaining[:n_stocks - len(codes)])
    return codes[:n_stocks]


def compute_signals(df_klines, top_n=20):
    trend_set = set()
    factor_list = []
    industry_groups = {}

    # === 🆕 V2.2 (2026-08-07): 题材热度 + 事件催化 评分 ===
    # 板块联动加成: 当股票在当日热点板块 → +10 分
    # 资金强度: 成交额放量 + 主力净流入 → +8 分
    # 事件催化: 涨停/异动 → +5 分
    # 优先抓 Tushare 真实数据, 缺失则用 K 线推算
    try:
        import tushare as ts
        pro = ts.pro_api(os.environ.get('TUSHARE_TOKEN') or st.secrets.get('TUSHARE_TOKEN', ''))
        # 当日涨停 (>=9.5%)
        today_limit_up = set()
        # 当日大涨 (>=5%)
        today_big_up = set()
        # 主力净流入 TOP
        main_money_top = set()
        try:
            today_str = datetime.now().strftime('%Y%m%d')
            df_today = pro.daily(trade_date=today_str, fields='ts_code,close,pct_chg,amount')
            if df_today is not None and not df_today.empty:
                for _, r in df_today.iterrows():
                    code6 = r['ts_code'].split('.')[0]
                    if float(r.get('pct_chg', 0)) >= 9.5:
                        today_limit_up.add(code6)
                    elif float(r.get('pct_chg', 0)) >= 5.0:
                        today_big_up.add(code6)
        except Exception:
            pass
        # 主力净流入 (用龙虎榜或资金流)
        try:
            df_money = pro.moneyflow(trade_date=today_str, fields='ts_code,net_mf_amount')
            if df_money is not None and not df_money.empty:
                top_money = df_money.nlargest(100, 'net_mf_amount')
                main_money_top = set(r['ts_code'].split('.')[0] for _, r in top_money.iterrows())
        except Exception:
            pass
    except Exception:
        today_limit_up = set()
        today_big_up = set()
        main_money_top = set()

    # 当日热点板块 (用 industry 平均涨幅推算)
    hot_industries = set()
    try:
        ind_perf = df_klines.groupby('industry')['pct_change'].mean().sort_values(ascending=False)
        # 取涨幅 TOP 5 板块
        hot_industries = set(ind_perf.head(5).index.tolist())
    except Exception:
        pass

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
            # === 🛡️ 动量天花板保护 (2026-08-06 新增, 避免追高) ===
            overbought_penalty = 0
            if ret_20 > 80:
                overbought_penalty = 30
            elif ret_20 > 50:
                overbought_penalty = 15
            pct_today = float(last.get('pct_change', 0))
            if pct_today > 7:
                overbought_penalty += 10
            ma5 = df['close'].iloc[-5:].mean()
            bias_5 = (float(last['close']) / ma5 - 1) * 100 if ma5 > 0 else 0
            if bias_5 > 15:
                overbought_penalty += 10
            # === 🆕 V2.2: 题材热度 + 资金强度 + 事件催化 (2026-08-07) ===
            theme_bonus = 0
            money_bonus = 0
            event_bonus = 0
            # 1) 题材热度: 板块当日涨幅 TOP 5 → +10
            ind = str(last.get('industry', '未分类'))
            if ind in hot_industries and ind != 'nan' and ind != '':
                theme_bonus += 10
            # 2) 资金强度: 主力净流入 TOP 100 → +8, 当日成交额 > 5 亿 → +5
            code_str = str(code).zfill(6)
            if code_str in main_money_top:
                money_bonus += 8
            amount = float(last.get('amount', 0))
            if amount > 5e8:  # 5 亿
                money_bonus += 5
            # 3) 事件催化: 当日涨停 +15, 大涨 +5
            if code_str in today_limit_up:
                event_bonus += 15
            elif code_str in today_big_up:
                event_bonus += 5
            # 原评分 (动量)
            base_score = 50 + ret_20 * 1.5 - vol * 2 - overbought_penalty
            # V2.2 加成 (题材30% + 资金25% + 事件30% = 85% 总权重加成, 稀释动量 60%)
            new_score = base_score * 0.6 + (theme_bonus * 3 + money_bonus * 2 + event_bonus * 3) * 0.4
            factor_list.append((code, new_score))
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
            # 复盘用: 标注超买程度
            overbought_penalty = 0
            warnings = []
            if ret_20 > 80:
                overbought_penalty = 30
                warnings.append('🔥20日>80%')
            elif ret_20 > 50:
                overbought_penalty = 15
                warnings.append('⚠️20日>50%')
            pct_today = float(last.get('pct_change', 0))
            if pct_today > 7:
                overbought_penalty += 10
                warnings.append('⚡今日>7%')
            ma5 = df_sub['close'].iloc[-5:].mean()
            bias_5 = (float(last['close']) / ma5 - 1) * 100 if ma5 > 0 else 0
            if bias_5 > 15:
                overbought_penalty += 10
                warnings.append('📈乖离>15%')
            score = 50 + ret_20 * 1.5 - vol * 2 - overbought_penalty
            rows.append({
                '代码': str(code),
                '名称': str(last.get('name', code)),
                '行业': str(last.get('industry', '未分类')),
                '现价': round(float(last['close']), 2),
                '今日%': round(float(last['pct_change']), 2),
                '20日%': round(ret_20, 2),
                '波动率': round(vol, 2),
                '综合分': round(score, 2),
                '风险标签': ' / '.join(warnings) if warnings else '✅正常',
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
    if pct >= 9.0 or pct < -3.0:
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


def _render_compact_picks(df):
    """紧凑显示股票列表(去掉行业、行距紧凑、手机友好)"""
    if df is None or df.empty:
        return
    # 选定列(不显示行业、波动率冗余)
    wanted = ['代码', '名称', '现价', '今日%', '20日%', '综合分', '风险标签']
    cols = [c for c in wanted if c in df.columns]
    if not cols:
        cols = list(df.columns)
    sub = df[cols].copy()

    # 格式化
    def _fmt(v):
        if isinstance(v, float):
            if abs(v) >= 1000:
                return f"{v:.0f}"
            return f"{v:.2f}"
        return str(v)

    # 用 markdown 表格(紧凑)
    header = '| ' + ' | '.join(cols) + ' |'
    sep = '|' + '|'.join(['---'] * len(cols)) + '|'
    body = []
    for _, row in sub.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            txt = _fmt(v)
            # 颜色高亮:涨绿跌红
            if c in ('今日%', '20日%', '综合分'):
                if isinstance(v, (int, float)) and v > 0:
                    txt = f"🟢{txt}"
                elif isinstance(v, (int, float)) and v < 0:
                    txt = f"🔴{txt}"
            cells.append(txt)
        body.append('| ' + ' | '.join(cells) + ' |')
    st.markdown('\n'.join([header, sep] + body))


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
                code = h.get('code', '')
                name = h.get('name', code)
                cost = h.get('cost_price', 0) or 0
                shares = h.get('shares', 0) or 0
                grp = h.get('group', '未分组')
                ccy = h.get('currency', 'CNY')
                # 跳过港股/债券
                if str(code).endswith('.HK') or h.get('type') == 'bond':
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"**{name}**(港股/债券)")
                    if c2.button("🗑", key=f"del_{i}"):
                        holdings.pop(i)
                        save_holdings(holdings)
                        st.rerun()
                    continue

                # 持仓股:点开看详情 + 编辑/卖出
                with st.expander(f"{code} {name} | {grp}", expanded=False):
                    st.caption(f"成本 {cost} {ccy} × {shares} 股")
                    with st.form(key=f"edit_form_{i}"):
                        ec1, ec2, ec3 = st.columns(3)
                        # 用 text_input + parse 避免 number_input 默认值 bug
                        new_cost_str = ec1.text_input("成本价", value=f"{float(cost):.2f}", key=f"cost_{i}")
                        new_shares_str = ec2.text_input("股数", value=str(int(shares)), key=f"sh_{i}")
                        group_opts = ['深亏', '浅亏', '保本', '温和盈利', '高盈利', '未分组']
                        cur_idx = group_opts.index(grp) if grp in group_opts else 5
                        new_grp = ec3.selectbox("分组", group_opts, index=cur_idx, key=f"grp_{i}")
                        bc1, bc2 = st.columns(2)
                        if bc1.form_submit_button("💾 保存", use_container_width=True):
                            try:
                                new_cost_v = float(new_cost_str)
                                new_shares_v = int(new_shares_str)
                                holdings[i]['cost_price'] = new_cost_v
                                holdings[i]['shares'] = new_shares_v
                                holdings[i]['group'] = new_grp
                                save_holdings(holdings)
                                st.success("已保存")
                                st.rerun()
                            except ValueError:
                                st.error("成本价/股数必须是数字")
                        if bc2.form_submit_button("📤 标记卖出", use_container_width=True):
                            st.session_state[f'sell_idx'] = i
                            st.rerun()

                    # 卖出表单
                    if st.session_state.get(f'sell_idx') == i:
                        with st.form(key=f"sell_form_{i}"):
                            st.write(f"**卖出 {name}({code})**")
                            sell_price = st.number_input("卖出价", min_value=0.0, value=0.0, step=0.01)
                            sell_shares = st.number_input("卖出股数", min_value=0, value=int(shares), step=100)
                            sc1, sc2 = st.columns(2)
                            if sc1.form_submit_button("✅ 确认卖出", use_container_width=True):
                                if sell_price > 0 and sell_shares > 0:
                                    # 移到 closed_holdings.json
                                    closed_file = 'closed_holdings.json'
                                    closed = []
                                    if os.path.exists(closed_file):
                                        try:
                                            with open(closed_file, 'r', encoding='utf-8') as f:
                                                closed = json.load(f)
                                        except Exception:
                                            closed = []
                                    cost_total = cost * sell_shares
                                    sell_total = sell_price * sell_shares
                                    profit_pct = (sell_price - cost) / cost * 100 if cost > 0 else 0
                                    closed.append({
                                        'code': code, 'name': name,
                                        'cost_price': cost, 'sell_price': sell_price,
                                        'shares': sell_shares, 'profit_pct': round(profit_pct, 2),
                                        'note': f'6.26 标记卖出',
                                    })
                                    with open(closed_file, 'w', encoding='utf-8') as f:
                                        json.dump(closed, f, ensure_ascii=False, indent=2)
                                    # 从持仓里减
                                    if sell_shares >= shares:
                                        holdings.pop(i)
                                    else:
                                        holdings[i]['shares'] = shares - sell_shares
                                    save_holdings(holdings)
                                    st.success(f"已记录卖出:盈利 {profit_pct:+.2f}%")
                                    # 推送到 GitHub (两个文件)
                                    try:
                                        with open(closed_file, 'rb') as fh:
                                            ok1, msg1 = push_to_github(fh.read(), f'sell {code} {name} {profit_pct:+.2f}%', 'closed_holdings.json')
                                        with open(HOLDINGS_FILE, 'rb') as fh:
                                            ok2, msg2 = push_to_github(fh.read(), f'update holdings after sell {code}', 'my_holdings.json')
                                        if ok1 and ok2:
                                            st.caption("☁️ 已同步 GitHub")
                                        else:
                                            st.caption(f"⚠️ GitHub 同步: {msg1} / {msg2}")
                                    except Exception as e:
                                        st.caption(f"⚠️ 推送异常: {e}")
                                    st.session_state.pop(f'sell_idx', None)
                                    st.rerun()
                            if sc2.form_submit_button("取消", use_container_width=True):
                                st.session_state.pop(f'sell_idx', None)
                                st.rerun()

                    # 删除按钮
                    if st.button("🗑 删除该持仓", key=f"rm_{i}"):
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
                st.caption("点按钮拉取 39 只持仓(需 30 秒)")

            signals = []
            if refresh:
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
                    lines = []
                    for s in items:
                        ret = f"{s['ret']:+.1f}%" if s.get('ret') is not None else '-'
                        tips = ' / '.join(f"{t[0]}{t[1]}" for t in s['tips'])
                        lines.append(f"**{s['name']}** {s['close']:.2f} 累计{ret}　**{tips}**")
                    st.markdown('<br>'.join(lines), unsafe_allow_html=True)
                # 港股/债券
                others = [h for h in holdings if str(h.get('code', '')).endswith('.HK') or h.get('type') == 'bond']
                if others:
                    st.caption(f"港股/债券 {len(others)} 只不参与 A 股实时信号")
            else:
                st.warning("未能获取到信号,请检查 Tushare 连接")

        st.write("--- 添加 ---")
        with st.form(key="add_form"):
            ac1, ac2, ac3, ac4 = st.columns(4)
            new_code = ac1.text_input("代码", placeholder="6位如 600519")
            new_cost = ac2.number_input("成本价", min_value=0.0, value=0.0, step=0.01)
            new_shares_v = ac3.number_input("股数", min_value=0, value=0, step=100)
            new_grp_v = ac4.selectbox("分组", ['深亏', '浅亏', '保本', '温和盈利', '高盈利', '未分组'], index=5)
            if st.form_submit_button("➕ 添加持仓", use_container_width=True):
                nc = new_code.strip()
                if len(nc) == 6 and nc.isdigit() and df_stocks is not None:
                    match = df_stocks[df_stocks['code'] == nc]
                    if not match.empty:
                        name = match.iloc[0]['name']
                        if not any(h.get('code') == nc for h in holdings):
                            holdings.append({
                                'code': nc, 'name': name,
                                'cost_price': float(new_cost),
                                'shares': int(new_shares_v),
                                'group': new_grp_v,
                            })
                            save_holdings(holdings)
                            st.success(f"已添加 {nc} {name} (成本 {new_cost} × {new_shares_v} 股)")
                            st.rerun()
                        else:
                            st.warning(f"{nc} 已在持仓中")
                    else:
                        st.error(f"未找到代码 {nc}")
                else:
                    st.error("代码必须是 6 位数字")
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
        n_stocks = st.slider("扫描数", 50, 4000, 4000, 50)
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
    view_mode = st.radio("页面模式", ["量化选股", "🎯 今日精选", "🎯 双引擎", "📐 实战公式", "🎯 多公式共振", "每日复盘", "📝 我的笔记"], index=0, key="view_mode")

st.markdown("""
## Vibe 量化 v2.1 (升级版)
- 三策略精选 (胜率 83%)
- 5 过滤叠加 (胜率 100%) 含涨跌幅>-3%
- 7 条件叠加 (宽松/严格)
- 公式 2 (中线 5-10 天 胜率 100%) 含独立/叠加双模式
- 🆕 用户公式 (动量买点,独立扫描) - 早盘短线 1-3 天
- 🆕 **每日 5 企推** (题材+资金+技术+事件 4 维评分, 动量天花板保护)
- 2000 智能采样 (主板+创业板+科创板)
- 北京时间显示
""")

if view_mode == "🎯 今日精选":
    st.header("🎯 每日 5 企推 (Vibe Daily Picks)")
    st.caption("📊 综合: 题材热度30% + 资金强度25% + 技术形态15% + 事件催化30% | 🛡️ 动量天花板保护")

    # 优先 data/ (workflow 自动 commit), 兜底 reports/
    if os.path.exists('data/today_picks.json'):
        picks_file = 'data/today_picks.json'
    else:
        picks_file = 'reports/today_picks.json'
    if not os.path.exists(picks_file):
        st.error(f"❌ {picks_file} 不存在, 请先运行 `python scripts/daily_picks.py`")
        st.info("💡 数据源: 8/6 复盘数据已生成今日精选 (commit 8a1cefdd20)")
    else:
        try:
            with open(picks_file, 'r', encoding='utf-8') as f:
                picks_data = json.load(f)
        except Exception as e:
            st.error(f"读取 {picks_file} 失败: {e}")
            st.stop()

        # 顶部信息
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric("📅 日期", picks_data.get("date", "—"))
        with col2:
            st.metric("🕘 更新", picks_data.get("update_time", "—"))
        with col3:
            st.metric("🏷️ 版本", picks_data.get("version", "—"))

        # 大盘观点
        market_view = picks_data.get("market_view", "")
        if market_view:
            st.info(f"🌍 **大盘观点**: {market_view}")

        st.divider()

        # 5 只精选
        picks = picks_data.get("picks", [])
        if not picks:
            st.warning("今日无精选")
        else:
            for p in picks:
                rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][p.get("rank", 1) - 1]
                risk_color = {"低": "🟢", "中低": "🟢", "中": "🟡", "中高": "🟠", "高": "🔴"}.get(p.get("risk_level", "中"), "🟡")

                with st.container():
                    st.markdown(f"""
### {rank_emoji} #{p['rank']} {p['code']} {p['name']}  (得分: **{p['score']}**)
""")

                    # 主题标签
                    themes_str = " | ".join([f"`{t}`" for t in p.get("themes", [])])
                    st.markdown(f"**🎯 主题**: {themes_str}")

                    # 评分明细
                    sb = p.get("score_breakdown", {})
                    if sb:
                        cols = st.columns(4)
                        cols[0].metric("题材", sb.get("theme", 0))
                        cols[1].metric("资金", sb.get("money", 0))
                        cols[2].metric("技术", sb.get("tech", 0))
                        cols[3].metric("事件", sb.get("event", 0))

                    # 核心逻辑
                    st.markdown(f"**💡 核心逻辑**: {p.get('thesis', '—')}")

                    # 入场/目标/止损
                    col_e, col_t, col_s, col_r = st.columns(4)
                    col_e.markdown(f"**🎯 入场**\n\n{p.get('entry', '—')}")
                    col_t.markdown(f"**🎁 目标**\n\n{p.get('target', '—')}")
                    col_s.markdown(f"**🛑 止损**\n\n{p.get('stop', '—')}")
                    col_r.markdown(f"**⚠️ 风险**\n\n{risk_color} {p.get('risk_level', '中')}")

                    st.divider()

        # 过滤掉
        filtered = picks_data.get("filtered_out", [])
        if filtered:
            with st.expander(f"⚠️ 今日过滤掉 ({len(filtered)} 只 - 动量天花板保护)", expanded=False):
                for f in filtered:
                    st.markdown(f"- **{f['code']} {f['name']}**: {f['reason']}")

        # 风险提示
        st.caption(picks_data.get("risk_warning", "⚠️ 仅供参考, 不构成投资建议"))

    st.stop()


if view_mode == "🎯 双引擎":
    st.header("🎯 双引擎选股 (V1.1 A+C)")
    st.caption("📊 题材精选 (5 企推) + 量化形态 (V2.2) 双重验证 | 🎯 交集 = 高信心")

    # 优先 data/ (workflow 自动 commit), 兜底 reports/
    if os.path.exists('data/today_picks.json'):
        picks_file = 'data/today_picks.json'
    else:
        picks_file = 'reports/today_picks.json'
    if not os.path.exists(picks_file):
        st.error(f"❌ {picks_file} 不存在")
    else:
        with open(picks_file, 'r', encoding='utf-8') as f:
            picks_data = json.load(f)

        # 顶部信息
        col1, col2, col3, col4 = st.columns(4)
        summary = picks_data.get("summary", {})
        col1.metric("5 企推", summary.get("theme_picks", 0))
        col2.metric("量化补充", summary.get("quant_picks", 0))
        col3.metric("🎯 双引擎", summary.get("intersection", 0))
        col4.metric("总候选", summary.get("total", 0))

        st.divider()

        # 交集优先
        intersection = picks_data.get("intersection", [])
        if intersection:
            st.success(f"🎯 **双引擎交集** ({len(intersection)} 只): {', '.join(intersection)}")
            st.markdown("**🎯 双引擎 = 题材 + 形态 双重确认, 高信心, 可加仓**")
        else:
            st.info("ℹ️ 今日无双引擎交集 (题材股偏强, 形态股偏稳, 天然交集少)")

        st.divider()

        # 5 企推精选
        st.subheader("🔥 5 企推精选 (主推)")
        for p in picks_data.get("picks", []):
            risk_color = {"低": "🟢", "中低": "🟢", "中": "🟡", "中高": "🟠", "高": "🔴"}.get(p.get("risk_level", "中"), "🟡")
            with st.container():
                tag = p.get("tag", "🔥 仅精选")
                st.markdown(f"### {tag} #{p['rank']} {p['code']} {p['name']}  (得分: {p['score']})")
                st.markdown(f"**🎯 主题**: {' | '.join(p.get('themes', []))}")
                st.markdown(f"**💡 逻辑**: {p.get('thesis', '—')}")
                cols = st.columns(4)
                cols[0].markdown(f"**入场**\n\n{p.get('entry', '—')}")
                cols[1].markdown(f"**目标**\n\n{p.get('target', '—')}")
                cols[2].markdown(f"**止损**\n\n{p.get('stop', '—')}")
                cols[3].markdown(f"**风险**\n\n{risk_color} {p.get('risk_level', '中')}")
                st.divider()

        # 量化补充
        quant_picks = picks_data.get("quant_picks", [])
        if quant_picks:
            st.subheader("📊 量化补充 (V2.2 形态)")
            st.caption("形态突破但题材热度不够, 稳健标的, 观察")
            for p in quant_picks:
                risk_color = {"低": "🟢", "中低": "🟢", "中": "🟡", "中高": "🟠", "高": "🔴"}.get(p.get("risk_level", "中"), "🟡")
                with st.container():
                    tag = p.get("tag", "📊 仅量化")
                    st.markdown(f"### {tag} {p['code']} {p['name']}  (得分: {p['score']})")
                    st.markdown(f"**🎯 主题**: {' | '.join(p.get('themes', []))}")
                    st.markdown(f"**💡 逻辑**: {p.get('thesis', '—')}")
                    cols = st.columns(4)
                    cols[0].markdown(f"**入场**\n\n{p.get('entry', '—')}")
                    cols[1].markdown(f"**目标**\n\n{p.get('target', '—')}")
                    cols[2].markdown(f"**止损**\n\n{p.get('stop', '—')}")
                    cols[3].markdown(f"**风险**\n\n{risk_color} {p.get('risk_level', '中')}")
                    st.divider()

        st.caption(picks_data.get("risk_warning", "⚠️ 仅供参考"))

    st.stop()



# ============ 📐 实战公式 (4 个) ============
if view_mode == "📐 实战公式":
    st.header("📐 实战公式 (4 个 Vibe 验证)")
    st.caption("🎯 4 个经市场验证的实战选股公式 | 覆盖: 底部反转 / 趋势确立 / 价值起涨 / 主力介入")

    formulas_file = "data/formulas_picks.json"
    if not os.path.exists(formulas_file):
        # 兜底读 reports/
        formulas_file = "reports/formulas_picks.json"
    if not os.path.exists(formulas_file):
        st.error("❌ 公式 picks 还没生成,等今晚 17:00 daily.yml 跑完就有")
        st.info("💡 想立刻跑?在 GitHub Actions 手动触发 'daily' workflow")
        st.stop()

    with open(formulas_file, "r", encoding="utf-8") as f:
        formulas_data = json.load(f)

    st.success(f"📅 数据日期: {formulas_data.get('date', 'N/A')} | ⏰ {formulas_data.get('update_time', 'N/A')} | 版本: {formulas_data.get('version', 'N/A')}")

    # 🌟 精选 6 只 - 开盘关注
    top_picks = formulas_data.get("top_picks", [])
    if top_picks:
        st.markdown("### 🌟 今日精选 (8/26 开盘重点关注)")
        st.caption(formulas_data.get("top_picks_note", ""))
        import pandas as pd
        df_top = pd.DataFrame([{
            "代码": p["code"],
            "名称": p["name"],
            "PE": p.get("pe", 0),
            "市值(亿)": p.get("mv_yi", 0),
            "理由": p.get("thesis", ""),
            "止损": p.get("stop", ""),
            "目标": p.get("target", ""),
        } for p in top_picks])
        st.dataframe(df_top, use_container_width=True, hide_index=True)
        st.divider()
    
    # 🎯 共振统计概览
    resonance = formulas_data.get("resonance", [])
    if resonance:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🎯 共振总数", len(resonance))
        c2.metric("💎 3+公式", sum(1 for r in resonance if r['hit_count'] >= 3))
        c3.metric("⭐ 2公式", sum(1 for r in resonance if r['hit_count'] == 2))
        c4.metric("📊 公式总命中", sum(len(v) for v in formulas_data.get("formulas", {}).values()))
        st.info("💡 **多公式共振 = 高信心信号**!同一只票被多个公式选中,说明技术面/资金面/基本面多维度确认,优先级 > 单公式。点 '🎯 多公式共振' 看详情。")
    st.divider()

    # 3 大策略 + 1 个实战公式
    if "strategies" in formulas_data:
        # v3.0 多策略
        tab1, tab2, tab3, tab4 = st.tabs([
            "🅰️ 保守稳健",
            "🅱️ 趋势跟随",
            "🅲️ 抄底反弹",
            "🎯 共振 (2+)",
        ])
    else:
        # v2.x 老格式
        tab1, tab2, tab3, tab4 = st.tabs([
            "1️⃣ 缩量企稳上穿MA20",
            "2️⃣ 多金叉共振",
            "3️⃣ 起量+基本面",
            "4️⃣ 强势主力介入",
        ])

    if "strategies" in formulas_data:
        formula_keys = ["A_保守稳健", "B_趋势跟随", "C_抄底反弹"]
    else:
        formula_keys = [
            "1_缩量企稳上穿MA20",
            "2_多金叉共振",
            "3_起量基本面",
            "4_强势主力",
        ]
    if "strategies" in formulas_data:
        formula_descs = [
            "**思路**: 温和涨 + 站上均价 + 资金回流 + 业绩正 + 风口加权\n\n**适用**: 震荡市/慢牛,稳健持仓\n\n**风险**: 低,胜率优先",
            "**思路**: 强势红盘 + 量比放大 + 资金共振 + 板块联动\n\n**适用**: 普涨市,趋势跟随\n\n**风险**: 中,追高有回撤",
            "**思路**: 跌 1-5% + 缩量 + 业绩正 + 资金不大幅流出\n\n**适用**: 熊市/震荡,反共识抄底\n\n**风险**: 中,需快进快出",
            "**思路**: 2+ 策略同时选中 = 多维度确认\n\n**适用**: 高信心信号\n\n**风险**: 取决于命中策略",
        ]
    else:
        formula_descs = [
            "**思路**: 抄底型 — 近1月跌20%+ 缩量企稳 + 站上MA20 + 资金小幅回流\n\n**适用**: 左侧布局,博反弹\n\n**风险**: 中,需严格止损",
            "**思路**: 趋势型 — 上穿MA60 + MACD金叉 + 资金共振 + 量价齐升\n\n**适用**: 右侧追涨,中线持有\n\n**风险**: 中,关键支撑跌破止损",
            "**思路**: 价值型 — 起量 + 业绩 + BPS 前 5\n\n**适用**: 中线持有,基本面兜底\n\n**风险**: 低,价值投资者",
            "**思路**: 主力型 — 量价齐升 + 资金榜 top3\n\n**适用**: 短线博弈,快进快出\n\n**风险**: 高,严控仓位",
        ]

    for tab, key, desc in zip([tab1, tab2, tab3, tab4], formula_keys, formula_descs):
        with tab:
            st.markdown(desc)
            st.divider()
            # 兼容 v3.0 (strategies 字段) 和 v2.x (formulas 字段)
            if "strategies" in formulas_data:
                picks = formulas_data.get("strategies", {}).get(key, [])
                # v3.0 格式: 已经是 dict 列表
                df_picks = pd.DataFrame([{
                    "代码": p["code"],
                    "名称": p.get("name", ""),
                    "涨跌幅": f"{p.get('pct_chg', 0):+.2f}%",
                    "板块": p.get("industry", ""),
                    "风口": "🔥" if p.get("in_hot_industry") else "",
                    "3日资金(亿)": f"{p.get('money_3d', 0)/10000:+.2f}",
                } for p in picks])
            else:
                picks = formulas_data.get("formulas", {}).get(key, [])
                df_picks = pd.DataFrame([{"代码": p.split()[0], "名称": p.split()[1] if len(p.split()) > 1 else ""} for p in picks])
            
            if not picks:
                st.warning("⚠️ 今日无符合条件股票 (可能市场不满足条件)")
                st.info("💡 这种时候不要硬买,空仓也是策略")
            else:
                st.success(f"✅ 找到 {len(picks)} 只")
                st.dataframe(df_picks, use_container_width=True, hide_index=True)
                st.caption("💡 建议先加入自选,等回踩不破 MA5/MA10 再介入,严设止损")

    # 🛡️ 市场环境 + 板块联动展示
    market = formulas_data.get("market", {})
    if market:
        st.divider()
        st.subheader("🛡️ 大盘环境 + 板块联动")
        st.markdown(f"**{market.get('status', 'N/A')}**")
        cols = st.columns(5)
        cols[0].metric("大盘平均", f"{float(market.get('market_pct', 0)):+.2f}%")
        cols[1].metric("涨家比", f"{float(market.get('up_ratio', 0))*100:.0f}%")
        cols[2].metric("涨停", int(market.get('up_limit', 0)))
        cols[3].metric("跌停", int(market.get('down_limit', 0)))
        # hot_industries 可能是 list (新) 或 int (老), 兼容
        hot = market.get('hot_industries', 0)
        if isinstance(hot, list):
            hot_count = len(hot)
        else:
            hot_count = int(hot)
        cols[4].metric("风口行业数", hot_count)
        hot = market.get('hot_industries', [])
        if hot:
            st.success(f"🔥 风口行业: {', '.join(hot)}")
        else:
            st.info("暂无明显风口行业")
    
    # 💼 持仓风险预警
    holdings_warnings = formulas_data.get("holdings_warnings", [])
    if holdings_warnings:
        st.divider()
        st.subheader("💼 持仓风险预警")
        import pandas as pd
        df_warn = pd.DataFrame([{
            "代码": w["code"],
            "名称": w["name"],
            "成本": w.get("cost", 0),
            "现价": w["close"],
            "累计%": f"{w.get('ret', 0):+.1f}%",
            "今日%": f"{w.get('pct_today', 0):+.2f}%",
            "信号": " | ".join(w.get("signals", [])),
        } for w in holdings_warnings])
        st.dataframe(df_warn, use_container_width=True, hide_index=True)
    
    st.divider()
    st.info("💡 4 个公式可与「量化选股」叠加使用,选择共振票胜率更高")
    st.stop()




# ============ 🎯 多公式共振 (自动筛选) ============
if view_mode == "🎯 多公式共振":
    st.header("🎯 多公式共振 (自动筛选)")
    st.caption("💎 同一只票被 2 个以上实战公式同时选中 = 高信心信号")

    formulas_file = "data/formulas_picks.json"
    if not os.path.exists(formulas_file):
        formulas_file = "reports/formulas_picks.json"
    if not os.path.exists(formulas_file):
        st.error("❌ 公式 picks 还没生成")
        st.stop()

    with open(formulas_file, "r", encoding="utf-8") as f:
        formulas_data = json.load(f)

    resonance = formulas_data.get("resonance", [])
    if not resonance:
        st.warning("⚠️ 今日无共振股票 (各公式选出的票没重叠)")
        st.info("💡 这种时候市场方向不明确,建议空仓观望")
        st.stop()

    # 顶部统计
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 共振总数", len(resonance))
    c2.metric("💎 3+ 公式", sum(1 for r in resonance if r['hit_count'] >= 3))
    c3.metric("⭐ 2 公式", sum(1 for r in resonance if r['hit_count'] == 2))
    c4.metric("📅 日期", formulas_data.get('date', 'N/A'))

    st.divider()

    # 按 hit_count 分组
    high_resonance = [r for r in resonance if r['hit_count'] >= 3]
    mid_resonance = [r for r in resonance if r['hit_count'] == 2]

    if high_resonance:
        st.markdown("### 💎 顶级共振 (3+ 公式) — 重点关注")
        for r in high_resonance:
            with st.container():
                cols = st.columns([1, 3, 1, 1, 1, 4])
                with cols[0]:
                    st.markdown(f"## 🎯")
                with cols[1]:
                    st.markdown(f"**{r['code']} {r['name']}**")
                    st.caption(f"行业: {r.get('industry', 'N/A')}")
                with cols[2]:
                    pct = r['pct_chg']
                    color = "🟢" if pct > 0 else "🔴"
                    st.metric("涨跌幅", f"{color} {pct:+.2f}%")
                with cols[3]:
                    st.metric("换手率", f"{r.get('turnover_rate', 0):.1f}%")
                with cols[4]:
                    st.metric("量比", f"{r.get('volume_ratio', 0):.2f}")
                with cols[5]:
                    hit_badges = " ".join([f"`{h.split('_')[0]}️⃣`" for h in r['hit_formulas']])
                    st.markdown(f"**命中公式**: {hit_badges}")
                    st.caption(f"3日资金: {r.get('money_3d', 0)/10000:+.2f} 亿")
                st.divider()

    if mid_resonance:
        st.markdown("### ⭐ 中度共振 (2 公式) — 可关注")
        # 表格展示
        import pandas as pd
        df_mid = pd.DataFrame([{
            "代码": r['code'],
            "名称": r['name'],
            "行业": r.get('industry', ''),
            "今日涨跌幅": f"{r['pct_chg']:+.2f}%",
            "换手率": f"{r.get('turnover_rate', 0):.1f}%",
            "量比": f"{r.get('volume_ratio', 0):.2f}",
            "3日资金(亿)": f"{r.get('money_3d', 0)/10000:+.2f}",
            "命中公式": " ".join([h.split('_')[0] + "️⃣" for h in r['hit_formulas']]),
        } for r in mid_resonance])
        st.dataframe(df_mid, use_container_width=True, hide_index=True)

    st.divider()
    st.info("💡 **用法**: 顶级共振(3+公式) 开盘 30 分钟观察,中度共振(2公式) 可做短线。严设止损!")

    st.stop()


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
                st.markdown(f"### 1. 三策略精选 ({len(df_3)} 只)")
                _render_compact_picks(df_3)
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
                    st.markdown(f"### 2. 5 过滤叠加 ({len(df_extra)} 只)")
                    _render_compact_picks(df_extra)
                else:
                    st.info("三策略通过的股未通过 5 过滤")

            if not df_3.empty:
                with st.spinner("应用 7 条件..."):
                    seven_codes = apply_seven_conditions(df_sub, df_3['代码'].tolist(), strict=seven_strict)
                    df_7 = df_3[df_3['代码'].isin(seven_codes)].copy() if seven_codes else pd.DataFrame()
                mode_label = "严格" if seven_strict else "宽松"
                if not df_7.empty:
                    st.markdown(f"### 3. 7 条件叠加/{mode_label} ({len(df_7)} 只)")
                    _render_compact_picks(df_7)
                else:
                    st.info(f"三策略通过的股未通过 7 条件({mode_label}模式)")

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
                        st.markdown(f"### 4. 公式 2 (独立 - 不过三策略) ({len(df_f2)} 只)")
                        st.success(f"5天 +4.88% / 10天 +11.33% 胜率 100%")
                        _render_compact_picks(df_f2)
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
                        st.markdown(f"### 4. 公式 2 (叠加 - 需过三策略) ({len(df_f2)} 只)")
                        st.success(f"5天 +4.88% / 10天 +11.33% 胜率 100%")
                        _render_compact_picks(df_f2)
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
                    st.markdown(f"### 5. 🆕 用户公式 (动量买点,独立) ({len(df_uf)} 只)")
                    st.success("独立扫描,不叠加 Vibe 1-4 模块")
                    st.caption("4 条公式: ①竞价量比>5 ②开盘涨幅 2-5% ③近 3 日成交额递增 ④收盘>20日线")
                    _render_compact_picks(df_uf)
                else:
                    st.info("用户公式:今天 0 只通过 - 早盘无买点信号,空仓观察")
                st.divider()
        except Exception as e:
            st.error(f"出错: {e}")
            import traceback
            st.code(traceback.format_exc())

st.divider()
st.caption(f"Vibe v2.0 | {(datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')} (北京时间)")

# 8/25 21:50 触发 App 重启读取 8/25 数据

# v3.2 上线 2026-08-26 21:35 (智能优先级 + top 3 推荐)
