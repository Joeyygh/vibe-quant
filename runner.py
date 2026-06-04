"""Vibe 量化系统 - 主控制器"""
import os
import yaml
import pandas as pd
from data import DataFetcher
from indicators import sma
from trend import TrendStrategy
from rotation import IndustryRotation
from factors import MultiFactor
from risk import RiskManager
from backtest import BacktestEngine

class VibeQuant:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.data = DataFetcher(cache_dir=self.config['system']['cache_dir'])
        self.trend = TrendStrategy(self.config['trend'])
        self.rotation = IndustryRotation(self.config['rotation'])
        self.factors = MultiFactor(self.config['factors'])
        self.risk = RiskManager(self.config['risk'])
        self.backtest = BacktestEngine(self.config['backtest'])

    def load_data(self, n_stocks=100, min_market_cap=50):
        print("加载数据...")
        stock_list = self.data.get_stock_list()
        if stock_list.empty:
            return {}
        if 'market_cap_yi' in stock_list.columns:
            stock_list = stock_list[stock_list['market_cap_yi'] >= min_market_cap]
        stock_list = stock_list.head(n_stocks)
        codes = stock_list['code'].tolist()
        kline_data = self.data.get_kline_batch(codes, start=self.config['data']['start_date'])
        name_map = dict(zip(stock_list['code'], stock_list['name']))
        for code, df in kline_data.items():
            df['name'] = name_map.get(code, '')
        return kline_data

    def get_industry_map(self):
        return self.data.get_industry_map()

    def run_trend_scan(self, kline_data, top_n=10):
        return self.trend.scan_market(kline_data, top_n=top_n)

    def run_rotation_scan(self, kline_data, industry_map):
        return self.rotation.generate_holdings(kline_data, industry_map)

    def run_factor_scan(self, kline_data):
        return self.factors.select_top_stocks(kline_data)

    def run_all(self, kline_data, industry_map):
        return {
            'trend': self.run_trend_scan(kline_data),
            'rotation': self.run_rotation_scan(kline_data, industry_map),
            'factors': self.run_factor_scan(kline_data),
        }

    def daily_report(self, n_stocks=50):
        kline_data = self.load_data(n_stocks=n_stocks)
        if not kline_data:
            return {}
        industry_map = self.get_industry_map()
        return self.run_all(kline_data, industry_map)


def create_vibe(config_path="config.yaml"):
    return VibeQuant(config_path)


if __name__ == "__main__":
    vibe = create_vibe()
    report = vibe.daily_report(n_stocks=30)
    for name, df in report.items():
        print(f"\n=== {name} ===")
        if df is None or df.empty:
            print("无信号")
        else:
            print(df.to_string())
