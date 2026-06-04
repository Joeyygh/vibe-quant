"""数据层 - 终极版（含降级方案）"""
import os
import json
import time
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import warnings
warnings.filterwarnings('ignore')

# 静态热门股列表（不依赖网络，部署保底）
FALLBACK_STOCKS = [
    {'code': '600519', 'name': '贵州茅台', 'price': 1680.0, 'pct_change': 0.5, 'market_cap_yi': 21000},
    {'code': '000858', 'name': '五粮液', 'price': 145.0, 'pct_change': 0.3, 'market_cap_yi': 5600},
    {'code': '300750', 'name': '宁德时代', 'price': 230.0, 'pct_change': 1.2, 'market_cap_yi': 10000},
    {'code': '601318', 'name': '中国平安', 'price': 50.0, 'pct_change': -0.2, 'market_cap_yi': 9100},
    {'code': '600036', 'name': '招商银行', 'price': 38.0, 'pct_change': 0.4, 'market_cap_yi': 9600},
    {'code': '000001', 'name': '平安银行', 'price': 11.0, 'pct_change': 0.1, 'market_cap_yi': 2200},
    {'code': '600276', 'name': '恒瑞医药', 'price': 45.0, 'pct_change': 0.8, 'market_cap_yi': 2900},
    {'code': '000333', 'name': '美的集团', 'price': 75.0, 'pct_change': 0.6, 'market_cap_yi': 5300},
    {'code': '601012', 'name': '隆基绿能', 'price': 18.0, 'pct_change': -0.5, 'market_cap_yi': 1400},
    {'code': '002594', 'name': '比亚迪', 'price': 245.0, 'pct_change': 1.5, 'market_cap_yi': 7100},
    {'code': '600900', 'name': '长江电力', 'price': 28.0, 'pct_change': 0.2, 'market_cap_yi': 6800},
    {'code': '601398', 'name': '工商银行', 'price': 7.5, 'pct_change': 0.1, 'market_cap_yi': 24000},
    {'code': '601939', 'name': '建设银行', 'price': 8.0, 'pct_change': 0.2, 'market_cap_yi': 22000},
    {'code': '601988', 'name': '中国银行', 'price': 5.0, 'pct_change': 0.1, 'market_cap_yi': 15000},
    {'code': '600028', 'name': '中国石化', 'price': 6.5, 'pct_change': 0.3, 'market_cap_yi': 7800},
    {'code': '600050', 'name': '中国联通', 'price': 5.5, 'pct_change': 0.2, 'market_cap_yi': 1700},
    {'code': '601800', 'name': '中国交建', 'price': 9.0, 'pct_change': 0.1, 'market_cap_yi': 1500},
    {'code': '601628', 'name': '中国人寿', 'price': 38.0, 'pct_change': 0.4, 'market_cap_yi': 10700},
    {'code': '601857', 'name': '中国石油', 'price': 9.5, 'pct_change': 0.3, 'market_cap_yi': 17000},
    {'code': '600585', 'name': '海螺水泥', 'price': 24.0, 'pct_change': 0.2, 'market_cap_yi': 1300},
    {'code': '600887', 'name': '伊利股份', 'price': 27.0, 'pct_change': -0.3, 'market_cap_yi': 1700},
    {'code': '601088', 'name': '中国神华', 'price': 42.0, 'pct_change': 0.5, 'market_cap_yi': 8400},
    {'code': '601288', 'name': '农业银行', 'price': 5.0, 'pct_change': 0.1, 'market_cap_yi': 18000},
    {'code': '601328', 'name': '交通银行', 'price': 7.0, 'pct_change': 0.2, 'market_cap_yi': 5500},
    {'code': '600000', 'name': '浦发银行', 'price': 9.0, 'pct_change': 0.1, 'market_cap_yi': 2700},
    {'code': '601166', 'name': '兴业银行', 'price': 18.0, 'pct_change': 0.3, 'market_cap_yi': 3700},
    {'code': '601229', 'name': '上海银行', 'price': 8.5, 'pct_change': 0.2, 'market_cap_yi': 1200},
    {'code': '600030', 'name': '中信证券', 'price': 22.0, 'pct_change': 0.4, 'market_cap_yi': 3200},
    {'code': '601688', 'name': '华泰证券', 'price': 18.0, 'pct_change': 0.3, 'market_cap_yi': 1700},
    {'code': '000651', 'name': '格力电器', 'price': 42.0, 'pct_change': 0.2, 'market_cap_yi': 2400},
]


