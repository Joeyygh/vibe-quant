# ⚙️ GitHub Actions 修复补丁 (2026-08-10)

## 问题
`daily_picks_dynamic.py` 已部署,但 `daily.yml` 和 `daily_report.yml` 因 GitHub 安全策略无法用 PAT 推送。
需要用户在 GitHub 网页上**手动复制**下面 2 个文件。

## 操作步骤 (1 分钟)

### 1. `.github/workflows/daily.yml` 替换为:
```yaml
name: Daily Data Update

on:
  schedule:
    - cron: '0 9 * * 1-5'   # 17:00 北京时间
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-data:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install tushare pandas pyarrow

      - name: Update data
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
        run: |
          mkdir -p data
          python scripts/update_data.py

      - name: Generate today picks (动态精选 v1.4)
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
        run: |
          python scripts/daily_picks_dynamic.py

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ reports/today_picks.json
          git diff --staged --quiet || git commit -m "chore: daily data + picks update $(date +%Y-%m-%d)"
          git push
```

### 2. `.github/workflows/daily_report.yml` 替换为:
```yaml
name: Daily Report

on:
  schedule:
    - cron: '0 22 * * 1-5'   # 06:00 北京次日 (滞后 13 小时, 让 picks 先跑)
  workflow_dispatch:

permissions:
  contents: write

jobs:
  generate-report:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install tushare pandas pyarrow yfinance numpy

      - name: Fetch news & announcements
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
        run: |
          python scripts/fetch_news.py

      - name: Generate daily report
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
        run: |
          python scripts/daily_report.py

      - name: Commit report
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          file_pattern: 'reports/*.md'
          commit_message: 'daily report: ${{ github.event.head_commit.message }}'
```

### 3. 提交即可
打开 GitHub 网页,直接点 "Edit" 按钮,把上面的内容贴进去,提交 commit 即可。

## 为什么需要改
当前 `daily.yml` 只跑 `update_data.py` 更新 K 线,但**不跑** `daily_picks.py`。
所以 `today_picks.json` 永远停在 8/8 那次手动跑的数据。

改完后,17:00 北京时间会:
1. ✅ 更新 K 线 (update_data.py)
2. ✅ 生成今日精选 (daily_picks_dynamic.py) ← **新增**
3. ✅ 一次性 commit data/ + reports/today_picks.json

## 文件说明
- `scripts/daily_picks_dynamic.py` (已推送): 基于 Tushare 当日真实盘面动态生成 5企推+量化+双引擎
- `today_picks.json` (今日已推送): 8/10 当日精选 (5企推+7量化+2双引擎, 中钨高新+工业富联)
