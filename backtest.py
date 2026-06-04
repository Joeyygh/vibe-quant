"""回测引擎"""
import pandas as pd
import numpy as np

class BacktestEngine:
    def __init__(self, config):
        self.initial_cash = config.get('initial_cash', 1_000_000)
        self.commission = config.get('commission', 0.0003)
        self.slippage = config.get('slippage', 0.001)

    def calc_metrics(self, nav):
        if nav.empty or len(nav) < 2:
            return {}
        total_return = (nav.iloc[-1] / nav.iloc[0]) - 1
        days = len(nav)
        years = max(days / 365, 0.1)
        annual_return = (1 + total_return) ** (1 / years) - 1
        cummax = nav.cummax()
        dd = (nav - cummax) / cummax
        max_drawdown = abs(dd.min())
        daily_ret = nav.pct_change().dropna()
        if daily_ret.std() > 0:
            sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252)
        else:
            sharpe = 0
        win_rate = (daily_ret > 0).sum() / max(len(daily_ret), 1)
        gains = daily_ret[daily_ret > 0]
        losses = daily_ret[daily_ret < 0]
        if len(losses) > 0 and losses.mean() != 0:
            profit_loss_ratio = abs(gains.mean() / losses.mean())
        else:
            profit_loss_ratio = 0
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
        }

    def backtest_rotation(self, kline_data, target_weights, rebalance_days=5):
        if target_weights.empty:
            return pd.Series()
        all_dates = sorted(set().union(*[set(df['date']) for df in kline_data.values() if df is not None]))
        all_dates = pd.to_datetime(all_dates)
        nav = pd.Series(index=all_dates, dtype=float)
        nav.iloc[0] = self.initial_cash
        holdings = {row['code']: 0 for _, row in target_weights.iterrows()}
        cash = self.initial_cash
        for i, date in enumerate(all_dates):
            date_str = date.strftime("%Y-%m-%d")
            portfolio_value = cash
            for code in holdings:
                df = kline_data.get(code)
                if df is None:
                    continue
                price_data = df[df['date'] <= date_str]
                if not price_data.empty:
                    portfolio_value += holdings[code] * price_data.iloc[-1]['close']
            nav.iloc[i] = portfolio_value
        return nav
