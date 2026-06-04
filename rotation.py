"""行业轮动策略"""
import pandas as pd
import numpy as np

class IndustryRotation:
    def __init__(self, config):
        self.lookback = config.get('lookback', 20)
        self.top_n = config.get('top_n', 5)
        self.stocks_per_industry = config.get('stocks_per_industry', 3)
        self.min_strength = config.get('min_industry_strength', 0.02)

    def get_industry_performance(self, kline_data, industry_map):
        """计算行业整体表现"""
        industry_returns = {}
        for code, df in kline_data.items():
            if df is None or len(df) < self.lookback + 1:
                continue
            industry = industry_map.get(code, '其他')
            if industry == '其他':
                continue
            ret = (df.iloc[-1]['close'] / df.iloc[-self.lookback]['close'] - 1)
            if industry not in industry_returns:
                industry_returns[industry] = []
            industry_returns[industry].append(ret)
        rows = []
        for ind, rets in industry_returns.items():
            if len(rets) < 3:
                continue
            rows.append({
                'industry': ind,
                'avg_return': np.mean(rets),
                'n_stocks': len(rets),
            })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values('avg_return', ascending=False)

    def get_top_industries(self, industry_perf):
        if industry_perf.empty:
            return []
        df = industry_perf[industry_perf['avg_return'] > self.min_strength]
        return df.head(self.top_n)['industry'].tolist()

    def select_stocks_in_industry(self, industry, kline_data, industry_map, top_k=None):
        if top_k is None:
            top_k = self.stocks_per_industry
        candidates = []
        for code, df in kline_data.items():
            if industry_map.get(code) != industry:
                continue
            if df is None or len(df) < self.lookback + 1:
                continue
            try:
                ret = (df.iloc[-1]['close'] / df.iloc[-self.lookback]['close'] - 1)
                candidates.append({
                    'code': code,
                    'name': df.iloc[-1].get('name', ''),
                    'return': ret,
                    'price': df.iloc[-1]['close'],
                })
            except Exception:
                continue
        if not candidates:
            return []
        df_cand = pd.DataFrame(candidates)
        return df_cand.sort_values('return', ascending=False).head(top_k)['code'].tolist()

    def generate_holdings(self, kline_data, industry_map):
        ind_perf = self.get_industry_performance(kline_data, industry_map)
        top_industries = self.get_top_industries(ind_perf)
        if not top_industries:
            return pd.DataFrame()
        holdings = []
        weight_per_industry = 1.0 / len(top_industries)
        weight_per_stock = weight_per_industry / self.stocks_per_industry
        for ind in top_industries:
            codes = self.select_stocks_in_industry(ind, kline_data, industry_map)
            for code in codes:
                if code in kline_data:
                    df = kline_data[code]
                    holdings.append({
                        'code': code,
                        'name': df.iloc[-1].get('name', ''),
                        'industry': ind,
                        'target_weight': weight_per_stock,
                        'price': df.iloc[-1]['close'],
                    })
        return pd.DataFrame(holdings)
