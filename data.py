"""数据层 - 精简版"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List
import warnings
warnings.filterwarnings('ignore')

class DataFetcher:
    def __init__(self, cache_dir="./data"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_stock_list(self):
        """获取全A股列表"""
        cache_file = os.path.join(self.cache_dir, "stock_list.parquet")
        if os.path.exists(cache_file):
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
                '成交量': 'volume', '成交额': 'amount'
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
            print(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    def get_kline(self, code, start="2020-01-01", end=None):
        """获取K线数据"""
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")
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
                end_date=end.replace("-", ""), adjust="qfq"
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low',
                '成交量': 'volume', '成交额': 'amount'
            })
            df['date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d")
            df['code'] = code
            try:
                df.to_parquet(cache_file)
            except Exception:
                pass
            return df
        except Exception as e:
            print(f"获取K线失败: {e}")
            return pd.DataFrame()

    def get_kline_batch(self, codes: List[str], start="2020-01-01"):
        """批量获取K线"""
        return {code: self.get_kline(code, start) for code in codes}

    def get_industry_map(self):
        """获取行业分类"""
        try:
            import akshare as ak
            industry_map = {}
            boards = ak.stock_board_industry_name_em()
            for _, b in boards.iterrows():
                industry = b['板块名称']
                stocks = ak.stock_board_industry_cons_em(symbol=industry)
                if stocks is not None and not stocks.empty:
                    for _, s in stocks.iterrows():
                        industry_map[str(s['代码']).zfill(6)] = industry
            return industry_map
        except Exception as e:
            print(f"行业分类获取失败: {e}")
            return {}
