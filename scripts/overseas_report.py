#!/usr/bin/env python3
"""
A 股盘前外围影响报告
====================================
数据源: Yahoo Finance (美股/港股/商品/外汇/富时A50)
用途: 早上 7:00 之前出, 让用户在 9:30 开盘前看到外围对 A 股的预判
覆盖:
  ✓ 美股隔夜 (三大指数 + 关键科技股 + 中概股)
  ✓ 港股昨日 (恒生 / 恒生科技 / 权重股 腾讯阿里美团)
  ✓ 大宗商品 (原油 / 黄金 / 白银 / 铜 / 美元 / 离岸人民币)
  ✓ 富时中国 A50 期货 (夜盘)
  ✓ 自动预判: 对今日 A 股开盘/板块影响
  ✓ 持仓相关: 美股持仓用户的中概股映射 (阿里->A 股阿里概念)

输出: reports/overnight_{target_date}.md
"""
import os
import sys
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import numpy as np
import yfinance as yf

beijing_tz = timezone(timedelta(hours=8))
now = datetime.now(beijing_tz)
REPORTS_DIR = 'reports'
os.makedirs(REPORTS_DIR, exist_ok=True)

# 美股: 三大指数 + VIX + 关键科技股 + 中概股
US_TICKERS = {
    '^GSPC': '标普 500', '^DJI': '道琼斯', '^IXIC': '纳斯达克', '^VIX': 'VIX 恐慌',
    'AAPL': '苹果', 'MSFT': '微软', 'NVDA': '英伟达', 'TSLA': '特斯拉',
    'GOOGL': '谷歌', 'AMZN': '亚马逊', 'META': 'Meta',
    'BABA': '阿里巴巴', 'PDD': '拼多多', 'JD': '京东', 'BIDU': '百度',
    'NIO': '蔚来', 'XPEV': '小鹏', 'LI': '理想',
}

# 港股: 恒生指数 + 恒生科技 + 权重股
HK_TICKERS = {
    '^HSI': '恒生指数', '^HSTECH': '恒生科技',
    '0700.HK': '腾讯', '9988.HK': '阿里-W',
    '3690.HK': '美团', '9618.HK': '京东-W', '9999.HK': '网易',
    '1810.HK': '小米', '1211.HK': '比亚迪', '1024.HK': '快手',
    '2269.HK': '药明生物', '0941.HK': '中移动',
}

# 商品 + 外汇
COMMODITY_TICKERS = {
    'CL=F': 'WTI 原油', 'BZ=F': '布伦特原油',
    'GC=F': '黄金', 'SI=F': '白银', 'HG=F': '铜',
    'DX-Y.NYB': '美元指数', 'CNH=X': '离岸人民币',
    'BTC-USD': '比特币', '^TNX': '美 10 年期国债',
}

# 富时中国 A50 期货 (夜盘)
A50_TICKERS = {
    'CN1=F': '富时中国 A50 期货 (夜盘)',
}


def get_yf_data(tickers_dict, label, period='5d'):
    """批量拉 yfinance 数据, 返回 {显示名: {close, change_pct, prev_close}}"""
    result = {}
    symbols = list(tickers_dict.keys())
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period=period, auto_adjust=True)
            if hist is None or len(hist) < 1:
                continue
            # 取最近两个交易日
            if len(hist) >= 2:
                close = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2])
                pct = (close - prev) / prev * 100 if prev else 0
                result[tickers_dict[sym]] = {
                    'symbol': sym,
                    'close': close,
                    'prev_close': prev,
                    'change_pct': pct,
                    'date': hist.index[-1].strftime('%Y-%m-%d'),
                }
            else:
                close = float(hist['Close'].iloc[-1])
                result[tickers_dict[sym]] = {
                    'symbol': sym,
                    'close': close,
                    'prev_close': close,
                    'change_pct': 0,
                    'date': hist.index[-1].strftime('%Y-%m-%d'),
                }
        except Exception as e:
            print(f"  ⚠️ {sym} ({tickers_dict[sym]}) 拉取失败: {e}", file=sys.stderr)
    return result


def fmt_pct(p):
    if p is None:
        return '-'
    icon = '🟢' if p > 0 else ('🔴' if p < 0 else '⚪')
    sign = '+' if p > 0 else ''
    return f"{icon} {sign}{p:.2f}%"


