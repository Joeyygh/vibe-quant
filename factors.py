"""多因子选股模型"""
import pandas as pd
import numpy as np
from indicators import sma, momentum, volatility

class MultiFactor:
    def __init__(self, config):
        self.weights = config.get('weights', {
            'value': 0.20, 'quality': 0.25, 'growth': 0.20,
            'momentum': 0.25, 'volatility': 0.10
        })
        self.top_n = config.get('top_n', 10)

    def calc_value_score(self, kline_data):
        scores = {}
        for code, df in kline_data.items():
            if df is None or df.empty:
                continue
            try:
                year_low = df['low'].tail(250).min()
                year_high = df['high'].tail(250).max()
                if year_high > 0:
                    position = (df.iloc[-1]['close'] - year_low) / (year_high - year_low)
                    scores[code] = (1 - position) * 100
            except Exception:
                continue
        return pd.Series(scores)

    def calc_quality_score(self, kline_data):
        scores = {}
        for code, df in kline_data.items():
            if df is None or len(df) < 60:
                continue
            try:
                vol_60 = volatility(df['close'], 60)
                if not vol_60.empty and not pd.isna(vol_60.iloc[-1]):
                    v = vol_60.iloc[-1]
                    if v < 30:
                        scores[code] = 100
                    elif v < 50:
                        scores[code] = 70
                    else:
                        scores[code] = 30
            except Exception:
                continue
        return pd.Series(scores)

    def calc_growth_score(self, kline_data):
        scores = {}
        for code, df in kline_data.items():
            if df is None or len(df) < 120:
                continue
            try:
                ret_120 = (df.iloc[-1]['close'] / df.iloc[-120]['close'] - 1)
                if ret_120 > 0.30:
                    scores[code] = 100
                elif ret_120 > 0.10:
                    scores[code] = 70
                elif ret_120 > 0:
                    scores[code] = 50
                else:
                    scores[code] = 20
            except Exception:
                continue
        return pd.Series(scores)

    def calc_momentum_score(self, kline_data):
        scores = {}
        for code, df in kline_data.items():
            if df is None or len(df) < 60:
                continue
            try:
                mom_20 = momentum(df['close'], 20)
                if not pd.isna(mom_20.iloc[-1]):
                    m = mom_20.iloc[-1]
                    if m > 10:
                        scores[code] = 100
                    elif m > 0:
                        scores[code] = 70
                    elif m > -5:
                        scores[code] = 40
                    else:
                        scores[code] = 10
            except Exception:
                continue
        return pd.Series(scores)

    def calc_total_score(self, kline_data):
        value = self.calc_value_score(kline_data)
        quality = self.calc_quality_score(kline_data)
        growth = self.calc_growth_score(kline_data)
        mom = self.calc_momentum_score(kline_data)
        all_codes = set(value.index) | set(quality.index) | set(growth.index) | set(mom.index)
        rows = []
        for code in all_codes:
            score = 0
            score += value.get(code, 0) * self.weights.get('value', 0.20)
            score += quality.get(code, 0) * self.weights.get('quality', 0.25)
            score += growth.get(code, 0) * self.weights.get('growth', 0.20)
            score += mom.get(code, 0) * self.weights.get('momentum', 0.25)
            df = kline_data.get(code)
            if df is not None and not df.empty:
                rows.append({
                    'code': code,
                    'name': df.iloc[-1].get('name', ''),
                    'price': df.iloc[-1]['close'],
                    'pct_change': df.iloc[-1].get('pct_change', 0),
                    'total_score': score,
                })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values('total_score', ascending=False)

    def select_top_stocks(self, kline_data):
        df = self.calc_total_score(kline_data)
        if df.empty:
            return df
        return df.head(self.top_n)
