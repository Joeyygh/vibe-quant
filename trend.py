"""趋势策略 - 精简版（海龟交易法则）"""
import pandas as pd
import numpy as np
from indicators import sma, atr, volume_ratio

class TrendStrategy:
    def __init__(self, config):
        self.lookback = config.get('lookback', 20)
        self.vol_mult = config.get('vol_mult', 1.5)
        self.stop_loss = config.get('stop_loss', 0.08)
        self.take_profit = config.get('take_profit', 0.30)
        self.trailing_stop = config.get('trailing_stop', 0.10)

    def generate_signal(self, df):
        """生成买卖信号"""
        df = df.copy().sort_values('date').reset_index(drop=True)
        df['ma20'] = sma(df['close'], 20)
        df['vol_ratio'] = volume_ratio(df['volume'], 20)
        df['high_n'] = df['high'].rolling(self.lookback, min_periods=1).max()
        df['breakout'] = df['close'] > df['high_n'].shift(1)
        df['vol_ok'] = df['vol_ratio'] > self.vol_mult
        df['trend_ok'] = df['close'] > df['ma20']
        df['buy_signal'] = df['breakout'] & df['vol_ok'] & df['trend_ok']
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
                        'price': latest.get('close', 0),
                        'pct_change': latest.get('pct_change', 0),
                        'vol_ratio': round(latest.get('vol_ratio', 0), 2),
                    })
            except Exception:
                continue
        if not results:
            return pd.DataFrame()
        df_result = pd.DataFrame(results).head(top_n)
        return df_result.sort_values('vol_ratio', ascending=False)