def build_impact_forecast(us, hk, comm, a50):
    """根据外围数据自动生成对今日 A 股的影响预判"""
    forecasts = []

    # 美股三大指数影响
    sp500 = us.get('标普 500', {}).get('change_pct')
    nasdaq = us.get('纳斯达克', {}).get('change_pct')
    dow = us.get('道琼斯', {}).get('change_pct')

    if sp500 is not None and nasdaq is not None:
        avg_us = (sp500 + nasdaq) / 2
        if avg_us > 1.0:
            forecasts.append(f"🚀 **美股大涨** (标普 {fmt_pct(sp500)} / 纳指 {fmt_pct(nasdaq)}) → A 股今日高开概率大, 关注科技股/创业板/科创板龙头")
        elif avg_us > 0.3:
            forecasts.append(f"📈 **美股小涨** (标普 {fmt_pct(sp500)}) → A 股小幅高开, 不必过度乐观")
        elif avg_us < -1.0:
            forecasts.append(f"🔻 **美股大跌** (标普 {fmt_pct(sp500)} / 纳指 {fmt_pct(nasdaq)}) → A 股低开概率大, 警惕科技股回调")
        elif avg_us < -0.3:
            forecasts.append(f"📉 **美股小跌** (标普 {fmt_pct(sp500)}) → A 股可能低开, 但不必恐慌")

    # VIX
    vix = us.get('VIX 恐慌', {}).get('change_pct')
    vix_close = us.get('VIX 恐慌', {}).get('close')
    if vix_close and vix:
        if vix_close > 25 and vix > 10:
            forecasts.append(f"⚠️ **VIX 飙升** (现 {vix_close:.2f}, {fmt_pct(vix)}) → 市场恐慌, A 股可能承压")
        elif vix_close < 15:
            forecasts.append(f"😌 **VIX 偏低** ({vix_close:.2f}) → 市场情绪平稳, 有利于风险偏好")

    # 港股影响
    hsi = hk.get('恒生指数', {}).get('change_pct')
    hstech = hk.get('恒生科技', {}).get('change_pct')
    if hsi is not None:
        if hsi > 1.0:
            forecasts.append(f"🇭🇰 **港股大涨** (恒指 {fmt_pct(hsi)} / 恒科 {fmt_pct(hstech or 0)}) → A 股港股联动板块(互联网/科技)看高一线")
        elif hsi < -1.0:
            forecasts.append(f"🇭🇰 **港股大跌** (恒指 {fmt_pct(hsi)}) → 警惕港股联动股回调")

    # 中概股
    baba = us.get('阿里巴巴', {}).get('change_pct')
    pdd = us.get('拼多多', {}).get('change_pct')
    jd = us.get('京东', {}).get('change_pct')
    if baba is not None and abs(baba) > 1.5:
        forecasts.append(f"🛒 **中概电商异动** (阿里 {fmt_pct(baba)} / 拼多多 {fmt_pct(pdd or 0)} / 京东 {fmt_pct(jd or 0)}) → 关注 A 股电商/物流板块")

    # 商品
    oil = comm.get('WTI 原油', {}).get('change_pct')
    gold = comm.get('黄金', {}).get('change_pct')
    copper = comm.get('铜', {}).get('change_pct')
    if oil and oil > 2.5:
        forecasts.append(f"🛢️ **原油暴涨** ({fmt_pct(oil)}) → 关注油气股(中国石油/中国海油/中海油服)")
    elif oil and oil < -2.5:
        forecasts.append(f"🛢️ **原油暴跌** ({fmt_pct(oil)}) → 关注航空股利好, 化工/能源股承压")
    if gold and gold > 1.5:
        forecasts.append(f"🥇 **黄金上涨** ({fmt_pct(gold)}) → 关注黄金股(山东黄金/紫金矿业/中金黄金)")
    if copper and abs(copper) > 1.5:
        forecasts.append(f"🔶 **铜价异动** ({fmt_pct(copper)}) → 关注铜矿股(江西铜业/云南铜业)")

    # 美元 / 人民币
    dxy = comm.get('美元指数', {}).get('change_pct')
    cnh = comm.get('离岸人民币', {}).get('change_pct')
    if dxy and dxy > 0.8:
        forecasts.append(f"💵 **美元走强** ({fmt_pct(dxy)}) → 新兴市场承压, 北向资金可能流出")
    if cnh and cnh > 0.5:
        # 离岸人民币用 1 USD = X CNH, 涨表示人民币贬值
        forecasts.append(f"💴 **离岸人民币贬值** ({fmt_pct(cnh)}) → 利好出口股, 利空造纸/航空等负债行业")

    # A50 期货
    a50_close = a50.get('富时中国 A50 期货 (夜盘)', {}).get('change_pct')
    if a50_close is not None:
        if abs(a50_close) > 0.5:
            forecasts.append(f"🇨🇳 **A50 期货隔夜** {fmt_pct(a50_close)} → A 股开盘直接参考 (偏离较大说明外围影响明显)")

    return forecasts


