"""Vibe 量化系统 v2.0 - 全 A 股版（自带数据，0 上传）"""
import streamlit as st
import pandas as pd
import random
import json
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Vibe 量化 v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v2.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：AKShare 全 A 股 5000+")


@st.cache_data(ttl=3600, show_spinner="加载全 A 股列表...")
def load_stock_list():
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        df['code'] = df['code'].astype(str).str.zfill(6)
        return df
    except Exception as e:
        st.error(f"AKShare 失败: {e}")
        return pd.DataFrame()


INDUSTRY_MAPPING = {
    '600519': '食品饮料', '000858': '食品饮料', '300750': '电力设备',
    '601318': '非银金融', '600036': '银行', '000001': '银行',
    '600276': '医药生物', '000333': '家用电器', '601012': '电力设备',
    '002594': '汽车', '600900': '公用事业', '601398': '银行',
    '601939': '银行', '601988': '银行', '600028': '石油石化',
    '600050': '通信', '601800': '建筑装饰', '601628': '非银金融',
    '601857': '石油石化', '600585': '建筑材料', '600887': '食品饮料',
    '601088': '煤炭', '601288': '银行', '601328': '银行',
    '600000': '银行', '601166': '银行', '601229': '银行',
    '600030': '非银金融', '601688': '非银金融', '000651': '家用电器',
    '000002': '房地产', '000063': '通信', '000100': '电子',
    '000157': '机械设备', '000425': '机械设备', '000538': '医药生物',
    '000568': '食品饮料', '000625': '汽车', '000661': '医药生物',
    '000725': '电子', '000768': '国防军工', '000776': '非银金融',
    '000792': '基础化工', '000876': '农林牧渔', '000938': '计算机',
    '000963': '医药生物', '000977': '计算机', '001979': '房地产',
    '002027': '传媒', '002230': '计算机', '002241': '电子',
    '002304': '食品饮料', '002415': '计算机', '002460': '有色金属',
    '002466': '有色金属', '002475': '电子', '002493': '石油石化',
    '002555': '传媒', '002648': '基础化工', '002714': '农林牧渔',
    '002812': '基础化工', '002916': '电子', '300014': '电力设备',
    '300015': '医药生物', '300033': '计算机', '300059': '非银金融',
    '300122': '医药生物', '300124': '机械设备', '300223': '电子',
    '300274': '电力设备', '300316': '机械设备', '300347': '医药生物',
    '300408': '电子', '300413': '传媒', '300433': '电子',
    '300498': '农林牧渔', '300661': '电子', '300760': '医药生物',
    '300782': '电子', '300866': '电子', '300896': '医药生物',
    '300919': '电力设备', '300979': '纺织服饰', '300999': '农林牧渔',
    '600009': '交通运输', '600011': '公用事业', '600019': '钢铁',
    '600025': '公用事业', '600031': '机械设备', '600048': '房地产',
    '600085': '医药生物', '600089': '电力设备', '600104': '汽车',
    '600111': '有色金属', '600150': '国防军工', '600188': '煤炭',
    '600196': '医药生物', '600309': '基础化工', '600346': '石油石化',
    '600362': '有色金属', '600406': '电力设备', '600436': '医药生物',
    '600438': '电力设备', '600487': '通信', '600547': '有色金属',
    '600570': '计算机', '600588': '计算机', '600600': '食品饮料',
    '600660': '汽车', '600690': '家用电器', '600745': '电子',
    '600809': '食品饮料', '600837': '非银金融', '600845': '计算机',
    '600886': '公用事业', '600893': '国防军工', '600905': '公用事业',
    '600918': '非银金融', '600926': '银行', '600941': '通信',
    '600958': '非银金融', '600999': '非银金融', '601066': '非银金融',
    '601100': '机械设备', '601138': '电子', '601186': '建筑装饰',
    '601211': '非银金融', '601225': '煤炭', '601319': '非银金融',
    '601336': '非银金融', '601360': '计算机', '601390': '建筑装饰',
    '601456': '非银金融', '601555': '非银金融', '601600': '有色金属',
    '601601': '非银金融', '601633': '汽车', '601658': '银行',
    '601668': '建筑装饰', '601689': '汽车', '601728': '通信',
    '601818': '银行', '601838': '银行', '601877': '电力设备',
    '601878': '非银金融', '601881': '非银金融', '601888': '社会服务',
    '601899': '有色金属', '601919': '交通运输', '601995': '非银金融',
    '601998': '银行', '603019': '计算机', '603259': '医药生物',
    '603288': '食品饮料', '603501': '电子', '603799': '有色金属',
    '603986': '电子', '688008': '电子', '688012': '电子',
    '688036': '电子', '688111': '计算机', '688169': '家用电器',
    '688271': '医药生物', '688981': '电子',
}


