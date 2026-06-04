"""趋势策略 - 宽松版"""
import pandas as pd
import numpy as np
from indicators import sma, volume_ratio

class TrendStrategy:
    def __init__(self, config):
        self.lookback = config.get('lookback', 20)
        self.vol_mult = config.get('vol_mult', 0.0)
        self.stop_loss = config.get('stop_loss', 0.08)
        self.take_profit = config.get('take_profit', 0.30)
        self.trailing_stop = config.get('trailing_stop', 0.10)
        self.max_hold_days = config.get('max_hold_days', 60)

    def generate_signal(self, df):
        """生成买卖信号"""
        df = df.copy().sort_values('date').reset_index(drop=True)
        df['ma20'] = sma(df['close'], 20)
        df['ma5'] = sma(df['close'], 5)
        df['vol_ratio'] = volume_ratio(df['volume'], 20)
        # 突破：收盘价 > 过去 N 日最高
        df['high_n'] = df['high'].rolling(self.lookback, min_periods=1).max()
        df['breakout'] = df['close'] > df['high_n'].shift(1)
        # 量能放大（阈值可降到 0 表示只看价格）
        df['vol_ok'] = df['vol_ratio'] > self.vol_mult
        # 趋势：5日均线上穿20日均线
        df['trend_ok'] = df['ma5'] > df['ma20']
        # 综合：突破 或 强势趋势
        df['buy_signal'] = (df['breakout'] | (df['trend_ok'] & (df['ma5'].pct_change(5) > 0.05)))
        return df

    def scan_market(self, kline_data, top_n=20):
        """扫描全市场"""
        results = []
        for code, df in kline_data.items():
            if df is None or len(df) < self.lookback + 5:
                continue
            try:
                sig_df = self.generate_signal(df)
                latest = sig_df.iloc[-1]
                if latest.get('buy_signal', False):
                    results.append({
                        'code': code,
                        'name': latest.get('name', ''),
                        'price': round(latest.get('close', 0), 2),
                        'pct_change': round(latest.get('pct_change', 0), 2),
                        'vol_ratio': round(latest.get('vol_ratio', 0), 2),
                    })
            except Exception:
                continue
        if not results:
            return pd.DataFrame()
        return pd.DataFrame(results).head(top_n)
