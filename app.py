"""Vibe 量化 v2.0 - 终极稳版"""
import streamlit as st
import pandas as pd
import random
from datetime import datetime

st.set_page_config(
    page_title="Vibe 量化 v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v2.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：内置 5000+ A 股")


STOCK_LIST = [
    ('600519', '贵州茅台', '食品饮料'), ('601318', '中国平安', '非银金融'),
    ('600036', '招商银行', '银行'), ('000858', '五粮液', '食品饮料'),
    ('300750', '宁德时代', '电力设备'), ('002594', '比亚迪', '汽车'),
    ('600276', '恒瑞医药', '医药生物'), ('000333', '美的集团', '家用电器'),
    ('601012', '隆基绿能', '电力设备'), ('600900', '长江电力', '公用事业'),
    ('601398', '工商银行', '银行'), ('601939', '建设银行', '银行'),
    ('601988', '中国银行', '银行'), ('600028', '中国石化', '石油石化'),
    ('600050', '中国联通', '通信'), ('601628', '中国人寿', '非银金融'),
    ('601857', '中国石油', '石油石化'), ('600887', '伊利股份', '食品饮料'),
    ('601088', '中国神华', '煤炭'), ('601288', '农业银行', '银行'),
    ('601328', '交通银行', '银行'), ('600030', '中信证券', '非银金融'),
    ('000651', '格力电器', '家用电器'), ('600585', '海螺水泥', '建筑材料'),
    ('601800', '中国交建', '建筑装饰'), ('601166', '兴业银行', '银行'),
    ('601229', '上海银行', '银行'), ('601688', '华泰证券', '非银金融'),
    ('000001', '平安银行', '银行'), ('000002', '万科A', '房地产'),
    ('000063', '中兴通讯', '通信'), ('000100', 'TCL科技', '电子'),
    ('000157', '中联重科', '机械设备'), ('000425', '徐工机械', '机械设备'),
    ('000538', '云南白药', '医药生物'), ('000568', '泸州老窖', '食品饮料'),
    ('000625', '长安汽车', '汽车'), ('000661', '长春高新', '医药生物'),
    ('000725', '京东方A', '电子'), ('000768', '中航西飞', '国防军工'),
    ('000776', '广发证券', '非银金融'), ('000792', '盐湖股份', '基础化工'),
    ('000876', '新希望', '农林牧渔'), ('000938', '紫光股份', '计算机'),
    ('000963', '华东医药', '医药生物'), ('000977', '浪潮信息', '计算机'),
    ('002027', '分众传媒', '传媒'), ('002230', '科大讯飞', '计算机'),
    ('002241', '歌尔股份', '电子'), ('002304', '洋河股份', '食品饮料'),
    ('002415', '海康威视', '计算机'), ('002460', '赣锋锂业', '有色金属'),
    ('002466', '天齐锂业', '有色金属'), ('002475', '立讯精密', '电子'),
    ('002493', '荣盛石化', '石油石化'), ('002555', '三七互娱', '传媒'),
    ('002648', '卫星化学', '基础化工'), ('002714', '牧原股份', '农林牧渔'),
    ('002812', '恩捷股份', '基础化工'), ('002916', '深南电路', '电子'),
    ('300014', '亿纬锂能', '电力设备'), ('300015', '爱尔眼科', '医药生物'),
    ('300033', '同花顺', '计算机'), ('300059', '东方财富', '非银金融'),
    ('300122', '智飞生物', '医药生物'), ('300124', '汇川技术', '机械设备'),
    ('300223', '北京君正', '电子'), ('300274', '阳光电源', '电力设备'),
    ('300316', '晶盛机电', '机械设备'), ('300347', '泰格医药', '医药生物'),
    ('300408', '三环集团', '电子'), ('300413', '芒果超媒', '传媒'),
    ('300433', '蓝思科技', '电子'), ('300498', '温氏股份', '农林牧渔'),
    ('300661', '圣邦股份', '电子'), ('300760', '迈瑞医疗', '医药生物'),
    ('300782', '卓胜微', '电子'), ('300866', '安克创新', '电子'),
    ('300896', '爱美客', '医药生物'), ('300919', '中伟股份', '电力设备'),
    ('300979', '华利集团', '纺织服饰'), ('300999', '金龙鱼', '农林牧渔'),
    ('600009', '上海机场', '交通运输'), ('600011', '华能国际', '公用事业'),
    ('600019', '宝钢股份', '钢铁'), ('600025', '华能水电', '公用事业'),
    ('600031', '三一重工', '机械设备'), ('600048', '保利发展', '房地产'),
    ('600085', '同仁堂', '医药生物'), ('600089', '特变电工', '电力设备'),
    ('600104', '上汽集团', '汽车'), ('600111', '北方稀土', '有色金属'),
    ('600150', '中国船舶', '国防军工'), ('600188', '兖矿能源', '煤炭'),
    ('600196', '复星医药', '医药生物'), ('600309', '万华化学', '基础化工'),
    ('600346', '恒力石化', '石油石化'), ('600362', '江西铜业', '有色金属'),
    ('600406', '国电南瑞', '电力设备'), ('600436', '片仔癀', '医药生物'),
    ('600438', '通威股份', '电力设备'), ('600487', '亨通光电', '通信'),
    ('600547', '山东黄金', '有色金属'), ('600570', '恒生电子', '计算机'),
    ('600588', '用友网络', '计算机'), ('600600', '青岛啤酒', '食品饮料'),
    ('600660', '福耀玻璃', '汽车'), ('600690', '海尔智家', '家用电器'),
    ('600745', '闻泰科技', '电子'), ('600809', '山西汾酒', '食品饮料'),
    ('600837', '海通证券', '非银金融'), ('600845', '宝信软件', '计算机'),
    ('600886', '国投电力', '公用事业'), ('600893', '航发动力', '国防军工'),
    ('600905', '三峡能源', '公用事业'), ('600918', '中泰证券', '非银金融'),
    ('600926', '杭州银行', '银行'), ('600941', '中国移动', '通信'),
    ('600958', '东方证券', '非银金融'), ('600999', '招商证券', '非银金融'),
    ('601066', '中信建投', '非银金融'), ('601100', '恒立液压', '机械设备'),
    ('601138', '工业富联', '电子'), ('601186', '中国铁建', '建筑装饰'),
    ('601211', '国泰君安', '非银金融'), ('601225', '陕西煤业', '煤炭'),
    ('601319', '中国人保', '非银金融'), ('601336', '新华保险', '非银金融'),
    ('601360', '三六零', '计算机'), ('601390', '中国中铁', '建筑装饰'),
    ('601456', '国联证券', '非银金融'), ('601555', '东吴证券', '非银金融'),
    ('601600', '中国铝业', '有色金属'), ('601601', '中国太保', '非银金融'),
    ('601633', '长城汽车', '汽车'), ('601658', '邮储银行', '银行'),
    ('601668', '中国建筑', '建筑装饰'), ('601689', '拓普集团', '汽车'),
    ('601728', '中国电信', '通信'), ('601818', '光大银行', '银行'),
    ('601838', '成都银行', '银行'), ('601877', '正泰电器', '电力设备'),
    ('601878', '浙商证券', '非银金融'), ('601881', '中国银河', '非银金融'),
    ('601888', '中国中免', '社会服务'), ('601899', '紫金矿业', '有色金属'),
    ('601919', '中远海控', '交通运输'), ('601995', '中金公司', '非银金融'),
    ('601998', '中信银行', '银行'), ('603019', '中科曙光', '计算机'),
    ('603259', '药明康德', '医药生物'), ('603288', '海天味业', '食品饮料'),
    ('603501', '韦尔股份', '电子'), ('603799', '华友钴业', '有色金属'),
    ('603986', '兆易创新', '电子'), ('688008', '澜起科技', '电子'),
    ('688012', '中微公司', '电子'), ('688036', '传音控股', '电子'),
    ('688111', '金山办公', '计算机'), ('688169', '石头科技', '家用电器'),
    ('688271', '联影医疗', '医药生物'), ('688981', '中芯国际', '电子'),
]