def generate_overseas_report():
    # target_date = 今天 (因为这报告是盘前看今天)
    target_date = now.strftime('%Y-%m-%d')

    print(f"开始拉取外围数据, 报告日期: {target_date}")
    print("=" * 60)

    us = get_yf_data(US_TICKERS, '美股')
    hk = get_yf_data(HK_TICKERS, '港股')
    comm = get_yf_data(COMMODITY_TICKERS, '商品/外汇')
    a50 = get_yf_data(A50_TICKERS, 'A50 期货')

    print(f"美股: {len(us)} / {len(US_TICKERS)}")
    print(f"港股: {len(hk)} / {len(HK_TICKERS)}")
    print(f"商品: {len(comm)} / {len(COMMODITY_TICKERS)}")
    print(f"A50:  {len(a50)} / {len(A50_TICKERS)}")

    sections = []
    sections.append(f"# 🌍 A 股盘前外围影响报告 - {target_date}")
    sections.append("")
    sections.append(f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M')} 北京时间")
    sections.append("**用途**: 开盘前 (9:30) 预判外围对 A 股的影响")
    sections.append("**数据源**: Yahoo Finance (美股/港股/商品/外汇/A50 期货)")
    sections.append("")
    sections.append("> ⏰ 9:30 前必读 | 8:00 前生成的,9:30 开盘前最后看一眼")
    sections.append("")
    sections.append("---")
    sections.append("")

    # === 一、美股隔夜 ===
    sections.append("## 一、美股隔夜收盘")
    sections.append("")
    sections.append("*美股夏令时北京时间凌晨 4:00 收盘, 冬令时凌晨 5:00 收盘*")
    sections.append("")
    sections.append("### 1.1 主要指数")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    for n in ['标普 500', '道琼斯', '纳斯达克', 'VIX 恐慌']:
        if n in us:
            sections.append(f"| **{n}** | {us[n]['close']:.2f} | {fmt_pct(us[n]['change_pct'])} |")
        else:
            sections.append(f"| {n} | - | 数据缺失 |")
    sections.append("")

    sections.append("### 1.2 关键科技股")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    for n in ['苹果', '微软', '英伟达', '特斯拉', '谷歌', '亚马逊', 'Meta']:
        if n in us:
            sections.append(f"| {n} | {us[n]['close']:.2f} | {fmt_pct(us[n]['change_pct'])} |")
    sections.append("")

    sections.append("### 1.3 中概股 (A 股联动)")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 | A 股关联 |")
    sections.append("|------|------|--------|----------|")
    cn_map = {
        '阿里巴巴': '电商/云计算',
        '拼多多': '电商',
        '京东': '电商/物流',
        '百度': 'AI/自动驾驶',
        '蔚来': '新能源车',
        '小鹏': '新能源车',
        '理想': '新能源车',
    }
    for n, link in cn_map.items():
        if n in us:
            sections.append(f"| {n} | {us[n]['close']:.2f} | {fmt_pct(us[n]['change_pct'])} | {link} |")
    sections.append("")

    # === 二、港股昨日 ===
    sections.append("## 二、港股昨日收盘")
    sections.append("")
    sections.append("*港股交易时间: 9:30-16:00 北京, 收盘比 A 股晚 1 小时*")
    sections.append("")
    sections.append("### 2.1 主要指数")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    for n in ['恒生指数', '恒生科技']:
        if n in hk:
            sections.append(f"| **{n}** | {hk[n]['close']:,.2f} | {fmt_pct(hk[n]['change_pct'])} |")
    sections.append("")

    sections.append("### 2.2 权重股")
    sections.append("")
    sections.append("| 名称 | 收盘 | 涨跌幅 |")
    sections.append("|------|------|--------|")
    for n in ['腾讯', '阿里-W', '美团', '京东-W', '网易', '小米', '比亚迪', '快手', '药明生物', '中移动']:
        if n in hk:
            sections.append(f"| {n} | {hk[n]['close']:.2f} | {fmt_pct(hk[n]['change_pct'])} |")
    sections.append("")

    # === 三、商品 + 外汇 ===
    sections.append("## 三、大宗商品 & 外汇")
    sections.append("")
    sections.append("| 品种 | 价格 | 涨跌幅 | A 股关联 |")
    sections.append("|------|------|--------|----------|")
    link_map = {
        'WTI 原油': '油气股 / 航空',
        '布伦特原油': '油气股',
        '黄金': '黄金股 (山东黄金等)',
        '白银': '白银股',
        '铜': '铜矿股 (江西铜业等)',
        '美元指数': '北向资金 / 新兴市场',
        '离岸人民币': '出口股 / 航空',
        '比特币': '概念股',
        '美 10 年期国债': '高股息股 / 红利',
    }
    for n, link in link_map.items():
        if n in comm:
            sections.append(f"| **{n}** | {comm[n]['close']:.2f} | {fmt_pct(comm[n]['change_pct'])} | {link} |")
    sections.append("")

    # === 四、A50 期货 ===
    sections.append("## 四、富时中国 A50 期货 (夜盘)")
    sections.append("")
    if a50:
        for n, d in a50.items():
            sections.append(f"**{n}**: 收盘 **{d['close']:.2f}**  涨跌幅 **{fmt_pct(d['change_pct'])}**")
            sections.append("")
            if abs(d['change_pct']) > 0.5:
                sections.append(f"> ⚠️ A50 期货隔夜 {fmt_pct(d['change_pct'])}, **A 股今日开盘大概率高{('开' if d['change_pct']>0 else '开低走平')}**")
                sections.append("")
    else:
        sections.append("> 数据缺失")
        sections.append("")

    # === 五、自动影响预判 ===
    sections.append("## 五、自动影响预判 (基于外围数据)")
    sections.append("")
    sections.append("> 下面是基于外围表现自动生成的预判, 仅供参考, **9:25 集合竞价才定盘**")
    sections.append("")
    forecasts = build_impact_forecast(us, hk, comm, a50)
    if forecasts:
        for f in forecasts:
            sections.append(f"- {f}")
    else:
        sections.append("- 外围波动较小, A 股开盘受外围直接影响有限")
    sections.append("")

    # === 六、操作建议 ===
    sections.append("## 六、今日操作建议")
    sections.append("")
    sections.append("### ⏰ 时间表")
    sections.append("- **9:15-9:25** 集合竞价: 看 A50 期货 + 港股 + 关键股票竞价")
    sections.append("- **9:30-10:00** 开盘第一小时: 决定加仓/减仓, 不追高不杀跌")
    sections.append("- **11:30-13:00** 午盘: 观望外围, 美股盘前")
    sections.append("- **14:30-15:00** 尾盘: 决定次日策略")
    sections.append("")

    sections.append("### 🎯 策略建议")
    sections.append("")
    sp500 = us.get('标普 500', {}).get('change_pct')
    hsi = hk.get('恒生指数', {}).get('change_pct')
    if sp500 is not None and hsi is not None:
        avg = (sp500 + hsi) / 2
        if avg > 1.5:
            sections.append("- 🟢 **外围强势**: 关注 A 股开盘表现, **顺势而为, 不追高**")
        elif avg < -1.5:
            sections.append("- 🔴 **外围弱势**: 不要急于抄底, **等 30 分钟观察量能再说**")
        else:
            sections.append("- 🟡 **外围震荡**: **按个股技术面操作**, 不必太看重外围")
    sections.append("")
    sections.append("### ⚠️ 风险提示")
    sections.append("")
    sections.append("- 上述预判 **不是稳赚的**, 外围和 A 股常背离")
    sections.append("- **绝对不能机械执行**, 必须结合当日开盘量能 + 政策消息")
    sections.append("- 有疑问优先看 daily_report (21:00 那份) 的选股清单")
    sections.append("")

    sections.append("---")
    sections.append("")
    sections.append(f"**报告生成**: GitHub Actions 北京时间 06:00 自动")
    sections.append("**配套使用**: 21:00 的 `daily_report` (日内复盘) + 当前报告 (外围影响) = 完整决策")
    sections.append("")

    output_path = os.path.join(REPORTS_DIR, f'overnight_{target_date}.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sections))
    print(f"\n✅ 外围影响报告已生成: {output_path}")
    return output_path, target_date


if __name__ == '__main__':
    try:
        path, date = generate_overseas_report()
    except Exception as e:
        import traceback
        print(f"\n❌ 失败: {e}")
        traceback.print_exc()
        sys.exit(1)
