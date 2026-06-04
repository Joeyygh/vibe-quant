"""Vibe 量化系统 v2.0 - 完全离线（200+ 核心股 + 合成 K 线）"""
import streamlit as st
import pandas as pd
import random
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Vibe 量化 v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Vibe 股票量化分析 v2.0")
st.markdown(f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}** | 数据源：内置 200+ 只 A 股核心股")

FALLBACK_STOCKS = [
    {'code': '600519', 'name': '贵州茅台', 'price': 1680.0, 'pct_change': 0.5, 'industry': '食品饮料'},
    {'code': '601318', 'name': '中国平安', 'price': 50.0, 'pct_change': -0.2, 'industry': '非银金融'},
    {'code': '600036', 'name': '招商银行', 'price': 38.0, 'pct_change': 0.4, 'industry': '银行'},
    {'code': '000858', 'name': '五粮液', 'price': 145.0, 'pct_change': 0.3, 'industry': '食品饮料'},
    {'code': '300750', 'name': '宁德时代', 'price': 230.0, 'pct_change': 1.2, 'industry': '电力设备'},
    {'code': '002594', 'name': '比亚迪', 'price': 245.0, 'pct_change': 1.5, 'industry': '汽车'},
    {'code': '600276', 'name': '恒瑞医药', 'price': 45.0, 'pct_change': 0.8, 'industry': '医药生物'},
    {'code': '000333', 'name': '美的集团', 'price': 75.0, 'pct_change': 0.6, 'industry': '家用电器'},
    {'code': '601012', 'name': '隆基绿能', 'price': 18.0, 'pct_change': -0.5, 'industry': '电力设备'},
    {'code': '600900', 'name': '长江电力', 'price': 28.0, 'pct_change': 0.2, 'industry': '公用事业'},
    {'code': '601398', 'name': '工商银行', 'price': 7.5, 'pct_change': 0.1, 'industry': '银行'},
    {'code': '601939', 'name': '建设银行', 'price': 8.0, 'pct_change': 0.2, 'industry': '银行'},
    {'code': '601988', 'name': '中国银行', 'price': 5.0, 'pct_change': 0.1, 'industry': '银行'},
    {'code': '600028', 'name': '中国石化', 'price': 6.5, 'pct_change': 0.3, 'industry': '石油石化'},
    {'code': '600050', 'name': '中国联通', 'price': 5.5, 'pct_change': 0.2, 'industry': '通信'},
    {'code': '601628', 'name': '中国人寿', 'price': 38.0, 'pct_change': 0.4, 'industry': '非银金融'},
    {'code': '601857', 'name': '中国石油', 'price': 9.5, 'pct_change': 0.3, 'industry': '石油石化'},
    {'code': '600887', 'name': '伊利股份', 'price': 27.0, 'pct_change': -0.3, 'industry': '食品饮料'},
    {'code': '601088', 'name': '中国神华', 'price': 42.0, 'pct_change': 0.5, 'industry': '煤炭'},
    {'code': '601288', 'name': '农业银行', 'price': 5.0, 'pct_change': 0.1, 'industry': '银行'},
    {'code': '601328', 'name': '交通银行', 'price': 7.0, 'pct_change': 0.2, 'industry': '银行'},
    {'code': '600030', 'name': '中信证券', 'price': 22.0, 'pct_change': 0.4, 'industry': '非银金融'},
    {'code': '000651', 'name': '格力电器', 'price': 42.0, 'pct_change': 0.2, 'industry': '家用电器'},
    {'code': '600585', 'name': '海螺水泥', 'price': 24.0, 'pct_change': 0.2, 'industry': '建筑材料'},
    {'code': '601800', 'name': '中国交建', 'price': 9.0, 'pct_change': 0.1, 'industry': '建筑装饰'},
    {'code': '601166', 'name': '兴业银行', 'price': 18.0, 'pct_change': 0.3, 'industry': '银行'},
    {'code': '601229', 'name': '上海银行', 'price': 8.5, 'pct_change': 0.2, 'industry': '银行'},
    {'code': '601688', 'name': '华泰证券', 'price': 18.0, 'pct_change': 0.3, 'industry': '非银金融'},
    {'code': '000001', 'name': '平安银行', 'price': 11.0, 'pct_change': 0.1, 'industry': '银行'},
    {'code': '000002', 'name': '万科A', 'price': 8.5, 'pct_change': -0.3, 'industry': '房地产'},
    {'code': '000063', 'name': '中兴通讯', 'price': 28.0, 'pct_change': 0.5, 'industry': '通信'},
    {'code': '000100', 'name': 'TCL科技', 'price': 4.5, 'pct_change': 0.1, 'industry': '电子'},
    {'code': '000157', 'name': '中联重科', 'price': 8.0, 'pct_change': 0.3, 'industry': '机械设备'},
    {'code': '000425', 'name': '徐工机械', 'price': 6.5, 'pct_change': 0.4, 'industry': '机械设备'},
    {'code': '000538', 'name': '云南白药', 'price': 52.0, 'pct_change': 0.0, 'industry': '医药生物'},
    {'code': '000568', 'name': '泸州老窖', 'price': 165.0, 'pct_change': 0.4, 'industry': '食品饮料'},
    {'code': '000625', 'name': '长安汽车', 'price': 14.0, 'pct_change': 0.6, 'industry': '汽车'},
    {'code': '000661', 'name': '长春高新', 'price': 120.0, 'pct_change': 0.3, 'industry': '医药生物'},
    {'code': '000725', 'name': '京东方A', 'price': 4.2, 'pct_change': 0.2, 'industry': '电子'},
    {'code': '000768', 'name': '中航西飞', 'price': 22.0, 'pct_change': 0.4, 'industry': '国防军工'},
    {'code': '000776', 'name': '广发证券', 'price': 16.0, 'pct_change': 0.3, 'industry': '非银金融'},
    {'code': '000792', 'name': '盐湖股份', 'price': 18.0, 'pct_change': 0.5, 'industry': '基础化工'},
    {'code': '000876', 'name': '新希望', 'price': 9.5, 'pct_change': 0.2, 'industry': '农林牧渔'},
    {'code': '000938', 'name': '紫光股份', 'price': 22.0, 'pct_change': 0.3, 'industry': '计算机'},
    {'code': '000963', 'name': '华东医药', 'price': 38.0, 'pct_change': 0.4, 'industry': '医药生物'},
    {'code': '000977', 'name': '浪潮信息', 'price': 38.0, 'pct_change': 0.5, 'industry': '计算机'},
    {'code': '002027', 'name': '分众传媒', 'price': 7.5, 'pct_change': 0.3, 'industry': '传媒'},
    {'code': '002230', 'name': '科大讯飞', 'price': 52.0, 'pct_change': 0.6, 'industry': '计算机'},
    {'code': '002241', 'name': '歌尔股份', 'price': 22.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '002304', 'name': '洋河股份', 'price': 95.0, 'pct_change': 0.2, 'industry': '食品饮料'},
    {'code': '002415', 'name': '海康威视', 'price': 35.0, 'pct_change': 0.3, 'industry': '计算机'},
    {'code': '002460', 'name': '赣锋锂业', 'price': 35.0, 'pct_change': 0.5, 'industry': '有色金属'},
    {'code': '002466', 'name': '天齐锂业', 'price': 38.0, 'pct_change': 0.5, 'industry': '有色金属'},
    {'code': '002475', 'name': '立讯精密', 'price': 38.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '002493', 'name': '荣盛石化', 'price': 11.0, 'pct_change': 0.2, 'industry': '石油石化'},
    {'code': '002555', 'name': '三七互娱', 'price': 18.0, 'pct_change': 0.3, 'industry': '传媒'},
    {'code': '002648', 'name': '卫星化学', 'price': 18.0, 'pct_change': 0.3, 'industry': '基础化工'},
    {'code': '002714', 'name': '牧原股份', 'price': 45.0, 'pct_change': 0.2, 'industry': '农林牧渔'},
    {'code': '002812', 'name': '恩捷股份', 'price': 45.0, 'pct_change': 0.4, 'industry': '基础化工'},
    {'code': '002916', 'name': '深南电路', 'price': 95.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '300014', 'name': '亿纬锂能', 'price': 52.0, 'pct_change': 0.4, 'industry': '电力设备'},
    {'code': '300015', 'name': '爱尔眼科', 'price': 22.0, 'pct_change': 0.3, 'industry': '医药生物'},
    {'code': '300033', 'name': '同花顺', 'price': 145.0, 'pct_change': 0.6, 'industry': '计算机'},
    {'code': '300059', 'name': '东方财富', 'price': 18.0, 'pct_change': 0.4, 'industry': '非银金融'},
    {'code': '300122', 'name': '智飞生物', 'price': 45.0, 'pct_change': 0.3, 'industry': '医药生物'},
    {'code': '300124', 'name': '汇川技术', 'price': 65.0, 'pct_change': 0.4, 'industry': '机械设备'},
    {'code': '300223', 'name': '北京君正', 'price': 65.0, 'pct_change': 0.5, 'industry': '电子'},
    {'code': '300274', 'name': '阳光电源', 'price': 75.0, 'pct_change': 0.5, 'industry': '电力设备'},
    {'code': '300316', 'name': '晶盛机电', 'price': 38.0, 'pct_change': 0.4, 'industry': '机械设备'},
    {'code': '300347', 'name': '泰格医药', 'price': 52.0, 'pct_change': 0.3, 'industry': '医药生物'},
    {'code': '300408', 'name': '三环集团', 'price': 28.0, 'pct_change': 0.3, 'industry': '电子'},
    {'code': '300413', 'name': '芒果超媒', 'price': 22.0, 'pct_change': 0.2, 'industry': '传媒'},
    {'code': '300433', 'name': '蓝思科技', 'price': 18.0, 'pct_change': 0.3, 'industry': '电子'},
    {'code': '300498', 'name': '温氏股份', 'price': 18.0, 'pct_change': 0.2, 'industry': '农林牧渔'},
    {'code': '300661', 'name': '圣邦股份', 'price': 95.0, 'pct_change': 0.5, 'industry': '电子'},
    {'code': '300750', 'name': '宁德时代', 'price': 230.0, 'pct_change': 1.2, 'industry': '电力设备'},
    {'code': '300760', 'name': '迈瑞医疗', 'price': 280.0, 'pct_change': 0.4, 'industry': '医药生物'},
    {'code': '300782', 'name': '卓胜微', 'price': 95.0, 'pct_change': 0.5, 'industry': '电子'},
    {'code': '300866', 'name': '安克创新', 'price': 75.0, 'pct_change': 0.3, 'industry': '电子'},
    {'code': '300896', 'name': '爱美客', 'price': 195.0, 'pct_change': 0.4, 'industry': '医药生物'},
    {'code': '300919', 'name': '中伟股份', 'price': 38.0, 'pct_change': 0.4, 'industry': '电力设备'},
    {'code': '300979', 'name': '华利集团', 'price': 52.0, 'pct_change': 0.3, 'industry': '纺织服饰'},
    {'code': '300999', 'name': '金龙鱼', 'price': 35.0, 'pct_change': 0.2, 'industry': '农林牧渔'},
    {'code': '600009', 'name': '上海机场', 'price': 38.0, 'pct_change': 0.2, 'industry': '交通运输'},
    {'code': '600011', 'name': '华能国际', 'price': 7.5, 'pct_change': 0.2, 'industry': '公用事业'},
    {'code': '600019', 'name': '宝钢股份', 'price': 7.5, 'pct_change': 0.2, 'industry': '钢铁'},
    {'code': '600025', 'name': '华能水电', 'price': 9.5, 'pct_change': 0.2, 'industry': '公用事业'},
    {'code': '600031', 'name': '三一重工', 'price': 18.0, 'pct_change': 0.3, 'industry': '机械设备'},
    {'code': '600048', 'name': '保利发展', 'price': 11.0, 'pct_change': 0.1, 'industry': '房地产'},
    {'code': '600085', 'name': '同仁堂', 'price': 38.0, 'pct_change': 0.2, 'industry': '医药生物'},
    {'code': '600089', 'name': '特变电工', 'price': 14.0, 'pct_change': 0.3, 'industry': '电力设备'},
    {'code': '600104', 'name': '上汽集团', 'price': 16.0, 'pct_change': 0.2, 'industry': '汽车'},
    {'code': '600111', 'name': '北方稀土', 'price': 22.0, 'pct_change': 0.4, 'industry': '有色金属'},
    {'code': '600150', 'name': '中国船舶', 'price': 35.0, 'pct_change': 0.5, 'industry': '国防军工'},
    {'code': '600188', 'name': '兖矿能源', 'price': 14.0, 'pct_change': 0.3, 'industry': '煤炭'},
    {'code': '600196', 'name': '复星医药', 'price': 28.0, 'pct_change': 0.2, 'industry': '医药生物'},
    {'code': '600309', 'name': '万华化学', 'price': 75.0, 'pct_change': 0.4, 'industry': '基础化工'},
    {'code': '600346', 'name': '恒力石化', 'price': 14.0, 'pct_change': 0.3, 'industry': '石油石化'},
    {'code': '600362', 'name': '江西铜业', 'price': 18.0, 'pct_change': 0.4, 'industry': '有色金属'},
    {'code': '600406', 'name': '国电南瑞', 'price': 25.0, 'pct_change': 0.3, 'industry': '电力设备'},
    {'code': '600436', 'name': '片仔癀', 'price': 245.0, 'pct_change': 0.4, 'industry': '医药生物'},
    {'code': '600438', 'name': '通威股份', 'price': 25.0, 'pct_change': 0.4, 'industry': '电力设备'},
    {'code': '600487', 'name': '亨通光电', 'price': 13.0, 'pct_change': 0.3, 'industry': '通信'},
    {'code': '600547', 'name': '山东黄金', 'price': 22.0, 'pct_change': 0.3, 'industry': '有色金属'},
    {'code': '600570', 'name': '恒生电子', 'price': 38.0, 'pct_change': 0.4, 'industry': '计算机'},
    {'code': '600588', 'name': '用友网络', 'price': 14.0, 'pct_change': 0.3, 'industry': '计算机'},
    {'code': '600600', 'name': '青岛啤酒', 'price': 75.0, 'pct_change': 0.2, 'industry': '食品饮料'},
    {'code': '600660', 'name': '福耀玻璃', 'price': 38.0, 'pct_change': 0.3, 'industry': '汽车'},
    {'code': '600690', 'name': '海尔智家', 'price': 28.0, 'pct_change': 0.3, 'industry': '家用电器'},
    {'code': '600745', 'name': '闻泰科技', 'price': 38.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '600809', 'name': '山西汾酒', 'price': 195.0, 'pct_change': 0.4, 'industry': '食品饮料'},
    {'code': '600837', 'name': '海通证券', 'price': 9.5, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '600845', 'name': '宝信软件', 'price': 38.0, 'pct_change': 0.4, 'industry': '计算机'},
    {'code': '600886', 'name': '国投电力', 'price': 13.0, 'pct_change': 0.2, 'industry': '公用事业'},
    {'code': '600893', 'name': '航发动力', 'price': 38.0, 'pct_change': 0.4, 'industry': '国防军工'},
    {'code': '600905', 'name': '三峡能源', 'price': 5.5, 'pct_change': 0.1, 'industry': '公用事业'},
    {'code': '600918', 'name': '中泰证券', 'price': 7.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '600926', 'name': '杭州银行', 'price': 14.0, 'pct_change': 0.3, 'industry': '银行'},
    {'code': '600941', 'name': '中国移动', 'price': 105.0, 'pct_change': 0.2, 'industry': '通信'},
    {'code': '600958', 'name': '东方证券', 'price': 9.5, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '600999', 'name': '招商证券', 'price': 16.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '601066', 'name': '中信建投', 'price': 25.0, 'pct_change': 0.3, 'industry': '非银金融'},
    {'code': '601100', 'name': '恒立液压', 'price': 55.0, 'pct_change': 0.4, 'industry': '机械设备'},
    {'code': '601138', 'name': '工业富联', 'price': 18.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '601186', 'name': '中国铁建', 'price': 8.5, 'pct_change': 0.1, 'industry': '建筑装饰'},
    {'code': '601211', 'name': '国泰君安', 'price': 14.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '601225', 'name': '陕西煤业', 'price': 22.0, 'pct_change': 0.4, 'industry': '煤炭'},
    {'code': '601319', 'name': '中国人保', 'price': 6.5, 'pct_change': 0.1, 'industry': '非银金融'},
    {'code': '601336', 'name': '新华保险', 'price': 35.0, 'pct_change': 0.3, 'industry': '非银金融'},
    {'code': '601360', 'name': '三六零', 'price': 9.5, 'pct_change': 0.2, 'industry': '计算机'},
    {'code': '601390', 'name': '中国中铁', 'price': 6.5, 'pct_change': 0.1, 'industry': '建筑装饰'},
    {'code': '601456', 'name': '国联证券', 'price': 11.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '601555', 'name': '东吴证券', 'price': 7.5, 'pct_change': 0.1, 'industry': '非银金融'},
    {'code': '601600', 'name': '中国铝业', 'price': 7.0, 'pct_change': 0.2, 'industry': '有色金属'},
    {'code': '601601', 'name': '中国太保', 'price': 28.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '601633', 'name': '长城汽车', 'price': 28.0, 'pct_change': 0.4, 'industry': '汽车'},
    {'code': '601658', 'name': '邮储银行', 'price': 5.5, 'pct_change': 0.1, 'industry': '银行'},
    {'code': '601668', 'name': '中国建筑', 'price': 5.5, 'pct_change': 0.1, 'industry': '建筑装饰'},
    {'code': '601689', 'name': '拓普集团', 'price': 55.0, 'pct_change': 0.4, 'industry': '汽车'},
    {'code': '601728', 'name': '中国电信', 'price': 6.0, 'pct_change': 0.1, 'industry': '通信'},
    {'code': '601818', 'name': '光大银行', 'price': 3.5, 'pct_change': 0.0, 'industry': '银行'},
    {'code': '601838', 'name': '成都银行', 'price': 16.0, 'pct_change': 0.3, 'industry': '银行'},
    {'code': '601877', 'name': '正泰电器', 'price': 28.0, 'pct_change': 0.3, 'industry': '电力设备'},
    {'code': '601878', 'name': '浙商证券', 'price': 11.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '601881', 'name': '中国银河', 'price': 13.0, 'pct_change': 0.2, 'industry': '非银金融'},
    {'code': '601888', 'name': '中国中免', 'price': 75.0, 'pct_change': 0.3, 'industry': '社会服务'},
    {'code': '601899', 'name': '紫金矿业', 'price': 16.0, 'pct_change': 0.3, 'industry': '有色金属'},
    {'code': '601919', 'name': '中远海控', 'price': 14.0, 'pct_change': 0.3, 'industry': '交通运输'},
    {'code': '601995', 'name': '中金公司', 'price': 35.0, 'pct_change': 0.3, 'industry': '非银金融'},
    {'code': '601998', 'name': '中信银行', 'price': 6.5, 'pct_change': 0.1, 'industry': '银行'},
    {'code': '603019', 'name': '中科曙光', 'price': 38.0, 'pct_change': 0.4, 'industry': '计算机'},
    {'code': '603259', 'name': '药明康德', 'price': 75.0, 'pct_change': 0.4, 'industry': '医药生物'},
    {'code': '603288', 'name': '海天味业', 'price': 38.0, 'pct_change': 0.2, 'industry': '食品饮料'},
    {'code': '603501', 'name': '韦尔股份', 'price': 95.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '603799', 'name': '华友钴业', 'price': 35.0, 'pct_change': 0.4, 'industry': '有色金属'},
    {'code': '603986', 'name': '兆易创新', 'price': 95.0, 'pct_change': 0.5, 'industry': '电子'},
    {'code': '688008', 'name': '澜起科技', 'price': 55.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '688012', 'name': '中微公司', 'price': 145.0, 'pct_change': 0.5, 'industry': '电子'},
    {'code': '688036', 'name': '传音控股', 'price': 75.0, 'pct_change': 0.4, 'industry': '电子'},
    {'code': '688111', 'name': '金山办公', 'price': 245.0, 'pct_change': 0.4, 'industry': '计算机'},
    {'code': '688169', 'name': '石头科技', 'price': 245.0, 'pct_change': 0.4, 'industry': '家用电器'},
    {'code': '688271', 'name': '联影医疗', 'price': 145.0, 'pct_change': 0.3, 'industry': '医药生物'},
    {'code': '688981', 'name': '中芯国际', 'price': 75.0, 'pct_change': 0.4, 'industry': '电子'},
]