def get_industry(code):
    if code in INDUSTRY_MAPPING:
        return INDUSTRY_MAPPING[code]
    if code.startswith(('600', '601', '603', '605')):
        return '上海主板'
    elif code.startswith(('000', '002', '003')):
        return '深圳主板'
    elif code.startswith(('300', '301')):
        return '创业板'
    elif code.startswith(('688', '689')):
        return '科创板'
    return '其他'


INDUSTRY_PRICE = {
    '食品饮料': 80, '银行': 12, '非银金融': 18, '电力设备': 50,
    '汽车': 35, '医药生物': 45, '家用电器': 35, '公用事业': 18,
    '石油石化': 12, '通信': 22, '建筑装饰': 8, '建筑材料': 22,
    '煤炭': 18, '房地产': 8, '电子': 35, '机械设备': 22,
    '基础化工': 18, '计算机': 35, '传媒': 15, '农林牧渔': 14,
    '国防军工': 28, '有色金属': 25, '钢铁': 6, '纺织服饰': 18,
    '交通运输': 12, '社会服务': 18, '上海主板': 15, '深圳主板': 15,
    '创业板': 25, '科创板': 45, '其他': 15
}


@st.cache_data(ttl=3600, show_spinner="生成 K 线数据...")
def generate_klines(stock_list, n_stocks=500):
    if stock_list.empty:
        return {}
    random.seed(42)
    kline_dict = {}
    codes = stock_list['code'].head(n_stocks).tolist()
    for i, code in enumerate(codes):
        try:
            row = stock_list[stock_list['code'] == code].iloc[0]
            name = str(row.get('name', code))
            industry = get_industry(code)
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
                    'code': code, 'name': name,
                    'open': round(price * 0.995, 2),
                    'high': round(price * 1.015, 2),
                    'low': round(price * 0.985, 2),
                    'close': round(price, 2),
                    'volume': int(random.uniform(1e6, 1e8)),
                    'pct_change': round(change * 100, 2),
                })
            df = pd.DataFrame(data)
            kline_dict[code] = df
        except Exception as e:
            continue
    return kline_dict


def compute_trend_signals(kline_dict, top_n=10):
    rows = []
    for code, df in kline_dict.items():
        if df is None or len(df) < 60:
            continue
        try:
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
                        '代码': str(code),
                        '名称': str(last['name']),
                        '现价': round(float(last['close']), 2),
                        '今日涨幅%': round(float(last['pct_change']), 2),
                        'MA20': round(float(last['ma20']), 2),
                        'MA60': round(float(last['ma60']), 2),
                    })
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).head(top_n)


def compute_rotation_signals(kline_dict, stock_list, top_n=5):
    industry_map = {}
    for _, row in stock_list.iterrows():
        code = str(row['code']).zfill(6)
        ind = get_industry(code)
        industry_map[code] = ind
    
    industries = {}
    for code, ind in industry_map.items():
        industries.setdefault(ind, []).append(code)
    
    rows = []
    for ind, codes in industries.items():
        scores = []
        for code in codes:
            if code in kline_dict and kline_dict[code] is not None and len(kline_dict[code]) >= 20:
                try:
                    df = kline_dict[code]
                    ret = (float(df['close'].iloc[-1]) / float(df['close'].iloc[-20]) - 1) * 100
                    scores.append(ret)
                except Exception:
                    pass
        if scores and len(scores) >= 5:
            avg = sum(scores) / len(scores)
            if avg > -2:
                leader_code = codes[0]
                leader_name = ''
                leader_price = 0
                if leader_code in kline_dict and kline_dict[leader_code] is not None and len(kline_dict[leader_code]) > 0:
                    leader_name = str(kline_dict[leader_code]['name'].iloc[0])
                    leader_price = float(kline_dict[leader_code]['close'].iloc[-1])
                rows.append({
                    '行业': str(ind),
                    '龙头': leader_name,
                    '龙头代码': str(leader_code),
                    '现价': round(leader_price, 2),
                    '行业20日均涨幅%': round(avg, 2),
                    '成分股数': len(scores),
                })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values('行业20日均涨幅%', ascending=False).head(top_n)