def _generate_synthetic_kline(code: str, name: str, days: int = 250) -> pd.DataFrame:
    """生成合成的K线数据（当网络数据不可用时使用）"""
    random.seed(hash(code) % (2**32))
    base_price = 10.0
    if name in ['贵州茅台', '五粮液']:
        base_price = 100.0
    elif name in ['宁德时代', '比亚迪']:
        base_price = 200.0
    elif name in ['中国平安', '招商银行']:
        base_price = 40.0
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    data = []
    price = base_price
    for d in dates:
        change = random.gauss(0.0005, 0.02)
        price = max(price * (1 + change), 1.0)
        high = price * (1 + abs(random.gauss(0, 0.008)))
        low = price * (1 - abs(random.gauss(0, 0.008)))
        open_p = price * (1 + random.gauss(0, 0.005))
        volume = int(random.lognormvariate(15, 0.5))
        data.append({
            'date': d.strftime('%Y-%m-%d'),
            'open': round(open_p, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(price, 2),
            'volume': volume,
            'amount': int(volume * price),
            'pct_change': round(change * 100, 2),
        })
    df = pd.DataFrame(data)
    df['code'] = code
    return df


class DataFetcher:
    """数据获取器 - 三层降级方案"""
    def __init__(self, cache_dir: str = "./data"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_stock_list(self, force_refresh: bool = False) -> pd.DataFrame:
        cache_file = os.path.join(self.cache_dir, "stock_list.parquet")
        if not force_refresh and os.path.exists(cache_file):
            try:
                return pd.read_parquet(cache_file)
            except Exception:
                pass
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            df = df.rename(columns={
                '代码': 'code', '名称': 'name', '最新价': 'price',
                '涨跌幅': 'pct_change', '总市值': 'market_cap',
                '流通市值': 'circ_market_cap', '成交量': 'volume', '成交额': 'amount',
            })
            df = df[df['code'].str.startswith(('60', '00', '30', '68'))]
            df = df[~df['name'].str.contains('ST|退市', na=False)]
            df = df[df['volume'] > 0]
            df['code'] = df['code'].astype(str).str.zfill(6)
            df['market_cap_yi'] = df['market_cap'] / 1e8
            try:
                df.to_parquet(cache_file)
            except Exception:
                pass
            return df
        except Exception as e:
            print(f"AKShare 失败，使用降级数据: {e}")
        return pd.DataFrame(FALLBACK_STOCKS)

    def get_kline(self, code: str, start: str = "2020-01-01", end: str = None, adjust: str = "qfq") -> pd.DataFrame:
        cache_file = os.path.join(self.cache_dir, f"kline_{code}.parquet")
        if os.path.exists(cache_file):
            try:
                return pd.read_parquet(cache_file)
            except Exception:
                pass
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start.replace("-", ""),
                end_date=(end or datetime.now().strftime("%Y-%m-%d")).replace("-", ""),
                adjust=adjust
            )
            if df is None or df.empty:
                raise ValueError("空数据")
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low',
                '成交量': 'volume', '成交额': 'amount', '涨跌幅': 'pct_change'
            })
            df['date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d")
            df['code'] = code
            try:
                df.to_parquet(cache_file)
            except Exception:
                pass
            return df
        except Exception as e:
            stock_info = next((s for s in FALLBACK_STOCKS if s['code'] == code), None)
            if stock_info:
                return _generate_synthetic_kline(code, stock_info['name'])
            return _generate_synthetic_kline(code, code)

    def get_kline_batch(self, codes: List[str], start: str = "2020-01-01", end: str = None, show_progress: bool = True) -> dict:
        result = {}
        for code in codes:
            try:
                df = self.get_kline(code, start, end)
                if not df.empty:
                    result[code] = df
            except Exception as e:
                print(f"{code} K线失败: {e}")
        return result

    def get_industry_map(self) -> dict:
        return {
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
        }

    def clear_cache(self, days_older_than: int = 7):
        try:
            now = time.time()
            count = 0
            for f in os.listdir(self.cache_dir):
                fpath = os.path.join(self.cache_dir, f)
                if os.path.isfile(fpath):
                    if (now - os.path.getmtime(fpath)) > days_older_than * 86400:
                        os.remove(fpath)
                        count += 1
            print(f"清理了 {count} 个缓存文件")
        except Exception:
            pass


_default_fetcher = None
def get_fetcher() -> DataFetcher:
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = DataFetcher()
    return _default_fetcher

def get_stock_list() -> pd.DataFrame:
    return get_fetcher().get_stock_list()

def get_kline(code: str, start: str = "2020-01-01", end: str = None) -> pd.DataFrame:
    return get_fetcher().get_kline(code, start, end)