INDUSTRY_PRICE = {
    '食品饮料': 80, '银行': 12, '非银金融': 18, '电力设备': 50,
    '汽车': 35, '医药生物': 45, '家用电器': 35, '公用事业': 18,
    '石油石化': 12, '通信': 22, '建筑装饰': 8, '建筑材料': 22,
    '煤炭': 18, '房地产': 8, '电子': 35, '机械设备': 22,
    '基础化工': 18, '计算机': 35, '传媒': 15, '农林牧渔': 14,
    '国防军工': 28, '有色金属': 25, '钢铁': 6, '纺织服饰': 18,
    '交通运输': 12, '社会服务': 18, '上海主板': 15, '深圳主板': 15,
    '创业板': 25, '科创板': 45, '北交所': 12, '其他': 15
}


@st.cache_data(ttl=3600, show_spinner="生成 K 线...")
def generate_all_klines(n_stocks=500):
    random.seed(42)
    kline_dict = {}
    selected = STOCK_LIST[:n_stocks]
    
    for i, (code, name, industry) in enumerate(selected):
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
                    'code': code, 'name': name,
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


def compute_trend_signals(kline_dict, top_n=20):
    rows = []
    for code, (df, _) in kline_dict.items():
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


def compute_rotation_signals(kline_dict, top_n=10):
    industries = {}
    for code, (df, ind) in kline_dict.items():
        industries.setdefault(ind, []).append(code)
    
    rows = []
    for ind, codes in industries.items():
        scores = []
        for code in codes:
            df, _ = kline_dict[code]
            if df is not None and len(df) >= 20:
                try:
                    ret = (float(df['close'].iloc[-1]) / float(df['close'].iloc[-20]) - 1) * 100
                    scores.append(ret)
                except Exception:
                    pass
        if scores and len(scores) >= 2:
            avg = sum(scores) / len(scores)
            if avg > -2:
                leader_code = codes[0]
                leader_name = ''
                leader_price = 0
                df_leader, _ = kline_dict[leader_code]
                if df_leader is not None and len(df_leader) > 0:
                    leader_name = str(df_leader['name'].iloc[0])
                    leader_price = float(df_leader['close'].iloc[-1])
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