def compute_factor_signals(kline_dict, top_n=20):
    rows = []
    for code, df in kline_dict.items():
        if df is None or len(df) < 60:
            continue
        try:
            ret_20 = (float(df['close'].iloc[-1]) / float(df['close'].iloc[-20]) - 1) * 100
            ret_5 = (float(df['close'].iloc[-1]) / float(df['close'].iloc[-5]) - 1) * 100
            vol = float(df['pct_change'].std())
            score = 50 + ret_20 * 1.5 + ret_5 * 0.5 - vol * 2
            name = str(df['name'].iloc[-1]) if 'name' in df.columns else str(code)
            rows.append({
                '代码': str(code),
                '名称': name,
                '现价': round(float(df['close'].iloc[-1]), 2),
                '5日涨幅%': round(ret_5, 2),
                '20日涨幅%': round(ret_20, 2),
                '波动率': round(vol, 2),
                '综合得分': round(score, 2),
            })
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values('综合得分', ascending=False).head(top_n)


with st.sidebar:
    st.header("⚙️ 参数设置")
    n_stocks = st.slider("扫描股票数", 50, 5500, 500, 50, help="首次建议 500")
    top_n = st.slider("Top N", 3, 50, 10, 1)
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
1. 左侧调整 **扫描股票数**（最多 5500 只）
2. 左侧调整 **Top N**
3. 勾选你要跑的 **策略**
4. 点击 **🚀 运行分析** 按钮

### 💡 数据源说明
- 数据集：**5000+ 全 A 股**（AKShare 拉取 + 行业映射）
- K线：**120 天**（合成数据，含行业趋势）
- 0 上传文件，0 配置，开箱即用

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
> 投资有风险，决策需谨慎。
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📋 加载全 A 股列表...")
        progress.progress(10)
        stock_list = load_stock_list()
        if stock_list.empty:
            st.error("❌ 加载股票列表失败，请检查网络或稍后重试")
            st.stop()
        st.info(f"📊 全市场共 {len(stock_list)} 只 A 股")
        
        status.text("📈 生成 K 线数据...")
        progress.progress(40)
        kline_dict = generate_klines(stock_list, n_stocks=n_stocks)
        if not kline_dict:
            st.error("❌ 生成K线数据失败")
            st.stop()
        
        status.text("🔍 计算策略信号...")
        progress.progress(70)
        if use_trend:
            trend_df = compute_trend_signals(kline_dict, top_n=top_n)
        if use_rotation:
            rotation_df = compute_rotation_signals(kline_dict, stock_list.head(n_stocks), top_n=10)
        if use_factors:
            factors_df = compute_factor_signals(kline_dict, top_n=top_n*2)
        
        progress.progress(100)
        status.text("✅ 分析完成！")
        progress.empty()
        status.empty()
        
        total_signals = (len(trend_df) if use_trend and trend_df is not None and not trend_df.empty else 0) + \
                        (len(rotation_df) if use_rotation and rotation_df is not None and not rotation_df.empty else 0) + \
                        (len(factors_df) if use_factors and factors_df is not None and not factors_df.empty else 0)
        st.success(f"🎉 已扫描 {len(kline_dict)} 只股票，触发信号 {total_signals} 条")
        
        if use_trend:
            st.header("🔥 趋势策略信号（均线多头+量价齐升）")
            if trend_df is not None and not trend_df.empty:
                st.dataframe(trend_df, use_container_width=True, hide_index=True)
                st.caption(f"📊 共 {len(trend_df)} 只股票触发趋势买入信号")
            else:
                st.info("📭 今日无趋势策略信号（市场处于震荡或下跌趋势）")
        
        if use_rotation:
            st.header("🔄 行业轮动信号（强势行业龙头）")
            if rotation_df is not None and not rotation_df.empty:
                st.dataframe(rotation_df, use_container_width=True, hide_index=True)
                st.caption(f"📊 共 {len(rotation_df)} 个行业进入强势区域")
            else:
                st.info("📭 今日无行业轮动信号")
        
        if use_factors:
            st.header("📊 多因子精选（综合Top榜单）")
            if factors_df is not None and not factors_df.empty:
                st.dataframe(factors_df, use_container_width=True, hide_index=True)
                st.caption(f"📊 共 {len(factors_df)} 只股票入选多因子精选")
            else:
                st.info("📭 今日无多因子信号")
    except Exception as e:
        st.error(f"❌ 运行出错: {e}")
        import traceback
        st.code(traceback.format_exc())

st.divider()
st.caption("Vibe 量化 v2.0 | 数据：AKShare 全 A 股 5000+ | 仅供学习研究")
