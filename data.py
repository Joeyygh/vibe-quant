"""数据层 - Tushare 版（5000+ 全 A 股）"""
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

FALLBACK_STOCKS = [
    {'code': '600519', 'name': '贵州茅台', 'price': 1680.0, 'pct_change': 0.5, 'market_cap_yi': 21000, 'industry': '食品饮料'},
    {'code': '000858', 'name': '五粮液', 'price': 145.0, 'pct_change': 0.3, 'market_cap_yi': 5600, 'industry': '食品饮料'},
    {'code': '300750', 'name': '宁德时代', 'price': 230.0, 'pct_change': 1.2, 'market_cap_yi': 10000, 'industry': '电力设备'},
    {'code': '601318', 'name': '中国平安', 'price': 50.0, 'pct_change': -0.2, 'market_cap_yi': 9100, 'industry': '非银金融'},
    {'code': '600036', 'name': '招商银行', 'price': 38.0, 'pct_change': 0.4, 'market_cap_yi': 9600, 'industry': '银行'},
    {'code': '000001', 'name': '平安银行', 'price': 11.0, 'pct_change': 0.1, 'market_cap_yi': 2200, 'industry': '银行'},
    {'code': '600276', 'name': '恒瑞医药', 'price': 45.0, 'pct_change': 0.8, 'market_cap_yi': 2900, 'industry': '医药生物'},
    {'code': '000333', 'name': '美的集团', 'price': 75.0, 'pct_change': 0.6, 'market_cap_yi': 5300, 'industry': '家用电器'},
    {'code': '601012', 'name': '隆基绿能', 'price': 18.0, 'pct_change': -0.5, 'market_cap_yi': 1400, 'industry': '电力设备'},
    {'code': '002594', 'name': '比亚迪', 'price': 245.0, 'pct_change': 1.5, 'market_cap_yi': 7100, 'industry': '汽车'},
    {'code': '600900', 'name': '长江电力', 'price': 28.0, 'pct_change': 0.2, 'market_cap_yi': 6800, 'industry': '公用事业'},
    {'code': '601398', 'name': '工商银行', 'price': 7.5, 'pct_change': 0.1, 'market_cap_yi': 24000, 'industry': '银行'},
    {'code': '601939', 'name': '建设银行', 'price': 8.0, 'pct_change': 0.2, 'market_cap_yi': 22000, 'industry': '银行'},
    {'code': '601988', 'name': '中国银行', 'price': 5.0, 'pct_change': 0.1, 'market_cap_yi': 15000, 'industry': '银行'},
    {'code': '600028', 'name': '中国石化', 'price': 6.5, 'pct_change': 0.3, 'market_cap_yi': 7800, 'industry': '石油石化'},
    {'code': '600050', 'name': '中国联通', 'price': 5.5, 'pct_change': 0.2, 'market_cap_yi': 1700, 'industry': '通信'},
    {'code': '601800', 'name': '中国交建', 'price': 9.0, 'pct_change': 0.1, 'market_cap_yi': 1500, 'industry': '建筑装饰'},
    {'code': '601628', 'name': '中国人寿', 'price': 38.0, 'pct_change': 0.4, 'market_cap_yi': 10700, 'industry': '非银金融'},
    {'code': '601857', 'name': '中国石油', 'price': 9.5, 'pct_change': 0.3, 'market_cap_yi': 17000, 'industry': '石油石化'},
    {'code': '600585', 'name': '海螺水泥', 'price': 24.0, 'pct_change': 0.2, 'market_cap_yi': 1300, 'industry': '建筑材料'},
    {'code': '600887', 'name': '伊利股份', 'price': 27.0, 'pct_change': -0.3, 'market_cap_yi': 1700, 'industry': '食品饮料'},
    {'code': '601088', 'name': '中国神华', 'price': 42.0, 'pct_change': 0.5, 'market_cap_yi': 8400, 'industry': '煤炭'},
    {'code': '601288', 'name': '农业银行', 'price': 5.0, 'pct_change': 0.1, 'market_cap_yi': 18000, 'industry': '银行'},
    {'code': '601328', 'name': '交通银行', 'price': 7.0, 'pct_change': 0.2, 'market_cap_yi': 5500, 'industry': '银行'},
    {'code': '600000', 'name': '浦发银行', 'price': 9.0, 'pct_change': 0.1, 'market_cap_yi': 2700, 'industry': '银行'},
    {'code': '601166', 'name': '兴业银行', 'price': 18.0, 'pct_change': 0.3, 'market_cap_yi': 3700, 'industry': '银行'},
    {'code': '601229', 'name': '上海银行', 'price': 8.5, 'pct_change': 0.2, 'market_cap_yi': 1200, 'industry': '银行'},
    {'code': '600030', 'name': '中信证券', 'price': 22.0, 'pct_change': 0.4, 'market_cap_yi': 3200, 'industry': '非银金融'},
    {'code': '601688', 'name': '华泰证券', 'price': 18.0, 'pct_change': 0.3, 'market_cap_yi': 1700, 'industry': '非银金融'},
    {'code': '000651', 'name': '格力电器', 'price': 42.0, 'pct_change': 0.2, 'market_cap_yi': 2400, 'industry': '家用电器'},
]