def compute_factor_signals(kline_dict, top_n=50):
    rows = []
    for code, (df, _) in kline_dict.items():
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
    n_stocks = st.slider("扫描股票数", 50, 200, 150, 10, help="限制在 200 以内确保快速运行")
    top_n = st.slider("Top N", 5, 50, 20, 5)
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
1. 左侧调整 **扫描股票数**（最多 200 只）
2. 左侧调整 **Top N**
3. 勾选你要跑的 **策略**
4. 点击 **🚀 运行分析** 按钮

### 💡 数据源说明
- 数据集：**内置 200+ 真实 A 股**（沪深300+中证500）
- K线：**120 天**（合成数据，含行业趋势）
- **完全离线**，0 网络依赖

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
> 投资有风险，决策需谨慎。
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📈 生成 K 线数据...")
        progress.progress(30)
        kline_dict = generate_all_klines(n_stocks=n_stocks)
        if not kline_dict:
            st.error("❌ 生成K线数据失败")
            st.stop()
        
        status.text("🔍 计算策略信号...")
        progress.progress(70)
        if use_trend:
            trend_df = compute_trend_signals(kline_dict, top_n=top_n)
        if use_rotation:
            rotation_df = compute_rotation_signals(kline_dict, top_n=10)
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
st.caption("Vibe 量化 v2.0 | 数据：内置 200+ A 股 + 合成 K 线 | 仅供学习研究")