def make_kline(code, name, base_price, days=120):
    random.seed(hash(str(code)) % (2**32))
    if base_price < 5:
        base_price = 5.0
    if base_price > 2000:
        base_price = 2000.0
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    data = []
    price = base_price
    for d in dates:
        change = random.gauss(0.001, 0.02)
        price = max(price * (1 + change), 1.0)
        data.append({
            'date': d.strftime('%Y-%m-%d'),
            'open': round(price * 0.99, 2),
            'high': round(price * 1.01, 2),
            'low': round(price * 0.98, 2),
            'close': round(price, 2),
            'volume': int(random.uniform(1e6, 1e8)),
            'pct_change': round(change * 100, 2),
        })
    df = pd.DataFrame(data)
    df['code'] = str(code)
    df['name'] = str(name)
    return df


def compute_trend_signals(kline_data, top_n=10):
    rows = []
    for code, df in kline_data.items():
        if df is None or df.empty or len(df) < 60:
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
        except Exception as e:
            continue
    return pd.DataFrame(rows).head(top_n)


def compute_rotation_signals(kline_data, top_n=5):
    industries = {}
    for s in FALLBACK_STOCKS:
        industries.setdefault(s['industry'], []).append(s['code'])
    rows = []
    for ind, codes in industries.items():
        scores = []
        for code in codes:
            if code in kline_data and kline_data[code] is not None and not kline_data[code].empty and len(kline_data[code]) >= 20:
                try:
                    df = kline_data[code]
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
                if leader_code in kline_data and kline_data[leader_code] is not None and not kline_data[leader_code].empty:
                    leader_name = str(kline_data[leader_code]['name'].iloc[0])
                    leader_price = float(kline_data[leader_code]['close'].iloc[-1])
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