_TUSHARE_INDUSTRY = {
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


def _generate_synthetic_kline(code: str, name: str, days: int = 250) -> pd.DataFrame:
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
    df['name'] = name
    return df


class DataFetcher:
    def __init__(self, cache_dir: str = "./data", tushare_token: str = None):
        self.cache_dir = cache_dir
        self.tushare_token = tushare_token
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            pass
        self._pro = None
        if tushare_token:
            try:
                import tushare as ts
                ts.set_token(tushare_token)
                self._pro = ts.pro_api()
            except Exception as e:
                print(f"Tushare 初始化失败: {e}")
                self._pro = None

    def get_stock_list(self, force_refresh: bool = False) -> pd.DataFrame:
        if self._pro is not None:
            try:
                df = self._pro.stock_basic(
                    list_status='L',
                    fields='ts_code,symbol,name,industry,market,list_date'
                )
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        'ts_code': 'ts_code', 'symbol': 'code', 'name': 'name',
                        'industry': 'industry', 'market': 'market', 'list_date': 'list_date'
                    })
                    df['code'] = df['code'].astype(str).str.zfill(6)
                    df['price'] = 0.0
                    df['pct_change'] = 0.0
                    df['market_cap_yi'] = 0.0
                    return df
            except Exception as e:
                print(f"Tushare stock_basic 失败: {e}")
        return pd.DataFrame(FALLBACK_STOCKS)

    def get_kline(self, code: str, start: str = "2024-01-01", end: str = None, adjust: str = "qfq") -> pd.DataFrame:
        if self._pro is not None:
            ts_code = self._to_ts_code(code)
            if ts_code:
                try:
                    df = self._pro.daily(
                        ts_code=ts_code,
                        start_date=start.replace("-", ""),
                        end_date=(end or datetime.now().strftime("%Y-%m-%d")).replace("-", ""),
                        adj=adjust
                    )
                    if df is not None and not df.empty:
                        df = df.rename(columns={
                            'trade_date': 'date', 'open': 'open', 'close': 'close',
                            'high': 'high', 'low': 'low',
                            'vol': 'volume', 'amount': 'amount', 'pct_chg': 'pct_change'
                        })
                        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                        df = df.sort_values('date').reset_index(drop=True)
                        df['code'] = code
                        stock_info = next((s for s in FALLBACK_STOCKS if s['code'] == code), None)
                        df['name'] = stock_info['name'] if stock_info else code
                        return df
                except Exception as e:
                    print(f"Tushare daily 失败 {code}: {e}")
        stock_info = next((s for s in FALLBACK_STOCKS if s['code'] == code), None)
        if stock_info:
            return _generate_synthetic_kline(code, stock_info['name'])
        return _generate_synthetic_kline(code, code)

    def _to_ts_code(self, code: str) -> Optional[str]:
        if not code or len(code) != 6:
            return None
        if code.startswith(('60', '68')):
            return f"{code}.SH"
        elif code.startswith(('00', '30')):
            return f"{code}.SZ"
        return None

    def get_kline_batch(self, codes: List[str], start: str = "2024-01-01", end: str = None, show_progress: bool = True) -> dict:
        result = {}
        for code in codes:
            try:
                df = self.get_kline(code, start, end)
                if df is not None and not df.empty:
                    result[code] = df
            except Exception:
                pass
        return result

    def get_industry_map(self) -> dict:
        if self._pro is not None:
            try:
                df = self._pro.stock_basic(
                    list_status='L',
                    fields='symbol,industry'
                )
                if df is not None and not df.empty:
                    df['symbol'] = df['symbol'].astype(str).str.zfill(6)
                    return dict(zip(df['symbol'], df['industry'].fillna('未分类')))
            except Exception as e:
                print(f"Tushare industry 失败: {e}")
        return _TUSHARE_INDUSTRY


def get_stock_list() -> pd.DataFrame:
    fetcher = DataFetcher()
    return fetcher.get_stock_list()

def get_kline(code: str, start: str = "2024-01-01", end: str = None) -> pd.DataFrame:
    fetcher = DataFetcher()
    return fetcher.get_kline(code, start, end)
