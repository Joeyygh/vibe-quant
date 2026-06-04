"""技术指标库 - 精简版"""
import pandas as pd
import numpy as np

def sma(series, period=20):
    return series.rolling(window=period, min_periods=1).mean()

def ema(series, period=20):
    return series.ewm(span=period, adjust=False).mean()

def macd(close, fast=12, slow=26, signal=9):
    """返回 DIF, DEA, MACD柱"""
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    return dif, dea, (dif - dea) * 2

def rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def boll(close, period=20, std_mult=2.0):
    """布林带"""
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=1).std()
    return mid, mid + std_mult * std, mid - std_mult * std

def atr(df, period=14):
    """平均真实波幅"""
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def volume_ratio(volume, period=20):
    return volume / sma(volume, period).replace(0, np.nan)

def momentum(close, period=20):
    return (close / close.shift(period) - 1) * 100

def volatility(close, period=60):
    ret = close.pct_change()
    return ret.rolling(window=period, min_periods=period//2).std() * np.sqrt(252) * 100