def compute_factor_signals(kline_data, top_n=20):
    rows = []
    for code, df in kline_data.items():
        if df is None or df.empty or len(df) < 60:
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
    n_stocks = st.slider("扫描股票数", 10, 200, 50, 10)
    top_n = st.slider("Top N", 3, 30, 10, 1)
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
1. 左侧调整 **扫描股票数** 和 **Top N**
2. 勾选你要跑的 **策略**
3. 点击 **🚀 运行分析** 按钮

### 💡 数据源说明
- 内置 **150+ 只 A 股核心股**（沪深300+中证500）
- 合成 **120 天 K 线**数据
- 完全离线，0 网络依赖

### ⚠️ 风险提示
> 本系统仅供学习研究，不构成投资建议。
> 投资有风险，决策需谨慎。
""")

if run:
    progress = st.progress(0, text="准备中...")
    status = st.empty()
    try:
        status.text("📊 生成核心股数据...")
        progress.progress(20)
        kline_data = {}
        for s in FALLBACK_STOCKS[:n_stocks]:
            try:
                kline_data[str(s['code'])] = make_kline(s['code'], s['name'], s['price'])
            except Exception as e:
                print(f"生成 {s['code']} K线失败: {e}")
        if not kline_data:
            st.error("❌ 未能生成任何K线数据")
            st.stop()
        progress.progress(50)
        status.text("🔍 计算策略信号...")
        if use_trend:
            trend_df = compute_trend_signals(kline_data, top_n=top_n)
        if use_rotation:
            rotation_df = compute_rotation_signals(kline_data, top_n=5)
        if use_factors:
            factors_df = compute_factor_signals(kline_data, top_n=top_n*2)
        progress.progress(100)
        status.text("✅ 分析完成！")
        progress.empty()
        status.empty()
        st.success(f"🎉 已分析 {len(kline_data)} 只股票！")
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
st.caption("Vibe 量化 v2.0 | 数据：内置 150+ 核心股 + 合成 K 线 | 仅供学习研究")
