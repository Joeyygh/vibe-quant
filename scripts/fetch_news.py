"""
A 股新闻抓取脚本 v1.0
- 东方财富公告 API
- 东方财富研报 API
- 保存到 data/news/{date}.md
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone

import requests

beijing_tz = timezone(timedelta(hours=8))
now = datetime.now(beijing_tz)
NEWS_DIR = 'data/news'
os.makedirs(NEWS_DIR, exist_ok=True)


def get_target_date():
    """确定报告日期(A 股上一个交易日)"""
    today = now.date()
    target = today if now.hour >= 17 else (today - timedelta(days=1))
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target.strftime('%Y-%m-%d')


def fetch_announcements(target_date, top_n=30):
    """东方财富公告 API - 当日最新公告"""
    print(f"  → 抓取东方财富公告 (今日 {target_date})...")
    try:
        url = (
            f"https://np-anotice-stock.eastmoney.com/api/security/ann"
            f"?cb=jQuery&sr=-1&page_size={top_n}&page_index=1"
            f"&ann_type=A&client_source=web&stock_list=&f_node=0&s_node=0"
        )
        r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        text = r.text
        import re
        m = re.search(r'\((.*)\)', text)
        if not m:
            return []
        data = json.loads(m.group(1))
        items = data.get('data', {}).get('list', [])
        announcements = []
        for item in items:
            try:
                title = item.get('title', '').strip()
                if not title:
                    continue
                display_time = item.get('display_time', '')
                codes = item.get('codes', [])
                stocks = ', '.join([c.get('short_name', '') + '(' + c.get('stock_code', '') + ')'
                                     for c in codes[:3]])
                columns = item.get('columns', [])
                col_name = columns[0].get('column_name', '') if columns else ''
                art_code = item.get('art_code', '')
                announcements.append({
                    'title': title,
                    'time': display_time,
                    'stocks': stocks,
                    'category': col_name,
                    'url': f"https://data.eastmoney.com/notices/detail/{art_code}.html"
                })
            except Exception:
                continue
        return announcements
    except Exception as e:
        print(f"  ⚠️ 公告抓取失败: {e}")
        return []


def fetch_research_reports(target_date, top_n=20):
    """东方财富研报 API - 当日研报"""
    print(f"  → 抓取东方财富研报 (今日 {target_date})...")
    try:
        url = (
            f"https://reportapi.eastmoney.com/report/list"
            f"?cb=jQuery&industryCode=*&pageSize={top_n}&industry=*&rating=*"
            f"&ratingChange=*&beginTime={target_date.replace('-', '')}&endTime={target_date.replace('-', '')}"
            f"&pageNo=1&fields=&qType=0&orgCode=&code=*"
        )
        r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        text = r.text
        import re
        m = re.search(r'\((.*)\)', text)
        if not m:
            return []
        data = json.loads(m.group(1))
        items = data.get('data', [])
        reports = []
        for item in items:
            try:
                title = item.get('title', '').strip()
                stock_name = item.get('stockName', '')
                stock_code = item.get('stockCode', '')
                org_name = item.get('orgSName', '') or item.get('orgName', '')
                rating = item.get('emRatingName', '')
                target_price = item.get('indvAimPriceL', '') or item.get('indvAimPriceT', '')
                publish_date = item.get('publishDate', '')[:10]
                author = item.get('researcher', '')
                reports.append({
                    'title': title,
                    'stock': f"{stock_name}({stock_code})",
                    'org': org_name,
                    'rating': rating,
                    'target_price': target_price,
                    'date': publish_date,
                    'author': author
                })
            except Exception:
                continue
        return reports
    except Exception as e:
        print(f"  ⚠️ 研报抓取失败: {e}")
        return []


def generate_news_md(target_date, announcements, reports):
    """生成新闻 Markdown"""
    lines = []
    lines.append(f"# 📰 A 股新闻摘要 - {target_date}")
    lines.append("")
    lines.append(f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M')} 北京时间")
    lines.append("**数据源**: 东方财富(公告 + 研报)")
    lines.append("")
    lines.append("---")
    lines.append("")

    if announcements:
        lines.append(f"## 一、重要公告(前 {len(announcements)} 条)")
        lines.append("")
        lines.append("| 时间 | 类别 | 标题 | 涉及股票 |")
        lines.append("|------|------|------|----------|")
        for a in announcements:
            t = a['time'].split(' ')[1] if ' ' in a['time'] else a['time']
            title_short = a['title'][:60] + ('...' if len(a['title']) > 60 else '')
            lines.append(f"| {t} | {a['category']} | {title_short} | {a['stocks']} |")
        lines.append("")

    if reports:
        lines.append(f"## 二、机构研报(前 {len(reports)} 条)")
        lines.append("")
        lines.append("| 股票 | 评级 | 目标价 | 机构 | 标题 |")
        lines.append("|------|------|--------|------|------|")
        for r in reports:
            title_short = r['title'][:50] + ('...' if len(r['title']) > 50 else '')
            tp = f"{r['target_price']}" if r['target_price'] else '-'
            lines.append(f"| {r['stock']} | {r['rating']} | {tp} | {r['org']} | {title_short} |")
        lines.append("")

    if not announcements and not reports:
        lines.append("## ⚠️ 暂无新闻数据")
        lines.append("")
        lines.append("可能原因:")
        lines.append("- 今日为非交易日")
        lines.append("- 数据源暂不可用")
        lines.append("")
        lines.append("建议手动浏览:")
        lines.append("- 📰 财联社 https://www.cls.cn")
        lines.append("- 📰 东方财富 https://data.eastmoney.com")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**自动抓取** by fetch_news.py | GitHub Actions 06:00 跑")
    lines.append("")

    return '\n'.join(lines)


def main():
    target_date = get_target_date()
    print(f"\n{'='*50}\n开始抓取 {target_date} 新闻\n{'='*50}\n")

    announcements = fetch_announcements(target_date, top_n=30)
    print(f"  ✅ 获取 {len(announcements)} 条公告")

    reports = fetch_research_reports(target_date, top_n=20)
    print(f"  ✅ 获取 {len(reports)} 条研报")

    content = generate_news_md(target_date, announcements, reports)

    output_path = os.path.join(NEWS_DIR, f'{target_date}.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n✅ 新闻已保存: {output_path}")
    return output_path


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ 失败: {e}")
        traceback.print_exc()
        sys.exit(1)