"""风控模块"""
import pandas as pd

class RiskManager:
    def __init__(self, config):
        self.max_position_pct = config.get('max_position_pct', 0.20)
        self.max_industry_pct = config.get('max_industry_pct', 0.30)
        self.max_total_position = config.get('max_total_position', 0.80)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)
        self.max_drawdown_alert = config.get('max_drawdown_alert', 0.15)

    def check_position_limit(self, weights):
        adjusted = {}
        for code, w in weights.items():
            if w > self.max_position_pct:
                adjusted[code] = self.max_position_pct
            else:
                adjusted[code] = w
        return adjusted

    def check_industry_limit(self, weights, industry_map):
        ind_total = {}
        for code, w in weights.items():
            ind = industry_map.get(code, '其他')
            ind_total[ind] = ind_total.get(ind, 0) + w
        adjusted = weights.copy()
        for ind, total in ind_total.items():
            if total > self.max_industry_pct:
                scale = self.max_industry_pct / total
                for code in weights:
                    if industry_map.get(code) == ind:
                        adjusted[code] *= scale
        return adjusted

    def check_total_position(self, weights):
        total = sum(weights.values())
        if total > self.max_total_position:
            scale = self.max_total_position / total
            return {k: v * scale for k, v in weights.items()}
        return weights

    def apply_all_checks(self, weights, industry_map=None):
        weights = self.check_position_limit(weights)
        if industry_map:
            weights = self.check_industry_limit(weights, industry_map)
        weights = self.check_total_position(weights)
        return weights

    def calc_max_drawdown(self, nav):
        cummax = nav.cummax()
        dd = (nav - cummax) / cummax
        return abs(dd.min())
